from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .connector import TauronAmiplusConnector
from .const import (CONF_METER_ID, CONF_SHOW_GENERATION, CONF_TARIFF)


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    return await hass.async_add_executor_job(get_config_entry_diagnostics, entry)


def get_config_entry_diagnostics(entry: ConfigEntry) -> dict[str, Any]:
    user = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    meter_id = entry.data[CONF_METER_ID]
    show_generation_sensors = entry.data[CONF_SHOW_GENERATION]
    tariff = entry.data[CONF_TARIFF]

    connector = TauronAmiplusConnector(user, password, meter_id, show_generation_sensors)
    raw_data = connector.get_raw_data()

    return {
        "tariff": tariff,
        "raw_data_json_readings": raw_data.json_readings,
        "raw_data_json_daily": raw_data.json_daily,
        "raw_data_daily_date": raw_data.daily_date,
        "raw_data_json_monthly": raw_data.json_monthly,
        "raw_data_json_yearly": raw_data.json_yearly,
        "raw_data_tariff": raw_data.tariff,
    }