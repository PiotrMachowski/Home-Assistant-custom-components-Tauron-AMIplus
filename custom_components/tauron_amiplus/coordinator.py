"""Update coordinator for TAURON sensors."""
import logging
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (DEFAULT_UPDATE_INTERVAL, DOMAIN)
from .connector import TauronAmiplusRawData, TauronAmiplusConnector


_LOGGER = logging.getLogger(__name__)


class TauronAmiplusUpdateCoordinator(DataUpdateCoordinator[TauronAmiplusRawData]):

    def __init__(self, hass: HomeAssistant, username, password, meter_id):
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=DEFAULT_UPDATE_INTERVAL)
        self.connector = TauronAmiplusConnector(username, password, meter_id)

    async def _async_update_data(self) -> TauronAmiplusRawData:
        return await self.hass.async_add_executor_job(self._update)

    def _update(self) -> TauronAmiplusRawData:
        return self.connector.get_raw_data()
