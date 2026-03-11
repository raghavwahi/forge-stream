"""
Unit tests for EncryptionManager (AES-256-GCM).

All tests are pure-Python — no external services, databases, or environment
variables required.
"""

import base64

import pytest

from app.security.encryption import EncryptionManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SECRET_32 = "a" * 32
SECRET_32_B = "b" * 32


# ---------------------------------------------------------------------------
# Basic functionality
# ---------------------------------------------------------------------------


def test_encrypt_decrypt_roundtrip():
    manager = EncryptionManager(SECRET_32)
    plaintext = "sk-openai-test-key-12345"
    encrypted = manager.encrypt(plaintext)
    assert manager.decrypt(encrypted) == plaintext


def test_encrypt_produces_different_ciphertext_each_time():
    """Fresh nonce + salt per call means identical inputs differ."""
    manager = EncryptionManager(SECRET_32)
    e1 = manager.encrypt("same value")
    e2 = manager.encrypt("same value")
    assert e1 != e2


def test_encrypt_empty_string():
    manager = EncryptionManager(SECRET_32)
    encrypted = manager.encrypt("")
    assert manager.decrypt(encrypted) == ""


def test_encrypt_unicode_string():
    manager = EncryptionManager(SECRET_32)
    plaintext = "token-with-unicode-\u00e9\u00e0\u00fc"
    assert manager.decrypt(manager.encrypt(plaintext)) == plaintext


# ---------------------------------------------------------------------------
# Context / AAD binding
# ---------------------------------------------------------------------------


def test_context_binding_correct_context_decrypts():
    manager = EncryptionManager(SECRET_32)
    encrypted = manager.encrypt("secret", context="github_access_token")
    assert manager.decrypt(encrypted, context="github_access_token") == "secret"


def test_context_binding_wrong_context_raises():
    manager = EncryptionManager(SECRET_32)
    encrypted = manager.encrypt("secret", context="field_a")
    with pytest.raises(ValueError):
        manager.decrypt(encrypted, context="field_b")


def test_context_binding_missing_context_raises():
    """Encrypted with context; decrypted without — must fail."""
    manager = EncryptionManager(SECRET_32)
    encrypted = manager.encrypt("secret", context="github_access_token")
    with pytest.raises(ValueError):
        manager.decrypt(encrypted)


def test_no_context_roundtrip():
    manager = EncryptionManager(SECRET_32)
    encrypted = manager.encrypt("secret")
    assert manager.decrypt(encrypted) == "secret"


# ---------------------------------------------------------------------------
# Tamper detection (GCM authentication tag)
# ---------------------------------------------------------------------------


def test_tamper_detection():
    manager = EncryptionManager(SECRET_32)
    encrypted = manager.encrypt("secret")
    # Restore padding, flip the last byte of the raw payload, re-encode.
    padding = "=" * (4 - len(encrypted) % 4) if len(encrypted) % 4 else ""
    data = bytearray(base64.urlsafe_b64decode(encrypted + padding))
    data[-1] ^= 0xFF
    tampered = base64.urlsafe_b64encode(bytes(data)).rstrip(b"=").decode()
    with pytest.raises(ValueError):
        manager.decrypt(tampered)


def test_tamper_nonce_detected():
    manager = EncryptionManager(SECRET_32)
    encrypted = manager.encrypt("secret")
    padding = "=" * (4 - len(encrypted) % 4) if len(encrypted) % 4 else ""
    data = bytearray(base64.urlsafe_b64decode(encrypted + padding))
    # Flip a byte inside the nonce region (bytes 33–44 after the version+salt).
    data[35] ^= 0x01
    tampered = base64.urlsafe_b64encode(bytes(data)).rstrip(b"=").decode()
    with pytest.raises(ValueError):
        manager.decrypt(tampered)


def test_tamper_salt_detected():
    manager = EncryptionManager(SECRET_32)
    encrypted = manager.encrypt("secret")
    padding = "=" * (4 - len(encrypted) % 4) if len(encrypted) % 4 else ""
    data = bytearray(base64.urlsafe_b64decode(encrypted + padding))
    # Flip a byte inside the salt region (bytes 1–32).
    data[5] ^= 0x01
    tampered = base64.urlsafe_b64encode(bytes(data)).rstrip(b"=").decode()
    with pytest.raises(ValueError):
        manager.decrypt(tampered)


# ---------------------------------------------------------------------------
# Wrong master secret
# ---------------------------------------------------------------------------


def test_wrong_master_secret():
    manager1 = EncryptionManager(SECRET_32)
    manager2 = EncryptionManager(SECRET_32_B)
    encrypted = manager1.encrypt("secret")
    with pytest.raises(ValueError):
        manager2.decrypt(encrypted)


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def test_short_master_secret_rejected():
    with pytest.raises(ValueError):
        EncryptionManager("too-short")


def test_exactly_32_char_secret_accepted():
    manager = EncryptionManager("x" * 32)
    assert manager.decrypt(manager.encrypt("ok")) == "ok"


def test_longer_than_32_char_secret_accepted():
    manager = EncryptionManager("y" * 64)
    assert manager.decrypt(manager.encrypt("ok")) == "ok"


def test_invalid_base64_raises():
    manager = EncryptionManager(SECRET_32)
    with pytest.raises(ValueError):
        manager.decrypt("!!!not-valid-base64!!!")


def test_too_short_payload_raises():
    manager = EncryptionManager(SECRET_32)
    # A valid base64 payload that is far too short.
    short = base64.urlsafe_b64encode(b"\x01" + b"\x00" * 10).decode()
    with pytest.raises(ValueError):
        manager.decrypt(short)


def test_unsupported_version_raises():
    manager = EncryptionManager(SECRET_32)
    encrypted = manager.encrypt("secret")
    padding = "=" * (4 - len(encrypted) % 4) if len(encrypted) % 4 else ""
    data = bytearray(base64.urlsafe_b64decode(encrypted + padding))
    data[0] = 0xFF  # Override version byte.
    bad_version = base64.urlsafe_b64encode(bytes(data)).rstrip(b"=").decode()
    with pytest.raises(ValueError, match="Unsupported encryption version"):
        manager.decrypt(bad_version)


# ---------------------------------------------------------------------------
# Key rotation
# ---------------------------------------------------------------------------


def test_key_rotation():
    original_secret = "original-secret-key-32-chars-here"
    new_secret = "new-secret-key-for-rotation-32ch"
    manager = EncryptionManager(original_secret)
    encrypted = manager.encrypt("api-key-value")
    rotated = manager.rotate_key(encrypted, new_secret)
    new_manager = EncryptionManager(new_secret)
    assert new_manager.decrypt(rotated) == "api-key-value"


def test_key_rotation_with_context():
    original_secret = "original-secret-key-32-chars-here"
    new_secret = "new-secret-key-for-rotation-32ch"
    manager = EncryptionManager(original_secret)
    encrypted = manager.encrypt("api-key", context="github_access_token")
    rotated = manager.rotate_key(encrypted, new_secret, context="github_access_token")
    new_manager = EncryptionManager(new_secret)
    assert new_manager.decrypt(rotated, context="github_access_token") == "api-key"


def test_key_rotation_produces_different_ciphertext():
    original_secret = "original-secret-key-32-chars-here"
    new_secret = "new-secret-key-for-rotation-32ch"
    manager = EncryptionManager(original_secret)
    encrypted = manager.encrypt("api-key-value")
    rotated = manager.rotate_key(encrypted, new_secret)
    assert rotated != encrypted


def test_old_key_cannot_decrypt_rotated_value():
    original_secret = "original-secret-key-32-chars-here"
    new_secret = "new-secret-key-for-rotation-32ch"
    manager = EncryptionManager(original_secret)
    encrypted = manager.encrypt("api-key-value")
    rotated = manager.rotate_key(encrypted, new_secret)
    with pytest.raises(ValueError):
        manager.decrypt(rotated)


# ---------------------------------------------------------------------------
# generate_master_secret utility
# ---------------------------------------------------------------------------


def test_generate_master_secret_length():
    secret = EncryptionManager.generate_master_secret()
    # URL-safe base64 of 32 bytes is 43 characters (no padding).
    assert len(secret) == 43


def test_generate_master_secret_uniqueness():
    s1 = EncryptionManager.generate_master_secret()
    s2 = EncryptionManager.generate_master_secret()
    assert s1 != s2


def test_generated_secret_usable():
    secret = EncryptionManager.generate_master_secret()
    manager = EncryptionManager(secret)
    plaintext = "my-api-token"
    assert manager.decrypt(manager.encrypt(plaintext)) == plaintext
