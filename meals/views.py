from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Avg, Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from bookings.models import Booking, Review

from .forms import CookBioForm, CookSetupForm, MenuItemForm, OfferingForm, SearchForm
from .models import CookProfile, Course, MealType, MenuItem, Offering
from .search import search_offerings


def cook_required(view):
    """Logged in and has a kitchen; otherwise 403 (AZ-01). The view receives the cook profile."""

    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        cook = getattr(request.user, "cook_profile", None)
        if cook is None:
            raise PermissionDenied
        return view(request, cook, *args, **kwargs)

    return wrapper


def _form_page(request, form, *, title, action_label, back_url="kitchen"):
    return render(
        request,
        "meals/kitchen_form.html",
        {"form": form, "title": title, "action_label": action_label, "back_url": back_url},
    )


# --- The kitchen (the cook's own pages) --------------------------------------------------


@login_required
@require_http_methods(["GET", "POST"])
def kitchen_setup(request):
    if hasattr(request.user, "cook_profile"):
        return redirect("kitchen")
    form = CookSetupForm(request.POST if request.method == "POST" else None)
    if form.is_bound and form.is_valid():
        form.instance.user = request.user
        form.instance.food_safety_ack_at = timezone.now()
        form.save()
        messages.success(request, "Your kitchen is ready. Add your first dish.")
        return redirect("kitchen")
    return render(request, "meals/kitchen_setup.html", {"form": form})


@login_required
@require_GET
def kitchen(request):
    cook = getattr(request.user, "cook_profile", None)
    if cook is None:
        return redirect("kitchen_setup")
    now = timezone.now()
    offerings = cook.offerings.for_listing()
    context = {
        "cook": cook,
        "menu": _menu_grid(cook.menu_items.filter(is_active=True)),
        "upcoming": offerings.filter(serve_at__gte=now),
        "past": offerings.filter(serve_at__lt=now).order_by("-serve_at")[:10],
    }
    return render(request, "meals/kitchen.html", context)


@cook_required
@require_http_methods(["GET", "POST"])
def kitchen_bio(request, cook):
    form = CookBioForm(request.POST if request.method == "POST" else None, instance=cook)
    if form.is_bound and form.is_valid():
        form.save()
        messages.success(request, "Your bio was updated.")
        return redirect("kitchen")
    return _form_page(request, form, title="Edit your bio", action_label="Save bio")


@cook_required
@require_http_methods(["GET", "POST"])
def item_create(request, cook):
    form = MenuItemForm(cook, request.POST if request.method == "POST" else None)
    if form.is_bound and form.is_valid():
        item = form.save()
        messages.success(request, f"“{item.name}” was added to your menu.")
        return redirect("kitchen")
    return _form_page(request, form, title="Add a dish", action_label="Add dish")


@cook_required
@require_http_methods(["GET", "POST"])
def item_edit(request, cook, pk):
    item = get_object_or_404(MenuItem, pk=pk, cook=cook, is_active=True)
    form = MenuItemForm(cook, request.POST if request.method == "POST" else None, instance=item)
    if form.is_bound and form.is_valid():
        form.save()
        messages.success(request, f"“{item.name}” was updated.")
        return redirect("kitchen")
    return _form_page(request, form, title=f"Edit {item.name}", action_label="Save dish")


@cook_required
@require_POST
def item_archive(request, cook, pk):
    """Dishes are archived, never deleted, so past meals keep their menus (plan 3.1)."""
    item = get_object_or_404(MenuItem, pk=pk, cook=cook, is_active=True)
    item.is_active = False
    item.is_specialty = False
    item.save(update_fields=["is_active", "is_specialty"])
    messages.success(request, f"“{item.name}” was removed from your menu.")
    return redirect("kitchen")


@cook_required
@require_http_methods(["GET", "POST"])
def offering_create(request, cook):
    form = OfferingForm(cook, request.POST if request.method == "POST" else None)
    if form.is_bound and form.is_valid():
        offering = form.save()
        messages.success(request, f"“{offering.title}” is open for requests.")
        return redirect("kitchen")
    return _form_page(request, form, title="Open a meal", action_label="Open meal")


@cook_required
@require_http_methods(["GET", "POST"])
def offering_edit(request, cook, pk):
    offering = get_object_or_404(Offering, pk=pk, cook=cook)
    form = OfferingForm(cook, request.POST if request.method == "POST" else None, instance=offering)
    if form.is_bound and form.is_valid():
        form.save()
        messages.success(request, f"“{offering.title}” was updated.")
        return redirect("kitchen")
    return _form_page(request, form, title=f"Edit {offering.title}", action_label="Save meal")


@cook_required
@require_POST
def offering_delete(request, cook, pk):
    offering = get_object_or_404(Offering, pk=pk, cook=cook)
    if offering.bookings.exists():
        messages.error(request, f"“{offering.title}” has bookings, so it stays on record.")
    else:
        offering.delete()
        messages.success(request, f"“{offering.title}” was deleted.")
    return redirect("kitchen")


# --- Public pages ------------------------------------------------------------------------


def _menu_grid(items):
    """[(meal label, [(course label, [items])])] in breakfast, lunch, dinner order (MENU-03)."""
    items = list(items)
    return [
        (
            meal.label,
            [(f"{c.label}s", [i for i in items if i.meal_type == meal and i.course == c]) for c in Course],
        )
        for meal in MealType
    ]


@require_GET
def cook_page(request, pk):
    cook = get_object_or_404(CookProfile.objects.select_related("user__campus"), pk=pk, user__is_active=True)
    items = list(cook.menu_items.filter(is_active=True))
    meal_order = list(MealType)
    reviews = Review.objects.filter(booking__offering__cook=cook, hidden_at__isnull=True)
    context = {
        "cook": cook,
        "specialties": sorted((i for i in items if i.is_specialty), key=lambda i: meal_order.index(i.meal_type)),
        "menu": _menu_grid(items),
        "upcoming": cook.offerings.for_listing().filter(status=Offering.Status.OPEN, serve_at__gt=timezone.now()),
        "reviews": reviews.select_related("booking__diner", "booking__offering")[:20],
        "rating": reviews.aggregate(average=Avg("rating"), count=Count("pk")),
    }
    return render(request, "meals/cook.html", context)


@require_GET
def offering_detail(request, pk):
    offering = get_object_or_404(Offering.objects.for_listing(), pk=pk, cook__user__is_active=True)
    user = request.user
    is_cook = user.is_authenticated and offering.cook_id == user.pk
    is_confirmed_diner = (
        user.is_authenticated and offering.bookings.filter(diner=user, status=Booking.Status.CONFIRMED).exists()
    )
    context = {"offering": offering, "show_pickup_note": is_cook or is_confirmed_diner, "is_cook": is_cook}
    return render(request, "meals/offering.html", context)


@require_GET
def search(request):
    """GET /search. htmx gets the results partial; a plain GET gets the full page (SRCH-07, E2E-05)."""
    form = SearchForm(request.GET)
    paginator = Paginator(search_offerings(**form.filters()).for_listing(), 20)
    context = {"form": form, "page": paginator.get_page(request.GET.get("page")), "q": form.cleaned_data.get("q", "")}
    template = "partials/search_results.html" if request.headers.get("HX-Request") else "meals/search.html"
    return render(request, template, context)
