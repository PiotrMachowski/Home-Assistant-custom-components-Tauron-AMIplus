"""Update coordinator for TAURON sensors."""
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .connector import TauronAmiplusConnector, TauronAmiplusRawData
from .const import (DEFAULT_UPDATE_INTERVAL, DOMAIN)
from .statistics import update_statistics

_LOGGER = logging.getLogger(__name__)


class TauronAmiplusUpdateCoordinator(DataUpdateCoordinator[TauronAmiplusRawData]):

    def __init__(self, hass: HomeAssistant, username, password, meter_id, show_generation, show_12_months, show_configurable, show_configurable_date):
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=DEFAULT_UPDATE_INTERVAL)
        self.connector = TauronAmiplusConnector(username, password, meter_id, show_12_months, show_configurable, show_configurable_date)
        self.meter_id = meter_id
        self.show_generation = show_generation
        self.show_12_months = show_12_months
        self.show_configurable = show_configurable
        self.show_configurable_date = show_configurable_date

    async def _async_update_data(self) -> TauronAmiplusRawData:
        data = await self.hass.async_add_executor_job(self._update)
        if data is not None:
            if data.consumption is not None and data.consumption.json_month_hourly is not None:
                await self.generate_statistics(data.consumption.json_month_hourly, False)
            if self.show_generation and data.generation is not None and data.generation.json_month_hourly is not None:
                await self.generate_statistics(data.generation.json_month_hourly, True)
        return data

    async def generate_statistics(self, data, generation):
        await update_statistics(self.hass, self.meter_id, generation, data, self.connector)

    def _update(self) -> TauronAmiplusRawData:
        return self.connector.get_raw_data()
