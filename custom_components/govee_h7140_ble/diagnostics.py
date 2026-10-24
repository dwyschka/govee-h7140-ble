"""Diagnostics for the Govee H7140 integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_ADDRESS
from .coordinator import GoveeH7140Coordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry[GoveeH7140Coordinator]
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    client = coordinator.client
    return {
        "entry": {
            "title": entry.title,
            "address": entry.data.get(CONF_ADDRESS),
            "options": dict(entry.options),
        },
        "available": coordinator.available,
        "connected": client.connected,
        "last_advertisement": (
            client.last_adv.isoformat() if client.last_adv else None
        ),
        "state": client.state.as_dict(),
    }
