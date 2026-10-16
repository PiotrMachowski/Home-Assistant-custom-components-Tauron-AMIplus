"""Number entities with energy prices used to calculate cost statistics."""
import logging

from homeassistant.components.number import NumberMode, RestoreNumber
from homeassistant.core import callback
from homeassistant.const import EntityCategory
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_METER_ID, CONF_SHOW_COST, CONF_METER_NAME, CONF_TARIFF, CONST_URL_SERVICE, DEFAULT_NAME, DOMAIN
from .coordinator import TauronAmiplusUpdateCoordinator
from .typing_helpers import TauronAmiplusConfigEntry
from .zones import get_zones

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry: TauronAmiplusConfigEntry, async_add_entities):
    if not entry.options.get(CONF_SHOW_COST, False):
        return
    coordinator = entry.runtime_data.coordinator
    meter_id = entry.data[CONF_METER_ID]
    meter_name = entry.data[CONF_METER_NAME]
    tariff = entry.data[CONF_TARIFF]
    price_prefix = f"tauron-{meter_id}-price-zone-"

    entities = [TauronAmiplusFixedFeeNumber(coordinator, meter_id, meter_name, tariff)]
    known_zones = set()
    # Price entities of zones seen earlier are created right away, so that their values are restored
    # before the first data download. Zones that are new to this installation are added once data arrives.
    for registered in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id):
        if registered.domain == "number" and registered.unique_id.startswith(price_prefix):
            zone = registered.unique_id[len(price_prefix):]
            known_zones.add(zone)
            # Names used to contain the device name, e.g. "Tauron AMIplus 123 price Zone (T1)"
            zone_name = (registered.original_name or zone).split(" price ")[-1].removeprefix("Price ")
            entities.append(TauronAmiplusZonePriceNumber(coordinator, meter_id, meter_name, tariff, zone, zone_name))
    async_add_entities(entities)

    @callback
    def add_new_zones() -> None:
        new_entities = []
        for zone, zone_name in get_zones(coordinator.data).items():
            if zone not in known_zones:
                known_zones.add(zone)
                new_entities.append(TauronAmiplusZonePriceNumber(coordinator, meter_id, meter_name, tariff, zone,
                                                                 zone_name))
        if new_entities:
            async_add_entities(new_entities)

    add_new_zones()
    entry.async_on_unload(coordinator.async_add_listener(add_new_zones))


class TauronAmiplusCostNumber(CoordinatorEntity, RestoreNumber):
    """Base of numbers that configure cost calculation.

    Values live in the coordinator and are restored after restarts. Changing them doesn't reload the integration,
    new values are used the next time statistics are calculated.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 0
    _attr_native_max_value = 100000
    _attr_native_step = 0.0001

    def __init__(self, coordinator: TauronAmiplusUpdateCoordinator, meter_id: str, meter_name: str, tariff: str,
                 name: str, unique_id: str):
        super().__init__(coordinator)
        self._meter_id = meter_id
        self._meter_name = meter_name
        self._tariff = tariff
        self._attr_name = name
        self._attr_unique_id = unique_id

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_data = await self.async_get_last_number_data()
        if last_data is not None and last_data.native_value is not None:
            self._store(last_data.native_value)

    @property
    def available(self) -> bool:
        # Prices don't depend on a successful download, so they can be edited at any time
        return True

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._meter_id)},
            "name": f"{DEFAULT_NAME} {self._meter_name}",
            "manufacturer": "TAURON",
            "model": self._meter_id,
            "sw_version": f"Tariff {self._tariff}",
            "configuration_url": CONST_URL_SERVICE,
        }

    async def async_set_native_value(self, value: float) -> None:
        self._store(value)
        self.async_write_ha_state()

    def _store(self, value: float) -> None:
        raise NotImplementedError


class TauronAmiplusZonePriceNumber(TauronAmiplusCostNumber):
    """Price of 1 kWh in a tariff zone. Cost is calculated only when every zone has a price."""

    _attr_icon = "mdi:cash"

    def __init__(self, coordinator, meter_id, meter_name, tariff, zone: str, zone_name: str):
        super().__init__(coordinator, meter_id, meter_name, tariff, f"Price {zone_name}",
                         f"tauron-{meter_id}-price-zone-{zone}")
        self._zone = zone
        coordinator.cost_prices.setdefault(zone, None)

    @property
    def native_unit_of_measurement(self) -> str:
        return f"{self.hass.config.currency}/kWh"

    @property
    def native_value(self) -> float | None:
        return self.coordinator.cost_prices.get(self._zone)

    def _store(self, value: float) -> None:
        self.coordinator.cost_prices[self._zone] = value


class TauronAmiplusFixedFeeNumber(TauronAmiplusCostNumber):
    """Fixed monthly fee, spread evenly over the hours of the month."""

    _attr_icon = "mdi:cash-clock"

    def __init__(self, coordinator, meter_id, meter_name, tariff):
        super().__init__(coordinator, meter_id, meter_name, tariff, "Monthly fee",
                         f"tauron-{meter_id}-fixed-monthly-fee")

    @property
    def native_unit_of_measurement(self) -> str:
        return f"{self.hass.config.currency}/month"

    @property
    def native_value(self) -> float:
        return self.coordinator.cost_fixed_monthly_fee

    def _store(self, value: float) -> None:
        self.coordinator.cost_fixed_monthly_fee = value
