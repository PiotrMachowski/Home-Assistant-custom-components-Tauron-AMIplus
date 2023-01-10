"""Support for TAURON sensors."""
import datetime
import logging

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import CONF_MONITORED_VARIABLES, CONF_NAME, CONF_PASSWORD, CONF_USERNAME, ENERGY_KILO_WATT_HOUR
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (CONF_GENERATION, CONF_METER_ID, CONF_SHOW_GENERATION, CONF_TARIFF, CONF_URL_SERVICE, DEFAULT_NAME,
                    DOMAIN, SENSOR_TYPES, TYPE_CURRENT_READINGS)
from .coordinator import TauronAmiplusRawData, TauronAmiplusUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_METER_ID): cv.string,
    vol.Required(CONF_MONITORED_VARIABLES, default=[]):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_GENERATION, default=False): cv.boolean,
})


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    name = config.get(CONF_NAME)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    meter_id = config.get(CONF_METER_ID)
    generation = config.get(CONF_GENERATION)
    coordinator = TauronAmiplusUpdateCoordinator(hass, username, password, meter_id, generation)
    await coordinator.async_request_refresh()
    dev = []
    for variable in config[CONF_MONITORED_VARIABLES]:
        dev.append(TauronAmiplusSensor(coordinator, name, meter_id, generation, variable))
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
    generation = show_generation_sensors or any(sensor_type.startswith("generation") for sensor_type in sensor_types)
    coordinator = TauronAmiplusUpdateCoordinator(hass, user, password, meter_id, generation)
    await coordinator.async_request_refresh()
    for sensor_type in sensor_types:
        if not (sensor_type.startswith("generation") and not show_generation_sensors):
            sensor_name = SENSOR_TYPES[sensor_type][0]
            sensors.append(
                TauronAmiplusConfigFlowSensor(
                    coordinator,
                    sensor_name,
                    meter_id,
                    show_generation_sensors,
                    sensor_type,
                )
            )

    async_add_entities(sensors, True)


class TauronAmiplusSensor(SensorEntity, CoordinatorEntity[TauronAmiplusRawData]):

    def __init__(self, coordinator: TauronAmiplusUpdateCoordinator, name, meter_id, generation, sensor_type):
        super().__init__(coordinator)
        self.client_name = name
        self.meter_id = meter_id
        self.generation_enabled = generation or sensor_type.startswith("generation")
        self.sensor_type = sensor_type
        self.power_zones = None
        self.tariff = None
        self.power_zones_last_update = None
        self.power_zones_last_update_tech = datetime.datetime(2000, 1, 1)
        self.data = None
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
        if self.sensor_type.startswith("generation"):
            return None  # TODO support generation
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
        if self.sensor_type.endswith("daily") or "current" in self.sensor_type:
            return SensorStateClass.MEASUREMENT
        elif self.sensor_type.endswith(("monthly", "yearly")):
            return SensorStateClass.TOTAL_INCREASING
        else:
            return None

    def _handle_coordinator_update(self) -> None:
        if self.coordinator.data is None:
            return
        elif self.sensor_type == TYPE_CURRENT_READINGS and self.coordinator.data.json_readings is not None:
            self.update_readings(self.coordinator.data.json_readings, self.coordinator.data.tariff)
        elif self.sensor_type.endswith("daily") and self.coordinator.data.json_daily is not None:
            self.update_values(self.coordinator.data.json_daily)
            self.params = {"date": self.coordinator.data.daily_date, **self.params}
        elif self.sensor_type.endswith("monthly") and self.coordinator.data.json_monthly is not None:
            self.update_values(self.coordinator.data.json_monthly)
        elif self.sensor_type.endswith("yearly") and self.coordinator.data.json_yearly is not None:
            self.update_values(self.coordinator.data.json_yearly)
        self.async_write_ha_state()

    def update_readings(self, json_data, tariff):
        reading = json_data["data"][0]
        self._state = reading["C"]
        partials = {s: reading[s] for s in ["S1", "S2", "S3"] if reading[s] is not None}
        self.params = {"date": reading["Date"], **partials}
        self.tariff = tariff

    def update_values(self, json_data):
        total, tariff, zones = TauronAmiplusSensor.get_data_from_json(json_data)
        self._state = total
        self.tariff = tariff
        self.params = zones

    @staticmethod
    def get_data_from_json(json_data):
        total = round(json_data["data"]["sum"], 3)
        tariff = json_data["data"]["tariff"]
        zones = {v: round(json_data["data"]["zones"][k], 3) for (k, v) in json_data["data"]["zonesName"].items()}
        return total, tariff, zones

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"tauron-yaml-{self.meter_id}-{self.sensor_type.lower()}"


class TauronAmiplusConfigFlowSensor(TauronAmiplusSensor):

    def __init__(self, coordinator: TauronAmiplusUpdateCoordinator, name, meter_id, generation, sensor_type):
        """Initialize the sensor."""
        super().__init__(coordinator, name, meter_id, generation, sensor_type)

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.meter_id)},
            "name": f"eLicznik {self.meter_id}",
            "manufacturer": "TAURON",
            "model": self.meter_id,
            "sw_version": f"Tariff {self.tariff}",
            "via_device": None,
            "configuration_url": CONF_URL_SERVICE,
        }

    @property
    def name(self):
        return f"{DEFAULT_NAME} {self.meter_id} {self.client_name}"

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"tauron-{self.meter_id}-{self.sensor_type.lower()}"
