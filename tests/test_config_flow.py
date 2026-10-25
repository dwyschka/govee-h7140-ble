"""Home Assistant config-flow smoke tests."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from homeassistant import config_entries, data_entry_flow
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.govee_h7140_ble.const import CONF_ADDRESS, DOMAIN


@pytest.mark.asyncio
async def test_manual_flow(hass, enable_custom_integrations):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "custom_components.govee_h7140_ble.config_flow.async_ble_device_from_address",
        return_value=object(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ADDRESS: "AA:BB:CC:DD:EE:FF",
                "name": "Test Humidifier",
            },
        )
    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Humidifier"
    assert result["data"][CONF_ADDRESS] == "AA:BB:CC:DD:EE:FF"


@pytest.mark.asyncio
async def test_manual_flow_not_found(hass, enable_custom_integrations):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "custom_components.govee_h7140_ble.config_flow.async_ble_device_from_address",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_ADDRESS: "AA:BB:CC:DD:EE:FF", "name": "Test"},
        )
    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "not_found"}


@pytest.mark.asyncio
async def test_options_flow(hass, enable_custom_integrations):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test",
        data={CONF_ADDRESS: "AA:BB:CC:DD:EE:FF", "name": "Test"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"
    assert "poll_interval" in result["data_schema"].schema

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"poll_interval": 30, "idle_disconnect": 10}
    )
    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"]["poll_interval"] == 30
