"""Unified secret loading with fingerprint logging (no value exposure).

Usage: from config.secret_loader import get_secret

Resolves from environment only (optionally could extend to .env parsing if python-dotenv added).
Fingerprints: first 4 + last 4 chars and length; only in DEBUG.
"""
from __future__ import annotations
import os, logging

log = logging.getLogger("secrets")


def _fingerprint(val: str) -> str:
    if not val:
        return "<empty>"
    if len(val) <= 8:
        return f"len={len(val)}"
    return f"{val[:4]}…{val[-4:]} (len={len(val)})"


def get_secret(name: str, default: str | None = None, required: bool = False) -> str | None:
    val = os.getenv(name, default)
    if required and not val:
        raise RuntimeError(f"Missing required secret: {name}")
    if os.getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        log.debug("secret loaded %s fp=%s required=%s", name, _fingerprint(val or ""), required)
    return val

__all__ = ["get_secret"]
