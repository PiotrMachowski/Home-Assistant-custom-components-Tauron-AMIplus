"""Support for TAURON sensors."""
import datetime
import logging

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity,
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
)
from homeassistant.const import (
    CONF_MONITORED_VARIABLES,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    DEVICE_CLASS_ENERGY,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_GENERATION,
    CONF_METER_ID,
    CONF_SHOW_GENERATION,
    CONF_TARIFF,
    CONF_URL_SERVICE,
    DEFAULT_NAME,
    DOMAIN,
    SENSOR_TYPES,
    SUPPORTED_TARIFFS,
    TARIFF_G12,
    TARIFF_G12W,
    TYPE_ZONE,
    ZONE,
)
from .coordinator import TauronAmiplusRawData, TauronAmiplusUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_METER_ID): cv.string,
        vol.Required(CONF_MONITORED_VARIABLES, default=[]): vol.All(
            cv.ensure_list, [vol.In(SENSOR_TYPES)]
        ),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_GENERATION, default=False): cv.boolean,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    name = config.get(CONF_NAME)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    meter_id = config.get(CONF_METER_ID)
    generation = config.get(CONF_GENERATION)
    coordinator = TauronAmiplusUpdateCoordinator(
        hass, username, password, meter_id, generation
    )
    await coordinator.async_request_refresh()
    dev = []
    for variable in config[CONF_MONITORED_VARIABLES]:
        dev.append(
            TauronAmiplusSensor(coordinator, name, meter_id, generation, variable)
        )
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
    if tariff not in SUPPORTED_TARIFFS:
        sensor_types.pop(TYPE_ZONE)
    generation = show_generation_sensors or any(
        sensor_type.startswith("generation") for sensor_type in sensor_types
    )
    coordinator = TauronAmiplusUpdateCoordinator(
        hass, user, password, meter_id, generation
    )
    await coordinator.async_request_refresh()
    for sensor_type in sensor_types:
        if not (sensor_type.startswith("generation") and not show_generation_sensors):
            sensor_name = SENSOR_TYPES[sensor_type][3]
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
    def __init__(
        self,
        coordinator: TauronAmiplusUpdateCoordinator,
        name,
        meter_id,
        generation,
        sensor_type,
    ):
        super().__init__(coordinator)
        self.client_name = name
        self.meter_id = meter_id
        self.generation_enabled = generation or sensor_type.startswith("generation")
        self.sensor_type = str(sensor_type)
        self.unit = SENSOR_TYPES[sensor_type][0]
        self.power_zones = None
        self.tariff = None
        self.power_zones_last_update = None
        self.power_zones_last_update_tech = datetime.datetime(2000, 1, 1)
        self.data = None
        self.params = {}
        self._state = None
        if not sensor_type == ZONE:
            self.state_param = SENSOR_TYPES[sensor_type][1]
            self.additional_param_name = SENSOR_TYPES[sensor_type][2][0]
            self.additional_param = SENSOR_TYPES[sensor_type][2][1]

    @property
    def name(self):
        return f"{self.client_name} {self.sensor_type}"

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        _params = {
            "tariff": self.tariff,
            "zones_updated": self.power_zones_last_update,
            **self.params,
        }
        return _params

    @property
    def unit_of_measurement(self):
        return self.unit

    @property
    def icon(self):
        return "mdi:counter"

    @property
    def state_class(self):
        if self.sensor_type.endswith("daily"):
            return STATE_CLASS_MEASUREMENT
        elif self.sensor_type.endswith(("monthly", "yearly")):
            return STATE_CLASS_TOTAL_INCREASING  # so far no const available in homeassistant core
        else:
            return None

    @property
    def device_class(self):
        return DEVICE_CLASS_ENERGY

    @property
    def should_poll(self) -> bool:
        return self.sensor_type == ZONE

    async def async_update(self) -> None:
        if self.sensor_type == ZONE:
            self.update_zone()
        else:
            await super().async_update()

    def _handle_coordinator_update(self) -> None:
        if self.coordinator.data is None:
            return
        if self.coordinator.data.configuration_1_day_ago is not None and self.coordinator.data.configuration_2_days_ago is not None:
            self.update_configuration(
                self.coordinator.data.configuration_1_day_ago,
                self.coordinator.data.configuration_2_days_ago,
            )
        if self.sensor_type == ZONE:
            self.update_zone()
        elif self.sensor_type.endswith("daily") and self.coordinator.data.json_daily is not None:
            self.update_values_daily(self.coordinator.data.json_daily)
        elif self.sensor_type.endswith("monthly") and self.coordinator.data.json_monthly is not None:
            self.update_values_monthly(self.coordinator.data.json_monthly)
        elif self.sensor_type.endswith("yearly") and self.coordinator.data.json_yearly is not None:
            self.update_values_yearly(self.coordinator.data.json_yearly)
        self.async_write_ha_state()

    def update_configuration(self, config_1_day_ago, config_2_days_ago):
        now_datetime = datetime.datetime.now()
        if (
            now_datetime - datetime.timedelta(days=1)
        ) >= self.power_zones_last_update_tech:
            config = config_1_day_ago if now_datetime.hour >= 10 else config_2_days_ago
            self.power_zones = config[0]
            self.tariff = config[1]
            self.power_zones_last_update = config[2]
            self.power_zones_last_update_tech = now_datetime

    def update_zone(self):
        if self.tariff in SUPPORTED_TARIFFS:
            parsed_zones = self.power_zones[1]
            now_time = datetime.datetime.now().time()
            if (
                len(
                    list(
                        filter(
                            lambda x: x["start"] <= now_time < x["stop"], parsed_zones
                        )
                    )
                )
                > 0
            ):
                self._state = 1
            else:
                self._state = 2
            self.params = {}
            for power_zone in self.power_zones:
                pz_name = f"zone{power_zone} "
                pz = (
                    str(
                        list(
                            map(
                                lambda x: x["start"].strftime("%H:%M")
                                + " - "
                                + x["stop"].strftime("%H:%M"),
                                self.power_zones[power_zone],
                            )
                        )
                    )
                    .replace("[", "")
                    .replace("]", "")
                    .replace("'", "")
                )
                self.params[pz_name] = pz
        else:
            self._state = 1

    def update_values_daily(self, json_data):
        self._state = round(float(json_data[self.state_param]), 3)
        if self.tariff in SUPPORTED_TARIFFS:
            values = list(
                json_data["dane"][
                    "chart" if self.sensor_type.startswith("consumption") else "OZE"
                ].values()
            )
            z1 = list(filter(lambda x: x["Zone"] == "1", values))
            z2 = list(filter(lambda x: x["Zone"] == "2", values))
            sum_z1 = round(sum(float(val["EC"]) for val in z1), 3)
            sum_z2 = round(sum(float(val["EC"]) for val in z2), 3)
            day = values[0]["Date"]
            self.params = {"zone1": sum_z1, "zone2": sum_z2, "day": day}
        if self.generation_enabled:
            self.params = {
                **self.params,
                self.additional_param_name: round(
                    float(json_data[self.additional_param]), 3
                ),
            }

    def update_values_monthly(self, json_data):
        self._state = round(float(json_data[self.state_param]), 3)
        self.params = {}
        if self.tariff in SUPPORTED_TARIFFS:
            values = json_data["dane"][
                "chart" if self.sensor_type.startswith("consumption") else "OZE"
            ]
            z1 = list(filter(lambda x: "tariff1" in x, values))
            z2 = list(filter(lambda x: "tariff2" in x, values))
            sum_z1 = round(sum(float(val["tariff1"]) for val in z1), 3)
            sum_z2 = round(sum(float(val["tariff2"]) for val in z2), 3)
            month = datetime.datetime.strptime(values[0]["Date"], "%Y-%m-%d").strftime(
                "%Y-%m"
            )
            self.params = {"zone1": sum_z1, "zone2": sum_z2, "month": month}
        if self.generation_enabled:
            self.params = {
                **self.params,
                self.additional_param_name: round(
                    float(json_data[self.additional_param]), 3
                ),
            }

    def update_values_yearly(self, json_data):
        self._state = round(float(json_data[self.state_param]), 3)
        self.params = {}
        if self.tariff in SUPPORTED_TARIFFS:
            values = json_data["dane"][
                "chart" if self.sensor_type.startswith("consumption") else "OZE"
            ]
            z1 = list(filter(lambda x: "tariff1" in x, values))
            z2 = list(filter(lambda x: "tariff2" in x, values))
            sum_z1 = round(sum(float(val["tariff1"]) for val in z1), 3)
            sum_z2 = round(sum(float(val["tariff2"]) for val in z2), 3)
            year = datetime.datetime.strptime(values[0]["Date"], "%Y-%m").strftime("%Y")
            self.params = {"zone1": sum_z1, "zone2": sum_z2, "year": year}
        if self.generation_enabled:
            self.params = {
                **self.params,
                self.additional_param_name: round(
                    float(json_data[self.additional_param]), 3
                ),
            }

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"tauron-yaml-{self.meter_id}-{self.sensor_type.lower()}"


class TauronAmiplusConfigFlowSensor(TauronAmiplusSensor):
    def __init__(
        self,
        coordinator: TauronAmiplusUpdateCoordinator,
        name,
        meter_id,
        generation,
        sensor_type,
    ):
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
