"""
Clerk JWT authentication dependency for FastAPI.

Validates Bearer tokens by delegating to the event-planner's
/api/intelligence/session endpoint, which verifies the Clerk JWT and
returns the user's role from publicMetadata.

Only users with role 'root' or 'marketing' are permitted.

Required environment variables:
    WEBAPP_URL       — Base URL of the event-planner webapp
    CRON_SECRET_KEY  — Shared secret for calling /api/intelligence/session
"""

import hashlib
import os
import time
from typing import Any

import httpx
from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

WEBAPP_URL = os.environ.get("WEBAPP_URL", "").rstrip("/")
CRON_SECRET_KEY = os.environ.get("CRON_SECRET_KEY", "")
ALLOWED_ROLES = {"root", "marketing"}

# In-memory TTL cache: sha256(token) -> (expires_monotonic, auth_ctx)
_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_CACHE_TTL = 15 * 60  # 15 minutes

_bearer = HTTPBearer()


def _cache_get(token: str) -> dict[str, Any] | None:
    key = hashlib.sha256(token.encode()).hexdigest()
    entry = _cache.get(key)
    if entry and time.monotonic() < entry[0]:
        return entry[1]
    _cache.pop(key, None)
    return None


def _cache_set(token: str, ctx: dict[str, Any]) -> None:
    key = hashlib.sha256(token.encode()).hexdigest()
    _cache[key] = (time.monotonic() + _CACHE_TTL, ctx)


async def require_auth(
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
) -> dict[str, Any]:
    """
    FastAPI dependency: validates a Clerk JWT and enforces role-based access.

    Extracts the Bearer token from the Authorization header, checks an
    in-memory cache, then calls event-planner's /api/intelligence/session
    to verify the token and retrieve the user's role.

    Returns:
        {"user_id": str, "role": str}

    Raises:
        HTTP 401 — missing/invalid token or auth service rejected the token
        HTTP 403 — token is valid but role is not permitted
        HTTP 500 — auth service is not configured
        HTTP 503 — auth service is unreachable or timed out
    """
    token = credentials.credentials

    cached = _cache_get(token)
    if cached:
        return cached

    if not WEBAPP_URL or not CRON_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Auth service not configured")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{WEBAPP_URL}/api/intelligence/session",
                headers={
                    "Authorization": f"Bearer {CRON_SECRET_KEY}",
                    "Content-Type": "application/json",
                },
                json={"clerkToken": token},
            )
    except httpx.TimeoutException:
        raise HTTPException(status_code=503, detail="Auth service timeout")
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Auth service unavailable")

    if resp.status_code == 401:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if not resp.is_success:
        raise HTTPException(status_code=401, detail="Authentication failed")

    data = resp.json()
    role = data.get("role", "")

    if role not in ALLOWED_ROLES:
        raise HTTPException(
            status_code=403,
            detail=f"Access denied: role '{role}' is not permitted",
        )

    ctx: dict[str, Any] = {"user_id": data.get("userId"), "role": role}
    _cache_set(token, ctx)
    return ctx
