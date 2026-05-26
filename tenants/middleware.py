from django.db import connection
from django.http import JsonResponse
from django_tenants.utils import get_public_schema_name, get_tenant_model


class HeaderTenantMiddleware:
    """
    Resolves the tenant from the `X-Tenant-ID` request header instead of
    the request hostname. This is simpler for an internal-service ingestor
    where clients are gateways and CLIs, not browsers hitting subdomains.

    The header value must match a Tenant.schema_name. Unknown tenants
    return 404 (we deliberately don't disclose which tenants exist).

    Requests with no header are routed to the public schema so the admin,
    auth token endpoints, and tenant management still work.
    """

    EXEMPT_PATH_PREFIXES = ('/admin', '/api-token-auth', '/static')

    def __init__(self, get_response):
        self.get_response = get_response
        self.tenant_model = get_tenant_model()

    def __call__(self, request):
        tenant_id = request.headers.get('X-Tenant-ID')

        if not tenant_id or any(request.path.startswith(p) for p in self.EXEMPT_PATH_PREFIXES):
            connection.set_schema_to_public()
            return self.get_response(request)

        try:
            tenant = self.tenant_model.objects.get(schema_name=tenant_id)
        except self.tenant_model.DoesNotExist:
            return JsonResponse({'detail': 'unknown tenant'}, status=404)

        if tenant.schema_name == get_public_schema_name():
            connection.set_schema_to_public()
        else:
            connection.set_tenant(tenant)

        request.tenant = tenant
        return self.get_response(request)
