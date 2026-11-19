"""BOOK-01..15: the booking request and the state machine (plan 2.3, 3.3)."""

import threading
from datetime import timedelta

import pytest
from django.db import connection
from django.utils import timezone

from bookings import services
from bookings.errors import BookingError, BookingRejected, Forbidden
from bookings.models import Booking
from meals.models import Offering, OfferingNeed
from tests import factories as f

S = Booking.Status
A = Booking.Actor
BOOK = {"seats": "2", "contribution": "share", "allergen_ack": "on"}


def run_together(*calls):
    """Run each call on its own thread, so each gets its own DB connection, released at the same moment."""
    barrier = threading.Barrier(len(calls))
    results = []

    def run(call):
        try:
            barrier.wait()
            results.append(call())
        except BookingRejected as error:
            results.append(error)
        finally:
            connection.close()

    threads = [threading.Thread(target=run, args=(call,)) for call in calls]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return results


def make(offering, diner, status, **extra):
    cancelled_by = A.DINER if status == S.CANCELLED else None
    return f.booking(offering, diner, status=status, cancelled_by=cancelled_by, **extra)


@pytest.mark.django_db
def test_book_01_diner_books_two_seats_with_allergen_ack(client, offering, diner):
    client.force_login(diner)
    response = client.post(f"/offerings/{offering.pk}/book", BOOK)
    booking = Booking.objects.get()
    assert response.status_code == 303
    assert response["Location"] == f"/bookings/{booking.pk}"
    assert (booking.status, booking.seats, booking.diner, booking.offering) == (S.REQUESTED, 2, diner, offering)
    assert booking.allergen_ack_at is not None


@pytest.mark.django_db
def test_book_02_without_allergen_ack_shows_error_and_creates_nothing(client, offering, diner):
    client.force_login(diner)
    response = client.post(f"/offerings/{offering.pk}/book", {**BOOK, "allergen_ack": ""})
    assert response.status_code == 200
    assert "allergen_ack" in response.context["form"].errors
    assert b"Confirm that you have read the allergens for this meal." in response.content
    assert not Booking.objects.exists()


@pytest.mark.django_db
def test_book_03_cook_confirms_request(client, offering, diner):
    booking = make(offering, diner, S.REQUESTED)
    client.force_login(offering.cook.user)
    response = client.post(f"/bookings/{booking.pk}/transition", {"to": "confirmed"})
    assert response.status_code == 303
    booking.refresh_from_db()
    assert booking.status == S.CONFIRMED and booking.decided_at is not None


@pytest.mark.django_db
def test_book_04_diner_cannot_confirm_own_request(client, offering, diner):
    booking = make(offering, diner, S.REQUESTED)
    client.force_login(diner)
    response = client.post(f"/bookings/{booking.pk}/transition", {"to": "confirmed"})
    assert response.status_code == 403
    booking.refresh_from_db()
    assert booking.status == S.REQUESTED and booking.decided_at is None


@pytest.mark.django_db
def test_book_05_only_one_seat_left(client, offering, diner):
    make(offering, f.user(first="Sam"), S.CONFIRMED, seats=3)
    client.force_login(diner)
    response = client.post(f"/offerings/{offering.pk}/book", BOOK)
    assert response.status_code == 200
    assert b"Only 1 seat left." in response.content
    assert Booking.objects.filter(diner=diner).count() == 0
    response = client.post(f"/offerings/{offering.pk}/book", {**BOOK, "seats": "1"})
    assert response.status_code == 303
    assert Booking.objects.get(diner=diner).seats == 1


@pytest.mark.django_db(transaction=True)
def test_book_06_two_diners_racing_for_the_last_seat_get_one_booking(cook):
    offering = f.offering(cook, capacity=2, grocery_estimate_cents=0, share_per_seat_cents=0)
    make(offering, f.user(first="Sam"), S.CONFIRMED)
    first, second = f.user(first="Ava"), f.user(first="Bruno")
    results = run_together(
        lambda: services.request_booking(Offering.objects.get(pk=offering.pk), first, 1),
        lambda: services.request_booking(Offering.objects.get(pk=offering.pk), second, 1),
    )
    assert sum(isinstance(r, Booking) for r in results) == 1
    assert [r.message for r in results if isinstance(r, BookingRejected)] == ["This meal is full."]
    assert Booking.objects.filter(diner__in=[first, second]).count() == 1


@pytest.mark.django_db
def test_book_07_cook_cannot_book_own_offering(client, offering):
    with pytest.raises(BookingRejected, match="your own meal"):
        services.request_booking(offering, offering.cook.user, 1, "share")
    client.force_login(offering.cook.user)
    assert b"Request seats" not in client.get(f"/offerings/{offering.pk}").content
    response = client.post(f"/offerings/{offering.pk}/book", BOOK)
    assert response.status_code == 200
    assert b"You can&#x27;t book your own meal." in response.content
    assert not Booking.objects.exists()


@pytest.mark.django_db
def test_book_08_second_active_request_rejected_until_cancelled(offering, diner):
    first = services.request_booking(offering, diner, 1, "share")
    with pytest.raises(BookingRejected, match="already have a request"):
        services.request_booking(offering, diner, 1, "share")
    services.transition(first, S.CANCELLED, diner)
    second = services.request_booking(offering, diner, 1, "share")
    assert second.status == S.REQUESTED and second.pk != first.pk


@pytest.mark.django_db
@pytest.mark.parametrize("actor", [A.DINER, A.COOK, A.SYSTEM])
@pytest.mark.parametrize("to", list(S))
@pytest.mark.parametrize("source", list(S))
def test_book_09_exactly_the_five_edges_succeed(offering, diner, source, to, actor):
    assert len(services.ALLOWED) == 5
    booking = make(offering, diner, source)
    who = {A.DINER: diner, A.COOK: offering.cook.user, A.SYSTEM: A.SYSTEM}[actor]
    # Inside every time guard: after serving for "completed", before the cutoff for the rest.
    now = offering.serve_at + timedelta(hours=1) if to == S.COMPLETED else timezone.now()
    edge = (source, to)
    if edge not in services.ALLOWED:
        with pytest.raises(BookingError) as error:
            services.transition(booking, to, who, now=now)
        assert error.value.status == 409
    elif actor not in services.ALLOWED[edge]:
        with pytest.raises(Forbidden) as error:
            services.transition(booking, to, who, now=now)
        assert error.value.status == 403
    else:
        services.transition(booking, to, who, now=now)
        booking.refresh_from_db()
        assert booking.status == to
        assert booking.cancelled_by == (actor if to == S.CANCELLED else None)
        return
    booking.refresh_from_db()
    assert booking.status == source


@pytest.mark.django_db
def test_book_10_diner_cannot_cancel_confirmed_booking_after_cutoff(client, cook, diner):
    now = timezone.now()
    offering = f.offering(cook, serve_at=now + timedelta(hours=1), booking_cutoff_at=now - timedelta(minutes=5))
    booking = make(offering, diner, S.CONFIRMED)
    client.force_login(diner)
    response = client.post(f"/bookings/{booking.pk}/transition", {"to": "cancelled"})
    assert response.status_code == 409
    assert b"too late to cancel" in response.content
    booking.refresh_from_db()
    assert booking.status == S.CONFIRMED
    services.transition(booking, S.CANCELLED, cook.user)  # the cook may still cancel before serving
    booking.refresh_from_db()
    assert (booking.status, booking.cancelled_by) == (S.CANCELLED, A.COOK)


@pytest.mark.django_db
def test_book_11_completed_only_after_serve_time(offering, diner):
    booking = make(offering, diner, S.CONFIRMED)
    with pytest.raises(BookingError) as error:
        services.transition(booking, S.COMPLETED, offering.cook.user, now=offering.serve_at - timedelta(minutes=1))
    assert error.value.status == 409
    booking.refresh_from_db()
    assert booking.status == S.CONFIRMED
    later = offering.serve_at + timedelta(hours=2)
    services.transition(booking, S.COMPLETED, offering.cook.user, now=later)
    booking.refresh_from_db()
    assert (booking.status, booking.closed_at) == (S.COMPLETED, later)


@pytest.mark.django_db
def test_book_12_cancelling_offering_system_cancels_its_bookings(client, offering, diner):
    requested = make(offering, diner, S.REQUESTED)
    confirmed = make(offering, f.user(first="Sam"), S.CONFIRMED)
    client.force_login(offering.cook.user)
    response = client.post(f"/kitchen/offerings/{offering.pk}/cancel")
    assert response.status_code == 302
    offering.refresh_from_db()
    assert offering.status == Offering.Status.CANCELLED
    for booking in (requested, confirmed):
        booking.refresh_from_db()
        assert (booking.status, booking.cancelled_by) == (S.CANCELLED, A.SYSTEM)
        assert booking.closed_at is not None


@pytest.mark.django_db
def test_book_13_request_after_cutoff_is_rejected(client, cook, diner):
    now = timezone.now()
    offering = f.offering(cook, serve_at=now + timedelta(hours=1), booking_cutoff_at=now - timedelta(minutes=1))
    with pytest.raises(BookingRejected, match="closed"):
        services.request_booking(offering, diner, 1, "share")
    client.force_login(diner)
    page = client.get(f"/offerings/{offering.pk}").content.decode()
    assert "Requests for this meal are closed." in page and "Request seats" not in page
    assert client.post(f"/offerings/{offering.pk}/book", BOOK).status_code == 200
    assert not Booking.objects.exists()


@pytest.mark.django_db
def test_book_14_pickup_note_only_for_cook_and_confirmed_diner(client, offering, diner):
    note = "Lobby of North Hall (Demo)."
    url = f"/offerings/{offering.pk}"
    assert note not in client.get(url).content.decode()  # guest

    make(offering, diner, S.REQUESTED)
    client.force_login(diner)
    assert note not in client.get(url).content.decode()

    confirmed = f.user(first="Nia", last="Johnson")
    make(offering, confirmed, S.CONFIRMED)
    client.force_login(confirmed)
    assert note in client.get(url).content.decode()

    client.force_login(offering.cook.user)
    assert note in client.get(url).content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize("to", list(S))
def test_book_15_declined_booking_accepts_no_transition(offering, diner, to):
    booking = make(offering, diner, S.DECLINED)
    for who in (diner, offering.cook.user, A.SYSTEM):
        with pytest.raises(BookingError) as error:
            services.transition(booking, to, who)
        assert error.value.status == 409
    booking.refresh_from_db()
    assert booking.status == S.DECLINED


@pytest.mark.django_db
def test_booking_request_htmx_returns_panel_and_need_released_on_decline(client, offering, diner):
    """Supporting test: the htmx path of plan 2.3 step 5, and a bring-list claim through the form."""
    need = OfferingNeed.objects.create(offering=offering, label="1 lb spaghetti")
    client.force_login(diner)
    response = client.post(
        f"/offerings/{offering.pk}/book",
        {"seats": "1", "contribution": "ingredients", "need": need.pk, "allergen_ack": "on"},
        HTTP_HX_REQUEST="true",
    )
    html = response.content.decode()
    assert response.status_code == 200
    assert "<html" not in html and 'id="booking-panel"' in html
    assert "Request sent." in html and "Bring: 1 lb spaghetti" in html
    booking = Booking.objects.get()
    need.refresh_from_db()
    assert need.claimed_by_booking == booking and booking.share_cents == 0

    client.force_login(offering.cook.user)
    response = client.post(f"/bookings/{booking.pk}/transition", {"to": "declined", "next": "/me"})
    assert response["Location"] == "/me"
    need.refresh_from_db()
    assert need.claimed_by_booking is None


@pytest.mark.django_db
def test_booking_panel_states(client, offering, diner):
    """Supporting test: guests get a login link; a full or cancelled meal takes no requests."""
    page = client.get(f"/offerings/{offering.pk}").content.decode()
    assert f"/login?next=/offerings/{offering.pk}" in page
    response = client.post(f"/offerings/{offering.pk}/book", BOOK)
    assert response.status_code == 302 and response["Location"].startswith("/login?next=")

    make(offering, f.user(first="Sam"), S.CONFIRMED, seats=4)
    client.force_login(diner)
    assert "This meal is full." in client.get(f"/offerings/{offering.pk}").content.decode()

    services.cancel_offering(offering)
    assert "Requests for this meal are closed." in client.get(f"/offerings/{offering.pk}").content.decode()
    services.cancel_offering(offering)  # cancelling twice changes nothing


@pytest.mark.django_db
def test_cancel_offering_after_serve_time_is_refused(client, cook):
    offering = f.offering(cook, days_ahead=-1)
    client.force_login(cook.user)
    response = client.post(f"/kitchen/offerings/{offering.pk}/cancel", follow=True)
    assert b"already been served" in response.content
    offering.refresh_from_db()
    assert offering.status == Offering.Status.OPEN
