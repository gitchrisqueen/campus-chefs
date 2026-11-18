from django.conf import settings
from django.utils.cache import patch_cache_control


class PermissionsPolicyMiddleware:
    """Adds a Permissions-Policy header; Django has no built-in setting for it."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.headers.setdefault("Permissions-Policy", settings.PERMISSIONS_POLICY)
        return response


class NoStoreForAuthenticatedMiddleware:
    """Personal pages must not sit in a shared or back-button cache (plan 5.2, SEC-07)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            patch_cache_control(response, private=True, no_store=True)
        return response
