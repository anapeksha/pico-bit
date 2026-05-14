"""
Loot data encryption and compression at rest.

Uses a SHA-256-based stream cipher so the same code runs on both
MicroPython (Pico) and CPython (tests / dev host) without additional
dependencies.

File format:
    b'PCB1' (4 magic bytes)
    + nonce  (4 bytes, random per write)
    + XOR-encrypted payload (variable length)

Keystream generation: concatenate SHA-256(key + nonce + 2-byte counter)
blocks until enough bytes are available, then XOR with the compressed
plaintext.

Compression: zlib on CPython, deflate.ZLIB on MicroPython. Falls back to
no compression if neither module is available (e.g., stripped builds).

Backward compatibility: files that do not start with the magic header are
treated as unencrypted plaintext so existing unencrypted loot.json files
continue to be readable.
"""

import asyncio
import hashlib
import os

_MAGIC = b'PCB1'
_NONCE_LEN = 4
_HEADER_LEN = len(_MAGIC) + _NONCE_LEN  # 8


def derive_key(ssid: str, password: str) -> bytes:
    """Return a 32-byte AES/XOR key derived from the device AP credentials."""
    return hashlib.sha256((ssid + ':' + password).encode('utf-8')).digest()


async def _keystream(key: bytes, nonce: bytes, length: int) -> bytearray:
    out = bytearray()
    counter = 0
    while len(out) < length:
        ctr = bytes([(counter >> 8) & 0xFF, counter & 0xFF])
        out.extend(hashlib.sha256(key + nonce + ctr).digest())
        counter += 1
        if counter % 8 == 0:
            await asyncio.sleep(0)
    del out[length:]
    return out


def _xor(data: bytes, ks: bytearray) -> bytes:
    result = bytearray(len(data))
    for i in range(len(data)):
        result[i] = data[i] ^ ks[i]
    return bytes(result)


def _compress(data: bytes) -> bytes:
    try:
        import io

        import deflate  # type: ignore[import]

        buf = io.BytesIO()
        with deflate.DeflateIO(buf, deflate.ZLIB) as d:  # type: ignore[attr-defined]
            d.write(data)
        return buf.getvalue()
    except (ImportError, AttributeError):
        pass
    try:
        import zlib  # type: ignore[import]

        return zlib.compress(data, 6)
    except ImportError:
        return data


def _decompress(data: bytes) -> bytes:
    try:
        import io

        import deflate  # type: ignore[import]

        buf = io.BytesIO(data)
        with deflate.DeflateIO(buf, deflate.ZLIB) as d:  # type: ignore[attr-defined]
            return d.read()
    except (ImportError, AttributeError):
        pass
    try:
        import zlib  # type: ignore[import]

        return zlib.decompress(data)
    except ImportError:
        return data


async def encrypt(plaintext: str, key: bytes) -> bytes:
    """Compress and encrypt a plaintext JSON string; return opaque bytes."""
    try:
        nonce = os.urandom(_NONCE_LEN)
    except (AttributeError, OSError):
        nonce = b'\x00' * _NONCE_LEN
    compressed = _compress(plaintext.encode('utf-8'))
    ks = await _keystream(key, nonce, len(compressed))
    return _MAGIC + nonce + _xor(compressed, ks)


async def decrypt(data: bytes, key: bytes) -> str:
    """Decrypt and decompress loot bytes; returns the JSON string.

    Files that do not carry the PCB1 magic are assumed to be unencrypted
    (backward compatibility with pre-encryption loot files).
    """
    if data[:4] != _MAGIC:
        return data.decode('utf-8', 'ignore')
    nonce = data[4:_HEADER_LEN]
    encrypted = data[_HEADER_LEN:]
    ks = await _keystream(key, nonce, len(encrypted))
    compressed = _xor(encrypted, ks)
    return _decompress(compressed).decode('utf-8')
