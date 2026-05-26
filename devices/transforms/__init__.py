"""
Transform-stage abstraction.

A `Transform` takes a record dict, returns a (possibly modified) record
dict, and may short-circuit by raising `DropRecord`. Transforms are
composed left-to-right into a `TransformChain`.

The chain runs between an ingestion source and the storage writer, so
all sources go through the same parsing/enrichment/validation pipeline.
"""

from .base import DropRecord, Transform, TransformChain  # noqa: F401
from .base64_decoder import Base64Decoder  # noqa: F401
from .metadata_enricher import MetadataEnricher  # noqa: F401
from .status_interpreter import StatusInterpreter  # noqa: F401
