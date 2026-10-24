"""Binary sensors for the Govee H7140."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
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
    async_add_entities([GoveeH7140WaterLack(coordinator)])


class GoveeH7140WaterLack(GoveeH7140Entity, BinarySensorEntity):
    """Water-tank empty / lack-of-water problem."""

    _attr_translation_key = "water_lack"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator: GoveeH7140Coordinator) -> None:
        super().__init__(coordinator, "water_lack")

    @property
    def is_on(self) -> bool | None:
        return self.device_state.lack_water

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        state = self.device_state
        return {
            "misting": state.misting,
            "power": state.power,
            "raw_status": state.raw_frames[-1] if state.raw_frames else None,
        }
