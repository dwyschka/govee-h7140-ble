"""Entity/platform setup smoke test with a mocked BLE coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.govee_h7140_ble.const import CONF_ADDRESS, DOMAIN


@pytest.mark.asyncio
async def test_setup_and_unload(hass, enable_custom_integrations):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Humidifier",
        data={CONF_ADDRESS: "AA:BB:CC:DD:EE:FF", "name": "Test Humidifier"},
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.govee_h7140_ble.async_ble_device_from_address",
            return_value=object(),
        ),
        patch(
            "custom_components.govee_h7140_ble.async_register_callback",
            return_value=lambda: None,
        ),
        patch(
            "custom_components.govee_h7140_ble.GoveeH7140Coordinator.async_config_entry_first_refresh",
            new=AsyncMock(return_value=None),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    entity_ids = hass.states.async_entity_ids()
    assert any(entity_id.startswith("humidifier.") for entity_id in entity_ids), entity_ids
    assert any(entity_id.startswith("light.") for entity_id in entity_ids), entity_ids
    assert any(entity_id.startswith("sensor.") for entity_id in entity_ids), entity_ids
    assert any(
        entity_id.startswith("binary_sensor.") for entity_id in entity_ids
    ), entity_ids
    assert any(entity_id.startswith("number.") for entity_id in entity_ids), entity_ids

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
