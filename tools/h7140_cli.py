#!/usr/bin/env python3
"""Standalone Govee H7140 BLE client / protocol library CLI.

The Home Assistant integration uses the same protocol and encryption modules.
This CLI is the Mac-side reference tool used to verify commands against real
hardware without starting Home Assistant.

Install:
    python3 -m venv .venv
    .venv/bin/pip install bleak cryptography

Examples:
    python tools/h7140_cli.py scan
    python tools/h7140_cli.py --name 4491 state
    python tools/h7140_cli.py --name 4491 light on
    python tools/h7140_cli.py --name 4491 mode auto 55
    python tools/h7140_cli.py --name 4491 custom 8 5 60 60
    python tools/h7140_cli.py --name 4491 raw "AA 05 00"

The client auto-detects plaintext vs. Govee V1 encryption and performs the
e7 01/e7 02 handshake when needed.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import importlib.util
import sys
import types
from pathlib import Path
from typing import Any, Self

from bleak import BleakClient, BleakScanner

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "govee_h7140_ble"

# Load the HA-independent protocol modules without executing the HA __init__.
pkg = types.ModuleType("govee_h7140_ble")
pkg.__path__ = [str(ROOT)]  # type: ignore[attr-defined]
sys.modules["govee_h7140_ble"] = pkg
for module_name in ("const", "protocol", "encryption"):
    spec = importlib.util.spec_from_file_location(
        f"govee_h7140_ble.{module_name}", ROOT / f"{module_name}.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"govee_h7140_ble.{module_name}"] = module
    spec.loader.exec_module(module)

from govee_h7140_ble.encryption import (
    COMMUNICATION_KEY,
    build_handshake_request,
    encrypt_frame,
    parse_session_key,
    try_decrypt,
)
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
    query_custom_mode,
    query_flags,
    query_gear_limits,
    query_hardware,
    query_light,
    query_light_rgb,
    query_light_scene,
    query_manual_gear,
    query_mode,
    query_pact,
    query_power,
    query_serial,
    query_software,
    query_target_humidity,
    query_timer,
    query_version,
)

WRITE = "00010203-0405-0607-0809-0a0b0c0d2b11"
NOTIFY = "00010203-0405-0607-0809-0a0b0c0d2b10"


class Session:
    """A minimal standalone H7140 GATT session."""

    def __init__(self, device: Any) -> None:
        self.device = device
        self.client: BleakClient | None = None
        self.encryption = "unknown"
        self.session_key: bytes | None = None
        self.state = H7140State()
        self.frames: list[Frame] = []

    async def __aenter__(self) -> Self:
        self.client = BleakClient(self.device, timeout=20)
        await self.client.connect()
        await self.client.start_notify(NOTIFY, self._notify)
        await asyncio.sleep(0.35)
        await self.negotiate()
        return self

    async def __aexit__(self, *_exc: object) -> None:
        if self.client is not None:
            with contextlib.suppress(Exception):
                await self.client.stop_notify(NOTIFY)
            with contextlib.suppress(Exception):
                await self.client.disconnect()

    def _notify(self, _sender: Any, data: bytearray) -> None:
        raw = bytes(data)
        plaintext = self._decode(raw)
        if plaintext is None:
            print(f"  RX unparsed {raw.hex(' ')}")
            return
        try:
            frame = Frame.parse(plaintext)
        except ValueError:
            print(f"  RX invalid   {plaintext.hex(' ')}")
            return
        self.state.apply_frame(frame)
        self.frames.append(frame)
        print(f"  RX {frame}")

    def _decode(self, raw: bytes) -> bytes | None:
        if self.encryption == "v1":
            if self.session_key is not None:
                plaintext = try_decrypt(raw, self.session_key)
                if plaintext is not None:
                    return plaintext
            return try_decrypt(raw, COMMUNICATION_KEY)
        if self.encryption == "plaintext":
            return raw
        try:
            Frame.parse(raw)
            return raw
        except ValueError:
            return try_decrypt(raw, COMMUNICATION_KEY)

    async def _write_wire(self, wire: bytes) -> None:
        assert self.client is not None
        print(f"  TX {wire.hex(' ')}")
        await self.client.write_gatt_char(WRITE, wire, response=False)

    async def _write(self, frame: bytes) -> None:
        if self.encryption == "v1" and self.session_key is not None:
            await self._write_wire(encrypt_frame(frame, self.session_key))
        else:
            await self._write_wire(frame)

    async def negotiate(self) -> None:
        self.frames.clear()
        request = build_handshake_request(0x01)
        for _ in range(2):
            await self._write_wire(encrypt_frame(request, COMMUNICATION_KEY))
            await asyncio.sleep(1.0)
            for frame in list(self.frames):
                if frame.raw[:2] != b"\xe7\x01":
                    continue
                try:
                    self.session_key = parse_session_key(frame.raw)
                except ValueError:
                    continue
                break
            if self.session_key is not None:
                break
        if self.session_key is not None:
            confirm = build_handshake_request(0x02)
            await self._write_wire(encrypt_frame(confirm, COMMUNICATION_KEY))
            await asyncio.sleep(0.5)
            self.encryption = "v1"
            self.frames.clear()
            return

        # Plaintext fallback.
        self.frames.clear()
        await self._write_wire(query_power())
        await asyncio.sleep(1.0)
        if any(frame.command == 0x01 for frame in self.frames):
            self.encryption = "plaintext"
            return
        raise RuntimeError("no plaintext or V1 protocol response")

    async def query(self, body: bytes, command: int, selector: int | None = None) -> Frame | None:
        self.frames.clear()
        await self._write(body)
        await asyncio.sleep(0.45)
        for frame in self.frames:
            if frame.command != command:
                continue
            if selector is not None and frame.payload[:1] != bytes([selector]):
                continue
            return frame
        return None

    async def read_state(self) -> H7140State:
        for body, command, selector in [
            (query_power(), 0x01, None),
            (query_mode(), 0x05, 0x00),
            (query_manual_gear(), 0x05, 0x01),
            (query_custom_mode(), 0x05, 0x02),
            (query_target_humidity(), 0x05, 0x03),
            (query_flags(), 0x17, None),
            (query_gear_limits(), 0x1C, None),
            (query_timer(), 0x16, None),
            (query_light(), 0x1B, 0x01),
            (query_light_scene(), 0x1B, 0x04),
            (query_light_rgb(), 0x1B, 0x05),
            (query_version(), 0x06, None),
            (query_hardware(), 0x20, None),
            (query_software(), 0x21, None),
            (query_serial(), 0x07, 0x02),
            (query_pact(), 0xEF, None),
        ]:
            await self.query(body, command, selector)
        return self.state


async def find_device(name: str | None, address: str | None) -> Any:
    if address:
        return await BleakScanner.find_device_by_address(address, timeout=15)
    found = await BleakScanner.discover(timeout=15, return_adv=True)
    candidates = [
        (d, adv)
        for d, adv in found.values()
        if "H7140" in (d.name or "").upper()
        and (name is None or name.lower() in (d.name or "").lower())
    ]
    if not candidates:
        raise SystemExit("No H7140 found")
    for d, adv in candidates:
        print(
            f"Candidate {d.name} {d.address} "
            f"{ {hex(k): v.hex() for k, v in adv.manufacturer_data.items()} }"
        )
    return candidates[0][0]


async def run(args: argparse.Namespace) -> None:
    device = await find_device(args.name, args.address)
    if device is None:
        raise SystemExit("Device not found")
    print("Connecting", device.name)
    async with Session(device) as session:
        print("Protocol", session.encryption)
        if args.command == "state":
            state = await session.read_state()
            print(state.as_dict())
        elif args.command == "raw":
            raw = bytes.fromhex(args.value.replace(" ", ""))
            frame = raw if len(raw) == 20 else build_frame(raw)
            await session._write(frame)
            await asyncio.sleep(0.8)
        elif args.command == "power":
            await session._write(build_power(args.value == "on"))
            await asyncio.sleep(0.8)
        elif args.command == "mode":
            if args.value == "auto":
                await session._write(build_auto_mode(args.number or 55))
            elif args.value == "manual":
                await session._write(build_manual_mode(args.number or 5))
            else:
                await session._write(
                    build_custom_mode_params(
                        getattr(args, "high", None) or 8,
                        getattr(args, "low", None) or 5,
                        getattr(args, "high_duration", None) or 60,
                        getattr(args, "low_duration", None) or 60,
                    )
                )
            await asyncio.sleep(0.8)
        elif args.command == "target":
            await session._write(build_auto_mode(args.number or 55))
            await asyncio.sleep(0.8)
        elif args.command == "gear":
            await session._write(build_manual_mode(args.number or 5))
            await asyncio.sleep(0.8)
        elif args.command == "custom":
            await session._write(
                build_custom_mode_params(
                    args.high or 8,
                    args.low or 5,
                    args.high_duration or 60,
                    args.low_duration or 60,
                )
            )
            await asyncio.sleep(0.8)
        elif args.command == "light":
            if args.value == "on":
                await session._write(build_light_power(True))
            elif args.value == "off":
                await session._write(build_light_power(False))
            elif args.value == "brightness":
                await session._write(build_light_brightness(args.number or 50))
            elif args.value == "rgb":
                if args.rgb is None:
                    raise SystemExit("rgb needs R G B via --rgb")
                await session._write(build_light_rgb(*args.rgb))
            await asyncio.sleep(0.8)
        else:
            raise SystemExit(f"unknown command {args.command}")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--name", help="substring of the BLE name, e.g. 4491")
    p.add_argument("--address", help="exact BLE address / UUID")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("scan", help="list H7140 advertisements")
    sub.add_parser("state", help="read all state")
    raw = sub.add_parser("raw", help="send raw hex")
    raw.add_argument("value")
    power = sub.add_parser("power")
    power.add_argument("value", choices=["on", "off"])
    mode = sub.add_parser("mode")
    mode.add_argument("value", choices=["manual", "auto", "custom"])
    mode.add_argument("number", nargs="?", type=int)
    target = sub.add_parser("target")
    target.add_argument("number", type=int)
    gear = sub.add_parser("gear")
    gear.add_argument("number", type=int)
    custom = sub.add_parser("custom")
    custom.add_argument("high", type=int)
    custom.add_argument("low", type=int)
    custom.add_argument("high_duration", type=int)
    custom.add_argument("low_duration", type=int)
    light = sub.add_parser("light")
    light.add_argument("value", choices=["on", "off", "brightness", "rgb"])
    light.add_argument("number", nargs="?", type=int)
    light.add_argument("--rgb", nargs=3, type=int, metavar=("R", "G", "B"))
    return p


async def scan() -> None:
    found = await BleakScanner.discover(timeout=15, return_adv=True)
    for d, adv in found.values():
        if "H7140" in (d.name or "").upper():
            parsed = []
            for manufacturer_id, data in adv.manufacturer_data.items():
                parsed.append(AdvState.parse(manufacturer_id, data, adv.rssi))
            print(d.name, d.address, adv.rssi, [a.as_dict() for a in parsed])


def main() -> None:
    args = parser().parse_args()
    if args.command == "scan":
        asyncio.run(scan())
        return
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
