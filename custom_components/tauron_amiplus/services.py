"""Spook - Not your homie."""
from __future__ import annotations

import datetime
import logging
from typing import TYPE_CHECKING

import voluptuous as vol
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
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
        if device is None or not device.config_entries:
            _LOGGER.error(f"Device not found or has no config entries: {call.data['device_id']}")
            return
        config_entry_id = next(iter(device.config_entries))
        config_entry = self._hass.config_entries.async_get_entry(config_entry_id)
        if config_entry is None:
            _LOGGER.error(f"Config entry not found: {config_entry_id}")
            return
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
        if device is None or not device.config_entries:
            _LOGGER.error(f"Device not found or has no config entries: {call.data['device_id']}")
            return
        config_entry_id = next(iter(device.config_entries))
        config_entry: TauronAmiplusConfigEntry = self._hass.config_entries.async_get_entry(config_entry_id)
        if config_entry is None:
            _LOGGER.error(f"Config entry not found: {config_entry_id}")
            return
        await config_entry.runtime_data.coordinator.connector.async_clear_cache()


def register_all_services(hass: HomeAssistant) -> None:
    services = [DownloadStatisticsService(hass), ClearCacheService(hass)]
    for service in services:
        if not hass.services.has_service(service.domain, service.service):
            hass.services.async_register(service.domain, service.service, service.async_handle_service, service.schema)
