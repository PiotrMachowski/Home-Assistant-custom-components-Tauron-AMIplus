import datetime
import logging
from datetime import timedelta

import homeassistant.helpers.config_validation as cv
import requests
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_USERNAME, CONF_PASSWORD, CONF_NAME, CONF_MONITORED_VARIABLES)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

CONF_METER_ID = 'energy_meter_id'
CONF_GENERATION = 'check_generation'

DEFAULT_NAME = 'Tauron AMIPlus'

MIN_TIME_BETWEEN_UPDATES = datetime.timedelta(seconds=60)

ZONE = 'zone'
CONSUMPTION_DAILY = 'consumption_daily'
CONSUMPTION_MONTHLY = 'consumption_monthly'
CONSUMPTION_YEARLY = 'consumption_yearly'
GENERATION_DAILY = 'generation_daily'
GENERATION_MONTHLY = 'generation_monthly'
GENERATION_YEARLY = 'generation_yearly'

SENSOR_TYPES = {
    ZONE: [timedelta(minutes=1), None],
    CONSUMPTION_DAILY: [timedelta(hours=1), 'kWh', 'sum', ('generation', 'OZEValue')],
    CONSUMPTION_MONTHLY: [timedelta(hours=1), 'kWh', 'sum', ('generation', 'OZEValue')],
    CONSUMPTION_YEARLY: [timedelta(hours=1), 'kWh', 'sum', ('generation', 'OZEValue')],
    GENERATION_DAILY: [timedelta(hours=1), 'kWh', 'OZEValue', ('consumption', 'sum')],
    GENERATION_MONTHLY: [timedelta(hours=1), 'kWh', 'OZEValue', ('consumption', 'sum')],
    GENERATION_YEARLY: [timedelta(hours=1), 'kWh', 'OZEValue', ('consumption', 'sum')]
}

TARIFF_G12 = 'G12'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_METER_ID): cv.string,
    vol.Required(CONF_MONITORED_VARIABLES, default=[]):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_GENERATION, default=False): cv.boolean,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    name = config.get(CONF_NAME)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    meter_id = config.get(CONF_METER_ID)
    generation = config.get(CONF_GENERATION)
    dev = []
    for variable in config[CONF_MONITORED_VARIABLES]:
        dev.append(TauronAmiplusSensor(name, username, password, meter_id, generation, variable))
    add_entities(dev, True)


def calculate_configuration(username, password, meter_id, days_before=2):
    payload_login = {
        "username": username,
        "password": password,
        "service": "https://elicznik.tauron-dystrybucja.pl"
    }
    session = requests.session()
    session.request("POST", TauronAmiplusSensor.url_login, data=payload_login,
                    headers=TauronAmiplusSensor.headers)
    session.request("POST", TauronAmiplusSensor.url_login, data=payload_login,
                    headers=TauronAmiplusSensor.headers)
    config_date = (datetime.datetime.now() - datetime.timedelta(days_before))
    payload = {
        "dane[chartDay]": config_date.strftime('%d.%m.%Y'),
        "dane[paramType]": "day",
        "dane[smartNr]": meter_id,
        "dane[chartType]": 1
    }
    response = session.request("POST", TauronAmiplusSensor.url_charts,
                               data={**TauronAmiplusSensor.payload_charts, **payload},
                               headers=TauronAmiplusSensor.headers)
    json_data = response.json()
    zones = json_data['dane']['zone']
    parsed_zones = []
    for zone in zones:
        start = datetime.time(hour=int(zone['start'][11:]))
        stop = datetime.time(hour=int(zone['stop'][11:]))
        parsed_zones.append({'start': start, 'stop': stop})
    calculated_zones = []
    for i in range(0, len(parsed_zones)):
        next_i = (i + 1) % len(parsed_zones)
        start = datetime.time(parsed_zones[i]['stop'].hour)
        stop = datetime.time(parsed_zones[next_i]['start'].hour)
        calculated_zones.append({'start': start, 'stop': stop})
    power_zones = {1: parsed_zones, 2: calculated_zones}
    tariff = json_data['dane']['chart'][0]['Taryfa']
    return power_zones, tariff, config_date.strftime('%d.%m.%Y, %H:%M')


class TauronAmiplusSensor(Entity):
    url_login = "https://logowanie.tauron-dystrybucja.pl/login"
    url_charts = "https://elicznik.tauron-dystrybucja.pl/index/charts"
    headers = {
        'cache-control': "no-cache",
    }
    payload_charts = {
        "dane[cache]": 0,
        "dane[chartType]": 2
    }

    def __init__(self, name, username, password, meter_id, generation, sensor_type):
        self.client_name = name
        self.username = username
        self.password = password
        self.meter_id = meter_id
        self.additional_param_enabled = generation or sensor_type.startswith("generation")
        self.sensor_type = sensor_type
        self.unit = SENSOR_TYPES[sensor_type][1]
        configuration = calculate_configuration(username, password, meter_id)
        self.power_zones = configuration[0]
        self.mode = configuration[1]
        self.power_zones_last_update = configuration[2]
        self.power_zones_last_update_tech = datetime.datetime.now() - datetime.timedelta(days=1)
        self.data = None
        self.params = {}
        self._state = None
        self.update = Throttle(SENSOR_TYPES[sensor_type][0])(self._update)
        if not sensor_type == ZONE:
            self.state_param = SENSOR_TYPES[sensor_type][2]
            self.additional_param_name = SENSOR_TYPES[sensor_type][3][0]
            self.additional_param = SENSOR_TYPES[sensor_type][3][1]

    @property
    def name(self):
        return '{} {}'.format(self.client_name, self.sensor_type)

    @property
    def state(self):
        return self._state

    @property
    def device_state_attributes(self):
        _params = {'tariff': self.mode, 'updated': self.power_zones_last_update, **self.params}
        return _params

    @property
    def unit_of_measurement(self):
        return self.unit

    @property
    def icon(self):
        return 'mdi:counter'

    def _update(self):
        self.update_configuration()
        if self.sensor_type == ZONE:
            self.update_zone()
        elif self.sensor_type.endswith("daily"):
            self.update_values_daily()
        elif self.sensor_type.endswith("monthly"):
            self.update_values_monthly()
        elif self.sensor_type.endswith("yearly"):
            self.update_values_yearly()

    def get_session(self):
        payload_login = {
            "username": self.username,
            "password": self.password,
            "service": "https://elicznik.tauron-dystrybucja.pl"
        }
        session = requests.session()
        session.request("POST", TauronAmiplusSensor.url_login, data=payload_login,
                        headers=TauronAmiplusSensor.headers)
        session.request("POST", TauronAmiplusSensor.url_login, data=payload_login,
                        headers=TauronAmiplusSensor.headers)
        return session

    def update_configuration(self):
        now_datetime = datetime.datetime.now()
        if (now_datetime - datetime.timedelta(days=1)) >= self.power_zones_last_update_tech and now_datetime.hour >= 10:
            config = calculate_configuration(self.username, self.password, self.meter_id, 1)
            self.power_zones = config[0]
            self.mode = config[1]
            self.power_zones_last_update = config[2]
            self.power_zones_last_update_tech = now_datetime

    def update_zone(self):
        if self.mode == TARIFF_G12:
            parsed_zones = self.power_zones[1]
            now_time = datetime.datetime.now().time()
            if len(list(filter(lambda x: x['start'] <= now_time < x['stop'], parsed_zones))) > 0:
                self._state = 1
            else:
                self._state = 2
            self.params = {}
            for power_zone in self.power_zones:
                pz_name = 'zone{} '.format(power_zone)
                pz = str(list(map(lambda x: x['start'].strftime('%H:%M') + ' - ' + x['stop'].strftime('%H:%M'),
                                  self.power_zones[power_zone]))).replace('[', '').replace(']', '').replace("'", '')
                self.params[pz_name] = pz
        else:
            self._state = 1

    def update_values_daily(self):
        session = self.get_session()
        payload = {
            "dane[chartDay]": (datetime.datetime.now() - datetime.timedelta(1)).strftime('%d.%m.%Y'),
            "dane[paramType]": "day",
            "dane[smartNr]": self.meter_id,
            "dane[checkOZE]": "on" if self.additional_param_enabled else "off"
        }
        response = session.request("POST", TauronAmiplusSensor.url_charts,
                                   data={**TauronAmiplusSensor.payload_charts, **payload},
                                   headers=TauronAmiplusSensor.headers)
        correct_data = False
        if response.status_code == 200 and response.text.startswith('{"name"') and response.json()['isFull']:
            correct_data = True
        else:
            session = self.get_session()
            payload = {
                "dane[chartDay]": (datetime.datetime.now() - datetime.timedelta(2)).strftime('%d.%m.%Y'),
                "dane[paramType]": "day",
                "dane[smartNr]": self.meter_id,
                "dane[checkOZE]": "on" if self.additional_param_enabled else "off"
            }
            response = session.request("POST", TauronAmiplusSensor.url_charts,
                                       data={**TauronAmiplusSensor.payload_charts, **payload},
                                       headers=TauronAmiplusSensor.headers)
            if response.status_code == 200 and response.text.startswith('{"name"'):
                correct_data = True
        if correct_data:
            json_data = response.json()
            self._state = round(float(json_data[self.state_param]), 3)
            if self.mode == TARIFF_G12:
                values = json_data['dane']['chart']
                z1 = list(filter(lambda x: x['Zone'] == '1', values))
                z2 = list(filter(lambda x: x['Zone'] == '2', values))
                sum_z1 = round(sum(float(val['EC']) for val in z1), 3)
                sum_z2 = round(sum(float(val['EC']) for val in z2), 3)
                day = values[0]['Date']
                self.params = {'zone1': sum_z1, 'zone2': sum_z2, 'day': day}
            if self.additional_param_enabled:
                self.params = {**self.params, self.additional_param_name: round(float(json_data[self.additional_param]), 3)}

    def update_values_monthly(self):
        session = self.get_session()
        payload = {
            "dane[chartMonth]": datetime.datetime.now().month,
            "dane[chartYear]": datetime.datetime.now().year,
            "dane[paramType]": "month",
            "dane[smartNr]": self.meter_id,
            "dane[checkOZE]": "on" if self.additional_param_enabled else "off"
        }
        response = session.request("POST", TauronAmiplusSensor.url_charts,
                                   data={**TauronAmiplusSensor.payload_charts, **payload},
                                   headers=TauronAmiplusSensor.headers)
        if response.status_code == 200 and response.text.startswith('{"name"'):
            json_data = response.json()
            self._state = round(float(json_data[self.state_param]), 3)
            self.params = {}
            if self.mode == TARIFF_G12:
                values = json_data['dane']['chart']
                z1 = list(filter(lambda x: 'tariff1' in x, values))
                z2 = list(filter(lambda x: 'tariff2' in x, values))
                sum_z1 = round(sum(float(val['tariff1']) for val in z1), 3)
                sum_z2 = round(sum(float(val['tariff2']) for val in z2), 3)
                self.params = {'zone1': sum_z1, 'zone2': sum_z2}
            if self.additional_param_enabled:
                self.params = {**self.params, self.additional_param_name: round(float(json_data[self.additional_param]), 3)}

    def update_values_yearly(self):
        session = self.get_session()
        payload = {
            "dane[chartYear]": datetime.datetime.now().year,
            "dane[paramType]": "year",
            "dane[smartNr]": self.meter_id,
            "dane[chartType]": 2,
            "dane[checkOZE]": "on" if self.additional_param_enabled else "off"
        }
        response = session.request("POST", TauronAmiplusSensor.url_charts,
                                   data={**TauronAmiplusSensor.payload_charts, **payload},
                                   headers=TauronAmiplusSensor.headers)
        if response.status_code == 200 and response.text.startswith('{"name"'):
            json_data = response.json()
            self._state = round(float(json_data[self.state_param]), 3)
            self.params = {}
            if self.mode == TARIFF_G12:
                values = json_data['dane']['chart']
                z1 = list(filter(lambda x: 'tariff1' in x, values))
                z2 = list(filter(lambda x: 'tariff2' in x, values))
                sum_z1 = round(sum(float(val['tariff1']) for val in z1), 3)
                sum_z2 = round(sum(float(val['tariff2']) for val in z2), 3)
                self.params = {'zone1': sum_z1, 'zone2': sum_z2}
            if self.additional_param_enabled:
                self.params = {**self.params, self.additional_param_name: round(float(json_data[self.additional_param]), 3)}
