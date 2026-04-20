"""Append-only JSONL event journal."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from aurus.common.schemas import DomainModel, domain_from_json


class EventJournal:
    """Append-only event journal suitable for deterministic replay."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, event: DomainModel) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(event.to_json())
            handle.write("\n")

    def append_many(self, events: Iterable[DomainModel]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            for event in events:
                handle.write(event.to_json())
                handle.write("\n")

    def read(self) -> tuple[DomainModel, ...]:
        if not self.path.exists():
            return ()
        events: list[DomainModel] = []
        with self.path.open(encoding="utf-8") as handle:
            for line in handle:
                payload = line.strip()
                if payload:
                    events.append(domain_from_json(payload))
        return tuple(events)

