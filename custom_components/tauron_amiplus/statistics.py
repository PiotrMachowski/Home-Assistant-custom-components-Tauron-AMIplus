"""Support for TAURON sensors."""
import datetime
import logging

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import StatisticMetaData
from homeassistant.components.recorder.statistics import (async_add_external_statistics, get_last_statistics,
                                                          statistics_during_period)
from homeassistant.const import ENERGY_KILO_WATT_HOUR
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import get_time_zone

from .connector import TauronAmiplusConnector
from .const import CONST_CONSUMPTION, CONST_GENERATION, DEFAULT_NAME, STATISTICS_DOMAIN

_LOGGER = logging.getLogger(__name__)


async def update_statistics(hass: HomeAssistant, meter_id: str, generation: bool, json_daily: dict,
                            connector: TauronAmiplusConnector):
    raw_data = json_daily["data"]["allData"]

    data_type = CONST_GENERATION if generation else CONST_CONSUMPTION
    statistic_id = f"{STATISTICS_DOMAIN}:{meter_id}_{data_type}"
    last_stats = await get_instance(hass).async_add_executor_job(
        get_last_statistics, hass, 1, statistic_id, True, {"last_reset", "max", "mean", "min", "state", "sum"})

    if not last_stats:
        current_sum = 0
        last_stats_time = None
        now = datetime.datetime.now()
        start_range = (now - datetime.timedelta(365)).replace(day=1)
        data_year = await hass.async_add_executor_job(connector.get_raw_values_daily_for_range,
                                                      start_range, now, generation)
        if data_year is not None:
            raw_data = data_year["data"]["allData"]
    else:
        stat = await get_instance(hass).async_add_executor_job(
            statistics_during_period,
            hass, get_time(raw_data[0]), None, [statistic_id], "hour", None,
            {"last_reset", "max", "mean", "min", "state", "sum"})
        current_sum = stat[statistic_id][0]["sum"]
        last_stats_time = stat[statistic_id][0]["start"]

    metadata: StatisticMetaData = {
        "has_mean": False,
        "has_sum": True,
        "name": f"{DEFAULT_NAME} {meter_id} {data_type}",
        "source": STATISTICS_DOMAIN,
        "statistic_id": statistic_id,
        "unit_of_measurement": ENERGY_KILO_WATT_HOUR
    }
    statistic_data = []
    for raw_hour in raw_data:
        start = get_time(raw_hour)
        if last_stats_time is not None and start <= last_stats_time:
            continue
        usage = float(raw_hour["EC"])
        current_sum += usage
        stats = {
            "start": start,
            "state": usage,
            "sum": current_sum
        }
        statistic_data.append(stats)

    async_add_external_statistics(hass, metadata, statistic_data)


def get_time(raw_hour):
    zone = get_time_zone("Europe/Warsaw")
    date = raw_hour["Date"]
    hour = int(raw_hour["Hour"]) - 1
    return datetime.datetime.strptime(f"{date} {hour}:00", "%Y-%m-%d %H:%M").replace(tzinfo=zone)
