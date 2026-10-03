import secrets

from fastapi import Header, HTTPException, Request

from ..config import settings

LOOPBACK = {"127.0.0.1", "::1", "localhost"}


def _bearer_ok(authorization: str | None) -> bool:
    scheme, _, token = (authorization or "").partition(" ")
    return scheme.lower() == "bearer" and secrets.compare_digest(token.strip(), settings.api_key)


def require_key(authorization: str | None = Header(None)) -> None:
    """Ingest API: open when RAG_API_KEY is empty, otherwise needs the Bearer key."""
    if settings.api_key and not _bearer_ok(authorization):
        raise HTTPException(401, "invalid or missing API key", headers={"WWW-Authenticate": "Bearer"})


def require_admin(request: Request, authorization: str | None = Header(None)) -> None:
    """Server settings: needs the Bearer key when RAG_API_KEY is set, otherwise a request from this machine."""
    if settings.api_key:
        if not _bearer_ok(authorization):
            raise HTTPException(401, "invalid or missing API key", headers={"WWW-Authenticate": "Bearer"})
    elif (request.client.host if request.client else "") not in LOOPBACK:
        raise HTTPException(403, "set RAG_API_KEY to change settings from another machine")
