# IoT Payload Parser

Django REST Framework service for ingesting IoT device payloads. Accepts a base64
encoded data field, decodes it, and records a passing/failing status per device.

## Setup

```
git clone <repo> cd iot-data-ingestor o
cd cd iot-data-ingestor o
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

* The `data` field is base64 encrypted. The view decodes it, takes the hex
  representation, and parses the integer value. A value of `1` is recorded as
  `passing`, anything else is `failing`.
* `fCnt` is unique per device, not globally. Sending the same `fCnt` for the
  same `devEUI` twice returns `409 Conflict`.
* `rxInfo` and `txInfo` are stored as JSON without further modeling.
* Devices are created on first sight via `get_or_create`, so the client does
  not need to register a device ahead of time.
