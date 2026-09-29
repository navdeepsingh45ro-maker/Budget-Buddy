import os
from pathlib import Path
from dotenv import load_dotenv
from jose import jwt, JWTError
from datetime import datetime, timedelta

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Refuse to start without a real secret: a known default lets anyone forge tokens.
SECRET_KEY = os.getenv("JWT_SECRET")
if not SECRET_KEY or SECRET_KEY == "your_secure_jwt_secret_here":
    raise RuntimeError("JWT_SECRET is not set. Add a long random value to Backend/.env")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

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
    except JWTError:
        return None