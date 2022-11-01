"""Update coordinator for TAURON sensors."""
import datetime
import logging
import ssl

import requests
from requests import adapters
from urllib3 import poolmanager

from .const import (CONF_URL_CHARTS, CONF_URL_READINGS, CONF_URL_LOGIN, CONF_URL_SERVICE)
from .scrapers.total_meter_value_html_scraper import (TotalMeterValueHTMLScraper)

_LOGGER = logging.getLogger(__name__)


# to fix the SSLError
class TLSAdapter(adapters.HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False):
        """Create and initialize the urllib3 PoolManager."""
        ctx = ssl.create_default_context()
        ctx.set_ciphers("DEFAULT@SECLEVEL=1")
        ctx.check_hostname = False
        self.poolmanager = poolmanager.PoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            ssl_version=ssl.PROTOCOL_TLS,
            ssl_context=ctx,
        )


class TauronAmiplusRawData:
    def __init__(self):
        self.configuration_1_day_ago = None
        self.configuration_2_days_ago = None
        self.total_consumption = None
        self.json_daily = None
        self.json_monthly = None
        self.json_yearly = None


class TauronAmiplusConnector:
    url_login = CONF_URL_LOGIN
    url_charts = CONF_URL_CHARTS
    url_readings = CONF_URL_READINGS
    headers = {
        "cache-control": "no-cache",
    }
    payload_charts = {"dane[cache]": 0, "dane[chartType]": 2}

    def __init__(self, username, password, meter_id, generation):
        self.username = username
        self.password = password
        self.meter_id = meter_id
        self.generation_enabled = generation

    def get_raw_data(self) -> TauronAmiplusRawData:
        data = TauronAmiplusRawData()
        session = self.get_session()
        data.configuration_1_day_ago = self.calculate_configuration(session, 1, False)
        data.configuration_2_days_ago = self.calculate_configuration(session, 2, False)
        data.total_consumption = self.get_total_consumption(session)
        data.json_daily = self.get_values_daily(session)
        data.json_monthly = self.get_values_monthly(session)
        data.json_yearly = self.get_values_yearly(session)
        return data

    def get_session(self):
        payload_login = {
            "username": self.username,
            "password": self.password,
            "service": CONF_URL_SERVICE,
        }
        session = requests.session()
        session.mount("https://", TLSAdapter())
        session.request(
            "POST",
            TauronAmiplusConnector.url_login,
            data=payload_login,
            headers=TauronAmiplusConnector.headers,
        )
        session.request(
            "POST",
            TauronAmiplusConnector.url_login,
            data=payload_login,
            headers=TauronAmiplusConnector.headers,
        )
        session.request("POST", CONF_URL_SERVICE, data={"smart": self.meter_id}, headers=TauronAmiplusConnector.headers)
        return session

    def calculate_configuration(self, session, days_before=2, throw_on_empty=True):
        json_data = self.get_raw_values_daily(session, days_before)
        if json_data is None:
            if throw_on_empty:
                raise Exception("Failed to login")
            else:
                return None
        zones = json_data["dane"]["zone"]
        parsed_zones = []
        for zone_id in zones:
            if type(zone_id) is dict:
                zone = zone_id
            else:
                zone = zones[zone_id]
            start_hour = int(zone["start"][11:])
            stop_hour = int(zone["stop"][11:])
            if stop_hour == 24:
                stop_hour = 0
            parsed_zones.append({"start": datetime.time(hour=start_hour), "stop": datetime.time(hour=stop_hour)})
        calculated_zones = []
        for i in range(0, len(parsed_zones)):
            next_i = (i + 1) % len(parsed_zones)
            start = datetime.time(parsed_zones[i]["stop"].hour)
            stop = datetime.time(parsed_zones[next_i]["start"].hour)
            calculated_zones.append({"start": start, "stop": stop})
        power_zones = {1: parsed_zones, 2: calculated_zones}
        tariff = list(json_data["dane"]["chart"].values())[0]["Taryfa"]
        config_date = datetime.datetime.now() - datetime.timedelta(days_before)
        return power_zones, tariff, config_date.strftime("%d.%m.%Y, %H:%M")

    def get_total_consumption(self, session):
        yesterday = datetime.date.today() - datetime.timedelta(days = 1)

        response = session.request(
            "POST",
            TauronAmiplusConnector.url_readings,
            data = {
                "day": yesterday.strftime("%d.%m.%Y")
            },
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                **TauronAmiplusConnector.headers
            }
        )

        if response.status_code == 200:
            scraper = TotalMeterValueHTMLScraper()
            scraper.feed(response.text)

            if scraper.total:
                return {
                    "value": scraper.total,
                    "unit": scraper.unit,
                    "timestamp": scraper.timestamp,
                    "meter_id": scraper.meter_id
                }
        return None

    def get_values_yearly(self, session):
        payload = {
            "dane[chartYear]": datetime.datetime.now().year,
            "dane[paramType]": "year",
            "dane[smartNr]": self.meter_id,
            "dane[chartType]": 2,
        }
        return self.get_chart_values(session, payload)

    def get_values_monthly(self, session):
        payload = {
            "dane[chartMonth]": datetime.datetime.now().month,
            "dane[chartYear]": datetime.datetime.now().year,
            "dane[paramType]": "month",
            "dane[smartNr]": self.meter_id,
        }
        return self.get_chart_values(session, payload)

    def get_values_daily(self, session):
        data = self.get_raw_values_daily(session, 1)
        if data is None or not data["isFull"]:
            data = self.get_raw_values_daily(session, 2)
        return data

    def get_raw_values_daily(self, session, days_before):
        payload = {
            "dane[chartDay]": (
                    datetime.datetime.now() - datetime.timedelta(days_before)
            ).strftime("%d.%m.%Y"),
            "dane[paramType]": "day",
            "dane[smartNr]": self.meter_id,
        }
        return self.get_chart_values(session, payload)

    def get_chart_values(self, session, payload):
        if self.generation_enabled:
            payload["dane[checkOZE]"] = "on"
        response = session.request(
            "POST",
            TauronAmiplusConnector.url_charts,
            data={**TauronAmiplusConnector.payload_charts, **payload},
            headers=TauronAmiplusConnector.headers,
        )
        if response.status_code == 200 and response.text.startswith('{"name"'):
            json_data = response.json()
            return json_data
        return None

    @staticmethod
    def calculate_tariff(username, password, meter_id):
        coordinator = TauronAmiplusConnector(username, password, meter_id, False)
        session = coordinator.get_session()
        config = coordinator.calculate_configuration(session, 2)
        if config is not None:
            return config[1]
        raise Exception("Failed to login")
