from django.db import models
from django_tenants.models import DomainMixin, TenantMixin


class Tenant(TenantMixin):
    """
    Schema-per-tenant Postgres isolation. Each tenant gets its own
    Postgres schema, queried/migrated independently. Lets us hold
    multiple customers in one database while keeping their data
    physically separated for regulatory boundaries (HIPAA / SOC2 /
    per-customer DPA scopes), and lets each customer evolve their
    schema on their own cadence.
    """

    name = models.CharField(max_length=128)
    region = models.CharField(max_length=32, default='us-east-1')
    created_at = models.DateTimeField(auto_now_add=True)

    # If True, django-tenants auto-creates the schema on save.
    auto_create_schema = True

    def __str__(self):
        return f'{self.schema_name} ({self.name})'


class Domain(DomainMixin):
    """
    Maps a hostname to a tenant. We resolve tenants via an
    `X-Tenant-ID` header in middleware (see tenants.middleware),
    but django-tenants still requires the Domain table to exist
    and to seed a public domain for the shared schema.
    """
    pass
