"""Buttons for the Govee H7140."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import GoveeH7140Coordinator
from .entity import GoveeH7140Entity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: GoveeH7140Coordinator = entry.runtime_data
    async_add_entities([GoveeH7140RefreshButton(coordinator)])


class GoveeH7140RefreshButton(GoveeH7140Entity, ButtonEntity):
    """Force an immediate BLE poll."""

    _attr_translation_key = "refresh"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:refresh"

    def __init__(self, coordinator: GoveeH7140Coordinator) -> None:
        super().__init__(coordinator, "button_refresh")

    async def async_press(self) -> None:
        await self.coordinator.async_request_refresh()
