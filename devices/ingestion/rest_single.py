"""
Single-payload REST source. The original behavior of the API: one
JSON body per HTTP request.
"""

from typing import Iterable

from .base import IngestionSource, register


@register('rest_single')
class RestSingleIngestion(IngestionSource):
    def __init__(self, payload: dict):
        self.payload = payload

    def records(self) -> Iterable[dict]:
        yield self.payload
