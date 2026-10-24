"""Humidifier entity for the Govee H7140."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.humidifier import (
    HumidifierAction,
    HumidifierDeviceClass,
    HumidifierEntity,
    HumidifierEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import MAX_HUMIDITY, MIN_HUMIDITY, WORK_MODES
from .coordinator import GoveeH7140Coordinator
from .entity import GoveeH7140Entity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: GoveeH7140Coordinator = entry.runtime_data
    async_add_entities([GoveeH7140Humidifier(coordinator)])


class GoveeH7140Humidifier(GoveeH7140Entity, HumidifierEntity):
    """The main humidifier entity."""

    _attr_name = None
    _attr_device_class = HumidifierDeviceClass.HUMIDIFIER
    _attr_supported_features = HumidifierEntityFeature.MODES
    _attr_min_humidity = MIN_HUMIDITY
    _attr_max_humidity = MAX_HUMIDITY
    _attr_available_modes = WORK_MODES

    def __init__(self, coordinator: GoveeH7140Coordinator) -> None:
        super().__init__(coordinator, "humidifier")

    @property
    def is_on(self) -> bool:
        return bool(self.device_state.power)

    @property
    def current_humidity(self) -> int | None:
        if not self.coordinator.client.adv_humidity_enabled:
            return None
        return self.device_state.current_humidity

    @property
    def target_humidity(self) -> int:
        return self.device_state.target_humidity or 55

    @property
    def mode(self) -> str:
        return self.device_state.work_mode or "auto"

    @property
    def action(self) -> HumidifierAction:
        if not self.is_on:
            return HumidifierAction.OFF
        if self.device_state.misting:
            return HumidifierAction.HUMIDIFYING
        return HumidifierAction.IDLE

    async def async_set_mode(self, mode: str) -> None:
        if mode not in WORK_MODES:
            raise ValueError(f"unsupported humidifier mode: {mode}")
        await self.coordinator.client.async_set_work_mode(mode)

    async def async_set_humidity(self, humidity: int) -> None:
        await self.coordinator.client.async_set_target_humidity(humidity)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.client.async_set_power(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.client.async_set_power(False)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        state = self.device_state
        attrs: dict[str, Any] = {
            "work_mode_code": state.work_mode_code,
            "misting": state.misting,
            "lack_water": state.lack_water,
            "manual_gear": state.manual_gear,
            "low_gear": state.low_gear,
            "high_gear": state.high_gear,
            "custom_payload": (
                state.custom_payload.hex(" ").upper()
                if state.custom_payload
                else None
            ),
            "timer_raw": state.timer_raw.hex(" ").upper() if state.timer_raw else None,
            "auto_stop": state.auto_stop,
            "child_lock": state.child_lock,
            "pact": f"{state.pact_type}/{state.pact_code}"
            if state.pact_type is not None
            else None,
            "raw_frames": state.raw_frames[-20:],
        }
        return {key: value for key, value in attrs.items() if value is not None}
