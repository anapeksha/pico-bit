"""Tests for the loot_crypto encryption/decryption module."""

import json

import pytest

from server.loot_crypto import decrypt, derive_key, encrypt


def test_derive_key_is_deterministic() -> None:
    k1 = derive_key('PicoBit', 'secret')
    k2 = derive_key('PicoBit', 'secret')
    assert k1 == k2
    assert len(k1) == 32


def test_derive_key_differs_by_ssid_and_password() -> None:
    assert derive_key('Net1', 'pass') != derive_key('Net2', 'pass')
    assert derive_key('Net', 'pass1') != derive_key('Net', 'pass2')


def test_encrypt_produces_magic_header() -> None:
    key = derive_key('PicoBit', 'test')
    data = encrypt('{"hello": "world"}', key)
    assert data[:4] == b'PCB1'


def test_encrypt_decrypt_roundtrip() -> None:
    key = derive_key('PicoBit', 'roundtrip')
    plaintext = json.dumps({'system': {'hostname': 'target'}, 'timestamp': 12345})
    encrypted = encrypt(plaintext, key)
    recovered = decrypt(encrypted, key)
    assert json.loads(recovered) == json.loads(plaintext)


def test_decrypt_roundtrip_with_unicode() -> None:
    key = derive_key('SSID', 'pw')
    text = '{"msg": "héllo wörld 🔑"}'
    assert json.loads(decrypt(encrypt(text, key), key))['msg'] == 'héllo wörld 🔑'


def test_decrypt_backward_compat_with_plaintext_file() -> None:
    key = derive_key('PicoBit', 'test')
    plaintext = '{"timestamp": 999}'
    # Simulate an old unencrypted file stored as UTF-8 bytes
    raw = plaintext.encode('utf-8')
    assert decrypt(raw, key) == plaintext


def test_different_nonces_produce_different_ciphertext() -> None:
    key = derive_key('PicoBit', 'nonce-test')
    text = '{"a": 1}'
    # Two encryptions of the same plaintext should differ (random nonce)
    c1 = encrypt(text, key)
    c2 = encrypt(text, key)
    # Both decrypt correctly
    assert decrypt(c1, key) == text
    assert decrypt(c2, key) == text
    # Ciphertexts differ (with overwhelming probability)
    assert c1[4:] != c2[4:]  # nonce or body differs


def test_wrong_key_produces_garbage_not_valid_json() -> None:
    good_key = derive_key('PicoBit', 'correct')
    bad_key = derive_key('PicoBit', 'wrong')
    encrypted = encrypt('{"x": 1}', good_key)
    # Wrong key → XOR produces garbage → decompression or JSON parse must fail.
    # Accept any exception from either step.
    try:
        recovered = decrypt(encrypted, bad_key)
        json.loads(recovered)
        pytest.fail('Expected an error when decrypting with wrong key')
    except Exception:
        pass
