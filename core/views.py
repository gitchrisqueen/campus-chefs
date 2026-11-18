from django.db import DatabaseError, connection
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

# Phase 1 stub data for the live-search spike. Phase 5 replaces it with meals.search.
STUB_DISHES = [
    "French Toast",
    "Pancakes",
    "Grilled Cheese",
    "Baked Potato",
    "Macaroni and Cheese",
    "Collard Greens",
]


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
def search_stub(request):
    q = request.GET.get("q", "").strip().lower()
    results = [d for d in STUB_DISHES if q and q in d.lower()]
    template = "partials/search_stub_results.html" if request.headers.get("HX-Request") else "core/home.html"
    return render(request, template, {"q": q, "results": results})


@require_GET
def safety(request):
    return render(request, "core/safety.html")


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
