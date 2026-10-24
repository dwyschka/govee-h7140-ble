"""Number entities for the Govee H7140."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import MAX_MIST_LEVEL, MIN_MIST_LEVEL
from .coordinator import GoveeH7140Coordinator
from .entity import GoveeH7140Entity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: GoveeH7140Coordinator = entry.runtime_data
    async_add_entities([GoveeH7140MistLevel(coordinator)])


class GoveeH7140MistLevel(GoveeH7140Entity, NumberEntity):
    """Manual mist level (1 low .. 8 high)."""

    _attr_translation_key = "mist_level"
    _attr_native_min_value = MIN_MIST_LEVEL
    _attr_native_max_value = MAX_MIST_LEVEL
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER
    _attr_icon = "mdi:weather-rainy"

    def __init__(self, coordinator: GoveeH7140Coordinator) -> None:
        super().__init__(coordinator, "number_mist_level")

    @property
    def native_value(self) -> float | None:
        gear = self.device_state.manual_gear
        return float(gear) if gear is not None else None

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.client.async_set_manual_gear(int(value))
