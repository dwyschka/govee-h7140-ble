"""Sensors for the Govee H7140."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import WORK_MODES
from .coordinator import GoveeH7140Client, GoveeH7140Coordinator
from .entity import GoveeH7140Entity
from .protocol import H7140State


@dataclass(frozen=True, kw_only=True)
class H7140SensorEntityDescription(SensorEntityDescription):
    """Sensor description with a state accessor."""

    value_fn: Callable[[GoveeH7140Client], Any]


SENSORS: tuple[H7140SensorEntityDescription, ...] = (
    H7140SensorEntityDescription(
        key="current_humidity",
        translation_key="current_humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda client: (
            client.state.current_humidity if client.adv_humidity_enabled else None
        ),
    ),
    H7140SensorEntityDescription(
        key="target_humidity",
        translation_key="target_humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda client: client.state.target_humidity,
    ),
    H7140SensorEntityDescription(
        key="work_mode",
        translation_key="work_mode",
        device_class=SensorDeviceClass.ENUM,
        options=WORK_MODES,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda client: client.state.work_mode,
    ),
    H7140SensorEntityDescription(
        key="mist_level",
        translation_key="mist_level",
        icon="mdi:weather-rainy",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda client: client.state.manual_gear,
    ),
    H7140SensorEntityDescription(
        key="low_gear",
        translation_key="low_gear",
        icon="mdi:arrow-down-bold",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda client: client.state.low_gear,
    ),
    H7140SensorEntityDescription(
        key="high_gear",
        translation_key="high_gear",
        icon="mdi:arrow-up-bold",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda client: client.state.high_gear,
    ),
    H7140SensorEntityDescription(
        key="firmware",
        translation_key="firmware",
        icon="mdi:chip",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda client: client.state.firmware,
    ),
    H7140SensorEntityDescription(
        key="hardware",
        translation_key="hardware",
        icon="mdi:chip",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda client: client.state.hardware,
    ),
    H7140SensorEntityDescription(
        key="mcu_firmware",
        translation_key="mcu_firmware",
        icon="mdi:chip",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda client: client.state.mcu_firmware,
    ),
    H7140SensorEntityDescription(
        key="mcu_hardware",
        translation_key="mcu_hardware",
        icon="mdi:chip",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda client: client.state.mcu_hardware,
    ),
    H7140SensorEntityDescription(
        key="serial",
        translation_key="serial",
        icon="mdi:identifier",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda client: client.state.serial,
    ),
    H7140SensorEntityDescription(
        key="ble_mac",
        translation_key="ble_mac",
        icon="mdi:bluetooth",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda client: client.state.ble_mac,
    ),
    H7140SensorEntityDescription(
        key="rssi",
        translation_key="rssi",
        native_unit_of_measurement="dBm",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda client: client.state.rssi,
    ),
    H7140SensorEntityDescription(
        key="last_seen",
        translation_key="last_seen",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda client: client.state.last_seen,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: GoveeH7140Coordinator = entry.runtime_data
    async_add_entities(
        [GoveeH7140Sensor(coordinator, description) for description in SENSORS]
    )


class GoveeH7140Sensor(GoveeH7140Entity, SensorEntity):
    """A generic H7140 sensor."""

    entity_description: H7140SensorEntityDescription

    def __init__(
        self,
        coordinator: GoveeH7140Coordinator,
        description: H7140SensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, f"sensor_{description.key}")
        self.entity_description = description
        self._attr_translation_key = description.translation_key

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.client)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.key == "current_humidity":
            state: H7140State = self.device_state
            return {
                "advertisement": state.adv.as_dict() if state.adv else None,
            }
        return None
