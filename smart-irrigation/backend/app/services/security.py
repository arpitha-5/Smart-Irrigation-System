"""Security service: password hashing (PBKDF2-HMAC-SHA256) and JWT token handling.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

try:
    import jwt
except ImportError:
    jwt = None  # Graceful fallback to built-in hmac-sha256 token verification
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.session import get_db
from app.models.farmer import Farmer

log = logging.getLogger("irrigation.security")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

# ── Password Hashing ───────────────────────────────────────────────────────────────────

ITERATIONS = 100_000


def hash_password(password: str) -> str:
    """Hashes a password with PBKDF2-HMAC-SHA256 and a random cryptographic salt."""
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        ITERATIONS,
    )
    return f"pbkdf2_sha256${ITERATIONS}${salt}${dk.hex()}"


def verify_password(plain_password: str, hashed_password: Optional[str]) -> bool:
    """Verifies a password against the stored PBKDF2 hash using constant-time comparison."""
    if not hashed_password or not plain_password:
        return False
    try:
        parts = hashed_password.split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
            return False
        iterations = int(parts[1])
        salt = parts[2]
        stored_hash = parts[3]
        dk = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations,
        )
        return hmac.compare_digest(dk.hex(), stored_hash)
    except Exception as exc:  # noqa: BLE001
        log.warning("Password verification error: %s", exc)
        return False


# ── JWT Token Operations ───────────────────────────────────────────────────────────────

def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64url_decode(encoded: str) -> bytes:
    pad = (4 - (len(encoded) % 4)) % 4
    return base64.urlsafe_b64decode(encoded + ("=" * pad))


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Creates a signed HS256 JWT access token."""
    settings = get_settings()
    to_encode = data.copy()
    now_utc = datetime.now(timezone.utc)
    if expires_delta:
        expire = now_utc + expires_delta
    else:
        expire = now_utc + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    to_encode.update({"exp": int(expire.timestamp()), "iat": int(now_utc.timestamp())})

    if jwt is not None:
        return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    # Built-in HS256 fallback when pyjwt is not available
    header = {"alg": "HS256", "typ": "JWT"}
    h_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    p_b64 = _b64url_encode(json.dumps(to_encode, separators=(",", ":"), default=str).encode("utf-8"))
    signing_input = f"{h_b64}.{p_b64}".encode("utf-8")
    sig = hmac.new(settings.jwt_secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{h_b64}.{p_b64}.{_b64url_encode(sig)}"


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decodes and validates a JWT access token. Returns payload or None if invalid/expired."""
    settings = get_settings()
    if jwt is not None:
        try:
            return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        except (jwt.PyJWTError, Exception) as exc:
            log.debug("Token decode error: %s", exc)
            return None

    # Built-in HS256 fallback when pyjwt is not available
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        h_b64, p_b64, s_b64 = parts
        signing_input = f"{h_b64}.{p_b64}".encode("utf-8")
        expected_sig = hmac.new(settings.jwt_secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
        provided_sig = _b64url_decode(s_b64)
        if not hmac.compare_digest(expected_sig, provided_sig):
            return None
        payload = json.loads(_b64url_decode(p_b64).decode("utf-8"))
        exp = payload.get("exp")
        if exp is not None and datetime.now(timezone.utc).timestamp() > float(exp):
            return None
        return payload
    except Exception as exc:
        log.debug("Fallback token decode error: %s", exc)
        return None


# ── FastAPI Dependencies ───────────────────────────────────────────────────────────────

def get_optional_current_farmer(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Optional[Farmer]:
    """Extracts current farmer from Bearer token if provided, otherwise returns None."""
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload:
        return None
    farmer_id: Optional[str] = payload.get("sub")
    if not farmer_id:
        return None
    return db.get(Farmer, farmer_id)


def get_current_farmer(
    farmer: Optional[Farmer] = Depends(get_optional_current_farmer),
) -> Farmer:
    """Enforces authentication: raises 401 if token is missing or invalid."""
    if not farmer:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return farmer
