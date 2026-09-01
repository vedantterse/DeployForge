"""
Encryption for GitHub access tokens at rest.

Fernet (AES-128-CBC + HMAC) with a key from `TOKEN_ENCRYPTION_KEY`. The raw
OAuth token is only ever held in memory: what reaches the database is the
ciphertext in `GitHubConnection.access_token_enc`.

Generate a key with:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


class TokenEncryptionError(RuntimeError):
    """Raised when the encryption key is missing/invalid, or decryption fails."""


@lru_cache
def _fernet() -> Fernet:
    """Build the cipher once. Fails loudly on a missing or malformed key."""
    key = (settings.token_encryption_key or "").strip()
    if not key:
        raise TokenEncryptionError(
            "TOKEN_ENCRYPTION_KEY is not set. GitHub tokens cannot be stored "
            "without it — see .env.example."
        )
    try:
        return Fernet(key.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise TokenEncryptionError(
            "TOKEN_ENCRYPTION_KEY is not a valid Fernet key (expected 32 "
            "url-safe base64-encoded bytes)."
        ) from exc


def encrypt_token(token: str) -> str:
    """Encrypt a plaintext access token for storage."""
    if not token:
        raise TokenEncryptionError("Refusing to encrypt an empty token.")
    return _fernet().encrypt(token.encode("utf-8")).decode("utf-8")


def decrypt_token(encrypted: str) -> str:
    """
    Decrypt a stored token.

    Raises TokenEncryptionError if the ciphertext was produced with a different
    key (e.g. the key was rotated), rather than returning garbage.
    """
    try:
        return _fernet().decrypt(encrypted.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise TokenEncryptionError(
            "Stored GitHub token could not be decrypted. It was probably "
            "encrypted with a different TOKEN_ENCRYPTION_KEY; the user needs "
            "to reconnect GitHub."
        ) from exc
