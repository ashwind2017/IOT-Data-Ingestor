"""
File upload source. Reads NDJSON (one payload dict per line) out of an
uploaded file. Useful for backfill / replay from gateway log dumps.
"""

import json
from typing import Iterable

from .base import IngestionSource, register


@register('file_upload')
class FileUploadIngestion(IngestionSource):
    def __init__(self, file_obj):
        self.file_obj = file_obj

    def records(self) -> Iterable[dict]:
        for raw_line in self.file_obj:
            line = raw_line.decode('utf-8') if isinstance(raw_line, bytes) else raw_line
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                # Skip malformed lines; the ingestion result counter
                # tracks rejections so this gets surfaced upstream.
                continue
