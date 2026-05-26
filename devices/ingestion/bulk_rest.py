"""
Bulk REST source. Accepts a list of payload dicts; the view layer
handles each as its own atomic write so a single bad record doesn't
roll back the whole batch.
"""

from typing import Iterable

from .base import IngestionSource, register


@register('bulk_rest')
class BulkRestIngestion(IngestionSource):
    def __init__(self, payloads: list[dict]):
        self.payloads = payloads

    def records(self) -> Iterable[dict]:
        yield from self.payloads
