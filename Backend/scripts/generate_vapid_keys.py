"""Print a new pair of Web Push (VAPID) keys to put in Backend/.env.

Run once per environment:  python3 scripts/generate_vapid_keys.py
Changing the keys later invalidates every existing device subscription.
"""
import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


key = ec.generate_private_key(ec.SECP256R1())
print(f'VAPID_PUBLIC_KEY="{b64(key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint))}"')
print(f'VAPID_PRIVATE_KEY="{b64(key.private_numbers().private_value.to_bytes(32, "big"))}"')
print('VAPID_SUBJECT="mailto:support@budgetbuddy.app"')
