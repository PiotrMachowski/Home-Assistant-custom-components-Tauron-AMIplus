import datetime
import logging

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import StatisticMetaData
from homeassistant.components.recorder.statistics import (async_add_external_statistics, get_last_statistics,
                                                          statistics_during_period)
from homeassistant.const import ENERGY_KILO_WATT_HOUR
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import get_time_zone, utc_from_timestamp

from .connector import TauronAmiplusConnector, TauronAmiplusRawData
from .const import CONST_BALANCED, CONST_CONSUMPTION, CONST_GENERATION, DEFAULT_NAME, STATISTICS_DOMAIN

_LOGGER = logging.getLogger(__name__)


class TauronAmiplusStatisticsUpdater:

    def __init__(self, hass: HomeAssistant, connector: TauronAmiplusConnector, meter_id: str, show_generation: bool,
                 show_balanced: bool) -> None:
        self.hass = hass
        self.connector = connector
        self.meter_id = meter_id
        self.show_generation = show_generation
        self.show_balanced = show_balanced

    async def update_all(self, last_data: TauronAmiplusRawData) -> None:
        if last_data.consumption is None or last_data.consumption.json_last_30_days_hourly is None:
            return
        raw_data = {CONST_CONSUMPTION: last_data.consumption.json_last_30_days_hourly["data"]["allData"]}
        zones = last_data.consumption.json_last_30_days_hourly["data"]["zonesName"]
        if self.show_generation or self.show_balanced:
            if last_data.generation is None or last_data.generation.json_last_30_days_hourly is None:
                return
            raw_data[CONST_GENERATION] = last_data.generation.json_last_30_days_hourly["data"]["allData"]

        all_stat_ids = await self.prepare_stats_ids(zones)

        if not all([v["has_stats"] for v in all_stat_ids.values()]):
            now = datetime.datetime.now()
            start_range = (now - datetime.timedelta(365)).replace(day=1)
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
            if v["has_stats"]:
                stat = await self.get_stats(raw_data[v["data_source"]], s)
                v["sum"] = stat[s][0]["sum"]
                start = stat[s][0]["start"]
                if isinstance(start, float):
                    start = utc_from_timestamp(start)
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
                "has_stats": False
            }
            for s in suffixes
        }
        for k, v in all_stat_ids.items():
            v["has_stats"] = await self.has_stats(k)
        return all_stat_ids

    def get_stats_id(self, suffix):
        return f"{STATISTICS_DOMAIN}:{self.meter_id}_{suffix}".lower()

    def get_stats_name(self, suffix):
        return f"{DEFAULT_NAME} {self.meter_id} {suffix}"

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
            "unit_of_measurement": ENERGY_KILO_WATT_HOUR
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

    async def has_stats(self, statistic_id):
        return len(await self.get_last_stats(statistic_id)) > 0

    async def get_last_stats(self, statistic_id):
        return await get_instance(self.hass).async_add_executor_job(
            get_last_statistics,
            self.hass, 1, statistic_id, True, {"state", "sum"})

    async def get_stats(self, raw_data, statistic_id):
        return await get_instance(self.hass).async_add_executor_job(
            statistics_during_period,
            self.hass, self.get_time(raw_data[0]), None, [statistic_id], "hour", None, {"state", "sum"})

    @staticmethod
    def get_time(raw_hour):
        zone = get_time_zone("Europe/Warsaw")
        date = raw_hour["Date"]
        hour = int(raw_hour["Hour"]) - 1
        return datetime.datetime.strptime(f"{date} {hour}:00", "%Y-%m-%d %H:%M").replace(tzinfo=zone)
