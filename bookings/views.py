from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from meals.models import Offering
from meals.views import offering_context

from . import contributions, services
from .errors import BookingError
from .forms import BookingRequestForm, ReviewForm
from .models import Booking, Review

DONE = {
    Booking.Status.CONFIRMED: "Booking confirmed.",
    Booking.Status.DECLINED: "Request declined.",
    Booking.Status.CANCELLED: "Booking cancelled.",
    Booking.Status.COMPLETED: "Booking marked completed.",
}


def _see_other(url: str) -> HttpResponseRedirect:
    response = HttpResponseRedirect(url)
    response.status_code = 303
    return response


def _participant_booking(user, pk: int) -> Booking:
    """Only the diner and the cook can see a booking; anyone else gets 404 (AZ-03)."""
    queryset = Booking.objects.select_related("offering__cook__user__campus", "diner")
    return get_object_or_404(queryset, Q(diner=user) | Q(offering__cook__user=user), pk=pk)


def _blocked(request, booking: Booking, error: BookingError):
    """403 for a wrong actor, 409 for an edge that does not exist or a failed time guard (plan 3.3)."""
    context = {"booking": booking, "message": error.message, "status": error.status}
    return render(request, "bookings/blocked.html", context, status=error.status)


def _back(request, booking: Booking) -> str:
    target = request.POST.get("next", "")
    if url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
        return target
    return booking.get_absolute_url()


@require_POST
def book(request, pk):
    """POST /offerings/<id>/book. htmx gets the booking panel; a plain POST gets a 303 to the booking (plan 2.3)."""
    offering = get_object_or_404(Offering.objects.for_listing(), pk=pk, cook__user__is_active=True)
    if not request.user.is_authenticated:
        return redirect_to_login(reverse("offering_detail", args=[pk]))
    form = BookingRequestForm(offering, request.POST)
    booking = None
    if form.is_valid():
        try:
            booking = services.request_booking(offering, request.user, **form.service_kwargs())
        except BookingError as error:
            form.add_error(error.field if error.field in form.fields else None, error.message)
    htmx = request.headers.get("HX-Request") == "true"
    if booking and not htmx:
        return _see_other(booking.get_absolute_url())
    offering = Offering.objects.for_listing().get(pk=pk)
    context = offering_context(request, offering, form=None if booking else form, new_booking=booking)
    template = "meals/offering.html#booking_panel" if htmx else "meals/offering.html"
    return render(request, template, context)


@login_required
@require_GET
def booking_detail(request, pk):
    booking = _participant_booking(request.user, pk)
    return _detail(request, booking)


def _detail(request, booking: Booking, review_form: ReviewForm | None = None, status: int = 200):
    role = services.role_of(booking, request.user)
    can_review = services.review_block(booking, request.user) is None
    context = {
        "booking": booking,
        "offering": booking.offering,
        "is_cook": role == Booking.Actor.COOK,
        "actions": services.available(booking, role),
        "can_mark_received": role == Booking.Actor.COOK and contributions.can_mark_received(booking),
        "show_pickup_note": booking.status == Booking.Status.CONFIRMED,
        "now": timezone.now(),
        "review_form": (review_form or ReviewForm()) if can_review else None,
        "review": Review.objects.filter(booking=booking).first() if role == Booking.Actor.DINER else None,
    }
    return render(request, "bookings/detail.html", context, status=status)


@login_required
@require_POST
def booking_transition(request, pk):
    booking = _participant_booking(request.user, pk)
    to = request.POST.get("to", "")
    try:
        services.transition(booking, to, request.user)
    except BookingError as error:
        return _blocked(request, booking, error)
    messages.success(request, DONE[to])
    return _see_other(_back(request, booking))


@login_required
@require_POST
def booking_received(request, pk):
    booking = _participant_booking(request.user, pk)
    try:
        contributions.mark_received(booking, request.user)
    except BookingError as error:
        return _blocked(request, booking, error)
    messages.success(request, "Contribution marked received.")
    return _see_other(_back(request, booking))


@login_required
@require_POST
def booking_review(request, pk):
    booking = _participant_booking(request.user, pk)
    form = ReviewForm(request.POST)
    block = services.review_block(booking, request.user)
    if block:
        return _blocked(request, booking, block)
    if form.is_valid():
        try:
            services.submit_review(booking, request.user, **form.cleaned_data)
        except BookingError as error:
            return _blocked(request, booking, error)
        messages.success(request, "Thanks, your review is posted.")
        return _see_other(booking.get_absolute_url())
    return _detail(request, booking, review_form=form)
