"""Threat feed ingestion scaffold.

Provides pluggable feed interfaces with backoff, freshness tracking, and runtime param gating.
"""
from .manager import threat_feed_manager, ThreatFeedManager  # noqa: F401
