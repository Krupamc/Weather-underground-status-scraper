from pwdlib import PasswordHash
import jwt
from datetime import datetime, timedelta, timezone
import web_config as cfg

secret_key = cfg.secret_key
algorithm = cfg.algorithm
access_token_expire_minutes = cfg.access_token_expire_minuites

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=access_token_expire_minutes))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, secret_key, algorithm=algorithm)

# Hashing Helpers
password_hash = PasswordHash.recommended()

def hash_password(password: str) -> str:
    return password_hash.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)
