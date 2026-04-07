"""Custom component for EasyCare by Waterair."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .easycare import EasyCare

_LOGGER = logging.getLogger("custom_components.ha-easycare-waterair")

DOMAIN = "easycare_waterair"
CONF_POOL_ID = "pool_id"

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SENSOR,
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up EasyCare from the UI only."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up EasyCare from a config entry."""
    _LOGGER.debug("Start EasyCare config entry initialisation")

    easycare = await hass.async_add_executor_job(create_easycare, hass, entry.data)
    if easycare is None:
        return False

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = easycare

    coordinator = easycare.get_coordinator()
    await coordinator.async_refresh()
    module_coordinator = easycare.get_module_coordinator()
    await module_coordinator.async_refresh()
    light_coordinator = easycare.get_light_coordinator()
    await light_coordinator.async_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.debug("End EasyCare config entry initialisation")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an EasyCare config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok


def create_easycare(hass: HomeAssistant, config) -> EasyCare | None:
    """Create and connect to EasyCare."""
    easycare = EasyCare(
        hass,
        pool_id=config.get(CONF_POOL_ID),
        username=config.get(CONF_USERNAME),
        password=config.get(CONF_PASSWORD),
    )

    _LOGGER.debug("Calling EasyCare login")
    if easycare.connect() is False:
        return None

    return easycare
