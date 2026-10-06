import os
from pathlib import Path
from dotenv import load_dotenv
import jwt  # PyJWT
from datetime import datetime, timedelta
import hashlib
import hmac

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Refuse to start without a real secret: a known default lets anyone forge tokens.
SECRET_KEY = os.getenv("JWT_SECRET")
if not SECRET_KEY or SECRET_KEY == "your_secure_jwt_secret_here":
    raise RuntimeError("JWT_SECRET is not set. Add a long random value to Backend/.env")
if len(SECRET_KEY) < 32:
    raise RuntimeError("JWT_SECRET is too short. Use at least 32 random characters (python3 -c 'import secrets; print(secrets.token_urlsafe(48))')")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

def password_fingerprint(hashed_password: str) -> str:
    """Short keyed digest of the stored password hash, put in every token.

    When the password changes (or is reset), the fingerprint changes, so every
    token issued before that stops working: a stolen session can't outlive a
    password change.
    """
    return hmac.new(SECRET_KEY.encode(), hashed_password.encode(), hashlib.sha256).hexdigest()[:16]


def token_for_user(user) -> str:
    return create_access_token({"user_id": user.id, "pwd": password_fingerprint(user.password)})


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_access_token(token: str):
    try:
        payload = jwt.decode(token,SECRET_KEY,algorithms=[ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None