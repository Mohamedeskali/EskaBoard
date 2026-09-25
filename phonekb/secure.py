"""NaCl secretbox helpers shared by the server and the phone page.

Wire format of every WebSocket text frame (both directions):
    base64(nonce[24] || secretbox(json))
The page gets the 32-byte key from the URL fragment #k=<base64url>, which
browsers never send to the server.
"""
import base64
import binascii
import json
import secrets

import nacl.exceptions
import nacl.secret
import nacl.utils

KEY_SIZE = nacl.secret.SecretBox.KEY_SIZE  # 32


class BadFrame(ValueError):
    """Frame is not a valid secretbox for our key (plaintext, wrong key, tampered)."""


def new_key():
    return secrets.token_bytes(KEY_SIZE)


def key_to_b64url(key):
    return base64.urlsafe_b64encode(key).rstrip(b"=").decode()


def b64url_to_key(text):
    key = base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
    if len(key) != KEY_SIZE:
        raise ValueError(f"key must be {KEY_SIZE} bytes, got {len(key)}")
    return key


class Box:
    def __init__(self, key):
        self._box = nacl.secret.SecretBox(key)

    def seal(self, obj):
        data = json.dumps(obj, ensure_ascii=False).encode()
        nonce = nacl.utils.random(nacl.secret.SecretBox.NONCE_SIZE)
        return base64.b64encode(bytes(self._box.encrypt(data, nonce))).decode()

    def open(self, frame):
        try:
            raw = base64.b64decode(frame, validate=True)
            obj = json.loads(self._box.decrypt(raw))
        except (binascii.Error, ValueError, nacl.exceptions.CryptoError) as e:
            raise BadFrame(str(e) or type(e).__name__) from None
        if not isinstance(obj, dict):
            raise BadFrame("payload is not an object")
        return obj
