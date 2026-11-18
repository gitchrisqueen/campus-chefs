"""Failed-login limiter (plan 5.2).

- Counts failed logins only, keyed on sha256(lower(email)), so no raw email is stored.
- 5 failures in 15 minutes return 429 with Retry-After.
- Uses the "ratelimit" cache alias (its own table, so other keys cannot cull the counters).
- Never reads X-Forwarded-For and has no per-IP limit: behind Docker port publishing
  every client can share one gateway IP.

Known gaps (documented): the get-then-set is not atomic across workers, and anyone who
knows an email can lock that account out for 15 minutes.
"""

import hashlib
from functools import wraps

from django.core.cache import caches
from django.http import HttpResponse

MAX_FAILURES = 5
WINDOW_SECONDS = 15 * 60


def _key(email: str) -> str:
    return "login-fail:" + hashlib.sha256(email.strip().lower().encode()).hexdigest()


def limit_failed_logins(view):
    """Wrap a login view whose form posts the email as `username` (ours and the admin's)."""

    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if request.method != "POST":
            return view(request, *args, **kwargs)
        cache = caches["ratelimit"]
        key = _key(request.POST.get("username", ""))
        failures = cache.get(key, 0)
        if failures >= MAX_FAILURES:
            response = HttpResponse(
                "Too many failed logins for this email. Try again in 15 minutes.\n",
                status=429,
                content_type="text/plain; charset=utf-8",
            )
            response["Retry-After"] = str(WINDOW_SECONDS)
            return response
        response = view(request, *args, **kwargs)
        # A successful login redirects; a failed one re-renders the form with 200.
        if response.status_code == 200:
            cache.set(key, failures + 1, WINDOW_SECONDS)
        else:
            cache.delete(key)
        return response

    return wrapped
