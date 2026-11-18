from django.conf import settings


class PermissionsPolicyMiddleware:
    """Adds a Permissions-Policy header; Django has no built-in setting for it."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.headers.setdefault("Permissions-Policy", settings.PERMISSIONS_POLICY)
        return response
