"""
Encryption for GitHub access tokens at rest.

The implementation lives in `core/crypto.py` — it is not GitHub-specific — but
the token-shaped names and error message stay here, because "reconnect GitHub"
is the actionable advice when a token cannot be read.
"""

from __future__ import annotations

from app.core.crypto import EncryptionError, decrypt_value, encrypt_value

# Kept as an alias so existing callers and tests keep working.
TokenEncryptionError = EncryptionError


def encrypt_token(token: str) -> str:
    """Encrypt a plaintext access token for storage."""
    if not token:
        raise TokenEncryptionError("Refusing to encrypt an empty token.")
    return encrypt_value(token)


def decrypt_token(encrypted: str) -> str:
    """Decrypt a stored token, with GitHub-specific advice on failure."""
    try:
        return decrypt_value(encrypted)
    except EncryptionError as exc:
        raise TokenEncryptionError(
            "Stored GitHub token could not be decrypted. It was probably "
            "encrypted with a different TOKEN_ENCRYPTION_KEY; the user needs "
            "to reconnect GitHub."
        ) from exc
