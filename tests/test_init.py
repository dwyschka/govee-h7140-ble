"""Integration setup smoke tests."""

from __future__ import annotations

import pytest

from custom_components.govee_h7140_ble import async_setup
from custom_components.govee_h7140_ble.const import DOMAIN


@pytest.mark.asyncio
async def test_send_frame_service_registered(hass):
    assert await async_setup(hass, {})
    assert hass.services.has_service(DOMAIN, "send_frame")
