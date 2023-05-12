from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .connector import TauronAmiplusConnector
from .const import (CONF_METER_ID, CONF_SHOW_12_MONTHS, CONF_SHOW_BALANCED, CONF_SHOW_BALANCED_YEAR,
                    CONF_SHOW_CONFIGURABLE, CONF_SHOW_CONFIGURABLE_DATE, CONF_SHOW_GENERATION, CONF_STORE_STATISTICS,
                    CONF_TARIFF)


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    return await hass.async_add_executor_job(get_config_entry_diagnostics, entry)


def get_config_entry_diagnostics(entry: ConfigEntry) -> dict[str, Any]:
    user = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    meter_id = entry.data[CONF_METER_ID]
    tariff = entry.data[CONF_TARIFF]
    show_generation_sensors = entry.options.get(CONF_SHOW_GENERATION, False)
    show_12_months = entry.options.get(CONF_SHOW_12_MONTHS, False)
    show_balanced = entry.options.get(CONF_SHOW_BALANCED, False)
    show_balanced_year = entry.options.get(CONF_SHOW_BALANCED_YEAR, False)
    show_configurable = entry.options.get(CONF_SHOW_CONFIGURABLE, False)
    show_configurable_date = entry.options.get(CONF_SHOW_CONFIGURABLE_DATE, False)
    store_statistics = entry.options.get(CONF_STORE_STATISTICS, False)

    connector = TauronAmiplusConnector(user, password, meter_id,
                                       show_generation=show_generation_sensors,
                                       show_balanced=show_balanced)
    raw_data = connector.get_raw_data()

    return {
        "tariff": tariff,
        "show_generation_sensors": show_generation_sensors,
        "show_12_months": show_12_months,
        "show_balanced": show_balanced,
        "show_balanced_year": show_balanced_year,
        "show_configurable": show_configurable,
        "show_configurable_date": show_configurable_date,
        "store_statistics": store_statistics,
        "raw_data_tariff": raw_data.tariff,
        "raw_data_consumption": {
            "json_reading": raw_data.consumption.json_reading,
            "json_daily": raw_data.consumption.json_daily,
            "daily_date": raw_data.consumption.daily_date,
            "json_monthly": raw_data.consumption.json_monthly,
            "json_yearly": raw_data.consumption.json_yearly,
            "json_month_hourly": raw_data.consumption.json_month_hourly,
            "json_last_30_days_hourly": raw_data.consumption.json_last_30_days_hourly,
        },
        "raw_data_generation": {
            "json_reading": raw_data.generation.json_reading,
            "json_daily": raw_data.generation.json_daily,
            "daily_date": raw_data.generation.daily_date,
            "json_monthly": raw_data.generation.json_monthly,
            "json_yearly": raw_data.generation.json_yearly,
            "json_month_hourly": raw_data.generation.json_month_hourly,
            "json_last_30_days_hourly": raw_data.generation.json_last_30_days_hourly,
        }
    }
