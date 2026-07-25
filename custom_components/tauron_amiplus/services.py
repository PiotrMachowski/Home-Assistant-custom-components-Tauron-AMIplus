"""Spook - Not your homie."""
from __future__ import annotations

import datetime
import logging
from typing import TYPE_CHECKING

import voluptuous as vol
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr

from .const import CONF_SHOW_COST, DOMAIN
from .statistics import TauronAmiplusStatisticsUpdater
from .typing_helpers import TauronAmiplusConfigEntry

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall

_LOGGER = logging.getLogger(__name__)


class DownloadStatisticsService:

    domain = DOMAIN
    service = "download_statistics"
    schema = vol.Schema({
        vol.Required("device_id"): cv.string,
        vol.Required("start_date"): cv.date
    })

    def __init__(self, hass: HomeAssistant):
        self._hass = hass

    async def async_handle_service(self, call: ServiceCall) -> None:
        device_registry = dr.async_get(self._hass)
        now = datetime.date.today()
        start_date = call.data["start_date"]
        if start_date > now:
            _LOGGER.error(f"Failed to download statistics, date from the future: {start_date}")
            return
        device = device_registry.async_get(call.data["device_id"])
        [config_entry_id, *_] = device.config_entries
        config_entry = self._hass.config_entries.async_get_entry(config_entry_id)
        await TauronAmiplusStatisticsUpdater.manually_update(self._hass, start_date, config_entry)


class ForcePriceRecalculationService:

    domain = DOMAIN
    service = "force_price_recalculation"
    schema = vol.Schema({
        vol.Required("device_id"): cv.string,
    })

    def __init__(self, hass: HomeAssistant):
        self._hass = hass

    async def async_handle_service(self, call: ServiceCall) -> None:
        device_registry = dr.async_get(self._hass)
        device = device_registry.async_get(call.data["device_id"])
        [config_entry_id, *_] = device.config_entries
        config_entry: TauronAmiplusConfigEntry = self._hass.config_entries.async_get_entry(config_entry_id)
        if not config_entry.options.get(CONF_SHOW_COST, False):
            _LOGGER.error("Cannot force price recalculation, cost statistics are not enabled for this meter")
            return
        now = datetime.datetime.now()
        start_date = (now - datetime.timedelta(365)).replace(day=1, hour=0, minute=0, second=0, microsecond=0).date()
        await TauronAmiplusStatisticsUpdater.manually_update(self._hass, start_date, config_entry)


class ClearCacheService:

    domain = DOMAIN
    service = "clear_cache"
    schema = vol.Schema({
        vol.Required("device_id"): cv.string,
    })

    def __init__(self, hass: HomeAssistant):
        self._hass = hass

    async def async_handle_service(self, call: ServiceCall) -> None:
        device_registry = dr.async_get(self._hass)
        device = device_registry.async_get(call.data["device_id"])
        [config_entry_id, *_] = device.config_entries
        config_entry: TauronAmiplusConfigEntry = self._hass.config_entries.async_get_entry(config_entry_id)
        config_entry.runtime_data.coordinator.connector.clear_cache()


def register_all_services(hass: HomeAssistant) -> None:
    services = [DownloadStatisticsService(hass), ForcePriceRecalculationService(hass), ClearCacheService(hass)]
    for service in services:
        hass.services.async_register(service.domain, service.service, service.async_handle_service, service.schema)
