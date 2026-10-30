"""Update coordinator for TAURON sensors."""
import datetime
import logging
import time

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util.dt import get_time_zone

from .connector import TauronAmiplusConnector, TauronAmiplusRawData
from .const import (
    DOMAIN,
    SMART_POLLING_WINDOW_MORNING,
    SMART_POLLING_WINDOW_AFTERNOON,
    SMART_POLLING_WINDOW_RETRY,
)
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
            config_entry=None,
    ):
        initial_interval, _ = self.get_next_smart_poll_window()
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=initial_interval,
            update_method=self.update_method,
            config_entry=config_entry,
        )
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

    @staticmethod
    def get_next_smart_poll_window(
        now: datetime.datetime | None = None,
        yesterday_complete: bool = True,
    ) -> tuple[datetime.timedelta, datetime.datetime]:
        tz = get_time_zone("Europe/Warsaw")
        if now is None:
            now = datetime.datetime.now(tz)
        elif now.tzinfo is None:
            now = now.replace(tzinfo=tz)

        today = now.date()
        windows = [SMART_POLLING_WINDOW_MORNING, SMART_POLLING_WINDOW_AFTERNOON]
        if not yesterday_complete:
            windows.append(SMART_POLLING_WINDOW_RETRY)

        candidates: list[datetime.datetime] = []
        for h, m in windows:
            candidate = datetime.datetime.combine(today, datetime.time(h, m), tzinfo=tz)
            if (candidate - now).total_seconds() > 120:
                candidates.append(candidate)

        if not candidates:
            tomorrow = today + datetime.timedelta(days=1)
            h, m = SMART_POLLING_WINDOW_MORNING
            candidates.append(datetime.datetime.combine(tomorrow, datetime.time(h, m), tzinfo=tz))

        next_run = min(candidates)
        delta = next_run - now
        if delta.total_seconds() < 60:
            delta = datetime.timedelta(minutes=1)
        return delta, next_run

    async def update_method(self) -> TauronAmiplusRawData:
        start_time = time.monotonic()
        _LOGGER.info(f"[{self.meter_id}] Starting data update from Tauron eLicznik")
        try:
            data = await self._update()
            if data is not None and self.store_statistics:
                self.log("Starting statistics update")
                await self.generate_statistics(data)
                self.log("Updated all statistics")
            await self.connector.async_save_cache()
        except Exception as err:
            self.update_interval = datetime.timedelta(minutes=30)
            _LOGGER.warning(
                f"[{self.meter_id}] Update failed ({err}). Will retry in 30 minutes."
            )
            raise

        elapsed = time.monotonic() - start_time

        warsaw_tz = get_time_zone("Europe/Warsaw")
        yesterday = (datetime.datetime.now(warsaw_tz) - datetime.timedelta(days=1)).date()
        yesterday_ok = bool(self.connector.is_day_cached(yesterday))
        next_interval, next_time = self.get_next_smart_poll_window(yesterday_complete=yesterday_ok)
        self.update_interval = next_interval
        hours, remainder = divmod(int(next_interval.total_seconds()), 3600)
        minutes, _ = divmod(remainder, 60)

        _LOGGER.info(
            f"[{self.meter_id}] Update cycle finished successfully in {elapsed:.1f}s. "
            f"Next scheduled update at {next_time.strftime('%H:%M')} (in {hours}h {minutes}m"
            f"{', 22:30 retry skipped: yesterday complete' if yesterday_ok else ', including 22:30 retry: yesterday missing'})."
        )
        return data

    async def generate_statistics(self, data):
        statistics_updater = TauronAmiplusStatisticsUpdater(self.hass, self.connector, self.meter_id, self.meter_name,
                                                            self.show_generation, self.show_balanced)
        await statistics_updater.update_all(data)

    async def _update(self) -> TauronAmiplusRawData:
        return await self.connector.get_raw_data()

    def log(self, msg):
        _LOGGER.debug(f"[{self.meter_id}]: {msg}")
