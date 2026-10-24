"""Shared entity base for the Govee H7140 integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL, MODEL_NAME
from .coordinator import GoveeH7140Coordinator
from .protocol import H7140State


class GoveeH7140Entity(CoordinatorEntity[GoveeH7140Coordinator]):
    """Base class for all H7140 entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: GoveeH7140Coordinator, key: str) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_unique_id = f"{coordinator.client.address}_{key}"
        self._attr_device_info = self._build_device_info()

    def _build_device_info(self) -> DeviceInfo:
        state = self.device_state
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.client.address)},
            connections={
                (CONNECTION_BLUETOOTH, self.coordinator.client.address)
            },
            manufacturer=MANUFACTURER,
            model=f"{MODEL} ({MODEL_NAME})",
            name=self.coordinator.config_entry.title,
            sw_version=state.firmware,
            hw_version=state.hardware,
            serial_number=state.serial,
        )

    @property
    def device_state(self) -> H7140State:
        return self.coordinator.data or self.coordinator.client.state

    @property
    def available(self) -> bool:
        return self.coordinator.available

    @property
    def extra_state_attributes(self) -> dict[str, object] | None:
        return None
