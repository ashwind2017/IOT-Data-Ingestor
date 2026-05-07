# IoT Data Ingestor

Django REST Framework service for ingesting telemetry payloads from LoRaWAN-style IoT devices. Accepts a base64 encoded `data` field, decodes it into a status reading, and persists the payload alongside device metadata for downstream querying.

## Why this exists

IoT gateways forward thousands of small device payloads per day to backend services. The schema is messy (binary `data` encoded as base64, optional `rxInfo` and `txInfo` blobs that vary by gateway), uniqueness needs to be enforced per device rather than globally (LoRaWAN frame counters reset across devices), and the service has to absorb traffic from devices that have never been seen before without manual registration.

This project is a minimal, production-shaped ingestor that handles those concerns cleanly: token-authenticated POST endpoint, idempotent device creation, per-device fCnt deduplication, and JSON storage for the variable gateway metadata so the schema does not have to evolve every time a new gateway type appears.

## Architecture

```
Client (gateway / device)
  -> POST /api/payloads/ (Token-authenticated)
     -> PayloadInputSerializer validates the request shape
     -> base64 decode + integer parse for the `data` field
     -> Device.get_or_create on devEUI (auto-register on first sight)
     -> Payload.objects.create with unique_together (device, fCnt)
        -> IntegrityError on duplicate fCnt -> 409 Conflict
     -> Update device latest_status
     -> 201 Created with the persisted record
```

Two models:

- `Device`: keyed by `devEUI`, tracks `latest_status` and `created_at`. Auto-created on first payload.
- `Payload`: foreign key to Device, stores `fCnt`, decoded `data_hex`, status, and the raw `rxInfo` / `txInfo` blobs as JSON. Unique on `(device, fCnt)`.

## Design decisions

**Per-device fCnt uniqueness, not global.** LoRaWAN frame counters are device-local and reset; a global unique constraint would reject legitimate traffic. Enforced via `unique_together = ('device', 'fCnt')`.

**Auto-registration of devices.** Real fleets have devices coming online without prior registration. `get_or_create` on `devEUI` means the API works for unknown devices without a separate provisioning step.

**rxInfo and txInfo as JSONField, not modeled.** Gateway metadata varies across vendors and revisions. Modeling it strictly would require schema migrations for each new gateway type. JSON storage gives flexibility without losing queryability (Postgres supports JSONField indexing).

**Token authentication, not session.** Devices and gateways are not browsers. Token auth via DRF's built-in `TokenAuthentication` is the simplest fit; per-device tokens can be issued for fleet-scale isolation.

**409 on duplicate fCnt rather than overwrite.** Duplicates usually mean a gateway retransmitted; surfacing the conflict lets the client decide rather than silently dropping or clobbering data.

## Setup

```
git clone https://github.com/ashwind2017/IOT-Data-Ingestor.git
cd IOT-Data-Ingestor
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
```

Generate an auth token for the user you just made:

```
python manage.py drf_create_token <username>
```

## Run

```
python manage.py runserver
```

The endpoint is at `POST /api/payloads/`.

## Test

```
python manage.py test
```

## Example request

```
curl -X POST http://localhost:8000/api/payloads/ \
  -H "Authorization: Token <your-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "fCnt": 100,
    "devEUI": "abcdabcdabcdabcd",
    "data": "AQ==",
    "rxInfo": [{"gatewayID": "1234123412341234", "name": "G1", "time": "2022-07-19T11:00:00", "rssi": -57, "loRaSNR": 10}],
    "txInfo": {"frequency": 86810000, "dr": 5}
  }'
```

A successful response is `201 Created` with the saved payload.

## Notes

* The `data` field is base64 encoded. The view decodes it, takes the hex representation, and parses the integer value. A value of `1` is recorded as `passing`, anything else `failing`.
* `fCnt` is unique per device. Sending the same `fCnt` for the same `devEUI` twice returns `409 Conflict`.
* `rxInfo` and `txInfo` are stored as JSON without further modeling.
* Devices are created on first sight via `get_or_create`, so the client does not need to register a device ahead of time.

## What I would build next

* **Bulk ingestion endpoint** for gateways that batch payloads to reduce HTTP overhead. Would use `bulk_create` inside a `transaction.atomic()` with per-record validation.
* **Async ingestion via Celery or a task queue** so that the HTTP response can return immediately and parsing happens out of band, lifting throughput under burst load.
* **A second parser type** for devices that send richer payloads (multi-byte status, sensor readings) to demonstrate that the parser layer is pluggable rather than hardcoded.
* **Postgres + JSONField indexing** to support filtering on `rxInfo.gatewayID` and `txInfo.frequency` in production.
* **Docker + docker-compose** for one-command local setup including the database.
* **GitHub Actions CI** running the test suite on every push.
* **Prometheus metrics** for ingestion rate, parse failures, and per-device latest-seen timestamps.

## Stack

Python, Django 5.1, Django REST Framework, SQLite (dev), Token authentication.
