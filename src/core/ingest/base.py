from __future__ import annotations

import abc
from typing import AsyncIterator, Dict, Any


class EventSource(abc.ABC):
    """Abstract async event source."""

    @abc.abstractmethod
    async def stream(self) -> AsyncIterator[Dict[str, Any]]:  # raw event dicts
        ...

