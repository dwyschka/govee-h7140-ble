"""Local Bluetooth integration for the Govee H7140 humidifier."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.components.bluetooth import (
    BluetoothCallbackMatcher,
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
    async_register_callback,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse, callback
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr

from .const import (
    CONF_ADDRESS,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import GoveeH7140Coordinator

_LOGGER = logging.getLogger(__name__)

GoveeH7140ConfigEntry = ConfigEntry[GoveeH7140Coordinator]

SERVICE_SEND_FRAME = "send_frame"
SERVICE_SEND_FRAME_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): cv.string,
        vol.Required("frame"): cv.string,
        vol.Optional("expect_response", default=True): cv.boolean,
    }
)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Register integration-wide services."""

    async def _async_send_frame(call: ServiceCall) -> dict[str, Any]:
        device_id = call.data["device_id"]
        registry = dr.async_get(hass)
        device = registry.async_get(device_id)
        if device is None:
            raise HomeAssistantError(f"Unknown device_id: {device_id}")
        entry_id = next(iter(device.config_entries), None)
        if entry_id is None:
            raise HomeAssistantError("Device has no config entry")
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None or entry.domain != DOMAIN:
            raise HomeAssistantError("Device is not managed by this integration")
        coordinator: GoveeH7140Coordinator = entry.runtime_data
        try:
            response = await coordinator.client.async_send_raw(
                call.data["frame"], bool(call.data["expect_response"])
            )
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err
        return {"response": response}

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_FRAME,
        _async_send_frame,
        schema=SERVICE_SEND_FRAME_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: GoveeH7140ConfigEntry) -> bool:
    """Set up one H7140."""
    address = entry.data[CONF_ADDRESS]
    ble_device = async_ble_device_from_address(hass, address, connectable=True)
    if ble_device is None:
        raise ConfigEntryNotReady(
            f"H7140 {address} is not currently visible to the Bluetooth integration"
        )

    coordinator = GoveeH7140Coordinator(
        hass,
        entry,
        ble_device,
        address,
        entry.title,
    )
    entry.runtime_data = coordinator

    @callback
    def _async_adv_callback(
        service_info: BluetoothServiceInfoBleak, change: BluetoothChange
    ) -> None:
        if change is BluetoothChange.ADVERTISEMENT:
            coordinator.async_handle_advertisement(service_info)

    unsub = async_register_callback(
        hass,
        _async_adv_callback,
        BluetoothCallbackMatcher(address=address),
        BluetoothScanningMode.PASSIVE,
    )
    entry.async_on_unload(unsub)

    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def _async_options_updated(
        hass: HomeAssistant, entry: GoveeH7140ConfigEntry
    ) -> None:
        await hass.config_entries.async_reload(entry.entry_id)

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: GoveeH7140ConfigEntry) -> bool:
    """Unload an H7140."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok and entry.runtime_data is not None:
        await entry.runtime_data.async_shutdown()
    return unload_ok
