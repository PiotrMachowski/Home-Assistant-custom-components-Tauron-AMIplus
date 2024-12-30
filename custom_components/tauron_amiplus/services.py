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

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall

_LOGGER = logging.getLogger(__name__)


class DownloadStatisticsService:
    """Home Assistant Core integration service to disable a device."""

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
