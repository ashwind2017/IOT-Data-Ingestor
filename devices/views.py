"""
HTTP entry points for the four ingestion paths:

  - POST /api/payloads/         single REST (legacy shape preserved)
  - POST /api/payloads/bulk/    bulk REST (list of payloads)
  - POST /api/payloads/upload/  NDJSON file upload (backfill / replay)
  - POST /api/payloads/stream/  server-sent acks for a long-lived stream

All four drive the same source -> transforms -> storage pipeline.
"""

import json

from django.http import StreamingHttpResponse
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import FileUploadParser, JSONParser
from rest_framework.response import Response

from .ingestion import (
    BulkRestIngestion,
    FileUploadIngestion,
    RestSingleIngestion,
    StorageError,
    persist_record,
)
from .ingestion.pipeline import default_chain, run, run_streaming
from .serializers import BulkPayloadInputSerializer, PayloadInputSerializer
from .transforms import DropRecord


@api_view(['POST'])
def create_payload(request):
    """Single-record REST. Returns the persisted row, 409 on dup fCnt."""
    serializer = PayloadInputSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    source = RestSingleIngestion(serializer.validated_data)
    chain = default_chain()

    try:
        transformed = chain.run(next(iter(source.records())))
    except DropRecord as exc:
        return Response({'data': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except ValueError as exc:
        return Response({'data': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    try:
        record = persist_record(transformed)
    except StorageError as exc:
        if 'duplicate' in str(exc):
            return Response({'detail': str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    return Response(
        {
            'id': record.id,
            'devEUI': record.device.devEUI,
            'fCnt': record.fCnt,
            'data_hex': record.data_hex,
            'status': record.status,
            'received_at': record.received_at,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(['POST'])
def create_payloads_bulk(request):
    """Bulk-list REST. Each record is its own atomic write."""
    serializer = BulkPayloadInputSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    source = BulkRestIngestion(serializer.validated_data['payloads'])
    result = run(source)

    return Response(
        {
            'accepted': result.accepted,
            'rejected': result.rejected,
            'errors': result.errors[:20],
        },
        status=status.HTTP_207_MULTI_STATUS if result.rejected else status.HTTP_201_CREATED,
    )


@api_view(['POST'])
@parser_classes([FileUploadParser, JSONParser])
def upload_payloads_file(request):
    """
    NDJSON upload (one payload dict per line). Useful for backfill /
    replay from gateway log dumps.
    """
    file_obj = request.data.get('file')
    if not file_obj:
        return Response({'detail': 'no file uploaded'}, status=status.HTTP_400_BAD_REQUEST)

    source = FileUploadIngestion(file_obj)
    result = run(source)

    return Response({
        'accepted': result.accepted,
        'rejected': result.rejected,
        'errors': result.errors[:20],
    })


@api_view(['POST'])
def stream_payloads(request):
    """
    Server-Sent Events. Body is a JSON list of payloads; we acknowledge
    each one as it's processed instead of holding the response until
    the full batch is done. Real production use would consume from a
    long-lived connection (websocket or chunked transfer) — this is the
    same machinery wired to a request body so it's easy to demo.
    """
    try:
        payloads = json.loads(request.body or b'[]')
        if not isinstance(payloads, list):
            raise ValueError('body must be a JSON list')
    except (ValueError, json.JSONDecodeError) as exc:
        return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    source = BulkRestIngestion(payloads)

    def event_stream():
        for result in run_streaming(source):
            yield f'data: {json.dumps(result)}\n\n'
        yield 'event: done\ndata: {}\n\n'

    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response
