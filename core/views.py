from django.db import DatabaseError, connection
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET


@require_GET
def home(request):
    return render(request, "core/home.html")


@require_GET
def how_it_works(request):
    return render(request, "core/how_it_works.html")


@require_GET
def safety(request):
    return render(request, "core/safety.html")


@require_GET
def privacy(request):
    return render(request, "core/privacy.html")


@require_GET
@never_cache
def healthz(request):
    try:
        connection.ensure_connection()
    except DatabaseError:
        return HttpResponse("db unavailable", status=503, content_type="text/plain")
    return HttpResponse("ok", content_type="text/plain")


@require_GET
def robots(request):
    return HttpResponse("User-agent: *\nDisallow: /\n", content_type="text/plain")
