"""Config flow for EasyCare by Waterair."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import CONF_POOL_ID, DOMAIN, create_easycare

_LOGGER = logging.getLogger("custom_components.ha-easycare-waterair")


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


async def validate_input(hass: HomeAssistant, data: dict) -> dict:
    """Validate the user input allows us to connect."""
    easycare = await hass.async_add_executor_job(create_easycare, hass, data)
    if easycare is None:
        raise CannotConnect

    return {"title": data[CONF_USERNAME]}


class EasyCareConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an EasyCare config flow."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        if user_input is not None:
            user_input = dict(user_input)
            user_input[CONF_POOL_ID] = 1

            await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
            self._abort_if_unique_id_configured()

            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )
