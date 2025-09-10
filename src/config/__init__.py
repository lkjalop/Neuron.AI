"""Config package for performance tiers & flags."""

from .performance import ACTIVE_TIER  # noqa: F401
from .flags import flags  # noqa: F401

__all__ = ["ACTIVE_TIER", "flags"]
