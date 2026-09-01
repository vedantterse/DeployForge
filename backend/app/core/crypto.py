"""
Symmetric encryption for values stored at rest.

Fernet (AES-128-CBC + HMAC) with a key from `TOKEN_ENCRYPTION_KEY`. Used for
GitHub access tokens and for environment-variable values — anything that must
be readable by the application but never sit in the database as plaintext.

Generate a key with:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


class EncryptionError(RuntimeError):
    """Raised when the encryption key is missing/invalid, or decryption fails."""


@lru_cache
def _fernet() -> Fernet:
    """Build the cipher once. Fails loudly on a missing or malformed key."""
    key = (settings.token_encryption_key or "").strip()
    if not key:
        raise EncryptionError(
            "TOKEN_ENCRYPTION_KEY is not set. Secrets cannot be stored without "
            "it — see .env.example."
        )
    try:
        return Fernet(key.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise EncryptionError(
            "TOKEN_ENCRYPTION_KEY is not a valid Fernet key (expected 32 "
            "url-safe base64-encoded bytes)."
        ) from exc


def encrypt_value(plaintext: str) -> str:
    """Encrypt a value for storage. Empty input is refused, not silently stored."""
    if not plaintext:
        raise EncryptionError("Refusing to encrypt an empty value.")
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_value(ciphertext: str) -> str:
    """
    Decrypt a stored value.

    Raises EncryptionError if the ciphertext was produced with a different key
    (e.g. the key was rotated), rather than returning garbage.
    """
    try:
        return _fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise EncryptionError(
            "A stored value could not be decrypted. It was probably encrypted "
            "with a different TOKEN_ENCRYPTION_KEY."
        ) from exc
