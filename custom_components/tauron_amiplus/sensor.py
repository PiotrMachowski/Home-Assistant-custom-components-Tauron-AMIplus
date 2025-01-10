"""Support for TAURON sensors."""
import logging

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MONITORED_VARIABLES, CONF_NAME, CONF_PASSWORD, CONF_USERNAME, UnitOfEnergy
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.dt import parse_date

from .connector import TauronAmiplusRawData
from .const import (CONF_METER_ID, CONF_METER_NAME, CONF_SHOW_12_MONTHS, CONF_SHOW_BALANCED, CONF_SHOW_BALANCED_YEAR,
                    CONF_SHOW_CONFIGURABLE, CONF_SHOW_CONFIGURABLE_DATE, CONF_SHOW_GENERATION, CONF_STORE_STATISTICS,
                    CONF_TARIFF, CONST_BALANCED, CONST_CONFIGURABLE, CONST_DAILY, CONST_GENERATION,
                    CONST_LAST_12_MONTHS, CONST_MONTHLY, CONST_READING, CONST_URL_SERVICE, CONST_YEARLY, DEFAULT_NAME,
                    DOMAIN, SENSOR_TYPES, SENSOR_TYPES_YAML, TYPE_BALANCED_CONFIGURABLE, TYPE_BALANCED_DAILY,
                    TYPE_BALANCED_LAST_12_MONTHS, TYPE_BALANCED_MONTHLY, TYPE_BALANCED_YEARLY,
                    TYPE_AMOUNT, TYPE_AMOUNT_STATUS, TYPE_AMOUNT_VALUE)
from .coordinator import TauronAmiplusUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_METER_ID): cv.string,
    vol.Required(CONF_MONITORED_VARIABLES, default=[]):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES_YAML)]),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    name = config.get(CONF_NAME)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    meter_id = config.get(CONF_METER_ID)

    show_generation_sensors = any(filter(lambda v: CONST_GENERATION in v, config[CONF_MONITORED_VARIABLES]))
    show_12_months = any(filter(lambda v: CONST_LAST_12_MONTHS in v, config[CONF_MONITORED_VARIABLES]))
    show_balanced = any(filter(lambda v: CONST_BALANCED in v, config[CONF_MONITORED_VARIABLES]))
    show_balanced_year = CONF_SHOW_BALANCED_YEAR in config[CONF_MONITORED_VARIABLES]

    coordinator = TauronAmiplusUpdateCoordinator(hass, username, password, meter_id, name,
                                                 show_generation=show_generation_sensors,
                                                 show_12_months=show_12_months,
                                                 show_balanced=show_balanced,
                                                 show_balanced_year=show_balanced_year,
                                                 store_statistics=True)
    dev = []
    for variable in config[CONF_MONITORED_VARIABLES]:
        sensor_type_config = SENSOR_TYPES[variable]
        dev.append(TauronAmiplusSensor(coordinator, name, meter_id, variable, sensor_type_config["state_class"]))
    async_add_entities(dev, True)


async def async_setup_entry(hass, entry: ConfigEntry, async_add_entities):
    """Set up a TAURON sensor based on a config entry."""
    user = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    meter_id = entry.data[CONF_METER_ID]
    meter_name = entry.data[CONF_METER_NAME]
    tariff = entry.data[CONF_TARIFF]

    show_generation_sensors = entry.options.get(CONF_SHOW_GENERATION, False)
    show_12_months = entry.options.get(CONF_SHOW_12_MONTHS, False)
    show_balanced = entry.options.get(CONF_SHOW_BALANCED, False)
    show_balanced_year = entry.options.get(CONF_SHOW_BALANCED_YEAR, False)
    show_configurable = entry.options.get(CONF_SHOW_CONFIGURABLE, False)
    show_configurable_date = entry.options.get(CONF_SHOW_CONFIGURABLE_DATE, None)
    store_statistics = entry.options.get(CONF_STORE_STATISTICS, False)
    if show_configurable_date is not None:
        show_configurable_date = parse_date(show_configurable_date)
    else:
        show_configurable = False

    sensors = []
    sensor_types = {**SENSOR_TYPES}
    if not show_generation_sensors:
        sensor_types = {k: v for k, v in sensor_types.items() if not k.startswith(CONST_GENERATION)}
    if not show_balanced_year:
        sensor_types = {k: v for k, v in sensor_types.items() if not k == TYPE_BALANCED_YEARLY}
    if not show_balanced:
        sensor_types = {
            k: v for k, v in sensor_types.items() if (not k.startswith(CONST_BALANCED)) or k.endswith(CONST_YEARLY)
        }
    if not show_12_months:
        sensor_types = {k: v for k, v in sensor_types.items() if not k.endswith(CONST_LAST_12_MONTHS)}
    if not show_configurable:
        sensor_types = {k: v for k, v in sensor_types.items() if not k.endswith(CONST_CONFIGURABLE)}

    coordinator = TauronAmiplusUpdateCoordinator(hass, user, password, meter_id, meter_name,
                                                 show_generation=show_generation_sensors,
                                                 show_12_months=show_12_months,
                                                 show_balanced=show_balanced,
                                                 show_balanced_year=show_balanced_year,
                                                 show_configurable=show_configurable,
                                                 show_configurable_date=show_configurable_date,
                                                 store_statistics=store_statistics)
    await coordinator.async_request_refresh()
    for sensor_type, sensor_type_config in sensor_types.items():
        sensors.append(
            TauronAmiplusConfigFlowSensor(
                coordinator,
                sensor_type_config["name"],
                meter_id,
                sensor_type,
                sensor_type_config["state_class"],
                tariff,
                meter_name
            )
        )

    async_add_entities(sensors, True)


class TauronAmiplusSensor(SensorEntity, CoordinatorEntity):

    def __init__(self, coordinator: TauronAmiplusUpdateCoordinator, name: str, meter_id: str, sensor_type: str,
                 state_class: SensorStateClass):
        super().__init__(coordinator)
        self._client_name = name
        self._meter_id = meter_id
        self._generation = sensor_type.startswith(CONST_GENERATION)
        self._sensor_type = sensor_type
        self._state_class = state_class
        self._power_zones = None
        self._tariff = None
        self._params = {}
        self._state = None

    @property
    def name(self):
        return f"{self._client_name} {self._sensor_type}"

    @property
    def native_unit_of_measurement(self):
        if self._sensor_type == TYPE_AMOUNT_VALUE:
            return "zł"
        elif self._sensor_type == TYPE_AMOUNT_STATUS:
            return None
        return UnitOfEnergy.KILO_WATT_HOUR

    @property
    def device_class(self):
        if self._sensor_type.startswith(TYPE_AMOUNT):
            return None
        return SensorDeviceClass.ENERGY

    @property
    def native_value(self):
        return self._state

    @property
    def extra_state_attributes(self):
        _params = {
            "tariff": self._tariff,
            **self._params,
        }
        return _params

    @property
    def icon(self):
        return "mdi:counter"

    @property
    def state_class(self):
        return self._state_class

    def _handle_coordinator_update(self) -> None:
        self.log(f"Updating data for entry: {self._sensor_type}")
        data: TauronAmiplusRawData = self.coordinator.data
        if not self.available or data is None:
            return
        dataset = data.generation if self._generation else data.consumption
        self._tariff = data.tariff

        if self._sensor_type == TYPE_AMOUNT_VALUE and data.amount_value is not None:
            self._state = data.amount_value
            self._params = {"status": data.amount_status}
        elif self._sensor_type == TYPE_AMOUNT_STATUS and data.amount_status is not None:
            self._state = data.amount_status
            self._params = {"value": data.amount_value}
        elif self._sensor_type == TYPE_BALANCED_DAILY and data.balance_daily is not None:
            self.update_balanced_data(data.balance_daily)
        elif self._sensor_type == TYPE_BALANCED_MONTHLY and data.balance_monthly is not None:
            self.update_balanced_data(data.balance_monthly)
        elif self._sensor_type == TYPE_BALANCED_YEARLY and data.balance_yearly is not None:
            self.update_balanced_data(data.balance_yearly)
        elif self._sensor_type == TYPE_BALANCED_LAST_12_MONTHS and data.balance_last_12_months_hourly is not None:
            self.update_balanced_data(data.balance_last_12_months_hourly)
        elif self._sensor_type == TYPE_BALANCED_CONFIGURABLE and data.balance_configurable_hourly is not None:
            self.update_balanced_data(data.balance_configurable_hourly)
        elif self._sensor_type.endswith(CONST_READING) and dataset.json_reading is not None:
            self.update_reading(dataset.json_reading)
        elif self._sensor_type.endswith(CONST_DAILY) and dataset.json_daily is not None:
            self.update_values(dataset.json_daily)
            self._params = {"date": dataset.daily_date, **self._params}
        elif self._sensor_type.endswith(CONST_MONTHLY) and dataset.json_monthly is not None:
            self.update_values(dataset.json_monthly)
        elif self._sensor_type.endswith(CONST_YEARLY) and dataset.json_yearly is not None:
            self.update_values(dataset.json_yearly)
        elif self._sensor_type.endswith(CONST_LAST_12_MONTHS) and dataset.json_last_12_months_hourly is not None:
            self.update_values(dataset.json_last_12_months_hourly)
        elif self._sensor_type.endswith(CONST_CONFIGURABLE) and dataset.json_configurable_hourly is not None:
            self.update_values(dataset.json_configurable_hourly)
        self.async_write_ha_state()

    def update_reading(self, json_data):
        reading = json_data["data"][-1]
        self._state = reading["C"]
        partials = {s: reading[s] for s in ["S1", "S2", "S3"] if s in reading and reading[s] is not None}
        self._params = {"date": reading["Date"], **partials}

    def update_values(self, json_data):
        total, zones, data_range = TauronAmiplusSensor.get_data_from_json(json_data)
        self._state = total
        self._params = {**zones, "data_range": data_range}
        self._params = {k: v for k, v in self._params.items() if v is not None}

    def update_balanced_data(self, balanced_data):
        con = balanced_data[0]
        gen = balanced_data[1]
        balance, sum_consumption, sum_generation, zones, data_range = TauronAmiplusSensor.get_balanced_data(con, gen)
        self._state = round(balance, 3)
        self._params = {
            "sum_consumption": round(sum_consumption, 3),
            "sum_generation": round(sum_generation, 3),
            "data_range": data_range,
            **{k: round(v, 3) for (k, v) in zones.items()},
        }

    @staticmethod
    def get_data_from_json(json_data):
        total = round(json_data["data"]["sum"], 3)
        zones = {}
        data_range = None
        if (
            "zones" in json_data["data"]
            and len(json_data["data"]["zones"]) > 0
            and "zonesName" in json_data["data"]
            and len(json_data["data"]["zonesName"]) > 0
        ):
            zones = {v: round(json_data["data"]["zones"].get(k, 0), 3) for (k, v) in json_data["data"]["zonesName"].items()}
        if (
            "allData" in json_data["data"]
            and len(json_data["data"]["allData"]) > 0
            and "Date" in json_data["data"]["allData"][0]
        ):
            consumption_data = json_data["data"]["allData"]
            data_range = f"{consumption_data[0]['Date']} - {consumption_data[-1]['Date']}"
        return total, zones, data_range

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
        return f"tauron-yaml-{self._meter_id}-{self._sensor_type.lower()}"

    def log(self, msg):
        _LOGGER.debug(f"[{self._meter_id}]: {msg}")


class TauronAmiplusConfigFlowSensor(TauronAmiplusSensor):

    def __init__(self, coordinator: TauronAmiplusUpdateCoordinator, name: str, meter_id: str, sensor_type: str,
                 state_class: SensorStateClass, tariff: str, meter_name: str):
        """Initialize the sensor."""
        super().__init__(coordinator, name, meter_id, sensor_type, state_class)
        self._tariff = tariff
        self._meter_name = meter_name

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._meter_id)},
            "name": f"{DEFAULT_NAME} {self._meter_name}",
            "manufacturer": "TAURON",
            "model": self._meter_id,
            "sw_version": f"Tariff {self._tariff}",
            "via_device": None,
            "configuration_url": CONST_URL_SERVICE,
        }

    @property
    def name(self):
        return f"{DEFAULT_NAME} {self._meter_name} {self._client_name}"

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"tauron-{self._meter_id}-{self._sensor_type.lower()}"
