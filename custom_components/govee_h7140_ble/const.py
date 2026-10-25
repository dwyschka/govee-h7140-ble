"""Constants for the Govee H7140 BLE integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "govee_h7140_ble"
NAME: Final = "Govee H7140 BLE"
MANUFACTURER: Final = "Govee"
MODEL: Final = "H7140"
MODEL_NAME: Final = "Smart Humidifier Lite"

SERVICE_UUID: Final = "00010203-0405-0607-0809-0a0b0c0d1910"
WRITE_CHARACTERISTIC_UUID: Final = "00010203-0405-0607-0809-0a0b0c0d2b11"
NOTIFY_CHARACTERISTIC_UUID: Final = "00010203-0405-0607-0809-0a0b0c0d2b10"

MANUFACTURER_ID_ON: Final = 0x8802
MANUFACTURER_ID_SENSOR: Final = 0x8843
MANUFACTURER_IDS: Final = {MANUFACTURER_ID_ON, MANUFACTURER_ID_SENSOR}

CONF_ADDRESS: Final = "address"
CONF_NAME: Final = "name"
CONF_POLL_INTERVAL: Final = "poll_interval"
CONF_IDLE_DISCONNECT: Final = "idle_disconnect"
CONF_ENABLE_EXPERIMENTAL: Final = "enable_experimental"
CONF_ENABLE_ADV_HUMIDITY: Final = "enable_adv_humidity"
CONF_ENABLE_EXPERIMENTAL_SCENES: Final = "enable_experimental_scenes"
CONF_ENABLE_EXPERIMENTAL_AUTO_STOP: Final = "enable_experimental_auto_stop"

DEFAULT_NAME: Final = "H7140"
DEFAULT_POLL_INTERVAL: Final = 20
DEFAULT_IDLE_DISCONNECT: Final = 25
DEFAULT_ENABLE_EXPERIMENTAL: Final = False
DEFAULT_ENABLE_ADV_HUMIDITY: Final = True
DEFAULT_ENABLE_EXPERIMENTAL_SCENES: Final = False
DEFAULT_ENABLE_EXPERIMENTAL_AUTO_STOP: Final = False

MIN_POLL_INTERVAL: Final = 10
MAX_POLL_INTERVAL: Final = 300
MIN_IDLE_DISCONNECT: Final = 0
MAX_IDLE_DISCONNECT: Final = 300

UPDATE_INTERVAL: Final = timedelta(seconds=DEFAULT_POLL_INTERVAL)
SLOW_POLL_INTERVAL: Final = 300
RESPONSE_TIMEOUT: Final = 2.0
QUERY_GAP: Final = 0.12
COMMAND_GAP: Final = 0.35

FRAME_LENGTH: Final = 20

MIN_HUMIDITY: Final = 40
MAX_HUMIDITY: Final = 80
MIN_MIST_LEVEL: Final = 1
MAX_MIST_LEVEL: Final = 8
MIN_BRIGHTNESS: Final = 1
MAX_BRIGHTNESS: Final = 100

WORK_MODE_MANUAL: Final = 1
WORK_MODE_CUSTOM: Final = 2
WORK_MODE_AUTO: Final = 3

WORK_MODE_TO_NAME: Final = {
    WORK_MODE_MANUAL: "manual",
    WORK_MODE_CUSTOM: "custom",
    WORK_MODE_AUTO: "auto",
}
NAME_TO_WORK_MODE: Final = {v: k for k, v in WORK_MODE_TO_NAME.items()}
WORK_MODES: Final = ["manual", "custom", "auto"]

NIGHT_LIGHT_SCENES: Final = {
    1: "Forest",
    2: "Ocean",
    3: "Wetland",
    4: "Leisurely",
    5: "Sleep",
}
SCENE_NAME_TO_ID: Final = {v: k for k, v in NIGHT_LIGHT_SCENES.items()}

# Default custom-mode payload observed on a live H7140.  The exact meaning of
# every byte is not publicly documented; it is used verbatim when switching to
# Custom mode unless a newer payload has been learned from the device.
DEFAULT_CUSTOM_PAYLOAD: Final = bytes(
    [0x00, 0x08, 0x00, 0x3C, 0x00, 0x3C, 0x05, 0x00, 0x3C, 0x00, 0x3C, 0x01, 0xFF, 0xFF, 0xFF, 0xFF]
)

PLATFORMS: Final = [
    "humidifier",
    "light",
    "sensor",
    "binary_sensor",
    "number",
    "switch",
    "button",
]

# Entity translation keys / names
ATTR_RAW_FRAME: Final = "raw_frame"
