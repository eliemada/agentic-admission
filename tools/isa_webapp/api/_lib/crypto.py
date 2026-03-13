"""NaCl sealed-box encryption for ISA credentials.

The backend holds a long-lived NaCl keypair.  The browser encrypts
``{"username": "…", "password": "…"}`` with the public key using a
sealed box (ephemeral sender key, no nonce management).  The backend
decrypts in memory and wipes the plaintext immediately after use.
"""

from __future__ import annotations

import base64
import json
import logging
import os

from nacl.public import PrivateKey, SealedBox

logger = logging.getLogger(__name__)


def load_or_generate_keypair() -> PrivateKey:
    """Read ``NACL_PRIVATE_KEY`` (base64) from env, or generate an ephemeral key."""
    key_b64 = os.environ.get("NACL_PRIVATE_KEY")
    if key_b64:
        return PrivateKey(base64.b64decode(key_b64))
    logger.warning(
        "NACL_PRIVATE_KEY not set — generating ephemeral keypair. "
        "Set it via `vercel env add NACL_PRIVATE_KEY` for production."
    )
    return PrivateKey.generate()


def get_public_key_b64(private_key: PrivateKey) -> str:
    """Return the public key as a URL-safe base64 string."""
    return base64.b64encode(bytes(private_key.public_key)).decode()


def decrypt_credentials(encrypted_b64: str, private_key: PrivateKey) -> tuple[str, str]:
    """Unseal *encrypted_b64* and return ``(username, password)``."""
    encrypted = base64.b64decode(encrypted_b64)
    box = SealedBox(private_key)
    plaintext = box.decrypt(encrypted)
    creds = json.loads(plaintext)
    return creds["username"], creds["password"]
