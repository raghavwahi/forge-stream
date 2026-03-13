"""Minimal symmetric encryption manager for at-rest secret protection."""

from __future__ import annotations


class EncryptionManager:
    """Wraps a master secret for encrypting/decrypting sensitive values."""

    def __init__(self, master_secret: str) -> None:
        if not master_secret:
            raise ValueError("master_secret must not be empty")
        self._secret = master_secret

    def encrypt(self, plaintext: str) -> str:
        """Return an encrypted representation of *plaintext*."""
        raise NotImplementedError(
            "Encryption backend not yet configured. "
            "Install a suitable library (e.g. cryptography) and implement."
        )

    def decrypt(self, ciphertext: str) -> str:
        """Return the decrypted plaintext for *ciphertext*."""
        raise NotImplementedError(
            "Encryption backend not yet configured. "
            "Install a suitable library (e.g. cryptography) and implement."
        )
