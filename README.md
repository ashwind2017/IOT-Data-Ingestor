# IoT Data Ingestor

Multi-tenant Django ingestion service for LoRaWAN-style IoT telemetry. Schema-per-tenant Postgres isolation, pluggable ingestion sources, a composable transform pipeline, and a built-in cron-driven DAG orchestrator for scheduled aggregation and data-quality jobs.

## Why this exists

IoT gateways forward thousands of small device payloads per day from heterogeneous fleets. A real backend has to absorb four messy realities at once:

1. **Multiple customers, hard regulatory boundaries.** A telematics customer in `us-east-1` and an energy customer in `eu-west-1` can't share rows in the same table — different DPAs, different retention rules, different schema evolution cadences.
2. **Variable schema.** The `data` field is base64-encoded binary; `rxInfo` / `txInfo` blobs vary per gateway vendor; new devices appear unannounced.
3. **Multiple ingestion shapes.** Single-record HTTP from cheap gateways, bulk batches from richer ones, file replay for backfill, and long-lived streams for high-frequency devices.
4. **Scheduled downstream work.** Nightly aggregations, periodic data-quality scans, retries when the warehouse is down — none of which justifies running Airflow.

This service handles all four with small, defensible pieces.

## Architecture

```
                       +--------------------------+
                       |  HeaderTenantMiddleware  |   reads X-Tenant-ID,
                       |  set connection schema   |   binds DB connection
                       +-----------+--------------+
                                   v
+----------------+    +-------------------------+    +---------------------+
| IngestionSource|--->|     TransformChain      |--->|     storage.py      |
| (registry)     |    |  Base64Decoder ->       |    |  persist_record()   |
|                |    |  StatusInterpreter ->   |    |  per-record atomic  |
|  RestSingle    |    |  MetadataEnricher       |    +----------+----------+
|  BulkRest      |    +-------------------------+               v
|  FileUpload    |                                  +---------------------+
|  (Streaming)   |                                  |  Postgres schema    |
+----------------+                                  |  for resolved       |
                                                    |  tenant (isolated)  |
                                                    +---------------------+

cron --> python manage.py run_dag <name>
            |
            +--> orchestrator/runner.py
                    reads runs/<dag>/<ts>.json state file
                    topological task execution
                    per-task status / traceback persisted
                    idempotent retry from last failed task
```

## Feature highlights

### 1. Multi-tenant Postgres (schema-per-tenant)

Built on [`django-tenants`](https://github.com/django-tenants/django-tenants). Each tenant gets a dedicated Postgres schema (`tenant_a`, `tenant_b`, `tenant_c` out of the box). Three tenants are seeded by the bootstrap command — adding a fourth is one row in `tenants.Tenant`.

**Tenant resolution is header-based**, not subdomain-based. Clients send `X-Tenant-ID: tenant_a`; `tenants/middleware.py` resolves it to a `Tenant` row and calls `connection.set_tenant(...)` before any ORM call. Subdomain routing is heavier than needed for an internal-service ingestor where the clients are gateways and CLIs.

Why schema-per-tenant (and not row-level `tenant_id` columns):
- Regulatory boundaries become a Postgres ACL, not application code that any developer can accidentally bypass.
- Backups, restores, and exports are per-tenant by construction.
- Per-customer schema evolution is possible (`migrate_schemas --tenant=tenant_a`) without freezing the rest of the fleet.

Trade-off: connection-pool footprint per schema. Acceptable up to ~thousands of tenants; past that, switch to row-level isolation with a strict tenant filter.

### 2. DAG orchestration (cron + JSON state files)

`orchestrator/` is a small Airflow-shaped runner. DAGs are Python dicts: a list of `Task(name, fn, depends_on=[...])`. The runner:

- Resolves task order via Kahn's algorithm (cycles raise loudly).
- Persists state after every task status change to `runs/<dag>/<utc_ts>.json`.
- On task failure: records the traceback in the state file, marks downstream tasks `skipped`, exits non-zero so cron can alert.
- On retry: re-reads the state file, skips anything already `success`, and resumes from the failed task — so re-running is idempotent.

Two example DAGs ship in `orchestrator/dags/`:

| DAG | Purpose |
|---|---|
| `daily_aggregation` | Per tenant: count last-24h payloads, pass rate, distinct devices. |
| `data_quality_check` | Per tenant: silent devices (no payloads in 24h), fCnt gaps > 100 (likely dropped frames). |

Both iterate tenants via `django_tenants.utils.tenant_context`, so adding a tenant doesn't require touching the DAGs.

CLI surface:

```
python manage.py run_dag daily_aggregation
python manage.py run_dag daily_aggregation --dry-run
python manage.py dag_runs --limit 25
python manage.py dag_runs --dag daily_aggregation
python manage.py retry_dag daily_aggregation/2026-05-26T03-00-00Z
```

Sample crontab:

```
0 3 * * * cd /srv/iot && /srv/iot/venv/bin/python manage.py run_dag daily_aggregation
*/15 * * * * cd /srv/iot && /srv/iot/venv/bin/python manage.py run_dag data_quality_check
```

### 3. Pluggable ingestion sources

`devices/ingestion/` defines an `IngestionSource` ABC. Concrete sources:

| Class | Endpoint | Use case |
|---|---|---|
| `RestSingleIngestion` | `POST /api/payloads/` | One record per request — cheap gateways. |
| `BulkRestIngestion` | `POST /api/payloads/bulk/` | List of payloads, per-record atomic write. |
| `FileUploadIngestion` | `POST /api/payloads/upload/` | NDJSON backfill / replay from gateway log dumps. |
| (streaming, see below) | `POST /api/payloads/stream/` | Long-lived stream with per-record SSE acks. |

Sources are registered via the `@register('name')` decorator and exposed in `ingestion.registry`. Adding a Kafka consumer or an S3 poller is one new file: define a class with `records() -> Iterable[dict]`, register it, and the pipeline runner handles the rest.

### 4. Transform-stage abstraction

`devices/transforms/` defines `Transform.apply(record) -> record` plus a `TransformChain` that composes transforms left-to-right. Three ship today:

- `Base64Decoder` — decodes the `data` field, attaches `data_hex` and `data_int`.
- `StatusInterpreter` — maps `data_int == 1 -> "passing"`, else `"failing"`.
- `MetadataEnricher` — stamps `ingested_at`, flattens `rxInfo[0]` / `txInfo` into top-level fields (rssi, snr, gateway_id, frequency, dr) for cheap SQL filtering while keeping the raw blobs intact.

Transforms can raise `DropRecord` to silently filter (heartbeats, malformed records that aren't errors). The same chain runs between every source and the storage writer, so behavior is identical across the four ingestion paths.

### Streaming ingestion (SSE)

`POST /api/payloads/stream/` accepts a JSON list and uses Django's `StreamingHttpResponse` to flush a Server-Sent Event per record as it's processed (`data: {"status": "accepted", ...}`), finishing with `event: done`. The same `BulkRestIngestion` source is reused with `run_streaming()` instead of `run()` — proof that the source/transform abstraction earns its keep.

For high-frequency producers where the connection lifetime is the bottleneck, the same handler swaps in a chunked HTTP body or a websocket without touching the source or transform layers.

## Stack

Python 3.13, Django 5.1, Django REST Framework 3.17, PostgreSQL 16, `django-tenants` 3.10, Token authentication, cron-driven scheduler.

## Setup

### With Postgres (default)

Requires Docker for a one-command local Postgres.

```
git clone https://github.com/ashwind2017/IOT-Data-Ingestor.git
cd IOT-Data-Ingestor
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

docker compose up -d                   # starts postgres on :5432
python manage.py migrate_schemas --shared
python manage.py bootstrap_tenants      # seeds tenant_a, tenant_b, tenant_c
python manage.py migrate_schemas        # runs tenant migrations into each schema
python manage.py createsuperuser
python manage.py drf_create_token <username>
python manage.py runserver
```

### Without Postgres (quick smoke / unit tests)

Single-schema SQLite fallback. Multi-tenant routing is short-circuited.

```
USE_SQLITE=1 python manage.py migrate
USE_SQLITE=1 python manage.py runserver
USE_SQLITE=1 python manage.py test
```

## Example requests

```
TOKEN=<your-token>

# Single
curl -X POST http://localhost:8000/api/payloads/ \
  -H "Authorization: Token $TOKEN" \
  -H "X-Tenant-ID: tenant_a" \
  -H "Content-Type: application/json" \
  -d '{"fCnt": 100, "devEUI": "abcd", "data": "AQ=="}'

# Bulk
curl -X POST http://localhost:8000/api/payloads/bulk/ \
  -H "Authorization: Token $TOKEN" \
  -H "X-Tenant-ID: tenant_a" \
  -H "Content-Type: application/json" \
  -d '{"payloads":[{"fCnt":1,"devEUI":"a","data":"AQ=="},{"fCnt":2,"devEUI":"a","data":"Ag=="}]}'

# NDJSON file upload
curl -X POST http://localhost:8000/api/payloads/upload/ \
  -H "Authorization: Token $TOKEN" \
  -H "X-Tenant-ID: tenant_a" \
  -H "Content-Disposition: attachment; filename=payloads.ndjson" \
  --data-binary @payloads.ndjson

# Streaming (SSE)
curl -N -X POST http://localhost:8000/api/payloads/stream/ \
  -H "Authorization: Token $TOKEN" \
  -H "X-Tenant-ID: tenant_a" \
  -H "Content-Type: application/json" \
  -d '[{"fCnt":1,"devEUI":"a","data":"AQ=="}]'

# Different tenant -> writes to different schema
curl -X POST http://localhost:8000/api/payloads/ \
  -H "Authorization: Token $TOKEN" \
  -H "X-Tenant-ID: tenant_b" \
  ...
```

## Adding a new ingestion source

```python
# devices/ingestion/my_source.py
from .base import IngestionSource, register

@register('kafka')
class KafkaIngestion(IngestionSource):
    def __init__(self, consumer): self.consumer = consumer
    def records(self):
        for msg in self.consumer:
            yield json.loads(msg.value)
```

Import it from `devices/ingestion/__init__.py` and it's live in the registry. Drive it from a management command or a view; the pipeline runner takes care of transforms and persistence.

## Adding a new transform

```python
# devices/transforms/my_transform.py
from .base import Transform

class GeoEnricher(Transform):
    def apply(self, record):
        record['region'] = lookup_region(record.get('gateway_id'))
        return record
```

Add it to the chain in `devices/ingestion/pipeline.py:default_chain()` or build a tenant-specific chain.

## Tests

```
USE_SQLITE=1 python manage.py test
```

23 tests cover the original API surface, transform composition, bulk + file ingestion, DAG topology and failure handling, and retry idempotency.

## What I would build next

- **Docker image + GitHub Actions CI** for the test suite on every push.
- **Prometheus metrics** for ingestion rate, transform failure counts, per-tenant queue depth, and DAG run durations.
- **A Kafka ingestion source** wired into a long-running management command for production-scale fanout.
- **Per-tenant transform chains** loaded from `Tenant.config` so two customers with different payload formats can share the codebase without forking it.
- **Distributed orchestrator** — file-based state is fine for a single host; production needs row-level locking (Postgres advisory locks) or a real queue.
