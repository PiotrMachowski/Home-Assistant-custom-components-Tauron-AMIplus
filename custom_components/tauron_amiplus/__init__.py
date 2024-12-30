"""Support for Tauron sensors."""
import datetime
import logging

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.config_entries import ConfigEntry, SOURCE_IMPORT
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import DATE_STR_FORMAT

from .const import (
    CONF_METER_ID, CONF_METER_NAME, CONF_SHOW_12_MONTHS, CONF_SHOW_BALANCED, CONF_SHOW_BALANCED_YEAR,
    CONF_SHOW_CONFIGURABLE, CONF_SHOW_CONFIGURABLE_DATE, CONF_SHOW_GENERATION, CONF_STORE_STATISTICS, CONF_TARIFF,
    DOMAIN, PLATFORMS,
)
from .services import DownloadStatisticsService

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = datetime.timedelta(seconds=600)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_METER_ID): cv.string,
        vol.Required(CONF_TARIFF): cv.string,
    }
)


async def async_setup(hass, config):
    """Set up the TAURON component."""
    hass.data[DOMAIN] = {}

    if not hass.config_entries.async_entries(DOMAIN) and DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=config[DOMAIN]
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Set up TAURON as config entry."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    config_entry.async_on_unload(config_entry.add_update_listener(async_reload_entry))
    service = DownloadStatisticsService(hass)
    hass.services.async_register(service.domain, service.service, service.async_handle_service, service.schema)
    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
    return True


async def async_reload_entry(hass, entry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


async def async_migrate_entry(hass, config_entry: ConfigEntry):
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version == 1:
        data = {
            CONF_USERNAME: config_entry.data[CONF_USERNAME],
            CONF_PASSWORD: config_entry.data[CONF_PASSWORD],
            CONF_METER_ID: config_entry.data[CONF_METER_ID],
            CONF_TARIFF: config_entry.data[CONF_TARIFF],
        }
        options = {
            CONF_SHOW_GENERATION: config_entry.data[CONF_SHOW_GENERATION],
            CONF_SHOW_BALANCED: False,
            CONF_SHOW_12_MONTHS: False,
            CONF_SHOW_CONFIGURABLE: False,
            CONF_SHOW_CONFIGURABLE_DATE: datetime.date.today().strftime(DATE_STR_FORMAT),
        }
        config_entry.version = 2
        hass.config_entries.async_update_entry(config_entry, data=data, options=options)

    if config_entry.version == 2:
        data = {
            CONF_USERNAME: config_entry.data[CONF_USERNAME],
            CONF_PASSWORD: config_entry.data[CONF_PASSWORD],
            CONF_METER_ID: config_entry.data[CONF_METER_ID],
            CONF_TARIFF: config_entry.data[CONF_TARIFF],
            CONF_METER_NAME: config_entry.data[CONF_METER_ID],
        }
        options = {
            CONF_SHOW_GENERATION: config_entry.options[CONF_SHOW_GENERATION],
            CONF_SHOW_BALANCED: config_entry.options[CONF_SHOW_BALANCED],
            CONF_SHOW_BALANCED_YEAR: False,
            CONF_SHOW_12_MONTHS: config_entry.options[CONF_SHOW_12_MONTHS],
            CONF_SHOW_CONFIGURABLE: config_entry.options[CONF_SHOW_CONFIGURABLE],
            CONF_SHOW_CONFIGURABLE_DATE: config_entry.options[CONF_SHOW_CONFIGURABLE_DATE],
            CONF_STORE_STATISTICS: True,
        }
        config_entry.version = 3
        hass.config_entries.async_update_entry(config_entry, data=data, options=options)

    _LOGGER.info("Migration to version %s successful", config_entry.version)
    return True
