"""Authentication Service shim bridging to app.services.security.
Ensures full compatibility with Milestone 3 tests and services without external dependencies.
"""
from typing import Any, Dict, Optional, Union
from app.services import security


def hash_password(password: str) -> str:
    return security.hash_password(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return security.verify_password(plain_password, hashed_password)


def create_access_token(payload: Union[int, str, Dict[str, Any]]) -> str:
    if isinstance(payload, (int, str)):
        data = {"sub": str(payload)}
    else:
        data = payload
    return security.create_access_token(data)


def decode_access_token(token: str) -> Optional[int]:
    decoded = security.decode_access_token(token)
    if not decoded:
        return None
    sub = decoded.get("sub")
    if sub is None:
        return None
    try:
        return int(sub)
    except (ValueError, TypeError):
        return None
