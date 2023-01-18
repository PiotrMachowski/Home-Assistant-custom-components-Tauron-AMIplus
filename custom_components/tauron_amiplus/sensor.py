"""Support for TAURON sensors."""
import logging

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import CONF_MONITORED_VARIABLES, CONF_NAME, CONF_PASSWORD, CONF_USERNAME, ENERGY_KILO_WATT_HOUR
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (CONF_METER_ID, CONF_SHOW_GENERATION, CONF_TARIFF, CONST_BALANCED, CONST_DAILY, CONST_GENERATION,
                    CONST_LAST_12_MONTHS, CONST_MONTHLY, CONST_READING, CONST_URL_SERVICE, CONST_YEARLY, DEFAULT_NAME,
                    DOMAIN, SENSOR_TYPES, TYPE_BALANCED_DAILY, TYPE_BALANCED_MONTHLY)
from .coordinator import TauronAmiplusUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_METER_ID): cv.string,
    vol.Required(CONF_MONITORED_VARIABLES, default=[]):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    name = config.get(CONF_NAME)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    meter_id = config.get(CONF_METER_ID)
    calculate_generation = any(filter(lambda v: CONST_GENERATION in v, config[CONF_MONITORED_VARIABLES]))
    coordinator = TauronAmiplusUpdateCoordinator(hass, username, password, meter_id, calculate_generation)
    await coordinator.async_request_refresh()
    dev = []
    for variable in config[CONF_MONITORED_VARIABLES]:
        dev.append(TauronAmiplusSensor(coordinator, name, meter_id, variable))
    async_add_entities(dev, True)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up a TAURON sensor based on a config entry."""
    user = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    meter_id = entry.data[CONF_METER_ID]
    show_generation_sensors = entry.data[CONF_SHOW_GENERATION]
    tariff = entry.data[CONF_TARIFF]
    sensors = []
    sensor_types = {**SENSOR_TYPES}
    coordinator = TauronAmiplusUpdateCoordinator(hass, user, password, meter_id, show_generation_sensors)
    await coordinator.async_request_refresh()
    for sensor_type in sensor_types:
        if not (sensor_type.startswith((CONST_GENERATION, CONST_BALANCED)) and not show_generation_sensors):
            sensor_name = SENSOR_TYPES[sensor_type][0]
            sensors.append(
                TauronAmiplusConfigFlowSensor(
                    coordinator,
                    sensor_name,
                    meter_id,
                    sensor_type,
                    tariff
                )
            )

    async_add_entities(sensors, True)


class TauronAmiplusSensor(SensorEntity, CoordinatorEntity):

    def __init__(self, coordinator: TauronAmiplusUpdateCoordinator, name: str, meter_id: str, sensor_type: str):
        super().__init__(coordinator)
        self.client_name = name
        self.meter_id = meter_id
        self.generation = sensor_type.startswith(CONST_GENERATION)
        self.sensor_type = sensor_type
        self.power_zones = None
        self.tariff = None
        self.params = {}
        self._state = None

    @property
    def name(self):
        return f"{self.client_name} {self.sensor_type}"

    @property
    def native_unit_of_measurement(self):
        return ENERGY_KILO_WATT_HOUR

    @property
    def device_class(self):
        return SensorDeviceClass.ENERGY

    @property
    def native_value(self):
        return self._state

    @property
    def extra_state_attributes(self):
        _params = {
            "tariff": self.tariff,
            **self.params,
        }
        return _params

    @property
    def icon(self):
        return "mdi:counter"

    @property
    def state_class(self):
        if self.sensor_type.endswith(CONST_DAILY):
            return SensorStateClass.MEASUREMENT
        elif (self.sensor_type.endswith((CONST_MONTHLY, CONST_YEARLY, CONST_LAST_12_MONTHS)) or
              CONST_READING in self.sensor_type):
            return SensorStateClass.TOTAL_INCREASING
        else:
            return None

    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data
        if not self.available or data is None:
            return
        dataset = data.generation if self.generation else data.consumption

        if self.sensor_type == TYPE_BALANCED_DAILY and data.balance_daily is not None:
            self.update_balanced_data(data.balance_daily, data.tariff)
        elif self.sensor_type == TYPE_BALANCED_MONTHLY and data.balance_monthly is not None:
            self.update_balanced_data(data.balance_monthly, data.tariff)
        elif self.sensor_type.endswith(CONST_READING) and dataset.json_reading is not None:
            self.update_reading(dataset.json_reading, data.tariff)
        elif self.sensor_type.endswith(CONST_DAILY) and dataset.json_daily is not None:
            self.update_values(dataset.json_daily)
            self.params = {"date": dataset.daily_date, **self.params}
        elif self.sensor_type.endswith(CONST_MONTHLY) and dataset.json_monthly is not None:
            self.update_values(dataset.json_monthly)
        elif self.sensor_type.endswith(CONST_YEARLY) and dataset.json_yearly is not None:
            self.update_values(dataset.json_yearly)
        elif self.sensor_type.endswith(CONST_LAST_12_MONTHS) and dataset.json_last_12_months_hourly is not None:
            self.update_values(dataset.json_last_12_months_hourly)
        self.async_write_ha_state()

    def update_reading(self, json_data, tariff):
        reading = json_data["data"][-1]
        self._state = reading["C"]
        partials = {s: reading[s] for s in ["S1", "S2", "S3"] if reading[s] is not None}
        self.params = {"date": reading["Date"], **partials}
        self.tariff = tariff

    def update_values(self, json_data):
        total, tariff, zones = TauronAmiplusSensor.get_data_from_json(json_data)
        self._state = total
        self.tariff = tariff
        self.params = zones

    def update_balanced_data(self, balanced_data, tariff):
        con = balanced_data[0]
        gen = balanced_data[1]
        balance, sum_consumption, sum_generation, zones, data_range = TauronAmiplusSensor.get_balanced_data(con, gen)
        self._state = round(balance, 3)
        self.tariff = tariff
        self.params = {
            "sum_consumption": round(sum_consumption, 3),
            "sum_generation": round(sum_generation, 3),
            "data_range": data_range,
            **{k: round(v, 3) for (k, v) in zones.items()},
        }

    @staticmethod
    def get_data_from_json(json_data):
        total = round(json_data["data"]["sum"], 3)
        tariff = json_data["data"]["tariff"]
        zones = {}
        if len(json_data["data"]["zones"]) > 0:
            zones = {v: round(json_data["data"]["zones"][k], 3) for (k, v) in json_data["data"]["zonesName"].items()}
        return total, tariff, zones

    @staticmethod
    def get_balanced_data(consumption_data_json, generation_data_json):
        zone_names = consumption_data_json["data"]["zonesName"]
        consumption_data = consumption_data_json["data"]["allData"]
        generation_data = generation_data_json["data"]["allData"]
        if len(consumption_data) == 0 or len(generation_data) == 0:
            return 0, 0, 0, {}, ""
        data_range = f"{consumption_data[0]['Date']} - {consumption_data[-1]['Date']}"

        sum_consumption = 0
        sum_generation = 0
        zones = {}

        for consumption, generation in zip(consumption_data, generation_data):
            value_consumption = float(consumption["EC"])
            value_generation = float(generation["EC"])
            zone = zone_names[consumption["Zone"]]
            balance = value_consumption - value_generation
            if balance > 0:
                sum_consumption += balance
                zone_key = f"{zone}_consumption"
                if zone_key not in zones:
                    zones[zone_key] = 0
                zones[zone_key] += balance
            else:
                sum_generation += balance
                zone_key = f"{zone}_generation"
                if zone_key not in zones:
                    zones[zone_key] = 0
                zones[zone_key] += balance

        balance = sum_consumption + sum_generation
        return balance, sum_consumption, sum_generation, zones, data_range

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"tauron-yaml-{self.meter_id}-{self.sensor_type.lower()}"


class TauronAmiplusConfigFlowSensor(TauronAmiplusSensor):

    def __init__(self, coordinator: TauronAmiplusUpdateCoordinator, name, meter_id, sensor_type, tariff):
        """Initialize the sensor."""
        super().__init__(coordinator, name, meter_id, sensor_type)
        self._tariff = tariff

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.meter_id)},
            "name": f"eLicznik {self.meter_id}",
            "manufacturer": "TAURON",
            "model": self.meter_id,
            "sw_version": f"Tariff {self._tariff}",
            "via_device": None,
            "configuration_url": CONST_URL_SERVICE,
        }

    @property
    def name(self):
        return f"{DEFAULT_NAME} {self.meter_id} {self.client_name}"

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"tauron-{self.meter_id}-{self.sensor_type.lower()}"
