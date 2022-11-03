"""Config flow to configure TAURON component."""

import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import CONF_TARIFF, CONF_METER_ID, CONF_SHOW_GENERATION, DOMAIN
from .connector import TauronAmiplusConnector

_LOGGER = logging.getLogger(__name__)


class TauronAmiplusFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """TAURON config flow."""

    VERSION = 1

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
                    data = {**user_input, CONF_TARIFF: tariff}
                    """Finish config flow"""
                    return self.async_create_entry(title=f"eLicznik {user_input[CONF_METER_ID]}", data=data)
                errors = {CONF_METER_ID: "server_no_connection"}
                description_placeholders = {"error_info": str(calculated)}
            except Exception as e:
                errors = {CONF_METER_ID: "server_no_connection"}
                description_placeholders = {"error_info": str(e)}
                _LOGGER.error(str(e))

        data_schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required(CONF_METER_ID): str,
                vol.Optional(CONF_SHOW_GENERATION, default=False): bool,
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
            errors=errors,
            description_placeholders=description_placeholders,
        )
