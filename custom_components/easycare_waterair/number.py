"""Platform for sensor integration."""

from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger("custom_components.ha-easycare-waterair")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    numbers = []
    numbers.append(EasyCareSpotDuration())
    numbers.append(EasyCareEscalightDuration())

    async_add_entities(numbers)


class EasyCareSpotDuration(NumberEntity):
    """Representation of a Sensor."""

    def __init__(self) -> None:
        """Initialize EasyCare refresh button."""
        self._attr_name = "Easy-Care Pool Spot Light Duration (in hours)"
        self._attr_unique_id = "easycare_pool_spot_duration"
        self._attr_native_min_value = 1
        self._attr_native_max_value = 6
        self._attr_native_step = 1
        self._attr_native_value = 1
        _LOGGER.debug("EasyCare-Button-Sensor: %s created", self.name)

    async def async_set_native_value(self, value) -> None:
        """Update the current value."""
        self._attr_native_value = value
        self.async_write_ha_state()


class EasyCareEscalightDuration(NumberEntity):
    """Representation of a Sensor."""

    def __init__(self) -> None:
        """Initialize EasyCare refresh button."""
        self._attr_name = "Easy-Care Pool Escalight Light Duration (in hours)"
        self._attr_unique_id = "easycare_pool_escalight_duration"
        self._attr_native_min_value = 1
        self._attr_native_max_value = 6
        self._attr_native_step = 1
        self._attr_native_value = 1
        _LOGGER.debug("EasyCare-Button-Sensor: %s created", self.name)

    async def async_set_native_value(self, value) -> None:
        """Update the current value."""
        self._attr_native_value = value
        self.async_write_ha_state()
