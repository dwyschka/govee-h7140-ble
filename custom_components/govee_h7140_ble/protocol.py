"""Wire protocol for the Govee H7140 Smart Humidifier Lite.

The device speaks Govee's 20-byte BLE application protocol:

    byte 0     0x33 (write), 0x3A (write/read), 0xAA (query response),
               0xEE (notification)
    byte 1     command
    bytes 2-18 payload, zero padded
    byte 19    XOR of bytes 0..18

All frames below were verified against a live H7140 unless marked
"experimental".  The H7140 does not require Govee's AES/RC4 session for the
commands used here (pact value 1/2); it accepts plaintext frames.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Final

from .const import (
    DEFAULT_CUSTOM_PAYLOAD,
    FRAME_LENGTH,
    MANUFACTURER_ID_ON,
    MAX_BRIGHTNESS,
    MAX_HUMIDITY,
    MAX_MIST_LEVEL,
    MIN_BRIGHTNESS,
    MIN_HUMIDITY,
    MIN_MIST_LEVEL,
    NIGHT_LIGHT_SCENES,
    WORK_MODE_AUTO,
    WORK_MODE_CUSTOM,
    WORK_MODE_MANUAL,
    WORK_MODE_TO_NAME,
)

PREFIX_WRITE: Final = 0x33
PREFIX_WRITE_READ: Final = 0x3A
PREFIX_QUERY: Final = 0xAA
PREFIX_NOTIFY: Final = 0xEE

CMD_POWER: Final = 0x01
CMD_MODE: Final = 0x05
CMD_VERSION: Final = 0x06
CMD_INFO: Final = 0x07
CMD_TIMER_16: Final = 0x16
CMD_FLAGS_17: Final = 0x17
CMD_GEAR_LIMITS_1C: Final = 0x1C
CMD_LIGHT: Final = 0x1B
CMD_HARDWARE: Final = 0x20
CMD_SOFTWARE: Final = 0x21
CMD_PACT: Final = 0xEF


def checksum(body: bytes) -> int:
    """Return the XOR checksum of the first 19 bytes."""
    value = 0
    for byte in body:
        value ^= byte
    return value


def build_frame(body: bytes | str) -> bytes:
    """Build a 20-byte frame from a command body (prefix + command + payload)."""
    if isinstance(body, str):
        body = bytes.fromhex(body.replace(" ", "").replace(":", ""))
    if len(body) > FRAME_LENGTH - 1:
        raise ValueError(f"frame body too long: {len(body)}")
    padded = body.ljust(FRAME_LENGTH - 1, b"\x00")
    return padded + bytes([checksum(padded)])


def build_frame_hex(body: bytes | str) -> str:
    return build_frame(body).hex(" ").upper()


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, int(value)))


def build_power(on: bool) -> bytes:
    return build_frame(bytes([PREFIX_WRITE, CMD_POWER, 0x01 if on else 0x00]))


def build_manual_mode(gear: int) -> bytes:
    gear = _clamp(gear, MIN_MIST_LEVEL, MAX_MIST_LEVEL)
    return build_frame(bytes([PREFIX_WRITE_READ, CMD_MODE, WORK_MODE_MANUAL, gear]))


def build_auto_mode(target_humidity: int, auto_stop: bool = False) -> bytes:
    """Set Auto mode target humidity.

    Bit 7 of the target-humidity byte is the device's Auto Stop flag, verified
    on live hardware (55 % -> 0x37, 55 % + Auto Stop -> 0xB7).
    """
    humidity = _clamp(target_humidity, MIN_HUMIDITY, MAX_HUMIDITY)
    value = humidity | (0x80 if auto_stop else 0x00)
    return build_frame(bytes([PREFIX_WRITE_READ, CMD_MODE, WORK_MODE_AUTO, value]))


def build_custom_mode(payload: bytes = DEFAULT_CUSTOM_PAYLOAD) -> bytes:
    if len(payload) != 16:
        raise ValueError("custom-mode payload must be exactly 16 bytes")
    return build_frame(bytes([PREFIX_WRITE_READ, CMD_MODE, WORK_MODE_CUSTOM]) + payload)


def build_custom_mode_params(
    high_gear: int,
    low_gear: int,
    high_duration: int,
    low_duration: int,
) -> bytes:
    """Build the normalized custom-mode payload observed on the device.

    The H7140 mirrors each duration into two adjacent fields; the app's
    Custom mode uses high/low gear plus a duration per stage.
    """
    high_gear = _clamp(high_gear, MIN_MIST_LEVEL, MAX_MIST_LEVEL)
    low_gear = _clamp(low_gear, MIN_MIST_LEVEL, MAX_MIST_LEVEL)
    high_duration = _clamp(high_duration, 5, 720)
    low_duration = _clamp(low_duration, 5, 720)
    payload = bytearray(16)
    payload[1] = high_gear
    payload[3] = high_duration
    payload[5] = high_duration
    payload[6] = low_gear
    payload[8] = low_duration
    payload[10] = low_duration
    payload[11] = 0x01
    payload[12:16] = b"\xff\xff\xff\xff"
    return build_custom_mode(bytes(payload))


def build_target_humidity(target_humidity: int) -> bytes:
    return build_auto_mode(target_humidity)


def build_light_power(on: bool) -> bytes:
    return build_frame(
        bytes([PREFIX_WRITE_READ, CMD_LIGHT, 0x01, 0x01, 0x01 if on else 0x00])
    )


def build_light_brightness(brightness: int) -> bytes:
    level = _clamp(brightness, MIN_BRIGHTNESS, MAX_BRIGHTNESS)
    return build_frame(bytes([PREFIX_WRITE_READ, CMD_LIGHT, 0x01, 0x02, level]))


def build_light_rgb(red: int, green: int, blue: int) -> bytes:
    return build_frame(
        bytes(
            [
                PREFIX_WRITE_READ,
                CMD_LIGHT,
                0x05,
                0x0D,
                _clamp(red, 0, 255),
                _clamp(green, 0, 255),
                _clamp(blue, 0, 255),
            ]
        )
    )


def build_light_scene(scene: int) -> bytes:
    """Experimental: night-light scene selector 0x04 (1..5)."""
    scene = _clamp(scene, 1, 5)
    return build_frame(bytes([PREFIX_WRITE_READ, CMD_LIGHT, 0x04, scene]))


def build_auto_stop(target_humidity: int, on: bool) -> bytes:
    """Set the Auto Stop flag together with the current target humidity."""
    return build_auto_mode(target_humidity, on)


def query_power() -> bytes:
    return build_frame(bytes([PREFIX_QUERY, CMD_POWER]))


def query_mode() -> bytes:
    return build_frame(bytes([PREFIX_QUERY, CMD_MODE, 0x00]))


def query_manual_gear() -> bytes:
    return build_frame(bytes([PREFIX_QUERY, CMD_MODE, 0x01]))


def query_custom_mode() -> bytes:
    return build_frame(bytes([PREFIX_QUERY, CMD_MODE, 0x02]))


def query_target_humidity() -> bytes:
    return build_frame(bytes([PREFIX_QUERY, CMD_MODE, 0x03]))


def query_light() -> bytes:
    return build_frame(bytes([PREFIX_QUERY, CMD_LIGHT, 0x01]))


def query_light_rgb() -> bytes:
    return build_frame(bytes([PREFIX_QUERY, CMD_LIGHT, 0x05]))


def query_light_scene() -> bytes:
    return build_frame(bytes([PREFIX_QUERY, CMD_LIGHT, 0x04]))


def query_flags() -> bytes:
    return build_frame(bytes([PREFIX_QUERY, CMD_FLAGS_17]))


def query_gear_limits() -> bytes:
    return build_frame(bytes([PREFIX_QUERY, CMD_GEAR_LIMITS_1C]))


def query_timer() -> bytes:
    return build_frame(bytes([PREFIX_QUERY, CMD_TIMER_16]))


def query_version() -> bytes:
    return build_frame(bytes([PREFIX_QUERY, CMD_VERSION]))


def query_hardware() -> bytes:
    return build_frame(bytes([PREFIX_QUERY, CMD_HARDWARE]))


def query_software() -> bytes:
    return build_frame(bytes([PREFIX_QUERY, CMD_SOFTWARE]))


def query_serial() -> bytes:
    return build_frame(bytes([PREFIX_QUERY, CMD_INFO, 0x02]))


def query_hw_version() -> bytes:
    return build_frame(bytes([PREFIX_QUERY, CMD_INFO, 0x03]))


def query_mac() -> bytes:
    return build_frame(bytes([PREFIX_QUERY, CMD_INFO, 0x06]))


def query_mcu_sw() -> bytes:
    return build_frame(bytes([PREFIX_QUERY, CMD_INFO, 0x0A]))


def query_mcu_hw() -> bytes:
    return build_frame(bytes([PREFIX_QUERY, CMD_INFO, 0x0B]))


def query_ble_mac() -> bytes:
    return build_frame(bytes([PREFIX_QUERY, 0x14]))


def query_pact() -> bytes:
    return build_frame(bytes([PREFIX_QUERY, CMD_PACT]))


@dataclass(frozen=True)
class Frame:
    """A validated 20-byte Govee frame."""

    raw: bytes

    @classmethod
    def parse(cls, data: bytes, *, validate: bool = True) -> Frame:
        if len(data) < FRAME_LENGTH:
            raise ValueError(f"short frame: {len(data)} bytes")
        raw = bytes(data[:FRAME_LENGTH])
        if validate and checksum(raw[: FRAME_LENGTH - 1]) != raw[-1]:
            raise ValueError(f"bad checksum: {raw.hex(' ')}")
        return cls(raw)

    @property
    def prefix(self) -> int:
        return self.raw[0]

    @property
    def command(self) -> int:
        return self.raw[1]

    @property
    def payload(self) -> bytes:
        return self.raw[2 : FRAME_LENGTH - 1]

    def __str__(self) -> str:
        return self.raw.hex(" ").upper()


def _ascii(data: bytes) -> str | None:
    text = data.split(b"\x00", 1)[0].decode("ascii", errors="ignore").strip()
    return text or None


def _mac(data: bytes) -> str | None:
    if len(data) < 6 or not any(data[:6]):
        return None
    return ":".join(f"{byte:02X}" for byte in reversed(data[:6]))


@dataclass
class AdvState:
    """State decoded from a manufacturer advertisement."""

    manufacturer_id: int
    raw: bytes
    power: bool | None = None
    packet_type: int | None = None
    mode_code: int | None = None
    misting: bool | None = None
    humidity: int | None = None
    rssi: int | None = None

    @classmethod
    def parse(cls, manufacturer_id: int, data: bytes, rssi: int | None = None) -> AdvState:
        raw = bytes(data)
        state = cls(manufacturer_id=manufacturer_id, raw=raw, rssi=rssi)
        if len(raw) >= 3:
            state.packet_type = raw[2]
        if len(raw) >= 4:
            state.mode_code = raw[3]
        if len(raw) >= 5:
            state.misting = bool(raw[4] & 0x01)
        if len(raw) >= 6 and 1 <= raw[5] <= 100:
            state.humidity = raw[5]
        # Observed live packets:
        #   0x8802 ec 00 01 02 01 40  -> powered, humidifying, 64 %rH
        #   0x8802 ec 00 01 02 00 40  -> powered, idle,       64 %rH
        #   0x8843 ec 00 02 01 00 40  -> off / standby beacon
        if state.misting or manufacturer_id == MANUFACTURER_ID_ON and len(raw) >= 3 and raw[2] == 1:
            state.power = True
        elif manufacturer_id != MANUFACTURER_ID_ON and len(raw) >= 3 and raw[2] == 2:
            state.power = False
        return state

    def as_dict(self) -> dict[str, Any]:
        return {
            "manufacturer_id": f"0x{self.manufacturer_id:04X}",
            "raw": self.raw.hex(" ").upper(),
            "power": self.power,
            "packet_type": self.packet_type,
            "mode_code": self.mode_code,
            "misting": self.misting,
            "humidity": self.humidity,
            "rssi": self.rssi,
        }


@dataclass
class H7140State:
    """Last known H7140 state."""

    power: bool | None = None
    work_mode: str | None = None
    work_mode_code: int | None = None
    target_humidity: int | None = None
    manual_gear: int | None = None
    low_gear: int | None = None
    high_gear: int | None = None
    custom_payload: bytes | None = None
    custom_low_gear: int | None = None
    custom_high_gear: int | None = None
    custom_low_duration: int | None = None
    custom_high_duration: int | None = None
    night_light_on: bool | None = None
    night_light_brightness: int | None = None
    night_light_rgb: tuple[int, int, int] | None = None
    night_light_scene: int | None = None
    misting: bool | None = None
    current_humidity: int | None = None
    lack_water: bool | None = None
    auto_stop: bool | None = None
    child_lock: bool | None = None
    timer_raw: bytes | None = None
    firmware: str | None = None
    hardware: str | None = None
    mcu_firmware: str | None = None
    mcu_hardware: str | None = None
    serial: str | None = None
    ble_mac: str | None = None
    wifi_mac: str | None = None
    pact_type: int | None = None
    pact_code: int | None = None
    rssi: int | None = None
    adv: AdvState | None = None
    last_seen: datetime | None = None
    raw_frames: list[str] = field(default_factory=list)

    def add_raw(self, frame: bytes) -> None:
        self.raw_frames.append(bytes(frame).hex(" ").upper())
        if len(self.raw_frames) > 40:
            del self.raw_frames[:-40]

    def apply_frame(self, frame: Frame) -> None:
        self.add_raw(frame.raw)
        if frame.prefix not in (PREFIX_QUERY, PREFIX_NOTIFY, PREFIX_WRITE_READ, PREFIX_WRITE):
            return
        command = frame.command
        payload = frame.payload

        if command == CMD_POWER and frame.prefix == PREFIX_QUERY:
            if len(payload) >= 9:
                # Byte 2/4 are not a stable user-facing power flag across
                # H7140 firmware revisions.  The advertisement's humidifying
                # bit is used for power/action; byte 8 is the water-lack flag.
                self.lack_water = payload[8] == 0x01
            return

        if command == 0x10 and frame.prefix == PREFIX_QUERY:
            # 0x10 returns a compact copy of the status frame; keep it from
            # overwriting the authoritative power state.
            return

        if command == CMD_MODE and frame.prefix in (
            PREFIX_QUERY,
            PREFIX_WRITE_READ,
            PREFIX_NOTIFY,
        ):
            if len(payload) < 1:
                return
            selector = payload[0]
            if selector == 0x00 and len(payload) >= 2:
                code = payload[1]
                if code in WORK_MODE_TO_NAME:
                    self.work_mode_code = code
                    self.work_mode = WORK_MODE_TO_NAME[code]
            elif selector == 0x01 and len(payload) >= 2:
                self.manual_gear = payload[1]
            elif selector == 0x02 and len(payload) >= 17:
                custom = payload[1:17]
                self.custom_payload = custom
                self.custom_high_gear = custom[1] or None
                self.custom_high_duration = custom[3] or None
                self.custom_low_gear = custom[6] or None
                self.custom_low_duration = custom[8] or None
            elif selector == 0x03 and len(payload) >= 2:
                raw_target = payload[1]
                self.target_humidity = raw_target & 0x7F
                self.auto_stop = bool(raw_target & 0x80)
            return

        if command == CMD_FLAGS_17 and frame.prefix in (
            PREFIX_QUERY,
            PREFIX_WRITE_READ,
            PREFIX_NOTIFY,
        ):
            # The exact meaning of these two flags is not decoded yet.  Auto
            # Stop is carried in bit 7 of the target-humidity byte.
            if len(payload) >= 2:
                self.child_lock = bool(payload[1])
            return

        if command == CMD_GEAR_LIMITS_1C and frame.prefix in (
            PREFIX_QUERY,
            PREFIX_WRITE_READ,
            PREFIX_NOTIFY,
        ):
            if len(payload) >= 2:
                self.low_gear = payload[0]
                self.high_gear = payload[1]
            return

        if command == CMD_LIGHT and frame.prefix in (
            PREFIX_QUERY,
            PREFIX_WRITE_READ,
            PREFIX_NOTIFY,
        ):
            if len(payload) < 1:
                return
            selector = payload[0]
            if selector == 0x01 and len(payload) >= 3:
                self.night_light_on = payload[1] == 0x01
                if 1 <= payload[2] <= 100:
                    self.night_light_brightness = payload[2]
            elif selector == 0x05 and len(payload) >= 5:
                if payload[1] == 0x0D:
                    self.night_light_rgb = (payload[2], payload[3], payload[4])
            elif selector == 0x04 and len(payload) >= 2:
                self.night_light_scene = payload[1] or None
            return

        if command == CMD_TIMER_16:
            self.timer_raw = payload
            return

        if command == CMD_VERSION and frame.prefix == PREFIX_QUERY:
            self.firmware = _ascii(payload)
            return

        if command == CMD_HARDWARE and frame.prefix == PREFIX_QUERY:
            self.hardware = _ascii(payload)
            return

        if command == CMD_SOFTWARE and frame.prefix == PREFIX_QUERY:
            self.firmware = self.firmware or _ascii(payload)
            return

        if command == CMD_INFO and frame.prefix == PREFIX_QUERY:
            if len(payload) < 1:
                return
            selector = payload[0]
            data = payload[1:]
            if selector == 0x02:
                if len(data) >= 8 and any(data[:8]):
                    self.serial = data[:8].hex(" ").upper()
            elif selector == 0x03:
                self.hardware = _ascii(data) or self.hardware
            elif selector == 0x06:
                self.ble_mac = _mac(data) or self.ble_mac
            elif selector == 0x0A:
                self.mcu_firmware = _ascii(data)
            elif selector == 0x0B:
                self.mcu_hardware = _ascii(data)
            return

        if command == 0x14 and frame.prefix == PREFIX_QUERY:
            self.ble_mac = _mac(payload) or self.ble_mac
            return

        if command == CMD_PACT and frame.prefix == PREFIX_QUERY:
            if len(payload) >= 3:
                self.pact_type = (payload[0] << 8) | payload[1]
                self.pact_code = payload[2]
            return

    def apply_adv(self, adv: AdvState) -> None:
        self.adv = adv
        self.rssi = adv.rssi
        if adv.power is not None:
            self.power = adv.power
        if adv.misting is not None:
            self.misting = adv.misting
            # Byte 4 is the humidifying/active bit.  A true bit confirms that
            # the appliance is on; a false bit can also mean "target reached /
            # idle", so it must not clear an explicitly switched-on state.
            # 33 01 00 sets power=False explicitly.
            if adv.misting:
                self.power = True
        elif adv.power is not None:
            self.power = adv.power
        if adv.humidity is not None:
            self.current_humidity = adv.humidity

    def as_dict(self) -> dict[str, Any]:
        return {
            "power": self.power,
            "work_mode": self.work_mode,
            "work_mode_code": self.work_mode_code,
            "target_humidity": self.target_humidity,
            "manual_gear": self.manual_gear,
            "low_gear": self.low_gear,
            "high_gear": self.high_gear,
            "custom_payload": self.custom_payload.hex(" ").upper() if self.custom_payload else None,
            "custom_low_gear": self.custom_low_gear,
            "custom_high_gear": self.custom_high_gear,
            "custom_low_duration": self.custom_low_duration,
            "custom_high_duration": self.custom_high_duration,
            "night_light_on": self.night_light_on,
            "night_light_brightness": self.night_light_brightness,
            "night_light_rgb": list(self.night_light_rgb) if self.night_light_rgb else None,
            "night_light_scene": self.night_light_scene,
            "misting": self.misting,
            "current_humidity": self.current_humidity,
            "lack_water": self.lack_water,
            "auto_stop": self.auto_stop,
            "child_lock": self.child_lock,
            "timer_raw": self.timer_raw.hex(" ").upper() if self.timer_raw else None,
            "firmware": self.firmware,
            "hardware": self.hardware,
            "mcu_firmware": self.mcu_firmware,
            "mcu_hardware": self.mcu_hardware,
            "serial": self.serial,
            "ble_mac": self.ble_mac,
            "pact_type": self.pact_type,
            "pact_code": self.pact_code,
            "rssi": self.rssi,
            "advertisement": self.adv.as_dict() if self.adv else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
        }


def scene_name(scene: int | None) -> str | None:
    if scene is None:
        return None
    return NIGHT_LIGHT_SCENES.get(scene)
