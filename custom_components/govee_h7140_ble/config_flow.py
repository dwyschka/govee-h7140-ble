"""Config and options flow for the Govee H7140 BLE integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback

from .const import (
    CONF_ADDRESS,
    CONF_ENABLE_ADV_HUMIDITY,
    CONF_ENABLE_EXPERIMENTAL,
    CONF_ENABLE_EXPERIMENTAL_SCENES,
    CONF_IDLE_DISCONNECT,
    CONF_POLL_INTERVAL,
    DEFAULT_ENABLE_ADV_HUMIDITY,
    DEFAULT_ENABLE_EXPERIMENTAL,
    DEFAULT_ENABLE_EXPERIMENTAL_SCENES,
    DEFAULT_IDLE_DISCONNECT,
    DEFAULT_NAME,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    MAX_IDLE_DISCONNECT,
    MAX_POLL_INTERVAL,
    MIN_IDLE_DISCONNECT,
    MIN_POLL_INTERVAL,
    MODEL,
    MODEL_NAME,
)

_LOGGER = logging.getLogger(__name__)


class GoveeH7140ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for a Govee H7140."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_address: str | None = None
        self._discovered_name: str | None = None

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle a Bluetooth discovery."""
        address = discovery_info.address
        name = discovery_info.name or discovery_info.local_name or DEFAULT_NAME
        await self.async_set_unique_id(address)
        self._abort_if_unique_id_configured()
        self._discovery_info = discovery_info
        self._discovered_address = address
        self._discovered_name = name
        self.context["title_placeholders"] = {"name": name}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a discovered device."""
        assert self._discovered_address is not None
        if user_input is not None:
            address = self._discovered_address
            name = user_input.get(CONF_NAME) or self._discovered_name or DEFAULT_NAME
            await self.async_set_unique_id(address)
            self._abort_if_unique_id_configured(updates={CONF_ADDRESS: address})
            return self.async_create_entry(
                title=name,
                data={
                    CONF_ADDRESS: address,
                    CONF_NAME: name,
                },
            )

        return self.async_show_form(
            step_id="bluetooth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_NAME,
                        default=self._discovered_name or DEFAULT_NAME,
                    ): str,
                }
            ),
            description_placeholders={
                "name": self._discovered_name or DEFAULT_NAME,
                "address": self._discovered_address,
                "model": f"{MODEL} {MODEL_NAME}",
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manual setup by BLE address/UUID."""
        errors: dict[str, str] = {}
        if user_input is not None:
            address = str(user_input[CONF_ADDRESS]).strip().upper()
            name = str(user_input.get(CONF_NAME) or DEFAULT_NAME).strip() or DEFAULT_NAME
            await self.async_set_unique_id(address)
            self._abort_if_unique_id_configured()
            if async_ble_device_from_address(self.hass, address, connectable=True) is None:
                errors["base"] = "not_found"
            else:
                return self.async_create_entry(
                    title=name,
                    data={CONF_ADDRESS: address, CONF_NAME: name},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): str,
                    vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                }
            ),
            errors=errors,
            description_placeholders={"model": f"{MODEL} {MODEL_NAME}"},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return GoveeH7140OptionsFlow()


class GoveeH7140OptionsFlow(OptionsFlow):
    """Options for polling/experimental features."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_POLL_INTERVAL,
                    default=int(
                        options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
                    ),
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_POLL_INTERVAL, max=MAX_POLL_INTERVAL),
                ),
                vol.Optional(
                    CONF_IDLE_DISCONNECT,
                    default=int(
                        options.get(CONF_IDLE_DISCONNECT, DEFAULT_IDLE_DISCONNECT)
                    ),
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(
                        min=MIN_IDLE_DISCONNECT, max=MAX_IDLE_DISCONNECT
                    ),
                ),
                vol.Optional(
                    CONF_ENABLE_ADV_HUMIDITY,
                    default=bool(
                        options.get(
                            CONF_ENABLE_ADV_HUMIDITY,
                            DEFAULT_ENABLE_ADV_HUMIDITY,
                        )
                    ),
                ): bool,
                vol.Optional(
                    CONF_ENABLE_EXPERIMENTAL,
                    default=bool(
                        options.get(
                            CONF_ENABLE_EXPERIMENTAL,
                            DEFAULT_ENABLE_EXPERIMENTAL,
                        )
                    ),
                ): bool,
                vol.Optional(
                    CONF_ENABLE_EXPERIMENTAL_SCENES,
                    default=bool(
                        options.get(
                            CONF_ENABLE_EXPERIMENTAL_SCENES,
                            DEFAULT_ENABLE_EXPERIMENTAL_SCENES,
                        )
                    ),
                ): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
