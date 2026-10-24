"""Encryption tests using Govee V1 frames captured from a live H7140."""

from __future__ import annotations

import pytest
from govee_h7140_ble.encryption import (
    COMMUNICATION_KEY,
    build_handshake_request,
    decrypt_frame,
    encrypt_frame,
    identify_handshake_frame,
    parse_session_key,
    try_decrypt,
    validate_frame,
)


def f(hex_str: str) -> bytes:
    return bytes.fromhex(hex_str.replace(" ", ""))


COMM_FRAME = f(
    "c9 4e 0a 20 96 04 df df f3 07 ef 3c a0 20 ea 8b 68 ee 40 60"
)
COMM_PLAIN = f(
    "aa 01 00 00 01 03 6c fa 00 00 00 00 00 00 00 00 00 00 00 3f"
)
SESSION_KEY = f("70 9d cb f8 25 53 80 ad db 08 35 62 90 bd ea 18")
SESSION_FRAME = f(
    "da 6c 67 38 49 8d f7 a0 18 83 8b 34 1b f2 af ab 0f d5 3d 22"
)
SESSION_PLAIN = f(
    "aa 01 00 00 01 03 6c f3 00 00 00 00 00 00 00 00 00 00 00 36"
)
HANDSHAKE_01 = f(
    "c7 8c 6a 75 d7 33 7b 96 d1 e9 92 c1 f0 2c 70 67 a2 19 59 ce"
)


def test_communication_key_decrypt() -> None:
    assert decrypt_frame(COMM_FRAME, COMMUNICATION_KEY) == COMM_PLAIN


def test_session_key_decrypt() -> None:
    assert decrypt_frame(SESSION_FRAME, SESSION_KEY) == SESSION_PLAIN


def test_roundtrip() -> None:
    encrypted = encrypt_frame(COMM_PLAIN, COMMUNICATION_KEY)
    assert len(encrypted) == 20
    assert decrypt_frame(encrypted, COMMUNICATION_KEY) == COMM_PLAIN
    assert try_decrypt(COMM_FRAME, b"0123456789abcdef") is None


def test_handshake_request() -> None:
    frame = build_handshake_request(0x01, random_payload=bytes(range(17)))
    validate_frame(frame)
    assert frame[:2] == b"\xe7\x01"
    assert len(frame) == 20
    assert identify_handshake_frame(HANDSHAKE_01) == 0x01


def test_parse_session_key() -> None:
    plaintext = decrypt_frame(HANDSHAKE_01, COMMUNICATION_KEY)
    assert parse_session_key(plaintext) == f(
        "4f 7d aa d7 05 32 5f 8c ba e7 14 42 6f 9c ca f7"
    )
    with pytest.raises(ValueError):
        parse_session_key(COMM_PLAIN)
