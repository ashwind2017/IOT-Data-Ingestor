"""
Metadata enricher.

Two jobs:
  1. Stamp `ingested_at` (server clock) so we can later distinguish
     "device sent it at T" from "we received it at T+delta".
  2. Flatten the most useful fields from rxInfo / txInfo (rssi, snr,
     gateway id, frequency, dr) so simple SQL queries don't have to
     traverse JSON every time.

The original blobs are kept intact so nothing is lost.
"""

from datetime import datetime, timezone

from .base import Transform


class MetadataEnricher(Transform):
    def apply(self, record: dict) -> dict:
        record['ingested_at'] = datetime.now(timezone.utc).isoformat()

        rx = record.get('rxInfo') or []
        if isinstance(rx, list) and rx:
            first = rx[0] or {}
            record['gateway_id'] = first.get('gatewayID')
            record['rssi'] = first.get('rssi')
            record['lora_snr'] = first.get('loRaSNR')

        tx = record.get('txInfo') or {}
        if isinstance(tx, dict):
            record['frequency'] = tx.get('frequency')
            record['data_rate'] = tx.get('dr')

        return record
