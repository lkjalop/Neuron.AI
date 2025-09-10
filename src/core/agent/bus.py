"""In-memory publish/subscribe event bus (agent scaffold).

Lightweight synchronous bus for prototype agent message exchange. Not thread
safe; future versions can swap to asyncio.Queue or external broker.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Callable, Dict, List, Any
import time, uuid


class Message:
    def __init__(self, channel: str, payload: dict[str, Any]):
        self.id = str(uuid.uuid4())
        self.channel = channel
        self.payload = payload
        self.ts = time.time()


class EventBus:
    def __init__(self):
        self._subs: Dict[str, List[Callable[[Message], None]]] = defaultdict(list)
        self._history: List[Message] = []
        self._max_history = 500

    def subscribe(self, channel: str, callback: Callable[[Message], None]):
        self._subs[channel].append(callback)

    def publish(self, channel: str, payload: dict[str, Any]):
        msg = Message(channel, payload)
        self._history.append(msg)
        if len(self._history) > self._max_history:
            self._history.pop(0)
        for cb in list(self._subs.get(channel, [])):
            try:
                cb(msg)
            except Exception:
                pass
        return msg

    def history(self, channel: str | None = None, limit: int = 50):
        items = self._history if channel is None else [m for m in self._history if m.channel == channel]
        return items[-limit:]


_BUS: EventBus | None = None


def bus() -> EventBus:
    global _BUS
    if _BUS is None:
        _BUS = EventBus()
    return _BUS


__all__ = ["bus", "EventBus", "Message"]
