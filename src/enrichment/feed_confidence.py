"""Feed confidence helpers.

Stores and retrieves per-feed confidence weights to influence predictive models.
Default confidence = 1.0 if no record.
"""
from __future__ import annotations

import time
from typing import Optional

from storage import postgres  # type: ignore

async def set_feed_confidence(feed_name: str, weight: float):
    await postgres.execute(
        """
        INSERT INTO feed_confidence (feed_name, weight, updated_ts)
        VALUES ($1,$2,$3)
        ON CONFLICT (feed_name) DO UPDATE SET weight=EXCLUDED.weight, updated_ts=EXCLUDED.updated_ts
        """,
        feed_name,
        float(weight),
        time.time(),
    )

async def get_feed_confidence(feed_name: str) -> float:
    rows = await postgres.fetch("SELECT weight FROM feed_confidence WHERE feed_name=$1", feed_name)
    if not rows:
        return 1.0
    try:
        return float(rows[0][0])
    except Exception:
        return 1.0

__all__ = ["set_feed_confidence", "get_feed_confidence"]
