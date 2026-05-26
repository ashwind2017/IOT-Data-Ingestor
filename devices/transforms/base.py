"""
Transform base class and chain runner.

Design notes:

* Transforms are deliberately tiny units of work — easier to test,
  easier to swap, and the chain composition is the abstraction that
  matters at the interview level.
* Each transform mutates a copy of the record so a failure mid-chain
  doesn't leave a partially-mutated record.
* `DropRecord` is the sanctioned way to silently filter out a record
  (e.g., a heartbeat ping with no measurement); raising it does not
  count as an error.
"""

from __future__ import annotations

import copy
from abc import ABC, abstractmethod
from typing import Iterable


class DropRecord(Exception):
    """Raise from a transform to skip the current record entirely."""


class Transform(ABC):
    """One-step transform over a record dict."""

    @abstractmethod
    def apply(self, record: dict) -> dict:
        """Return a new (or modified) record dict."""

    @property
    def name(self) -> str:
        return self.__class__.__name__


class TransformChain:
    """
    Applies a sequence of transforms left-to-right.

    Example:
        chain = TransformChain([Base64Decoder(), StatusInterpreter()])
        clean = chain.run(raw_record)
    """

    def __init__(self, transforms: Iterable[Transform]):
        self.transforms = list(transforms)

    def run(self, record: dict) -> dict:
        out = copy.deepcopy(record)
        for t in self.transforms:
            out = t.apply(out)
        return out

    def names(self) -> list[str]:
        return [t.name for t in self.transforms]
