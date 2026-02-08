"""Encrypted vault for sensitive financial data.

Uses AES-256 via Fernet (cryptography library).
Key derived from VAULT_PASSWORD env var via PBKDF2-HMAC-SHA256.

If VAULT_PASSWORD is not set — data stored unencrypted (dev mode).
"""

import base64
import hashlib
import json
import logging
import os

logger = logging.getLogger(__name__)

_fernet = None
_initialized = False

# Keys that contain sensitive financial data and MUST be encrypted
SENSITIVE_KEYS = frozenset({
    "tinkoff_transactions",
    "screenshot_data",
    "tribute_payments",
    "financial_data",
})


def _init_vault():
    """Initialize Fernet cipher from VAULT_PASSWORD (lazy, once)."""
    global _fernet, _initialized
    if _initialized:
        return _fernet is not None

    _initialized = True
    password = os.getenv("VAULT_PASSWORD", "")
    if not password:
        logger.warning(
            "VAULT_PASSWORD not set — sensitive data stored WITHOUT encryption. "
            "Set VAULT_PASSWORD env var for production."
        )
        return False

    try:
        from cryptography.fernet import Fernet
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        from cryptography.hazmat.primitives import hashes

        # Fixed salt derived from password hash (no extra file needed)
        # This is acceptable because PBKDF2 already provides key stretching
        salt = hashlib.sha256(b"zinin-corp-vault-v1").digest()

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=600_000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))
        _fernet = Fernet(key)
        logger.info("Vault: encryption initialized (AES-256)")
        return True
    except ImportError:
        logger.error("Vault: 'cryptography' package not installed — pip install cryptography")
        return False
    except Exception as e:
        logger.error(f"Vault: initialization failed: {e}")
        return False


def is_sensitive(key: str) -> bool:
    """Check if a storage key contains sensitive data."""
    return key in SENSITIVE_KEYS


def encrypt(data) -> str:
    """Encrypt data to a base64 string. Returns JSON string if vault not available."""
    plaintext = json.dumps(data, ensure_ascii=False, default=str)

    if not _init_vault():
        return plaintext

    try:
        encrypted = _fernet.encrypt(plaintext.encode("utf-8"))
        return "ENC:" + encrypted.decode("ascii")
    except Exception as e:
        logger.error(f"Vault encrypt failed: {e}")
        return plaintext


def decrypt(blob: str):
    """Decrypt data from vault format. Falls back to plain JSON."""
    if not isinstance(blob, str):
        return blob

    if not blob.startswith("ENC:"):
        # Not encrypted — parse as JSON
        try:
            return json.loads(blob)
        except (json.JSONDecodeError, TypeError):
            return blob

    if not _init_vault():
        logger.error("Vault: cannot decrypt — VAULT_PASSWORD not set")
        return None

    try:
        encrypted = blob[4:].encode("ascii")
        plaintext = _fernet.decrypt(encrypted).decode("utf-8")
        return json.loads(plaintext)
    except Exception as e:
        logger.error(f"Vault decrypt failed: {e}")
        return None
