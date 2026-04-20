"""Bar data repository interfaces."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from aurus.common.schemas import BarEvent


class BarRepository(Protocol):
    """Read interface for historical or live-compatible bar stores."""

    def load_bars(
        self,
        *,
        instrument: str,
        timeframe: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[BarEvent]:
        """Load bars matching the requested instrument/time window."""

