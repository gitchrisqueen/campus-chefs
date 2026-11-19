"""Failed-login limiter (plan 5.2).

- Counts failed logins only, keyed on sha256 of the NFKC-normalized, stripped, lowercased
  email: the same folding the login form and the case-insensitive lookup apply, so every
  spelling that authenticates as one account shares one counter. No raw email is stored.
- Logs a warning on each lockout with only a key prefix, never the email.
- Fails open if the cache is unavailable: login keeps working and the error is logged.
- 5 failures in 15 minutes return 429 with Retry-After.
- Uses the "ratelimit" cache alias (its own table, so other keys cannot cull the counters).
- Never reads X-Forwarded-For and has no per-IP limit: behind Docker port publishing
  every client can share one gateway IP.

Known gaps (docs/SECURITY.md): the get-then-set is not atomic across workers, and anyone who
knows an email can lock that account out for 15 minutes.
"""

import hashlib
import logging
import unicodedata
from functools import wraps

from django.core.cache import caches
from django.http import HttpResponse

logger = logging.getLogger(__name__)

MAX_FAILURES = 5
WINDOW_SECONDS = 15 * 60


def _key(email: str) -> str:
    folded = unicodedata.normalize("NFKC", email).strip().lower()
    return "login-fail:" + hashlib.sha256(folded.encode()).hexdigest()


def take_slot(scope: str, ident: object, limits: tuple[tuple[str, int, int], ...]) -> str | None:
    """Count one use against every (name, window seconds, max) limit, or refuse it.

    Returns None when the use is allowed (and counted in every window), or the name of the first
    limit that is full (and counts nothing). Unlike the login limiter this fails CLOSED when the
    cache errors: it guards a paid API, so an unavailable counter must not mean unlimited calls.
    Fixed windows that start at the first counted use. The get-then-incr is not atomic across workers.
    """
    cache = caches["ratelimit"]
    keys = [(name, window, maximum, f"{scope}:{name}:{ident}") for name, window, maximum in limits]
    try:
        for name, _window, maximum, key in keys:
            if cache.get(key, 0) >= maximum:
                return name
        for _name, window, _maximum, key in keys:
            cache.add(key, 0, window)
            try:
                cache.incr(key)
            except ValueError:  # the window expired between add and incr
                cache.set(key, 1, window)
    except Exception:
        logger.exception("rate limiter unavailable; refusing the request (scope %s)", scope)
        return "unavailable"
    return None


def limit_failed_logins(view):
    """Wrap a login view whose form posts the email as `username` (ours and the admin's)."""

    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if request.method != "POST":
            return view(request, *args, **kwargs)
        cache = caches["ratelimit"]
        key = _key(request.POST.get("username", ""))
        try:
            failures = cache.get(key, 0)
        except Exception:
            logger.exception("rate limiter unavailable; allowing the login attempt")
            return view(request, *args, **kwargs)
        if failures >= MAX_FAILURES:
            logger.warning("login locked for key %s after %d failures", key[len("login-fail:") :][:12], failures)
            response = HttpResponse(
                "Too many failed logins for this email. Try again in 15 minutes.\n",
                status=429,
                content_type="text/plain; charset=utf-8",
            )
            response["Retry-After"] = str(WINDOW_SECONDS)
            return response
        response = view(request, *args, **kwargs)
        # A successful login redirects; a failed one re-renders the form with 200.
        try:
            if response.status_code == 200:
                cache.set(key, failures + 1, WINDOW_SECONDS)
            else:
                cache.delete(key)
        except Exception:
            logger.exception("rate limiter unavailable; the attempt was not counted")
        return response

    return wrapped
