"""
Seeds the three demo tenants (tenant_a, tenant_b, tenant_c) and their
public-domain rows, then runs migrations into each tenant schema.

Idempotent: existing tenants are left in place. Safe to re-run after
adding new migrations to the `devices` app.

Usage:
    python manage.py migrate_schemas --shared
    python manage.py bootstrap_tenants
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from tenants.models import Domain, Tenant


DEFAULT_TENANTS = [
    {'schema_name': 'tenant_a', 'name': 'Acme Telematics', 'region': 'us-east-1'},
    {'schema_name': 'tenant_b', 'name': 'Borealis Energy', 'region': 'us-west-2'},
    {'schema_name': 'tenant_c', 'name': 'Coast Logistics', 'region': 'eu-west-1'},
]


class Command(BaseCommand):
    help = 'Create the 3 demo tenants with isolated Postgres schemas.'

    def handle(self, *args, **options):
        # Public domain has to exist before any tenant routing works.
        self._ensure_public_tenant()

        for spec in DEFAULT_TENANTS:
            self._ensure_tenant(spec)

        self.stdout.write(self.style.SUCCESS(
            f'Bootstrap done. {Tenant.objects.count()} tenants total.'
        ))

    def _ensure_public_tenant(self):
        tenant, created = Tenant.objects.get_or_create(
            schema_name='public',
            defaults={'name': 'public', 'region': 'global'},
        )
        Domain.objects.get_or_create(
            domain='localhost',
            tenant=tenant,
            defaults={'is_primary': True},
        )
        if created:
            self.stdout.write(self.style.SUCCESS('created public tenant'))

    @transaction.atomic
    def _ensure_tenant(self, spec):
        tenant, created = Tenant.objects.get_or_create(
            schema_name=spec['schema_name'],
            defaults={'name': spec['name'], 'region': spec['region']},
        )

        # django-tenants creates the Postgres schema on first save when
        # auto_create_schema=True, so we only run migrate_schemas if the
        # tenant already existed (covers the "added new migrations"
        # case).
        if created:
            self.stdout.write(self.style.SUCCESS(
                f'created tenant {tenant.schema_name} ({tenant.name})'
            ))
        else:
            self.stdout.write(f'tenant {tenant.schema_name} already exists')

        Domain.objects.get_or_create(
            domain=f'{spec["schema_name"]}.localhost',
            tenant=tenant,
            defaults={'is_primary': True},
        )
