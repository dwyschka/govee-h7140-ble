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
    async_add_entities(
        [
            GoveeH7140MistLevel(coordinator),
            GoveeH7140CustomNumber(
                coordinator,
                "number_custom_high_gear",
                "custom_high_gear",
                "custom_high_gear",
                8,
                1,
                8,
                "mdi:arrow-up-bold",
            ),
            GoveeH7140CustomNumber(
                coordinator,
                "number_custom_low_gear",
                "custom_low_gear",
                "custom_low_gear",
                5,
                1,
                8,
                "mdi:arrow-down-bold",
            ),
            GoveeH7140CustomNumber(
                coordinator,
                "number_custom_high_duration",
                "custom_high_duration",
                "custom_high_duration",
                60,
                5,
                720,
                "mdi:timer-outline",
            ),
            GoveeH7140CustomNumber(
                coordinator,
                "number_custom_low_duration",
                "custom_low_duration",
                "custom_low_duration",
                60,
                5,
                720,
                "mdi:timer-outline",
            ),
        ]
    )


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


class GoveeH7140CustomNumber(GoveeH7140Entity, NumberEntity):
    """A parameter of the device's Custom mode.

    Writing any of these parameters switches the humidifier to Custom mode and
    writes the complete normalized 16-byte custom payload.
    """

    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self,
        coordinator: GoveeH7140Coordinator,
        key: str,
        translation_key: str,
        value_key: str,
        default: int,
        minimum: int,
        maximum: int,
        icon: str,
    ) -> None:
        super().__init__(coordinator, key)
        self._attr_translation_key = translation_key
        self._value_key = value_key
        self._default = default
        self._attr_native_min_value = minimum
        self._attr_native_max_value = maximum
        self._attr_icon = icon

    def _current(self) -> int:
        return int(getattr(self.device_state, self._value_key) or self._default)

    @property
    def native_value(self) -> float:
        return float(self._current())

    async def async_set_native_value(self, value: float) -> None:
        state = self.device_state
        high = state.custom_high_gear or 8
        low = state.custom_low_gear or 5
        high_duration = state.custom_high_duration or 60
        low_duration = state.custom_low_duration or 60
        new = int(value)
        if self._value_key == "custom_high_gear":
            high = new
        elif self._value_key == "custom_low_gear":
            low = new
        elif self._value_key == "custom_high_duration":
            high_duration = new
        elif self._value_key == "custom_low_duration":
            low_duration = new
        await self.coordinator.client.async_set_custom_params(
            high, low, high_duration, low_duration
        )
