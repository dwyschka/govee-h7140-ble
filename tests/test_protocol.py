"""Protocol tests using frames captured from a live Govee H7140."""

from __future__ import annotations

import pytest
from govee_h7140_ble.protocol import (
    AdvState,
    Frame,
    H7140State,
    build_auto_mode,
    build_custom_mode_params,
    build_frame,
    build_light_brightness,
    build_light_power,
    build_light_rgb,
    build_manual_mode,
    build_power,
    checksum,
)


def f(hex_str: str) -> bytes:
    return bytes.fromhex(hex_str.replace(" ", ""))


def test_checksum_and_build() -> None:
    assert build_frame("aa 01") == f(
        "aa 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 ab"
    )
    assert checksum(build_frame("aa 01")[:19]) == 0xAB
    assert build_power(True) == f(
        "33 01 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 33"
    )
    assert build_power(False) == f(
        "33 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 32"
    )
    assert build_auto_mode(55) == f(
        "3a 05 03 37 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 0b"
    )
    assert build_manual_mode(5) == f(
        "3a 05 01 05 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 3b"
    )
    assert build_light_power(True) == f(
        "3a 1b 01 01 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 20"
    )
    assert build_light_brightness(50) == f(
        "3a 1b 01 02 32 00 00 00 00 00 00 00 00 00 00 00 00 00 00 10"
    )
    assert build_light_rgb(255, 0, 0) == f(
        "3a 1b 05 0d ff 00 00 00 00 00 00 00 00 00 00 00 00 00 00 d6"
    )


def test_parse_rejects_bad_checksum() -> None:
    with pytest.raises(ValueError):
        Frame.parse(f("aa 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00"))


def test_status_frame() -> None:
    state = H7140State()
    state.apply_frame(
        Frame.parse(
            f("aa 01 00 00 01 03 78 96 00 00 01 00 00 00 00 00 00 00 00 46")
        )
    )
    assert state.lack_water is True
    assert state.power is None


def test_mode_frames() -> None:
    state = H7140State()
    state.apply_frame(
        Frame.parse(
            f("aa 05 00 03 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 ac")
        )
    )
    assert state.work_mode == "auto"
    state.apply_frame(
        Frame.parse(
            f("aa 05 01 05 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 ab")
        )
    )
    assert state.manual_gear == 5
    state.apply_frame(
        Frame.parse(
            f("aa 05 02 00 08 00 3c 00 00 05 00 3c 00 00 01 ff ff ff ff a1")
        )
    )
    assert state.custom_high_gear == 8
    assert state.custom_low_gear == 5
    assert state.custom_high_duration == 60
    assert state.custom_low_duration == 60
    state.apply_frame(
        Frame.parse(
            f("aa 05 03 37 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 9b")
        )
    )
    assert state.target_humidity == 55


def test_light_frames() -> None:
    state = H7140State()
    state.apply_frame(
        Frame.parse(
            f("aa 1b 01 00 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 b1")
        )
    )
    assert state.night_light_on is False
    assert state.night_light_brightness == 1
    state.apply_frame(
        Frame.parse(
            f("aa 1b 01 01 32 00 00 00 00 00 00 00 00 00 00 00 00 00 00 83")
        )
    )
    assert state.night_light_on is True
    assert state.night_light_brightness == 50
    state.apply_frame(
        Frame.parse(
            f("aa 1b 05 0d ff 00 00 00 00 00 00 00 00 00 00 00 00 00 00 46")
        )
    )
    assert state.night_light_rgb == (255, 0, 0)


def test_flags_and_limits() -> None:
    state = H7140State()
    state.apply_frame(
        Frame.parse(
            f("aa 17 01 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 bd")
        )
    )
    assert state.auto_stop is True
    assert state.child_lock is True
    state.apply_frame(
        Frame.parse(
            f("aa 1c 01 08 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 bf")
        )
    )
    assert state.low_gear == 1
    assert state.high_gear == 8


def test_info_frames() -> None:
    state = H7140State()
    state.apply_frame(
        Frame.parse(
            f("aa 06 31 2e 30 30 2e 32 36 00 00 00 00 00 00 00 00 00 00 99")
        )
    )
    assert state.firmware == "1.00.26"
    state.apply_frame(
        Frame.parse(
            f("aa 07 03 31 2e 30 32 2e 30 30 00 00 00 00 00 00 00 00 00 9d")
        )
    )
    assert state.hardware == "1.02.00"
    state.apply_frame(
        Frame.parse(
            f("aa 07 02 90 44 20 07 c9 d0 c9 15 00 00 00 00 00 00 00 00 99")
        )
    )
    assert state.serial == "90 44 20 07 C9 D0 C9 15"
    state.apply_frame(
        Frame.parse(
            f("aa 14 d0 c9 07 20 44 90 00 00 00 00 00 00 00 00 00 00 00 54")
        )
    )
    assert state.ble_mac == "90:44:20:07:C9:D0"
    state.apply_frame(
        Frame.parse(
            f("aa ef 00 01 02 00 00 00 00 00 00 00 00 00 00 00 00 00 00 46")
        )
    )
    assert state.pact_type == 1
    assert state.pact_code == 2


def test_advertisement_on() -> None:
    adv = AdvState.parse(0x8802, f("ec 00 01 02 01 40"), rssi=-63)
    assert adv.power is True
    assert adv.misting is True
    assert adv.humidity == 64
    assert adv.rssi == -63


def test_advertisement_off() -> None:
    adv = AdvState.parse(0x8843, f("ec 00 02 01 00 40"), rssi=-67)
    assert adv.power is False
    assert adv.misting is False
    assert adv.humidity == 64


def test_advertisement_merge() -> None:
    state = H7140State()
    state.power = True
    state.apply_adv(AdvState.parse(0x8802, f("ec 00 01 02 00 40"), rssi=-60))
    assert state.power is True  # idle must not clear an explicit on state
    assert state.misting is False
    assert state.current_humidity == 64
    assert state.rssi == -60


def test_custom_mode_roundtrip() -> None:
    frame = build_custom_mode_params(7, 4, 30, 45)
    parsed = Frame.parse(frame)
    state = H7140State()
    state.apply_frame(parsed)
    assert state.custom_high_gear == 7
    assert state.custom_low_gear == 4
    assert state.custom_high_duration == 30
    assert state.custom_low_duration == 45


def test_custom_mode_push_is_parsed() -> None:
    state = H7140State()
    state.apply_frame(
        Frame.parse(
            build_frame(f("ee 05 02 00 07 00 1e 00 1e 04 00 2d 00 2d 01 ff ff ff ff"))
        )
    )
    assert state.custom_high_gear == 7
    assert state.custom_low_gear == 4
    assert state.custom_high_duration == 30
    assert state.custom_low_duration == 45


def test_light_echo_updates_state() -> None:
    state = H7140State()
    state.apply_frame(
        Frame.parse(
            f("3a 1b 01 01 32 00 00 00 00 00 00 00 00 00 00 00 00 00 00 13")
        )
    )
    assert state.night_light_on is True
    assert state.night_light_brightness == 50
