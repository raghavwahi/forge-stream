"""
AES-256-GCM encryption for sensitive values at rest.

Uses authenticated encryption (AES-GCM) to provide both confidentiality
and integrity protection. Each encryption operation generates a unique
96-bit nonce, preventing nonce reuse attacks.

Key derivation: PBKDF2-HMAC-SHA256 with a per-encryption salt to derive
a 256-bit AES key from the master secret.
"""

import base64
import os
from typing import Optional

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class EncryptionManager:
    """
    AES-256-GCM encryption manager for API keys and sensitive tokens.

    Encrypted format (URL-safe base64 encoded, padding stripped):
        [version:1][salt:32][nonce:12][ciphertext+tag:variable]

    The version byte allows future algorithm migration without breaking
    existing stored values.

    Context (AAD) binds ciphertext to its intended field, so an encrypted
    value for one field (e.g. "github_access_token") cannot be replayed
    into a different field (e.g. "openai_api_key").
    """

    VERSION = b"\x01"
    KEY_LENGTH = 32       # 256 bits
    NONCE_LENGTH = 12     # 96 bits — GCM standard recommendation
    SALT_LENGTH = 32      # 256 bits
    PBKDF2_ITERATIONS = 600_000  # OWASP 2023 recommendation

    def __init__(self, master_secret: str) -> None:
        """
        Initialise with the deployment master secret from the environment.

        Args:
            master_secret: At least 32-character string read from
                           ``ENCRYPTION_MASTER_SECRET``.

        Raises:
            ValueError: If the master secret is shorter than 32 characters.
        """
        if len(master_secret) < 32:
            raise ValueError("Master secret must be at least 32 characters")
        self._master_secret: bytes = master_secret.encode("utf-8")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def encrypt(self, plaintext: str, context: str = "") -> str:
        """
        Encrypt a plaintext string using AES-256-GCM.

        A fresh 256-bit salt and 96-bit nonce are generated for every
        call, ensuring that identical plaintexts produce different
        ciphertexts.

        Args:
            plaintext: The value to encrypt (e.g. an OAuth access token).
            context:   Optional purpose label used as Additional
                       Authenticated Data (AAD).  Pass the same value to
                       ``decrypt`` — mismatches cause decryption to fail.

        Returns:
            URL-safe base64 encoded string (no padding) containing the
            version byte, salt, nonce, ciphertext, and GCM auth tag.
        """
        salt = os.urandom(self.SALT_LENGTH)
        nonce = os.urandom(self.NONCE_LENGTH)
        key = self._derive_key(salt)

        aad = context.encode("utf-8") if context else None
        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), aad)

        payload = self.VERSION + salt + nonce + ciphertext
        return base64.urlsafe_b64encode(payload).rstrip(b"=").decode("utf-8")

    def decrypt(self, encrypted: str, context: str = "") -> str:
        """
        Decrypt a value produced by :meth:`encrypt`.

        Args:
            encrypted: URL-safe base64 encoded encrypted value.
            context:   Must exactly match the context used during
                       encryption.

        Returns:
            The original plaintext string.

        Raises:
            ValueError: If decryption fails for any reason — invalid key,
                        tampered ciphertext, mismatched context, or
                        unsupported version.
        """
        try:
            # Restore stripped padding before decoding.
            padding = "=" * (4 - len(encrypted) % 4) if len(encrypted) % 4 else ""
            raw = base64.urlsafe_b64decode(encrypted + padding)
        except Exception as exc:
            raise ValueError("Invalid encrypted value: base64 decode failed") from exc

        # Minimum size: 1 (version) + 32 (salt) + 12 (nonce) + 16 (GCM tag)
        min_length = 1 + self.SALT_LENGTH + self.NONCE_LENGTH + 16
        if len(raw) < min_length:
            raise ValueError("Invalid encrypted value: payload too short")

        version = raw[:1]
        if version != self.VERSION:
            raise ValueError(f"Unsupported encryption version: {version!r}")

        offset = 1
        salt = raw[offset : offset + self.SALT_LENGTH]
        offset += self.SALT_LENGTH
        nonce = raw[offset : offset + self.NONCE_LENGTH]
        offset += self.NONCE_LENGTH
        ciphertext = raw[offset:]

        key = self._derive_key(salt)
        aad = context.encode("utf-8") if context else None
        aesgcm = AESGCM(key)

        try:
            plaintext_bytes = aesgcm.decrypt(nonce, ciphertext, aad)
        except InvalidTag as exc:
            raise ValueError(
                "Decryption failed: invalid key, tampered data, or wrong context"
            ) from exc

        return plaintext_bytes.decode("utf-8")

    def rotate_key(
        self,
        encrypted: str,
        new_master_secret: str,
        context: str = "",
    ) -> str:
        """
        Re-encrypt a value with a new master secret (key rotation).

        Decrypts with the current master secret, then encrypts under the
        new one.  The new nonce and salt are freshly generated so the
        rotated ciphertext is independent of the original.

        Args:
            encrypted:         Existing encrypted value (from this manager).
            new_master_secret: The replacement master secret (>= 32 chars).
            context:           Context used when the value was first encrypted.

        Returns:
            New encrypted string using ``new_master_secret``.
        """
        plaintext = self.decrypt(encrypted, context=context)
        new_manager = EncryptionManager(new_master_secret)
        return new_manager.encrypt(plaintext, context=context)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _derive_key(self, salt: bytes) -> bytes:
        """
        Derive a 256-bit AES key via PBKDF2-HMAC-SHA256.

        The ``salt`` is unique per encrypted value, so dictionary and
        rainbow-table attacks against the master secret are infeasible.

        Args:
            salt: 32-byte random salt generated during encryption.

        Returns:
            32-byte derived key.
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=self.KEY_LENGTH,
            salt=salt,
            iterations=self.PBKDF2_ITERATIONS,
        )
        return kdf.derive(self._master_secret)

    # ------------------------------------------------------------------
    # Setup utility
    # ------------------------------------------------------------------

    @staticmethod
    def generate_master_secret() -> str:
        """
        Generate a cryptographically secure master secret suitable for use
        as ``ENCRYPTION_MASTER_SECRET``.

        Returns:
            URL-safe base64 encoded 32-byte random value (43 characters).
        """
        return base64.urlsafe_b64encode(os.urandom(32)).decode("utf-8")
