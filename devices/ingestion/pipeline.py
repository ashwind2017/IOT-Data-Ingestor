"""
Pipeline runner — glues IngestionSource -> TransformChain -> storage.

Every ingestion path (single, bulk, file, streaming) goes through this
function so the parsing/enrichment/persistence behavior is identical
regardless of how the record arrived.
"""

from typing import Iterator

from devices.transforms import (
    Base64Decoder,
    DropRecord,
    MetadataEnricher,
    StatusInterpreter,
    TransformChain,
)

from .base import IngestionResult, IngestionSource
from .storage import StorageError, persist_record


def default_chain() -> TransformChain:
    return TransformChain([
        Base64Decoder(),
        StatusInterpreter(),
        MetadataEnricher(),
    ])


def run(source: IngestionSource, chain: TransformChain | None = None) -> IngestionResult:
    """Drain a source. Return per-batch counters."""
    chain = chain or default_chain()
    result = IngestionResult()

    for raw in source.records():
        try:
            transformed = chain.run(raw)
        except DropRecord:
            result.rejected += 1
            continue
        except (ValueError, KeyError) as exc:
            result.rejected += 1
            result.errors.append(f'transform: {exc}')
            continue

        try:
            persist_record(transformed)
            result.accepted += 1
        except StorageError as exc:
            result.rejected += 1
            result.errors.append(str(exc))

    return result


def run_streaming(source: IngestionSource, chain: TransformChain | None = None) -> Iterator[dict]:
    """
    Streaming variant — yields a per-record result dict instead of
    accumulating, so SSE handlers can flush each acknowledgement to
    the client as records arrive.
    """
    chain = chain or default_chain()

    for raw in source.records():
        try:
            transformed = chain.run(raw)
        except DropRecord as exc:
            yield {'status': 'dropped', 'reason': str(exc)}
            continue
        except (ValueError, KeyError) as exc:
            yield {'status': 'error', 'reason': f'transform: {exc}'}
            continue

        try:
            persist_record(transformed)
            yield {
                'status': 'accepted',
                'devEUI': transformed.get('devEUI'),
                'fCnt': transformed.get('fCnt'),
            }
        except StorageError as exc:
            yield {'status': 'error', 'reason': str(exc)}
