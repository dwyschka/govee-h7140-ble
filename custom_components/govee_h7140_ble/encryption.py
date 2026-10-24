"""Govee V1 AES-128-ECB + RC4 frame encryption for the H7140.

The H7140 uses Govee's "V1" encrypted session for the control service:

* 16-byte AES-128-ECB for the first 16 bytes of a frame
* an RC4-compatible keystream XOR for the last 4 bytes
* a fixed communication key ``MakingLifeSmarte`` for the ``e7 01`` / ``e7 02``
  handshake
* a per-connection session key, returned in the plaintext ``e7 01`` reply,
  used for all later frames

All frames are still 20 bytes and keep the XOR checksum after decryption.
"""

from __future__ import annotations

import secrets
from typing import Final

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from .protocol import FRAME_LENGTH, checksum

COMMUNICATION_KEY: Final = b"MakingLifeSmarte"
KEY_LENGTH: Final = 16
HANDSHAKE_PAYLOAD_LENGTH: Final = 17
SESSION_KEY_START: Final = 2
SESSION_KEY_END: Final = SESSION_KEY_START + KEY_LENGTH


def _validate_key(key: bytes) -> None:
    if not isinstance(key, bytes) or len(key) != KEY_LENGTH:
        raise ValueError(f"expected a {KEY_LENGTH}-byte key, got {len(key)}")


def _rc4_xor(data: bytes, key: bytes) -> bytes:
    """Apply the Govee RC4-compatible tail transform."""
    state = list(range(256))
    j = 0
    for i in range(256):
        j = (j + state[i] + key[i % len(key)]) & 0xFF
        state[i], state[j] = state[j], state[i]

    i = 0
    j = 0
    transformed = bytearray()
    for value in data:
        i = (i + 1) & 0xFF
        j = (j + state[i]) & 0xFF
        state[i], state[j] = state[j], state[i]
        transformed.append(value ^ state[(state[i] + state[j]) & 0xFF])
    return bytes(transformed)


def validate_frame(frame: bytes) -> None:
    if len(frame) != FRAME_LENGTH:
        raise ValueError(f"expected {FRAME_LENGTH} bytes, got {len(frame)}")
    if checksum(frame[: FRAME_LENGTH - 1]) != frame[-1]:
        raise ValueError(f"invalid checksum: {frame.hex(' ')}")


def encrypt_frame(frame: bytes, key: bytes) -> bytes:
    """Encrypt one checksum-valid 20-byte application frame."""
    _validate_key(key)
    validate_frame(frame)
    encryptor = Cipher(algorithms.AES(key), modes.ECB()).encryptor()
    first = encryptor.update(frame[:KEY_LENGTH]) + encryptor.finalize()
    return first + _rc4_xor(frame[KEY_LENGTH:], key)


def decrypt_frame(frame: bytes, key: bytes) -> bytes:
    """Decrypt and validate one 20-byte Govee V1 wire frame."""
    _validate_key(key)
    if len(frame) != FRAME_LENGTH:
        raise ValueError(f"expected {FRAME_LENGTH} bytes, got {len(frame)}")
    decryptor = Cipher(algorithms.AES(key), modes.ECB()).decryptor()
    first = decryptor.update(frame[:KEY_LENGTH]) + decryptor.finalize()
    plaintext = first + _rc4_xor(frame[KEY_LENGTH:], key)
    validate_frame(plaintext)
    return plaintext


def try_decrypt(frame: bytes, key: bytes) -> bytes | None:
    try:
        return decrypt_frame(frame, key)
    except (ValueError, TypeError):
        return None


def build_handshake_request(
    command: int, *, random_payload: bytes | None = None
) -> bytes:
    """Build a checksum-valid e7 01/e7 02 handshake frame."""
    if command not in (0x01, 0x02):
        raise ValueError(f"unsupported handshake command 0x{command:02x}")
    if random_payload is None:
        random_payload = secrets.token_bytes(HANDSHAKE_PAYLOAD_LENGTH)
    if len(random_payload) != HANDSHAKE_PAYLOAD_LENGTH:
        raise ValueError(
            f"expected {HANDSHAKE_PAYLOAD_LENGTH} handshake payload bytes"
        )
    body = bytes((0xE7, command)) + random_payload
    return body + bytes([checksum(body)])


def parse_session_key(plaintext: bytes) -> bytes:
    """Extract the session key from a plaintext e7 01 response."""
    validate_frame(plaintext)
    if plaintext[:2] != b"\xe7\x01":
        raise ValueError("not an e7 01 session-key response")
    return plaintext[SESSION_KEY_START:SESSION_KEY_END]


def validate_handshake_confirmation(plaintext: bytes, request: bytes) -> None:
    """Validate the e7 02 echo from the device."""
    validate_frame(plaintext)
    if request[:2] != b"\xe7\x02" or plaintext != request:
        raise ValueError("invalid e7 02 handshake confirmation")


def identify_handshake_frame(frame: bytes) -> int | None:
    """Return 1/2 when the wire frame is a V1 handshake frame under the comm key."""
    plaintext = try_decrypt(frame, COMMUNICATION_KEY)
    if plaintext is None or plaintext[:2] not in (b"\xe7\x01", b"\xe7\x02"):
        return None
    return plaintext[1]
