"""Update coordinator for TAURON sensors."""
import datetime
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .connector import TauronAmiplusConnector, TauronAmiplusRawData
from .const import (DEFAULT_UPDATE_INTERVAL, DOMAIN)
from .statistics import TauronAmiplusStatisticsUpdater

_LOGGER = logging.getLogger(__name__)


class TauronAmiplusUpdateCoordinator(DataUpdateCoordinator[TauronAmiplusRawData]):

    def __init__(
            self,
            hass: HomeAssistant,
            config_entry_id: str,
            username: str,
            password: str,
            meter_id: str,
            meter_name: str,
            show_generation: bool = False,
            show_12_months: bool = False,
            show_balanced: bool = False,
            show_balanced_year: bool = False,
            show_configurable: bool = False,
            show_configurable_date: datetime.date | None = None,
            store_statistics: bool = False,
    ):
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=DEFAULT_UPDATE_INTERVAL,
                         update_method=self.update_method)
        self.connector = TauronAmiplusConnector(username, password, meter_id, hass, config_entry_id, show_generation, show_12_months,
                                                show_balanced, show_balanced_year, show_configurable,
                                                show_configurable_date)
        self.meter_id = meter_id
        self.meter_name = meter_name
        self.show_generation = show_generation
        self.show_12_months = show_12_months
        self.show_balanced = show_balanced
        self.show_configurable = show_configurable
        self.show_configurable_date = show_configurable_date
        self.store_statistics = store_statistics

    async def update_method(self) -> TauronAmiplusRawData:
        self.log("Starting data update")
        data = await self._update()
        self.log("Downloaded all data")
        if data is not None and self.store_statistics:
            self.log("Starting statistics update")
            await self.generate_statistics(data)
            self.log("Updated all statistics")
        return data

    async def generate_statistics(self, data):
        statistics_updater = TauronAmiplusStatisticsUpdater(self.hass, self.connector, self.meter_id, self.meter_name,
                                                            self.show_generation, self.show_balanced)
        await statistics_updater.update_all(data)

    async def _update(self) -> TauronAmiplusRawData:
        return await self.connector.get_raw_data()

    def log(self, msg):
        _LOGGER.debug(f"[{self.meter_id}]: {msg}")
