import base64
import binascii

from django.db import IntegrityError
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Device, Payload
from .serializers import PayloadInputSerializer


@api_view(['POST'])
def create_payload(request):
    serializer = PayloadInputSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    payload = serializer.validated_data
    raw = payload['data']

    # data is base64 encrypted; decode to bytes, render as hex,
    # then read the integer value to decide pass/fail
    try:
        decoded = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError):
        return Response({'data': 'invalid base64'}, status=status.HTTP_400_BAD_REQUEST)

    if not decoded:
        return Response({'data': 'empty payload'}, status=status.HTTP_400_BAD_REQUEST)

    data_hex = decoded.hex()
    value = int(data_hex, 16)
    record_status = 'passing' if value == 1 else 'failing'

    device, _ = Device.objects.get_or_create(devEUI=payload['devEUI'])

    try:
        record = Payload.objects.create(
            device=device,
            fCnt=payload['fCnt'],
            data_hex=data_hex,
            status=record_status,
            rx_info=payload.get('rxInfo', []),
            tx_info=payload.get('txInfo', {}),
        )
    except IntegrityError:
        return Response(
            {'detail': 'duplicate fCnt for device'},
            status=status.HTTP_409_CONFLICT,
        )

    device.latest_status = record_status
    device.save(update_fields=['latest_status'])

    return Response(
        {
            'id': record.id,
            'devEUI': device.devEUI,
            'fCnt': record.fCnt,
            'data_hex': record.data_hex,
            'status': record.status,
            'received_at': record.received_at,
        },
        status=status.HTTP_201_CREATED,
    )
