"""
IngestionSource abstract base class + registry.

Sources don't know how to write to the DB; they iterate raw records and
hand them off. The view layer drives them, runs each record through
the active transform chain, and persists via `storage.persist_record`.

New sources register themselves via the `@register('name')` decorator;
the registry is the integration point for management commands / future
admin UI.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Iterable


@dataclass
class IngestionResult:
    accepted: int = 0
    rejected: int = 0
    errors: list[str] = field(default_factory=list)

    def merge(self, other: 'IngestionResult') -> 'IngestionResult':
        self.accepted += other.accepted
        self.rejected += other.rejected
        self.errors.extend(other.errors)
        return self


class IngestionSource(ABC):
    """One source = one way of producing raw payload dicts."""

    @abstractmethod
    def records(self) -> Iterable[dict]:
        """Yield raw payload dicts (pre-transform)."""


# --- Registry ---------------------------------------------------------

registry: dict[str, type[IngestionSource]] = {}


def register(name: str) -> Callable[[type[IngestionSource]], type[IngestionSource]]:
    def _decorate(cls: type[IngestionSource]) -> type[IngestionSource]:
        registry[name] = cls
        return cls
    return _decorate
