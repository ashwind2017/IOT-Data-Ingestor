"""
DAG: data_quality_check

Scans each tenant for likely data-quality issues:

  - missing_devices: devices with no payload in the last 24h
  - fcnt_gaps: per device, jumps > 100 between consecutive fCnt values
                (suggests dropped frames)

Flags get accumulated into the run context so the JSON state file is
the audit trail.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from orchestrator.dag import DAG, Task, register_dag


def _iter_tenants():
    if getattr(settings, 'USE_SQLITE', False) or 'django_tenants' not in settings.INSTALLED_APPS:
        from contextlib import nullcontext
        yield 'default', nullcontext()
        return

    from django_tenants.utils import tenant_context
    from tenants.models import Tenant

    for tenant in Tenant.objects.exclude(schema_name='public'):
        yield tenant.schema_name, tenant_context(tenant)


def find_silent_devices(context):
    from devices.models import Device, Payload

    cutoff = timezone.now() - timedelta(hours=24)
    flagged = defaultdict(list)

    for label, ctx in _iter_tenants():
        with ctx:
            for device in Device.objects.all():
                if not Payload.objects.filter(device=device, received_at__gte=cutoff).exists():
                    flagged[label].append(device.devEUI)

    return {'silent_devices': dict(flagged)}


def find_fcnt_gaps(context):
    from devices.models import Device, Payload

    flagged = defaultdict(list)
    GAP_THRESHOLD = 100

    for label, ctx in _iter_tenants():
        with ctx:
            for device in Device.objects.all():
                fcnts = list(
                    Payload.objects.filter(device=device)
                    .order_by('fCnt')
                    .values_list('fCnt', flat=True)
                )
                for prev, cur in zip(fcnts, fcnts[1:]):
                    if cur - prev > GAP_THRESHOLD:
                        flagged[label].append({
                            'devEUI': device.devEUI,
                            'gap': cur - prev,
                            'from': prev,
                            'to': cur,
                        })
                        break  # one example per device is enough

    return {'fcnt_gaps': dict(flagged)}


def summarize(context):
    silent = context.get('silent_devices', {})
    gaps = context.get('fcnt_gaps', {})
    return {
        'summary': {
            'silent_device_count': sum(len(v) for v in silent.values()),
            'fcnt_gap_count': sum(len(v) for v in gaps.values()),
        },
    }


register_dag(DAG(
    name='data_quality_check',
    tasks=[
        Task('find_silent_devices', find_silent_devices),
        Task('find_fcnt_gaps', find_fcnt_gaps),
        Task('summarize', summarize, depends_on=['find_silent_devices', 'find_fcnt_gaps']),
    ],
))
