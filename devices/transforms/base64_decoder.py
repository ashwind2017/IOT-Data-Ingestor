"""
Base64 decoder transform.

Pulls the binary `data` field out of base64, attaches the hex string
and integer value so downstream transforms don't repeat the work.
"""

import base64
import binascii

from .base import DropRecord, Transform


class Base64Decoder(Transform):
    """Decode `data` field; populate `data_hex` and `data_int`."""

    def apply(self, record: dict) -> dict:
        raw = record.get('data')
        if not raw:
            raise DropRecord('empty data field')

        try:
            decoded = base64.b64decode(raw, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError(f'invalid base64: {exc}') from exc

        if not decoded:
            raise DropRecord('decoded payload is empty')

        record['data_hex'] = decoded.hex()
        record['data_int'] = int(record['data_hex'], 16)
        return record
