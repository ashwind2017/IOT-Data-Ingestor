"""
Storage writer. Takes a fully-transformed record and persists it via
the ORM, returning either the created Payload row or raising
StorageError.

Kept separate from sources so the same writer serves single, bulk,
file, and streaming paths.
"""

from django.db import IntegrityError, transaction

from devices.models import Device, Payload


class StorageError(Exception):
    pass


REQUIRED = ('devEUI', 'fCnt', 'data_hex', 'status')


@transaction.atomic
def persist_record(record: dict) -> Payload:
    for key in REQUIRED:
        if record.get(key) is None:
            raise StorageError(f'missing required field: {key}')

    device, _ = Device.objects.get_or_create(devEUI=record['devEUI'])

    try:
        payload = Payload.objects.create(
            device=device,
            fCnt=record['fCnt'],
            data_hex=record['data_hex'],
            status=record['status'],
            rx_info=record.get('rxInfo', []),
            tx_info=record.get('txInfo', {}),
        )
    except IntegrityError as exc:
        # unique_together (device, fCnt) violation -> dedupe
        raise StorageError('duplicate fCnt for device') from exc

    if device.latest_status != record['status']:
        device.latest_status = record['status']
        device.save(update_fields=['latest_status'])

    return payload


def persist_many(records: list[dict]) -> tuple[int, list[str]]:
    """
    Bulk path. Wraps each record in its own savepoint so one bad
    record doesn't poison the whole batch — surfacing per-record
    errors but committing the rest.
    """
    accepted = 0
    errors: list[str] = []
    for i, rec in enumerate(records):
        try:
            with transaction.atomic():
                persist_record(rec)
            accepted += 1
        except StorageError as exc:
            errors.append(f'record {i}: {exc}')
    return accepted, errors
