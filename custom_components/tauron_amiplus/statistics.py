import collections
import datetime
import inspect
import logging

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import StatisticMetaData, StatisticMeanType
from homeassistant.components.recorder.statistics import (async_add_external_statistics, get_last_statistics,
                                                          statistics_during_period)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import as_utc, get_time_zone, utc_from_timestamp

from .connector import TauronAmiplusConnector, TauronAmiplusRawData
from .const import (CONF_METER_ID, CONF_METER_NAME, CONF_SHOW_BALANCED, CONF_SHOW_GENERATION, CONST_BALANCED,
                    CONST_CONSUMPTION, CONST_GENERATION, DEFAULT_NAME, STATISTICS_DOMAIN)

_LOGGER = logging.getLogger(__name__)


class TauronAmiplusStatisticsUpdater:

    def __init__(self, hass: HomeAssistant, connector: TauronAmiplusConnector, meter_id: str, meter_name: str,
                 show_generation: bool, show_balanced: bool) -> None:
        self.hass = hass
        self.connector = connector
        self.meter_id = meter_id
        self.meter_name = meter_name
        self.show_generation = show_generation
        self.show_balanced = show_balanced

    async def _safe_delete_cache_day(self, day: datetime.date) -> None:
        if hasattr(self.connector, "_cache") and self.connector._cache is not None:
            res = self.connector._cache.delete_day(day)
            if inspect.isawaitable(res):
                await res

    @staticmethod
    async def manually_update(hass, start_date: datetime.date, entry) -> None:
        username = entry.data[CONF_USERNAME]
        password = entry.data[CONF_PASSWORD]
        meter_id = entry.data[CONF_METER_ID]
        meter_name = entry.data[CONF_METER_NAME]

        show_generation = entry.options.get(CONF_SHOW_GENERATION, False)
        show_balanced = entry.options.get(CONF_SHOW_BALANCED, False)

        connector = TauronAmiplusConnector(
            username,
            password,
            meter_id,
            hass=hass,
            config_entry_id=entry.entry_id,
            show_generation=show_generation,
            show_balanced=show_balanced,
        )
        statistics_updater = TauronAmiplusStatisticsUpdater(
            hass, connector, meter_id, meter_name, show_generation, show_balanced
        )

        data = await connector.get_raw_data()
        start_date_obj = start_date.date() if isinstance(start_date, datetime.datetime) else start_date
        start_datetime = datetime.datetime.combine(
            start_date_obj, datetime.time(0, 0, tzinfo=get_time_zone("Europe/Warsaw"))
        )
        if data is not None:
            await statistics_updater.update_all(data, start_datetime)
            await connector.async_save_cache()

    async def update_all(self, last_data: TauronAmiplusRawData, start_date: datetime.datetime | datetime.date = None) -> None:
        if last_data.consumption is None:
            return

        zones = {}
        if last_data.consumption.json_daily and "data" in last_data.consumption.json_daily:
            zones = last_data.consumption.json_daily["data"].get("zonesName", {})
        if not zones and last_data.consumption.json_monthly and "data" in last_data.consumption.json_monthly:
            zones = last_data.consumption.json_monthly["data"].get("zonesName", {})

        all_stat_ids = await self.prepare_stats_ids(zones)

        warsaw_tz = get_time_zone("Europe/Warsaw")
        now = datetime.datetime.now(warsaw_tz)
        yesterday = (now - datetime.timedelta(days=1)).date()
        max_history_date = (now - datetime.timedelta(days=365)).date()

        re_sync_from_time = None
        if start_date is not None:
            if isinstance(start_date, datetime.datetime):
                fetch_from = start_date.astimezone(warsaw_tz).date()
                start_date_utc = as_utc(start_date)
            else:
                fetch_from = start_date
                start_date_utc = as_utc(datetime.datetime.combine(start_date, datetime.time(0, 0), tzinfo=warsaw_tz))
            re_sync_from_time = start_date_utc
            _LOGGER.info(f"[{self.meter_id}] Manual statistics update requested from {fetch_from}")
            for d in [fetch_from + datetime.timedelta(days=x) for x in range((yesterday - fetch_from).days + 1)]:
                await self._safe_delete_cache_day(d)
        else:
            has_all_stats = all(v["last_stats_time"] is not None for v in all_stat_ids.values())
            if has_all_stats:
                min_last_time = min(v["last_stats_time"] for v in all_stat_ids.values())
                min_last_date = min_last_time.astimezone(warsaw_tz).date()
                _LOGGER.info(
                    f"[{self.meter_id}] Checking long-term statistics in Recorder: "
                    f"last recorded timestamp is {min_last_time}"
                )
                check_start = max(min_last_date - datetime.timedelta(days=7), max_history_date)
                primary_stat_id = self.get_stats_id(CONST_CONSUMPTION)
                earliest_incomplete = await self.find_earliest_incomplete_day(
                    primary_stat_id, check_start, yesterday
                )
                if earliest_incomplete is not None:
                    fetch_from = earliest_incomplete
                    re_sync_from_time = as_utc(
                        datetime.datetime.combine(earliest_incomplete, datetime.time(0, 0), tzinfo=warsaw_tz)
                    )
                    _LOGGER.info(
                        f"[{self.meter_id}] Re-syncing and healing statistics starting from {fetch_from}"
                    )
                    for d in [fetch_from + datetime.timedelta(days=x) for x in range((yesterday - fetch_from).days + 1)]:
                        await self._safe_delete_cache_day(d)
                else:
                    fetch_from = min_last_date - datetime.timedelta(days=1)
            else:
                # First run or missing stats: fetch default range (30 days back)
                fetch_from = (now - datetime.timedelta(days=30)).date()
                _LOGGER.info(
                    f"[{self.meter_id}] Checking long-term statistics in Recorder: "
                    f"initial sync for range {fetch_from} to {yesterday}"
                )

        # Guard against excessively old query ranges
        if fetch_from < max_history_date:
            fetch_from = max_history_date

        fetch_to = yesterday
        if fetch_from > fetch_to:
            _LOGGER.info(f"[{self.meter_id}] Statistics are already up to date up to yesterday ({fetch_to}).")
            return

        self.log(f"Fetching raw daily energy data for range: {fetch_from} to {fetch_to}")

        data_consumption = await self.connector.get_raw_values_daily_for_range(
            fetch_from, fetch_to, False, only_complete_days=True
        )
        if data_consumption is None or not data_consumption.get("data", {}).get("allData"):
            _LOGGER.info(f"[{self.meter_id}] No new consumption data available from Tauron for range {fetch_from} to {fetch_to}")
            return

        raw_data = {CONST_CONSUMPTION: data_consumption["data"]["allData"]}

        if self.show_generation or self.show_balanced:
            data_generation = await self.connector.get_raw_values_daily_for_range(
                fetch_from, fetch_to, True, only_complete_days=True
            )
            if data_generation is not None and data_generation.get("data", {}).get("allData"):
                raw_data[CONST_GENERATION] = data_generation["data"]["allData"]
            else:
                raw_data[CONST_GENERATION] = []

        if self.show_balanced:
            balanced_consumption, balanced_generation = self.prepare_balanced_raw_data(raw_data)
            raw_data[f"{CONST_BALANCED}_{CONST_CONSUMPTION}"] = balanced_consumption
            raw_data[f"{CONST_BALANCED}_{CONST_GENERATION}"] = balanced_generation

        total_inserted = 0
        for s, v in all_stat_ids.items():
            if v["data_source"] not in raw_data:
                continue
            if re_sync_from_time is not None:
                initial_sum, last_stats_time = await self.get_stat_before(
                    s, re_sync_from_time, v.get("last_stat_row")
                )
            else:
                initial_sum = v["sum"]
                last_stats_time = v["last_stats_time"]

            count = await self.update_stats(
                s,
                v["name"],
                initial_sum,
                last_stats_time,
                v["zone"],
                raw_data[v["data_source"]],
            )
            total_inserted += count

        if total_inserted > 0:
            _LOGGER.info(
                f"[{self.meter_id}] Successfully imported statistics into Energy Dashboard "
                f"for range {fetch_from} to {fetch_to} ({total_inserted} records across {len(all_stat_ids)} series)"
            )
        else:
            _LOGGER.info(
                f"[{self.meter_id}] Statistics are already up to date. Tauron has not published new hourly data yet."
            )

    async def prepare_stats_ids(self, zones):
        suffixes = [{
            "id": CONST_CONSUMPTION,
            "name": CONST_CONSUMPTION,
            "data": CONST_CONSUMPTION,
            "zone": None
        }]
        if self.show_generation:
            suffixes.append({
                "id": CONST_GENERATION,
                "name": CONST_GENERATION,
                "data": CONST_GENERATION,
                "zone": None
            })
        if self.show_balanced:
            suffixes.append({
                "id": f"{CONST_BALANCED}_{CONST_CONSUMPTION}",
                "name": f"{CONST_BALANCED} {CONST_CONSUMPTION}",
                "data": f"{CONST_BALANCED}_{CONST_CONSUMPTION}",
                "zone": None
            })
            suffixes.append({
                "id": f"{CONST_BALANCED}_{CONST_GENERATION}",
                "name": f"{CONST_BALANCED} {CONST_GENERATION}",
                "data": f"{CONST_BALANCED}_{CONST_GENERATION}",
                "zone": None
            })
        if len(zones) > 1:
            for s in [*suffixes]:
                suffixes.extend([
                    {
                        "id": f'{s["id"]}_zone_{zone}',
                        "name": f'{s["name"]} {zone_name}',
                        "data": s["data"],
                        "zone": zone
                    }
                    for zone, zone_name in zones.items()
                ])

        all_stat_ids = {
            self.get_stats_id(s["id"]): {
                "name": self.get_stats_name(s["name"]),
                "zone": s["zone"],
                "data_source": s["data"],
                "sum": 0.0,
                "last_stats_time": None,
                "last_stats_end": None
            }
            for s in suffixes
        }
        for k, v in all_stat_ids.items():
            last_stat = await self.get_last_stats(k)
            if k in last_stat and len(last_stat[k]) > 0:
                row = last_stat[k][0]
                v["last_stat_row"] = row
                v["sum"] = float(row.get("sum", 0.0) or 0.0)
                start = row.get("start")
                if isinstance(start, (int, float)):
                    start = utc_from_timestamp(start)
                elif isinstance(start, datetime.datetime) and start.tzinfo is None:
                    start = as_utc(start)
                v["last_stats_time"] = start

                end = row.get("end")
                if isinstance(end, (int, float)):
                    end = utc_from_timestamp(end)
                elif isinstance(end, datetime.datetime) and end.tzinfo is None:
                    end = as_utc(end)
                v["last_stats_end"] = end

        return all_stat_ids

    def get_stats_id(self, suffix):
        return f"{STATISTICS_DOMAIN}:{self.meter_id}_{suffix}".lower()

    def get_stats_name(self, suffix):
        return f"{DEFAULT_NAME} {self.meter_name} {suffix}"

    @staticmethod
    def are_stats_up_to_date(last_stats_end):
        if last_stats_end is None:
            return False
        now = datetime.datetime.now()
        return (as_utc(now) - last_stats_end).days < 30

    @staticmethod
    def prepare_balanced_raw_data(raw_data) -> (list, list):
        consumption_data = raw_data.get(CONST_CONSUMPTION, [])
        generation_data = raw_data.get(CONST_GENERATION, [])
        if not consumption_data or not generation_data:
            return [], []

        gen_by_time = {(g["Date"], g["Hour"]): g for g in generation_data}

        balanced_consumption = []
        balanced_generation = []

        for consumption in consumption_data:
            key = (consumption["Date"], consumption["Hour"])
            if key not in gen_by_time:
                continue
            generation = gen_by_time[key]
            value_consumption = float(consumption["EC"])
            value_generation = float(generation["EC"])
            balance = value_consumption - value_generation
            if balance > 0:
                output_consumption = {
                    "EC": f"{balance}",
                    "Date": consumption["Date"],
                    "Hour": consumption["Hour"],
                    "Zone": consumption["Zone"],
                }
                output_generation = {
                    "EC": "0",
                    "Date": generation["Date"],
                    "Hour": generation["Hour"],
                    "Zone": generation["Zone"],
                }
            else:
                output_consumption = {
                    "EC": "0",
                    "Date": consumption["Date"],
                    "Hour": consumption["Hour"],
                    "Zone": consumption["Zone"],
                }
                output_generation = {
                    "EC": f"{-balance}",
                    "Date": generation["Date"],
                    "Hour": generation["Hour"],
                    "Zone": generation["Zone"],
                }
            balanced_consumption.append(output_consumption)
            balanced_generation.append(output_generation)

        return balanced_consumption, balanced_generation

    async def update_stats(self, statistic_id, statistic_name, initial_sum, last_stats_time, zone_id, raw_data):
        current_sum = initial_sum
        metadata: StatisticMetaData = {
            "has_mean": False,
            "has_sum": True,
            "name": statistic_name,
            "source": STATISTICS_DOMAIN,
            "statistic_id": statistic_id,
            "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
            "mean_type": StatisticMeanType.NONE,
            "unit_class": "energy",
        }
        statistic_data = []
        for raw_hour in raw_data:
            start = self.get_time(raw_hour)
            if last_stats_time is not None and start <= last_stats_time:
                continue
            usage = float(raw_hour["EC"])
            if zone_id is not None and raw_hour["Zone"] != zone_id:
                usage = 0.0
            current_sum += usage
            stats = {
                "start": start,
                "state": usage,
                "sum": current_sum,
            }
            statistic_data.append(stats)

        if statistic_data:
            async_add_external_statistics(self.hass, metadata, statistic_data)
            self.log(f"Added {len(statistic_data)} new entries for statistic: {statistic_id}")
            return len(statistic_data)
        else:
            self.log(f"No new entries to update for statistic: {statistic_id}")
            return 0

    async def get_last_stats_date(self, statistic_id):
        last_stats = await self.get_last_stats(statistic_id)
        if statistic_id in last_stats and len(last_stats[statistic_id]) > 0:
            end = last_stats[statistic_id][0]["end"]
            if isinstance(end, (int, float)):
                end = utc_from_timestamp(end)
            elif isinstance(end, datetime.datetime) and end.tzinfo is None:
                end = as_utc(end)
            return end
        return None

    async def get_last_stats(self, statistic_id):
        return await get_instance(self.hass).async_add_executor_job(
            get_last_statistics,
            self.hass, 1, statistic_id, True, {"state", "sum"})

    async def get_stats(self, raw_data, statistic_id):
        return await get_instance(self.hass).async_add_executor_job(
            statistics_during_period,
            self.hass, self.get_time(raw_data[0]), None, [statistic_id], "hour", None, {"state", "sum"})

    async def get_stat_before(
        self, statistic_id: str, before_time: datetime.datetime, last_stat_row: dict | None
    ) -> tuple[float, datetime.datetime | None]:
        if last_stat_row is not None:
            last_start = self._get_row_start(last_stat_row)
            if last_start is not None and last_start < before_time:
                last_sum = float(last_stat_row.get("sum", 0.0) or 0.0)
                return last_sum, last_start

        start_search = before_time - datetime.timedelta(days=30)
        try:
            stats = await get_instance(self.hass).async_add_executor_job(
                statistics_during_period,
                self.hass,
                start_search,
                before_time,
                {statistic_id},
                "hour",
                None,
                {"sum", "state"},
            )
            if stats and statistic_id in stats and len(stats[statistic_id]) > 0:
                rows = [r for r in stats[statistic_id] if self._get_row_start(r) < before_time]
                if rows:
                    last_row = rows[-1]
                    row_sum = float(last_row.get("sum", 0.0) or 0.0)
                    row_start = self._get_row_start(last_row)
                    return row_sum, row_start
        except Exception as e:
            _LOGGER.warning(f"Failed to query statistics before {before_time} for {statistic_id}: {e}")

        return 0.0, None

    async def find_earliest_incomplete_day(
        self, statistic_id: str, start_date: datetime.date, end_date: datetime.date
    ) -> datetime.date | None:
        """Find the earliest day in [start_date, end_date] with partial/incomplete hours in Recorder."""
        warsaw_tz = get_time_zone("Europe/Warsaw")
        start_utc = as_utc(datetime.datetime.combine(start_date, datetime.time(0, 0), tzinfo=warsaw_tz))
        expected_end_hours = TauronAmiplusConnector.get_expected_hours_for_day(end_date)
        end_utc = as_utc(datetime.datetime.combine(end_date, datetime.time(0, 0), tzinfo=warsaw_tz)) + datetime.timedelta(hours=expected_end_hours)

        try:
            stats = await get_instance(self.hass).async_add_executor_job(
                statistics_during_period,
                self.hass,
                start_utc,
                end_utc,
                {statistic_id},
                "hour",
                None,
                {"state", "sum"},
            )
            if not stats or statistic_id not in stats:
                return None

            records_by_date = collections.defaultdict(int)
            prev_sum = None
            inconsistent_dates = set()
            for r in stats[statistic_id]:
                row_start = self._get_row_start(r)
                if row_start is not None and start_utc <= row_start < end_utc:
                    row_date = row_start.astimezone(warsaw_tz).date()
                    records_by_date[row_date] += 1
                    row_sum = r.get("sum")
                    if row_sum is not None and prev_sum is not None and row_sum < prev_sum - 1e-4:
                        inconsistent_dates.add(row_date)
                    if row_sum is not None:
                        prev_sum = row_sum

            curr = start_date
            while curr <= end_date:
                expected = TauronAmiplusConnector.get_expected_hours_for_day(curr)
                actual = records_by_date.get(curr, 0)
                if curr in inconsistent_dates:
                    _LOGGER.info(
                        f"[{self.meter_id}] Detected inconsistent/decreasing sum in Recorder on {curr}. "
                        f"Triggering self-healing from this date."
                    )
                    return curr
                if 0 < actual < expected:
                    _LOGGER.info(
                        f"[{self.meter_id}] Detected incomplete day in Recorder for {curr}: "
                        f"{actual}/{expected} hours recorded. Triggering self-healing from this date."
                    )
                    return curr
                curr += datetime.timedelta(days=1)
        except Exception as e:
            _LOGGER.debug(f"Failed to check for incomplete days in Recorder: {e}")

        return None

    async def get_stats_count_in_range(
        self, statistic_id: str, start_time: datetime.datetime, end_time: datetime.datetime
    ) -> int:
        try:
            stats = await get_instance(self.hass).async_add_executor_job(
                statistics_during_period,
                self.hass,
                start_time,
                end_time,
                {statistic_id},
                "hour",
                None,
                {"state"},
            )
            if stats and statistic_id in stats:
                rows = [
                    r for r in stats[statistic_id]
                    if start_time <= self._get_row_start(r) < end_time
                ]
                return len(rows)
        except Exception as e:
            _LOGGER.debug(f"Failed to query stats count in range: {e}")
        return 0

    @staticmethod
    def _get_row_start(row: dict) -> datetime.datetime | None:
        start = row.get("start")
        if isinstance(start, (int, float)):
            return utc_from_timestamp(start)
        if isinstance(start, datetime.datetime) and start.tzinfo is None:
            return as_utc(start)
        return start

    def log(self, msg):
        _LOGGER.debug(f"[{self.meter_id}]: {msg}")

    @staticmethod
    def get_time(raw_hour):
        zone = get_time_zone("Europe/Warsaw")
        date_str = raw_hour["Date"]
        hour = int(raw_hour["Hour"]) - 1
        day_date = datetime.date.fromisoformat(date_str)
        day_start_local = datetime.datetime.combine(day_date, datetime.time(0, 0), tzinfo=zone)
        day_start_utc = as_utc(day_start_local)
        return day_start_utc + datetime.timedelta(hours=hour)
