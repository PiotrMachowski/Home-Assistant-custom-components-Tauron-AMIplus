"""Config flow to configure TAURON component."""

import logging
import re

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.selector import selector

from .connector import TauronAmiplusConnector
from .const import (CONF_METER_ID, CONF_METER_NAME, CONF_SHOW_12_MONTHS, CONF_SHOW_BALANCED, CONF_SHOW_BALANCED_YEAR,
                    CONF_SHOW_CONFIGURABLE, CONF_SHOW_CONFIGURABLE_DATE, CONF_SHOW_GENERATION, CONF_STORE_STATISTICS,
                    CONF_TARIFF, DOMAIN)

_LOGGER = logging.getLogger(__name__)


class TauronAmiplusFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """TAURON config flow."""

    VERSION = 3

    def __init__(self):
        """Initialize TAURON configuration flow."""
        self._username = None
        self._password = None
        self._meters = []
        self._tariff = None
        self._meter_id = None

    async def async_step_import(self, import_config):
        # pass
        return self.async_abort(reason="single_instance_allowed")

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if user_input is not None:
            return await self.async_step_init(user_input=None)
        return self.async_show_form(step_id="confirm")

    async def async_step_confirm(self, user_input=None):
        """Handle a flow start."""
        errors = {}
        if user_input is not None:
            return await self.async_step_init(user_input=None)
        return self.async_show_form(step_id="confirm", errors=errors)

    async def async_step_init(self, user_input=None):
        """Handle a flow start."""
        errors = {}
        description_placeholders = {"error_info": ""}
        if user_input is not None:
            if len(errors) == 0:
                try:
                    self._meters = []
                    calculated = await self.hass.async_add_executor_job(
                        TauronAmiplusConnector.get_available_meters, user_input[CONF_USERNAME],
                        user_input[CONF_PASSWORD])
                    if calculated is not None:
                        self._username = user_input[CONF_USERNAME]
                        self._password = user_input[CONF_PASSWORD]
                        self._meters = calculated
                    if len(self._meters) > 0:
                        return await self.async_step_select_meter()
                    errors = {CONF_PASSWORD: "server_no_connection"}
                    description_placeholders = {"error_info": str(calculated)}
                except Exception as e:
                    errors = {CONF_PASSWORD: "server_no_connection"}
                    description_placeholders = {"error_info": str(e)}
                    _LOGGER.error(str(e))

            return self.async_show_form(
                step_id="init",
                data_schema=self.get_schema_init(user_input),
                errors=errors,
                description_placeholders=description_placeholders,
            )

        return self.async_show_form(
            step_id="init",
            data_schema=self.get_schema_init(),
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def async_step_select_meter(self, user_input=None):
        """Handle a flow start."""
        errors = {}
        description_placeholders = {"error_info": ""}
        if user_input is not None:
            if not re.fullmatch(r"[a-zA-Z0-9_]+", user_input[CONF_METER_ID]):
                errors[CONF_METER_ID] = "invalid_meter_id"

            if len(errors) == 0:
                try:
                    tariff = await self.hass.async_add_executor_job(
                        TauronAmiplusConnector.calculate_tariff, self._username, self._password,
                        user_input[CONF_METER_ID])
                    if tariff is not None:
                        self._meter_id = user_input[CONF_METER_ID]
                        self._tariff = tariff
                        return await self.async_step_config_options()
                    errors = {CONF_METER_ID: "server_no_connection"}
                    description_placeholders = {"error_info": str(tariff)}
                except Exception as e:
                    errors = {CONF_PASSWORD: "server_no_connection"}
                    description_placeholders = {"error_info": str(e)}
                    _LOGGER.error(str(e))

            return self.async_show_form(
                step_id="select_meter",
                data_schema=self.get_schema_select_meter(user_input),
                errors=errors,
                description_placeholders=description_placeholders,
            )

        return self.async_show_form(
            step_id="select_meter",
            data_schema=self.get_schema_select_meter(),
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def async_step_config_options(self, user_input=None):
        """Handle a flow start."""
        errors = {}
        description_placeholders = {"error_info": ""}
        selected_meter_name = list(filter(lambda m: m["meter_id"] == self._meter_id, self._meters))
        if user_input is not None:
            if (user_input.get(CONF_SHOW_CONFIGURABLE, False) is True and
                    user_input.get(CONF_SHOW_CONFIGURABLE_DATE, None) is None):
                errors[CONF_SHOW_CONFIGURABLE_DATE] = "missing_configurable_start_date"

            if len(errors) == 0 and len(selected_meter_name) == 1:
                data = {
                    CONF_USERNAME: self._username,
                    CONF_PASSWORD: self._password,
                    CONF_METER_ID: self._meter_id,
                    CONF_TARIFF: self._tariff,
                    CONF_METER_NAME: user_input.get(CONF_METER_NAME, selected_meter_name[0]["meter_name"].split(" ")[0])
                }
                options = {
                    CONF_SHOW_GENERATION: user_input.get(CONF_SHOW_GENERATION, False),
                    CONF_SHOW_12_MONTHS: user_input.get(CONF_SHOW_12_MONTHS, False),
                    CONF_SHOW_BALANCED: user_input.get(CONF_SHOW_BALANCED, False),
                    CONF_SHOW_BALANCED_YEAR: user_input.get(CONF_SHOW_BALANCED_YEAR, False),
                    CONF_SHOW_CONFIGURABLE: user_input.get(CONF_SHOW_CONFIGURABLE, False),
                    CONF_SHOW_CONFIGURABLE_DATE: user_input.get(CONF_SHOW_CONFIGURABLE_DATE, None),
                    CONF_STORE_STATISTICS: user_input.get(CONF_STORE_STATISTICS, True),
                }

                """Finish config flow"""
                return self.async_create_entry(title=f"eLicznik {user_input[CONF_METER_NAME]}", data=data,
                                               options=options)

            return self.async_show_form(
                step_id="config_options",
                data_schema=self.get_schema_config_options(user_input),
                errors=errors,
                description_placeholders=description_placeholders,
                last_step=True
            )

        return self.async_show_form(
            step_id="config_options",
            data_schema=self.get_schema_config_options(),
            errors=errors,
            description_placeholders=description_placeholders,
        )

    @staticmethod
    def get_schema_init(user_input=None):
        if user_input is None:
            user_input = {}
        data_schema = vol.Schema({
            vol.Required(CONF_USERNAME,
                         default=user_input.get(CONF_USERNAME, vol.UNDEFINED)): str,
            vol.Required(CONF_PASSWORD,
                         default=user_input.get(CONF_PASSWORD, vol.UNDEFINED)): str,
        })
        return data_schema

    def get_schema_select_meter(self, user_input=None):
        if user_input is None:
            user_input = {}
        meter_options = list(
            map(lambda m: {"label": f"({m['meter_type']}) {m['meter_name']}", "value": m["meter_id"]}, self._meters))
        data_schema = vol.Schema({
            vol.Required(CONF_METER_ID,
                         default=user_input.get(CONF_METER_ID, vol.UNDEFINED)): selector(
                {"select": {"options": meter_options}}),
        })
        return data_schema

    def get_schema_config_options(self, user_input=None):
        if user_input is None:
            user_input = {}
        selected_meter_name = next(
            filter(lambda m: m["meter_id"] == self._meter_id, self._meters))["meter_name"].split(" ")[0]
        data_schema = vol.Schema({
            vol.Required(CONF_METER_NAME,
                         default=user_input.get(CONF_METER_NAME, selected_meter_name)): str,
            vol.Required(CONF_SHOW_GENERATION,
                         default=user_input.get(CONF_SHOW_GENERATION, vol.UNDEFINED)): bool,
            vol.Required(CONF_SHOW_12_MONTHS,
                         default=user_input.get(CONF_SHOW_12_MONTHS, vol.UNDEFINED)): bool,
            vol.Required(CONF_SHOW_BALANCED,
                         default=user_input.get(CONF_SHOW_BALANCED, vol.UNDEFINED)): bool,
            vol.Required(CONF_SHOW_BALANCED_YEAR,
                         default=user_input.get(CONF_SHOW_BALANCED_YEAR, vol.UNDEFINED)): bool,
            vol.Required(CONF_SHOW_CONFIGURABLE,
                         default=user_input.get(CONF_SHOW_CONFIGURABLE, vol.UNDEFINED)): bool,
            vol.Optional(CONF_SHOW_CONFIGURABLE_DATE,
                         default=user_input.get(CONF_SHOW_CONFIGURABLE_DATE, vol.UNDEFINED)): selector({"date": {}}),
            vol.Required(CONF_STORE_STATISTICS,
                         default=user_input.get(CONF_STORE_STATISTICS, True)): bool,
        })
        return data_schema

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return TauronAmiplusOptionsFlowHandler(config_entry)


class TauronAmiplusOptionsFlowHandler(config_entries.OptionsFlow):
    """Tauron Amiplus config flow options handler."""

    def __init__(self, config_entry):
        """Initialize HACS options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)

    async def async_step_init(self, user_input=None):  # pylint: disable=unused-argument
        """Manage the options."""
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            if (user_input.get(CONF_SHOW_CONFIGURABLE, False) is True and
                    user_input.get(CONF_SHOW_CONFIGURABLE_DATE, None) is None):
                errors[CONF_SHOW_CONFIGURABLE_DATE] = "missing_configurable_start_date"
            if len(errors) == 0:
                self.options.update(user_input)
                output = await self._update_options()
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)
                return output

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SHOW_GENERATION,
                                 default=self.get_option(CONF_SHOW_GENERATION, False)
                                 ): bool,
                    vol.Required(CONF_SHOW_12_MONTHS,
                                 default=self.get_option(CONF_SHOW_12_MONTHS, False)
                                 ): bool,
                    vol.Required(CONF_SHOW_BALANCED,
                                 default=self.get_option(CONF_SHOW_BALANCED, False)
                                 ): bool,
                    vol.Required(CONF_SHOW_BALANCED_YEAR,
                                 default=self.get_option(CONF_SHOW_BALANCED_YEAR, False)
                                 ): bool,
                    vol.Required(CONF_SHOW_CONFIGURABLE,
                                 default=self.get_option(CONF_SHOW_CONFIGURABLE, False)
                                 ): bool,
                    vol.Optional(CONF_SHOW_CONFIGURABLE_DATE,
                                 default=self.get_option(CONF_SHOW_CONFIGURABLE_DATE, vol.UNDEFINED)
                                 ): selector({"date": {}}),
                    vol.Required(CONF_STORE_STATISTICS,
                                 default=self.get_option(CONF_STORE_STATISTICS, True)
                                 ): bool,
                }
            ),
            errors=errors
        )

    def get_option(self, key, default):
        return self.options.get(key, default) if self.options.get(key, default) is not None else default

    async def _update_options(self):
        """Update config entry options."""
        return self.async_create_entry(
            title=self.config_entry.data.get(CONF_USERNAME), data=self.options
        )
