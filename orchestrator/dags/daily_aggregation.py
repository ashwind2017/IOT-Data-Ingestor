"""
DAG: daily_aggregation

For each tenant, scan the last 24h of payloads and produce a summary
row (total received, % passing, distinct devices). Designed to run
nightly via cron.

The actual aggregation tasks are tenant-aware: when invoked under
django-tenants we iterate every Tenant and switch the DB connection
per tenant. In SQLite/single-tenant mode we just process the one
schema.
"""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db import connection
from django.utils import timezone

from orchestrator.dag import DAG, Task, register_dag


def _iter_tenants():
    """Yield (label, ctx_manager) per tenant. ctx_manager binds DB."""
    if getattr(settings, 'USE_SQLITE', False) or 'django_tenants' not in settings.INSTALLED_APPS:
        from contextlib import nullcontext
        yield 'default', nullcontext()
        return

    from django_tenants.utils import schema_context, tenant_context
    from tenants.models import Tenant

    for tenant in Tenant.objects.exclude(schema_name='public'):
        yield tenant.schema_name, tenant_context(tenant)


def discover_tenants(_context):
    tenants = [label for label, _ in _iter_tenants()]
    return {'tenants': tenants}


def aggregate_per_tenant(context):
    from devices.models import Payload

    summaries = {}
    window_start = timezone.now() - timedelta(hours=24)

    for label, ctx in _iter_tenants():
        with ctx:
            qs = Payload.objects.filter(received_at__gte=window_start)
            total = qs.count()
            passing = qs.filter(status='passing').count()
            distinct_devices = qs.values('device_id').distinct().count()

            summaries[label] = {
                'total': total,
                'passing': passing,
                'pass_rate': round(passing / total, 4) if total else None,
                'distinct_devices': distinct_devices,
            }

    return {'summaries': summaries}


def emit_summary(context):
    # In real life this would write to a metrics store / S3 / Slack.
    # For the demo we just stash it back in the run state so the JSON
    # file shows what was computed.
    return {'emitted_at': timezone.now().isoformat()}


register_dag(DAG(
    name='daily_aggregation',
    tasks=[
        Task('discover_tenants', discover_tenants),
        Task('aggregate_per_tenant', aggregate_per_tenant, depends_on=['discover_tenants']),
        Task('emit_summary', emit_summary, depends_on=['aggregate_per_tenant']),
    ],
))
