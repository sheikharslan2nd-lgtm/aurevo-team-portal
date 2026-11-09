"""Small helpers for encrypting/decrypting sensitive values at rest.

The key is derived from Django's ``SECRET_KEY`` so deployments do not need an
extra secret. Rotating ``SECRET_KEY`` invalidates stored ciphertext, which is
the desired behaviour for credential storage.
"""

import base64
import hashlib

from django.conf import settings


def _fernet():
    from cryptography.fernet import Fernet

    key = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_value(value):
    if value is None:
        value = ""
    value = str(value)
    if value == "":
        return ""
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_value(value):
    if not value:
        return ""
    try:
        return _fernet().decrypt(value.encode("utf-8")).decode("utf-8")
    except Exception:
        return ""