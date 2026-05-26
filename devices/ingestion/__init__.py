"""
Pluggable ingestion sources.

A source is anything that produces raw payload dicts: a single-record
REST POST, a bulk REST POST, a file upload, an SSE stream, a Kafka
consumer in the future. They all funnel through the same transform
chain and storage writer, so adding a source means writing one class
and registering it.
"""

from .base import IngestionResult, IngestionSource, register, registry  # noqa: F401
from .bulk_rest import BulkRestIngestion  # noqa: F401
from .file_upload import FileUploadIngestion  # noqa: F401
from .rest_single import RestSingleIngestion  # noqa: F401
from .storage import StorageError, persist_record  # noqa: F401
