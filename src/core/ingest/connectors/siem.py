"""SIEM connector skeleton (Splunk / Elastic style).

Generates synthetic security events that could later be correlated with vulnerabilities.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterator, Dict, Any, List
import asyncio, random, time


@dataclass
class SIEMConfig:
    tenant_id: str = 'default'
    batch_size: int = 25
    synthetic_mode: bool = True


async def siem_stream(cfg: SIEMConfig) -> AsyncIterator[Dict[str, Any]]:
    for _ in range(3):
        await asyncio.sleep(0)
        for _ in range(cfg.batch_size):
            yield {
                'tenant_id': cfg.tenant_id,
                'event_type': 'siem_event',
                'timestamp': time.time(),
                'source': 'siem.synthetic',
                'metadata': {
                    'action': random.choice(['login_failed','process_start','network_connection']),
                    'host': f'host-{random.randint(1,50)}'
                },
                'features': {},
                'labels': {}
            }

__all__ = ['siem_stream', 'SIEMConfig']
