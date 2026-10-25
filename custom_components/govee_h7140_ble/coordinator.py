"""BLE connection and state coordinator for the Govee H7140."""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from bleak import BleakClient
from bleak.exc import BleakError
from bleak_retry_connector import establish_connection
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ENABLE_ADV_HUMIDITY,
    CONF_ENABLE_EXPERIMENTAL,
    CONF_ENABLE_EXPERIMENTAL_AUTO_STOP,
    CONF_ENABLE_EXPERIMENTAL_SCENES,
    CONF_IDLE_DISCONNECT,
    CONF_POLL_INTERVAL,
    DEFAULT_CUSTOM_PAYLOAD,
    DEFAULT_ENABLE_ADV_HUMIDITY,
    DEFAULT_ENABLE_EXPERIMENTAL,
    DEFAULT_ENABLE_EXPERIMENTAL_AUTO_STOP,
    DEFAULT_ENABLE_EXPERIMENTAL_SCENES,
    DEFAULT_IDLE_DISCONNECT,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    MANUFACTURER_IDS,
    MAX_HUMIDITY,
    MAX_MIST_LEVEL,
    MIN_HUMIDITY,
    MIN_MIST_LEVEL,
    NAME_TO_WORK_MODE,
    NOTIFY_CHARACTERISTIC_UUID,
    QUERY_GAP,
    RESPONSE_TIMEOUT,
    SLOW_POLL_INTERVAL,
    WORK_MODE_AUTO,
    WORK_MODE_CUSTOM,
    WORK_MODE_MANUAL,
    WRITE_CHARACTERISTIC_UUID,
)
from .encryption import (
    COMMUNICATION_KEY,
    build_handshake_request,
    encrypt_frame,
    parse_session_key,
    try_decrypt,
)
from .protocol import (
    AdvState,
    Frame,
    H7140State,
    build_auto_mode,
    build_auto_stop,
    build_custom_mode,
    build_custom_mode_params,
    build_frame,
    build_light_brightness,
    build_light_power,
    build_light_rgb,
    build_light_scene,
    build_manual_mode,
    build_power,
    checksum,
    query_ble_mac,
    query_custom_mode,
    query_flags,
    query_gear_limits,
    query_hardware,
    query_hw_version,
    query_light,
    query_light_rgb,
    query_light_scene,
    query_mac,
    query_manual_gear,
    query_mcu_hw,
    query_mcu_sw,
    query_mode,
    query_pact,
    query_power,
    query_serial,
    query_software,
    query_target_humidity,
    query_timer,
    query_version,
)

_LOGGER = logging.getLogger(__name__)


class GoveeH7140Client:
    """Owns the BLE link, serializes commands and maintains the state."""

    def __init__(
        self,
        hass: HomeAssistant,
        address: str,
        name: str,
        ble_device: Any,
        options: dict[str, Any],
    ) -> None:
        self.hass = hass
        self.address = address
        self.name = name
        self.ble_device = ble_device
        self.options = options
        self.state = H7140State()
        self.last_adv: datetime | None = None
        self._client: BleakClient | None = None
        self._lock = asyncio.Lock()
        self._frames: deque[Frame] = deque(maxlen=200)
        self._frame_event = asyncio.Event()
        self._raw_frames: deque[bytes] = deque(maxlen=200)
        self._raw_event = asyncio.Event()
        self._session_key: bytes | None = None
        self._encryption: str = "unknown"
        self._negotiating = False
        self._last_negotiation_attempt: float = 0.0
        self._idle_handle: asyncio.TimerHandle | None = None
        self._metadata_loaded = False
        self._last_slow_poll: float = 0.0
        self._state_callback: Callable[[], None] | None = None
        self._closed = False

    # ------------------------------------------------------------------ setup
    def set_state_callback(self, callback_fn: Callable[[], None]) -> None:
        self._state_callback = callback_fn

    @property
    def poll_interval(self) -> int:
        return int(self.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL))

    @property
    def idle_disconnect(self) -> int:
        return int(self.options.get(CONF_IDLE_DISCONNECT, DEFAULT_IDLE_DISCONNECT))

    @property
    def adv_humidity_enabled(self) -> bool:
        return bool(
            self.options.get(
                CONF_ENABLE_ADV_HUMIDITY, DEFAULT_ENABLE_ADV_HUMIDITY
            )
        )

    @property
    def experimental_enabled(self) -> bool:
        return bool(
            self.options.get(CONF_ENABLE_EXPERIMENTAL, DEFAULT_ENABLE_EXPERIMENTAL)
        )

    @property
    def scenes_enabled(self) -> bool:
        return self.experimental_enabled and bool(
            self.options.get(
                CONF_ENABLE_EXPERIMENTAL_SCENES,
                DEFAULT_ENABLE_EXPERIMENTAL_SCENES,
            )
        )

    @property
    def auto_stop_enabled(self) -> bool:
        return self.experimental_enabled and bool(
            self.options.get(
                CONF_ENABLE_EXPERIMENTAL_AUTO_STOP,
                DEFAULT_ENABLE_EXPERIMENTAL_AUTO_STOP,
            )
        )

    @property
    def connected(self) -> bool:
        return bool(self._client and self._client.is_connected)

    @property
    def available(self) -> bool:
        if self.connected:
            return True
        if self.last_adv is not None:
            age = (dt_util.utcnow() - self.last_adv).total_seconds()
            if age < 300:
                return True
        return False

    # ------------------------------------------------------------------- state
    @callback
    def _notify_state(self) -> None:
        if self._state_callback is not None:
            self._state_callback()

    def _decode(self, raw: bytes) -> bytes | None:
        """Return the plaintext application frame for a notification."""
        if self._encryption == "v1":
            if self._session_key is not None:
                plaintext = try_decrypt(raw, self._session_key)
                if plaintext is not None:
                    return plaintext
            # Delayed handshake/transition frames still use the communication key.
            return try_decrypt(raw, COMMUNICATION_KEY)
        if self._encryption == "plaintext":
            try:
                Frame.parse(raw)
                return raw
            except ValueError:
                return None
        # Unknown mode: accept plaintext, then the comm-key encrypted form.
        try:
            Frame.parse(raw)
            return raw
        except ValueError:
            return try_decrypt(raw, COMMUNICATION_KEY)

    def _handle_raw(self, raw: bytes) -> None:
        self._raw_frames.append(raw)
        self._raw_event.set()
        plaintext = self._decode(raw)
        if plaintext is None:
            _LOGGER.debug("%s: unparsed notification %s", self.address, raw.hex(" "))
            return
        try:
            frame = Frame.parse(plaintext)
        except ValueError:
            return
        self.state.apply_frame(frame)
        self.state.last_seen = dt_util.utcnow()
        self._frames.append(frame)
        self._frame_event.set()
        self._notify_state()

    def _on_notify(self, _sender: Any, data: bytearray) -> None:
        self.hass.loop.call_soon_threadsafe(self._handle_raw, bytes(data))

    @callback
    def handle_advertisement(self, service_info: BluetoothServiceInfoBleak) -> None:
        """Update state from a passive BLE advertisement."""
        best: AdvState | None = None
        for manufacturer_id, data in service_info.manufacturer_data.items():
            if manufacturer_id not in MANUFACTURER_IDS:
                continue
            adv = AdvState.parse(manufacturer_id, data, service_info.rssi)
            # Prefer the main 0x8802 packet over the 0x8843 beacon when both
            # are present in the same advertisement.
            if best is None or manufacturer_id == 0x8802:
                best = adv
        if best is None:
            return
        self.last_adv = dt_util.utcnow()
        self.state.last_seen = self.last_adv
        self.state.apply_adv(best)
        self._notify_state()

    # --------------------------------------------------------------- BLE link
    async def _ensure_connected(self) -> None:
        if self._closed:
            raise UpdateFailed("integration is shutting down")
        if self._client is not None and self._client.is_connected:
            return
        ble_device = (
            async_ble_device_from_address(self.hass, self.address, connectable=True)
            or self.ble_device
        )
        if ble_device is None:
            raise UpdateFailed(f"BLE device {self.address} not found")

        def _get_device() -> Any:
            return (
                async_ble_device_from_address(
                    self.hass, self.address, connectable=True
                )
                or ble_device
            )

        try:
            self._client = await establish_connection(
                BleakClient,
                ble_device,
                self.name,
                max_attempts=2,
                timeout=15,
                ble_device_callback=_get_device,
            )
            await self._client.start_notify(
                NOTIFY_CHARACTERISTIC_UUID, self._on_notify
            )
            # Bluetooth proxies may need a moment before the first
            # notification is routed after the CCCD write.
            await asyncio.sleep(0.35)
            _LOGGER.debug("%s: connected", self.address)
            await self._async_negotiate()
        except (BleakError, TimeoutError, EOFError, OSError) as err:
            self._client = None
            raise UpdateFailed(f"could not connect to {self.address}: {err}") from err

    async def async_disconnect(self) -> None:
        if self._idle_handle is not None:
            self._idle_handle.cancel()
            self._idle_handle = None
        client, self._client = self._client, None
        self._session_key = None
        self._encryption = "unknown"
        self._last_negotiation_attempt = 0.0
        self._raw_frames.clear()
        self._frames.clear()
        if client is None:
            return
        try:
            if client.is_connected:
                await client.stop_notify(NOTIFY_CHARACTERISTIC_UUID)
        except (BleakError, EOFError, OSError):
            pass
        try:
            await client.disconnect()
        except (BleakError, EOFError, OSError):
            pass
        _LOGGER.debug("%s: disconnected", self.address)

    def _schedule_disconnect(self) -> None:
        if self._idle_handle is not None:
            self._idle_handle.cancel()
            self._idle_handle = None
        delay = self.idle_disconnect
        if delay <= 0:
            self.hass.async_create_task(self.async_disconnect())
            return

        def _close() -> None:
            self._idle_handle = None
            self.hass.async_create_task(self.async_disconnect())

        self._idle_handle = self.hass.loop.call_later(delay, _close)

    async def async_stop(self) -> None:
        self._closed = True
        await self.async_disconnect()

    # -------------------------------------------------------------- transport
    def _encode_frame(self, frame: bytes) -> bytes:
        if (
            self._encryption == "v1"
            and self._session_key is not None
        ):
            return encrypt_frame(frame, self._session_key)
        return frame

    async def _write_wire(self, frame: bytes) -> None:
        if self._client is None or not self._client.is_connected:
            await self._ensure_connected()
        assert self._client is not None
        await self._client.write_gatt_char(
            WRITE_CHARACTERISTIC_UUID, frame, response=False
        )

    async def _write(self, frame: bytes) -> None:
        if self._encryption == "unknown":
            await self._async_negotiate()
        if self._encryption == "unknown":
            raise UpdateFailed(
                "BLE protocol negotiation failed; the H7140 is off, asleep, "
                "or the encrypted handshake was not answered"
            )
        await self._write_wire(self._encode_frame(frame))

    async def _async_negotiate(self) -> None:
        """Detect plaintext vs Govee V1 and negotiate a session key."""
        if self._negotiating or self._encryption != "unknown":
            return
        now = self.hass.loop.time()
        if now - self._last_negotiation_attempt < 10:
            return
        self._last_negotiation_attempt = now
        self._negotiating = True
        try:
            # 1) Govee V1 handshake first.  This is the mode used by current
            #    H7140 firmware.  The reply may take >1 s through a Bluetooth
            #    proxy, so poll for up to 3 seconds and retry once.
            self._raw_frames.clear()
            self._frames.clear()
            request = build_handshake_request(0x01)
            session_key: bytes | None = None
            for _attempt in range(2):
                await self._write_wire(encrypt_frame(request, COMMUNICATION_KEY))
                deadline = self.hass.loop.time() + 1.6
                while self.hass.loop.time() < deadline:
                    for raw in list(self._raw_frames):
                        plaintext = try_decrypt(raw, COMMUNICATION_KEY)
                        if plaintext is None or plaintext[:2] != b"\xe7\x01":
                            continue
                        try:
                            session_key = parse_session_key(plaintext)
                        except ValueError:
                            continue
                        break
                    if session_key is not None:
                        break
                    await asyncio.sleep(0.1)
                if session_key is not None:
                    break

            if session_key is not None:
                confirmation = build_handshake_request(0x02)
                await self._write_wire(
                    encrypt_frame(confirmation, COMMUNICATION_KEY)
                )
                deadline = self.hass.loop.time() + 1.6
                while self.hass.loop.time() < deadline:
                    if any(
                        (plaintext := try_decrypt(raw, COMMUNICATION_KEY))
                        is not None
                        and plaintext[:2] == b"\xe7\x02"
                        for raw in list(self._raw_frames)
                    ):
                        break
                    await asyncio.sleep(0.1)

                self._session_key = session_key
                self._encryption = "v1"
                self._frames.clear()
                self._raw_frames.clear()
                _LOGGER.debug("%s: Govee V1 session established", self.address)
                # A failed verification is not fatal; the next poll retries.
                await self._query(query_power(), 0x01, timeout=1.6)
                return

            # 2) Plaintext fallback.  Some H7140/H714E firmware revisions do
            #    not use the encrypted session.
            self._raw_frames.clear()
            self._frames.clear()
            await self._write_wire(query_power())
            deadline = self.hass.loop.time() + 1.6
            while self.hass.loop.time() < deadline:
                for raw in list(self._raw_frames):
                    try:
                        Frame.parse(raw)
                    except ValueError:
                        continue
                    self._encryption = "plaintext"
                    _LOGGER.debug("%s: plaintext protocol", self.address)
                    return
                await asyncio.sleep(0.1)

            _LOGGER.warning(
                "%s: BLE protocol negotiation failed; device may be off, "
                "in protection/standby, or connected to the Govee app",
                self.address,
            )
        finally:
            self._negotiating = False

    def _drop_pending(self, command: int, selector: int | None) -> None:
        kept: deque[Frame] = deque(maxlen=200)
        for frame in self._frames:
            if frame.command == command and (
                selector is None or frame.payload[:1] == bytes([selector])
            ):
                continue
            kept.append(frame)
        self._frames = kept

    async def _wait_for(
        self, command: int, selector: int | None = None, timeout: float = RESPONSE_TIMEOUT
    ) -> Frame | None:
        deadline = self.hass.loop.time() + timeout
        while True:
            for index, frame in enumerate(self._frames):
                if frame.command != command:
                    continue
                if selector is not None and frame.payload[:1] != bytes([selector]):
                    continue
                del self._frames[index]
                return frame
            remaining = deadline - self.hass.loop.time()
            if remaining <= 0:
                return None
            self._frame_event.clear()
            try:
                await asyncio.wait_for(self._frame_event.wait(), remaining)
            except TimeoutError:
                return None

    async def _query(
        self,
        body: bytes,
        command: int,
        selector: int | None = None,
        timeout: float = RESPONSE_TIMEOUT,
    ) -> Frame | None:
        self._drop_pending(command, selector)
        await self._write(body)
        await asyncio.sleep(QUERY_GAP)
        frame = await self._wait_for(command, selector, timeout)
        if frame is not None:
            self.state.apply_frame(frame)
        return frame

    async def async_send_raw(self, frame_hex: str, expect_response: bool = True) -> str | None:
        """Send a raw 20-byte frame or a shorter body and optionally wait."""
        cleaned = frame_hex.replace(" ", "").replace(":", "").replace("-", "")
        try:
            raw = bytes.fromhex(cleaned)
        except ValueError as err:
            raise ValueError(f"invalid hex frame: {frame_hex}") from err
        if len(raw) == 20:
            if checksum(raw[:19]) != raw[19]:
                raise ValueError("invalid XOR checksum in raw frame")
            frame = raw
        elif len(raw) < 20:
            frame = build_frame(raw)
        else:
            raise ValueError("frame must be at most 20 bytes")

        async with self._lock:
            await self._ensure_connected()
            await self._write(frame)
            response: Frame | None = None
            if expect_response:
                response = await self._wait_for(0xAA, None, RESPONSE_TIMEOUT)
                if response is not None:
                    self.state.apply_frame(response)
            self._schedule_disconnect()
        self._notify_state()
        return str(response) if response else None

    # --------------------------------------------------------------- polling
    async def async_update(self) -> H7140State:
        async with self._lock:
            await self._ensure_connected()
            if self._encryption == "unknown":
                await self._async_negotiate()
            try:
                responses = 0
                if await self._query(query_power(), 0x01, timeout=1.5):
                    responses += 1
                if await self._query(query_mode(), 0x05, 0x00, timeout=1.2):
                    responses += 1
                if await self._query(
                    query_target_humidity(), 0x05, 0x03, timeout=1.2
                ):
                    responses += 1
                if await self._query(query_light(), 0x1B, 0x01, timeout=1.2):
                    responses += 1

                if responses == 0:
                    # Nothing answered.  Keep the advertisement-derived state
                    # instead of reporting a successful empty poll.
                    if self.state.adv is not None and self.state.adv.power is not None:
                        self.state.power = self.state.adv.power
                    return self.state

                now = self.hass.loop.time()
                if now - self._last_slow_poll >= SLOW_POLL_INTERVAL:
                    self._last_slow_poll = now
                    await self._query(query_manual_gear(), 0x05, 0x01, timeout=1.2)
                    await self._query(query_custom_mode(), 0x05, 0x02, timeout=1.2)
                    await self._query(query_flags(), 0x17, timeout=1.2)
                    await self._query(query_gear_limits(), 0x1C, timeout=1.2)
                    await self._query(query_light_rgb(), 0x1B, 0x05, timeout=1.2)
                    await self._query(query_light_scene(), 0x1B, 0x04, timeout=1.2)
                    await self._query(query_timer(), 0x16, timeout=1.2)

                if not self._metadata_loaded:
                    await self._load_metadata()
                self._metadata_loaded = bool(
                    self.state.firmware or self.state.serial or self.state.hardware
                )
            finally:
                self._schedule_disconnect()
        return self.state

    async def _load_metadata(self) -> None:
        """Read versions/serial/MAC once; failures are retried on next poll."""
        await self._query(query_version(), 0x06)
        await self._query(query_hardware(), 0x20)
        await self._query(query_software(), 0x21)
        await self._query(query_serial(), 0x07, 0x02)
        await self._query(query_hw_version(), 0x07, 0x03)
        await self._query(query_mac(), 0x07, 0x06)
        await self._query(query_mcu_sw(), 0x07, 0x0A)
        await self._query(query_mcu_hw(), 0x07, 0x0B)
        await self._query(query_ble_mac(), 0x14)
        await self._query(query_pact(), 0xEF)

    # -------------------------------------------------------------- commands
    async def async_set_power(self, on: bool) -> None:
        async with self._lock:
            await self._ensure_connected()
            await self._write(build_power(on))
            if on:
                # Wait up to two seconds for the state notification.  If the
                # tank is empty the firmware keeps the device in protection
                # mode and no state is returned; the advertisement will then
                # keep reporting off.
                await self._wait_for(0x01, None, 2.0)
                self.state.power = True
                self.state.misting = True
            else:
                self.state.power = False
                self.state.misting = False
            self._schedule_disconnect()
        self._notify_state()

    async def async_set_work_mode(
        self,
        mode: str,
        *,
        gear: int | None = None,
        target_humidity: int | None = None,
        custom_payload: bytes | None = None,
    ) -> None:
        code = NAME_TO_WORK_MODE.get(mode)
        if code is None:
            raise ValueError(f"unknown work mode: {mode}")
        if code == WORK_MODE_MANUAL:
            level = gear or self.state.manual_gear or self.state.low_gear or 5
            frame = build_manual_mode(level)
        elif code == WORK_MODE_AUTO:
            humidity = target_humidity or self.state.target_humidity or 55
            humidity = max(MIN_HUMIDITY, min(MAX_HUMIDITY, int(humidity)))
            frame = build_auto_mode(humidity)
        else:
            payload = custom_payload or self.state.custom_payload or DEFAULT_CUSTOM_PAYLOAD
            frame = build_custom_mode(payload)

        async with self._lock:
            await self._ensure_connected()
            await self._write(frame)
            await asyncio.sleep(0.25)
            await self._query(query_mode(), 0x05, 0x00)
            self._schedule_disconnect()
        self.state.work_mode = mode
        self.state.work_mode_code = code
        if code == WORK_MODE_MANUAL:
            self.state.manual_gear = gear or self.state.manual_gear
        elif code == WORK_MODE_AUTO:
            self.state.target_humidity = target_humidity or self.state.target_humidity
        self._notify_state()

    async def async_set_target_humidity(self, humidity: int) -> None:
        humidity = max(MIN_HUMIDITY, min(MAX_HUMIDITY, int(humidity)))
        async with self._lock:
            await self._ensure_connected()
            await self._write(build_auto_mode(humidity))
            await asyncio.sleep(0.25)
            await self._query(query_target_humidity(), 0x05, 0x03)
            self._schedule_disconnect()
        self.state.target_humidity = humidity
        self.state.work_mode = "auto"
        self.state.work_mode_code = WORK_MODE_AUTO
        self._notify_state()

    async def async_set_manual_gear(self, gear: int) -> None:
        gear = max(MIN_MIST_LEVEL, min(MAX_MIST_LEVEL, int(gear)))
        async with self._lock:
            await self._ensure_connected()
            await self._write(build_manual_mode(gear))
            await asyncio.sleep(0.25)
            await self._query(query_manual_gear(), 0x05, 0x01)
            self._schedule_disconnect()
        self.state.manual_gear = gear
        self.state.work_mode = "manual"
        self.state.work_mode_code = WORK_MODE_MANUAL
        self._notify_state()

    async def async_set_custom_params(
        self,
        high_gear: int,
        low_gear: int,
        high_duration: int,
        low_duration: int,
    ) -> None:
        frame = build_custom_mode_params(
            high_gear, low_gear, high_duration, low_duration
        )
        async with self._lock:
            await self._ensure_connected()
            await self._write(frame)
            await asyncio.sleep(0.25)
            await self._query(query_custom_mode(), 0x05, 0x02)
            self._schedule_disconnect()
        self.state.work_mode = "custom"
        self.state.work_mode_code = WORK_MODE_CUSTOM
        self.state.custom_high_gear = high_gear
        self.state.custom_low_gear = low_gear
        self.state.custom_high_duration = high_duration
        self.state.custom_low_duration = low_duration
        self._notify_state()

    async def async_set_light_power(self, on: bool) -> None:
        async with self._lock:
            await self._ensure_connected()
            await self._write(build_light_power(on))
            await asyncio.sleep(0.25)
            await self._query(query_light(), 0x1B, 0x01)
            self._schedule_disconnect()
        self.state.night_light_on = on
        self._notify_state()

    async def async_set_light_brightness(self, brightness: int) -> None:
        brightness = max(1, min(100, int(brightness)))
        async with self._lock:
            await self._ensure_connected()
            await self._write(build_light_brightness(brightness))
            await asyncio.sleep(0.25)
            await self._query(query_light(), 0x1B, 0x01)
            self._schedule_disconnect()
        self.state.night_light_on = True
        self.state.night_light_brightness = brightness
        self._notify_state()

    async def async_set_light_rgb(self, red: int, green: int, blue: int) -> None:
        async with self._lock:
            await self._ensure_connected()
            await self._write(build_light_rgb(red, green, blue))
            await asyncio.sleep(0.25)
            await self._query(query_light_rgb(), 0x1B, 0x05)
            self._schedule_disconnect()
        self.state.night_light_on = True
        self.state.night_light_rgb = (red, green, blue)
        self._notify_state()

    async def async_set_light_scene(self, scene: int) -> None:
        if not self.scenes_enabled:
            raise ValueError("experimental night-light scenes are disabled")
        scene = max(1, min(5, int(scene)))
        async with self._lock:
            await self._ensure_connected()
            await self._write(build_light_scene(scene))
            await asyncio.sleep(0.25)
            await self._query(query_light_scene(), 0x1B, 0x04)
            self._schedule_disconnect()
        self.state.night_light_on = True
        self.state.night_light_scene = scene
        self._notify_state()

    async def async_set_auto_stop(self, on: bool) -> None:
        if not self.auto_stop_enabled:
            raise ValueError("experimental Auto Stop is disabled")
        async with self._lock:
            await self._ensure_connected()
            await self._write(build_auto_stop(on))
            await asyncio.sleep(0.25)
            await self._query(query_flags(), 0x17)
            self._schedule_disconnect()
        self.state.auto_stop = on
        self._notify_state()


class GoveeH7140Coordinator(DataUpdateCoordinator[H7140State]):
    """DataUpdateCoordinator for the H7140."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        ble_device: Any,
        address: str,
        name: str,
    ) -> None:
        options = {**entry.data, **entry.options}
        poll = int(options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL))
        self.config_entry = entry
        self.client = GoveeH7140Client(hass, address, name, ble_device, options)
        self.client.set_state_callback(self._handle_client_state)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {address}",
            update_interval=timedelta(seconds=poll),
        )

    @property
    def available(self) -> bool:
        return self.client.available

    @callback
    def _handle_client_state(self) -> None:
        self.async_set_updated_data(self.client.state)

    async def _async_update_data(self) -> H7140State:
        try:
            return await self.client.async_update()
        except UpdateFailed:
            if self.client.available:
                return self.client.state
            raise
        except (BleakError, TimeoutError, EOFError, OSError) as err:
            if self.client.available:
                _LOGGER.debug("Using advertisement state: %s", err)
                return self.client.state
            raise UpdateFailed(f"communication with H7140 failed: {err}") from err

    @callback
    def async_handle_advertisement(
        self, service_info: BluetoothServiceInfoBleak
    ) -> None:
        self.client.handle_advertisement(service_info)

    async def async_shutdown(self) -> None:
        await self.client.async_stop()
        await super().async_shutdown()
