import datetime
import logging

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import StatisticMetaData
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

    @staticmethod
    async def manually_update(hass, start_date: datetime.date, entry):
        username = entry.data[CONF_USERNAME]
        password = entry.data[CONF_PASSWORD]
        meter_id = entry.data[CONF_METER_ID]
        meter_name = entry.data[CONF_METER_NAME]

        show_generation = entry.options.get(CONF_SHOW_GENERATION, False)
        show_balanced = entry.options.get(CONF_SHOW_BALANCED, False)

        connector = TauronAmiplusConnector(username, password, meter_id, show_generation=show_generation,
                                           show_balanced=show_balanced)
        statistics_updater = TauronAmiplusStatisticsUpdater(hass, connector, meter_id, meter_name, show_generation, show_balanced)

        data = await hass.async_add_executor_job(connector.get_raw_data)
        start_date = datetime.datetime.combine(start_date,
                                               datetime.time(tzinfo=datetime.datetime.now().astimezone().tzinfo))
        if data is not None:
            await statistics_updater.update_all(data, start_date)

    async def update_all(self, last_data: TauronAmiplusRawData, start_date: datetime.datetime = None) -> None:
        if last_data.consumption is None or last_data.consumption.json_last_30_days_hourly is None:
            return
        raw_data = {CONST_CONSUMPTION: last_data.consumption.json_last_30_days_hourly["data"]["allData"]}
        zones = last_data.consumption.json_last_30_days_hourly["data"]["zonesName"]
        if self.show_generation or self.show_balanced:
            if last_data.generation is None or last_data.generation.json_last_30_days_hourly is None:
                return
            raw_data[CONST_GENERATION] = last_data.generation.json_last_30_days_hourly["data"]["allData"]

        all_stat_ids = await self.prepare_stats_ids(zones)

        if (start_date is not None
                or not all([self.are_stats_up_to_date(v["last_stats_end"]) for v in all_stat_ids.values()])):
            now = datetime.datetime.now()
            if start_date is None:
                start_range = (now - datetime.timedelta(365)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            else:
                start_range = start_date.replace(tzinfo=None)
            data_consumption = await self.hass.async_add_executor_job(self.connector.get_raw_values_daily_for_range,
                                                                      start_range, now, False)
            if data_consumption is not None:
                raw_data[CONST_CONSUMPTION] = data_consumption["data"]["allData"]
            if self.show_generation or self.show_balanced:
                data_generation = await self.hass.async_add_executor_job(self.connector.get_raw_values_daily_for_range,
                                                                         start_range, now, True)
                if data_generation is not None:
                    raw_data[CONST_GENERATION] = data_generation["data"]["allData"]

        if self.show_balanced:
            balanced_consumption, balanced_generation = self.prepare_balanced_raw_data(raw_data)
            raw_data[f"{CONST_BALANCED}_{CONST_CONSUMPTION}"] = balanced_consumption
            raw_data[f"{CONST_BALANCED}_{CONST_GENERATION}"] = balanced_generation

        for s, v in all_stat_ids.items():
            if v["last_stats_end"] is not None:
                stat = await self.get_stats(raw_data[v["data_source"]], s)
                v["sum"] = stat[s][0]["sum"]
                start = stat[s][0]["start"]
                if isinstance(start, float):
                    start = utc_from_timestamp(start)
                if start_date is not None and start > start_date:
                    start = None
                    v["sum"] = 0
                v["last_stats_time"] = start

        for s, v in all_stat_ids.items():
            await self.update_stats(s, v["name"], v["sum"], v["last_stats_time"], v["zone"], raw_data[v["data_source"]])

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
                "sum": 0,
                "last_stats_time": None,
                "last_stats_end": None
            }
            for s in suffixes
        }
        for k, v in all_stat_ids.items():
            v["last_stats_end"] = await self.get_last_stats_date(k)
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
    def prepare_balanced_raw_data(raw_data) -> (dict, dict):
        consumption_data = raw_data[CONST_CONSUMPTION]
        generation_data = raw_data[CONST_GENERATION]
        if len(consumption_data) != len(generation_data):
            return {}, {}
        balanced_consumption = []
        balanced_generation = []

        for consumption, generation in zip(consumption_data, generation_data):
            value_consumption = float(consumption["EC"])
            value_generation = float(generation["EC"])
            balance = value_consumption - value_generation
            if balance > 0:
                output_consumption = {
                    "EC": f'{balance}',
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
                    "EC": f'{-balance}',
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
            "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR
        }
        statistic_data = []
        for raw_hour in raw_data:
            start = self.get_time(raw_hour)
            if last_stats_time is not None and start <= last_stats_time:
                continue
            usage = float(raw_hour["EC"])
            if zone_id is not None and raw_hour["Zone"] != zone_id:
                usage = 0
            current_sum += usage
            stats = {
                "start": start,
                "state": usage,
                "sum": current_sum
            }
            statistic_data.append(stats)
        async_add_external_statistics(self.hass, metadata, statistic_data)
        self.log(f"Updated {len(statistic_data)} entries for statistic: {statistic_id} ")

    async def get_last_stats_date(self, statistic_id):
        last_stats = await self.get_last_stats(statistic_id)
        if statistic_id in last_stats and len(last_stats[statistic_id]) > 0:
            end = last_stats[statistic_id][0]["end"]
            if isinstance(end, float):
                end = utc_from_timestamp(end)
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

    def log(self, msg):
        _LOGGER.debug(f"[{self.meter_id}]: {msg}")

    @staticmethod
    def get_time(raw_hour):
        zone = get_time_zone("Europe/Warsaw")
        date = raw_hour["Date"]
        hour = int(raw_hour["Hour"]) - 1
        return datetime.datetime.strptime(f"{date} {hour}:00", "%Y-%m-%d %H:%M").replace(tzinfo=zone)
