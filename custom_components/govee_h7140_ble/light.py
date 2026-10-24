"""Night-light entity for the Govee H7140."""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import NIGHT_LIGHT_SCENES, SCENE_NAME_TO_ID
from .coordinator import GoveeH7140Coordinator
from .entity import GoveeH7140Entity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: GoveeH7140Coordinator = entry.runtime_data
    async_add_entities([GoveeH7140NightLight(coordinator)])


class GoveeH7140NightLight(GoveeH7140Entity, LightEntity):
    """The RGB night light of the humidifier."""

    _attr_translation_key = "night_light"
    _attr_color_mode = ColorMode.RGB
    _attr_supported_color_modes: ClassVar[set[ColorMode]] = {ColorMode.RGB}

    def __init__(self, coordinator: GoveeH7140Coordinator) -> None:
        super().__init__(coordinator, "night_light")
        if coordinator.client.scenes_enabled:
            self._attr_supported_features = LightEntityFeature.EFFECT

    @property
    def is_on(self) -> bool:
        return bool(self.device_state.night_light_on)

    @property
    def brightness(self) -> int | None:
        level = self.device_state.night_light_brightness
        if level is None:
            return None
        if not self.is_on:
            return 0
        return max(1, min(255, round(level * 255 / 100)))

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        return self.device_state.night_light_rgb

    @property
    def effect_list(self) -> list[str] | None:
        if not self.coordinator.client.scenes_enabled:
            return None
        return list(NIGHT_LIGHT_SCENES.values())

    @property
    def effect(self) -> str | None:
        scene = self.device_state.night_light_scene
        if scene is None:
            return None
        return NIGHT_LIGHT_SCENES.get(scene)

    async def async_turn_on(self, **kwargs: Any) -> None:
        client = self.coordinator.client
        effect = kwargs.get(ATTR_EFFECT)
        rgb = kwargs.get(ATTR_RGB_COLOR)
        brightness = kwargs.get(ATTR_BRIGHTNESS)

        if not self.is_on and not any(
            value is not None for value in (effect, rgb, brightness)
        ):
            await client.async_set_light_power(True)
            return

        if not self.is_on:
            await client.async_set_light_power(True)
        if brightness is not None:
            level = max(1, min(100, round(int(brightness) * 100 / 255)))
            await client.async_set_light_brightness(level)
        if rgb is not None:
            red, green, blue = rgb
            await client.async_set_light_rgb(red, green, blue)
        if effect is not None:
            scene = SCENE_NAME_TO_ID.get(str(effect))
            if scene is None:
                raise ValueError(f"unknown night-light scene: {effect}")
            await client.async_set_light_scene(scene)
        if not any(value is not None for value in (effect, rgb, brightness)):
            await client.async_set_light_power(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.client.async_set_light_power(False)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        state = self.device_state
        return {
            "raw_power_brightness": {
                "on": state.night_light_on,
                "brightness": state.night_light_brightness,
            },
            "night_light_scene": state.night_light_scene,
        }
