"""Config flow to configure TAURON component."""

import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.selector import selector

from .connector import TauronAmiplusConnector
from .const import (CONF_METER_ID, CONF_SHOW_12_MONTHS, CONF_SHOW_BALANCED, CONF_SHOW_CONFIGURABLE,
                    CONF_SHOW_CONFIGURABLE_DATE, CONF_SHOW_GENERATION, CONF_TARIFF, DOMAIN)

_LOGGER = logging.getLogger(__name__)


class TauronAmiplusFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """TAURON config flow."""

    VERSION = 2

    def __init__(self):
        """Initialize TAURON configuration flow."""
        pass

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
            try:
                # Test the connection
                tariff = None
                calculated = await self.hass.async_add_executor_job(
                    TauronAmiplusConnector.calculate_tariff, user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD], user_input[CONF_METER_ID])
                if calculated is not None:
                    tariff = calculated
                if tariff is not None:
                    data = {
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_METER_ID: user_input[CONF_METER_ID],
                        CONF_TARIFF: tariff
                    }
                    options = {
                        CONF_SHOW_GENERATION: user_input.get(CONF_SHOW_GENERATION, False),
                        CONF_SHOW_12_MONTHS: user_input.get(CONF_SHOW_12_MONTHS, False),
                        CONF_SHOW_BALANCED: user_input.get(CONF_SHOW_BALANCED, False),
                        CONF_SHOW_CONFIGURABLE: user_input.get(CONF_SHOW_CONFIGURABLE, False),
                        CONF_SHOW_CONFIGURABLE_DATE: user_input.get(CONF_SHOW_CONFIGURABLE_DATE, None),
                    }

                    """Finish config flow"""
                    return self.async_create_entry(title=f"eLicznik {user_input[CONF_METER_ID]}", data=data,
                                                   options=options)
                errors = {CONF_METER_ID: "server_no_connection"}
                description_placeholders = {"error_info": str(calculated)}
            except Exception as e:
                errors = {CONF_METER_ID: "server_no_connection"}
                description_placeholders = {"error_info": str(e)}
                _LOGGER.error(str(e))

        data_schema = vol.Schema({
            vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str,
            vol.Required(CONF_METER_ID): str, vol.Required(CONF_SHOW_GENERATION, default=False): bool,
            vol.Required(CONF_SHOW_12_MONTHS, default=False): bool,
            vol.Required(CONF_SHOW_BALANCED, default=False): bool,
            vol.Required(CONF_SHOW_CONFIGURABLE, default=False): bool,
            vol.Optional(CONF_SHOW_CONFIGURABLE_DATE): selector({"date": {}})
        })

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
            errors=errors,
            description_placeholders=description_placeholders,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return TauronAmiplusOptionsFlowHandler(config_entry)


class TauronAmiplusOptionsFlowHandler(config_entries.OptionsFlow):
    """Blueprint config flow options handler."""

    def __init__(self, config_entry):
        """Initialize HACS options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)

    async def async_step_init(self, user_input=None):  # pylint: disable=unused-argument
        """Manage the options."""
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if user_input is not None:
            self.options.update(user_input)
            output = await self._update_options()
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return output

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SHOW_GENERATION,
                                 default=self.options.get(CONF_SHOW_GENERATION, False)
                                 ): bool,
                    vol.Required(CONF_SHOW_12_MONTHS,
                                 default=self.options.get(CONF_SHOW_12_MONTHS, False)
                                 ): bool,
                    vol.Required(CONF_SHOW_BALANCED,
                                 default=self.options.get(CONF_SHOW_BALANCED, False)
                                 ): bool,
                    vol.Required(CONF_SHOW_CONFIGURABLE,
                                 default=self.options.get(CONF_SHOW_CONFIGURABLE, False)
                                 ): bool,
                    vol.Optional(CONF_SHOW_CONFIGURABLE_DATE,
                                 default=self.options.get(CONF_SHOW_CONFIGURABLE_DATE, None)
                                 ): selector({"date": {}})
                }
            ),
        )

    async def _update_options(self):
        """Update config entry options."""
        return self.async_create_entry(
            title=self.config_entry.data.get(CONF_USERNAME), data=self.options
        )
