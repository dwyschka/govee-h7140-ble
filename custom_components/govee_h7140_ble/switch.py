"""Switches for the Govee H7140."""

from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import GoveeH7140Coordinator
from .entity import GoveeH7140Entity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: GoveeH7140Coordinator = entry.runtime_data
    if coordinator.client.auto_stop_enabled:
        async_add_entities([GoveeH7140AutoStop(coordinator)])


class GoveeH7140AutoStop(GoveeH7140Entity, SwitchEntity):
    """Experimental Auto Stop switch."""

    _attr_translation_key = "auto_stop"
    _attr_entity_registry_enabled_default = False
    _attr_icon = "mdi:water-off"

    def __init__(self, coordinator: GoveeH7140Coordinator) -> None:
        super().__init__(coordinator, "switch_auto_stop")

    @property
    def is_on(self) -> bool:
        return bool(self.device_state.auto_stop)

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.client.async_set_auto_stop(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.client.async_set_auto_stop(False)
