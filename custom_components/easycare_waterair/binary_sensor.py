"""Platform for sensor integration."""

from __future__ import annotations

from datetime import datetime
import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN
from .easycare import EasyCare

_LOGGER = logging.getLogger("custom_components.ha-easycare-waterair")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    easycare: EasyCare = hass.data[DOMAIN][entry.entry_id]
    sensors = []
    # MyEntity(coordinator, idx) for idx, ent in enumerate(easycare.get_coordinator().data)
    sensors.append(EasyCareConnectedSensorWithCoordinator(easycare))
    async_add_entities(sensors)


class EasyCareConnectedSensorWithCoordinator(CoordinatorEntity, BinarySensorEntity):
    """Representation of a Sensor."""

    def __init__(self, easycare: EasyCare) -> None:
        """Initialize EasyCare conenction sensor."""
        super().__init__(easycare.get_coordinator())
        self._attr_name = "Easy-Care connection"
        self._attr_is_on = easycare.get_connection_status()
        self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
        self._attr_icon = (
            "mdi:network-outline"
            if easycare.get_connection_status()
            else "mdi:network-off-outline"
        )
        self._attr_extra_state_attributes = {
            "token_valid": easycare.get_bearer() is not None,
            "last_update": datetime.now(),
        }
        self._attr_unique_id = "easycare_connection_sensor"
        self._easycare = easycare
        _LOGGER.debug("EasyCare-Binary-Sensor: %s created", self.name)

    def _handle_coordinator_update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        self._attr_icon = (
            "mdi:network-outline"
            if self._easycare.get_connection_status()
            else "mdi:network-off-outline"
        )
        self._attr_extra_state_attributes = {
            "token_valid": self._easycare.get_bearer() is not None,
            "last_update": datetime.now(),
        }
        self._attr_is_on = self._easycare.get_connection_status()
        self.async_write_ha_state()
        _LOGGER.debug("EasyCare update sensor %s", self.name)
