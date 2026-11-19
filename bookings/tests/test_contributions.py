"""CONTRIB-03..09, -11, -12: grocery contributions (plan 3.5). The app records them and never moves money."""

import html
import threading

import pytest
from django.db import connection

from bookings import services
from bookings.errors import BookingRejected
from bookings.models import Booking
from meals.models import Offering, OfferingNeed
from tests import factories as f

S = Booking.Status


def page(client, url: str) -> str:
    return html.unescape(client.get(url).content.decode())


@pytest.mark.django_db
def test_contrib_03_share_is_snapshotted_at_request_time(client, offering, diner):
    client.force_login(diner)
    client.post(f"/offerings/{offering.pk}/book", {"seats": "2", "contribution": "share", "allergen_ack": "on"})
    booking = Booking.objects.get()
    assert (booking.contribution, booking.share_cents) == ("share", 800)

    Offering.objects.filter(pk=offering.pk).update(share_per_seat_cents=300)
    booking.refresh_from_db()
    assert booking.share_cents == 800
    assert "Grocery share: $8.00, pay the cook in person" in page(client, f"/bookings/{booking.pk}")


@pytest.mark.django_db(transaction=True)
def test_contrib_04_bring_list_item_is_claimed_once_even_under_a_race(cook):
    offering = f.offering(cook)
    spaghetti = OfferingNeed.objects.create(offering=offering, label="1 lb spaghetti")
    first, second = f.user(first="Ava"), f.user(first="Bruno")

    booking = services.request_booking(offering, first, 1, "ingredients", need=spaghetti)
    spaghetti.refresh_from_db()
    assert spaghetti.claimed_by_booking == booking and booking.share_cents == 0
    with pytest.raises(BookingRejected, match="already claimed"):
        services.request_booking(offering, second, 1, "ingredients", need=spaghetti)
    assert not Booking.objects.filter(diner=second).exists()

    eggs = OfferingNeed.objects.create(offering=offering, label="1 dozen eggs")
    racers = [f.user(first="Nia"), f.user(first="Sam")]
    results = [None, None]

    def claim(index: int) -> None:
        try:
            barrier.wait()
            results[index] = services.request_booking(
                Offering.objects.get(pk=offering.pk), racers[index], 1, "ingredients", need=eggs
            )
        except BookingRejected as error:
            results[index] = error
        finally:
            connection.close()

    barrier = threading.Barrier(2)
    threads = [threading.Thread(target=claim, args=(i,)) for i in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sum(isinstance(r, Booking) for r in results) == 1
    eggs.refresh_from_db()
    assert eggs.claimed_by_booking in [r for r in results if isinstance(r, Booking)]
    assert Booking.objects.filter(diner__in=racers).count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("start", "to", "who"),
    [
        (S.REQUESTED, S.DECLINED, "cook"),
        (S.CONFIRMED, S.CANCELLED, "diner"),
        (S.CONFIRMED, S.CANCELLED, "cook"),
        (S.CONFIRMED, S.CANCELLED, "offering"),
    ],
)
def test_contrib_05_claim_is_released_on_decline_or_cancel(offering, diner, start, to, who):
    need = OfferingNeed.objects.create(offering=offering, label="1 lb spaghetti")
    booking = services.request_booking(offering, diner, 1, "ingredients", need=need)
    if start == S.CONFIRMED:
        services.transition(booking, S.CONFIRMED, offering.cook.user)
    if who == "offering":
        services.cancel_offering(offering)
    else:
        services.transition(booking, to, diner if who == "diner" else offering.cook.user)
    need.refresh_from_db()
    assert need.claimed_by_booking is None
    booking.refresh_from_db()
    assert booking.status == to
    assert booking.contribution_text == "Bring: an item from the bring list (released)"


@pytest.mark.django_db
def test_contrib_06_free_offering_has_no_choice_and_none_needs_a_free_meal(client, cook, diner):
    free = f.offering(cook, title="Soup Lunch", grocery_estimate_cents=0, share_per_seat_cents=0)
    client.force_login(diner)
    form_page = client.get(f"/offerings/{free.pk}").content.decode()
    assert "Request seats" in form_page and 'name="contribution"' not in form_page
    client.post(f"/offerings/{free.pk}/book", {"seats": "1", "contribution": "share", "allergen_ack": "on"})
    booking = Booking.objects.get()
    assert (booking.contribution, booking.share_cents) == ("none", 0)
    assert "Free meal: nothing to chip in" in page(client, f"/bookings/{booking.pk}")
    with pytest.raises(BookingRejected, match="free"):
        services.request_booking(free, f.user(first="Sam"), 1, "share")

    paid = f.offering(cook, title="Pancake Breakfast")
    response = client.post(f"/offerings/{paid.pk}/book", {"seats": "1", "contribution": "none", "allergen_ack": "on"})
    assert response.status_code == 200 and "contribution" in response.context["form"].errors
    assert not Booking.objects.filter(offering=paid).exists()
    with pytest.raises(BookingRejected, match="chip in"):
        services.request_booking(paid, diner, 1, "none")


@pytest.mark.django_db
def test_contrib_07_mark_received_status_codes(client, offering, diner):
    booking = f.booking(offering, diner, status=S.CONFIRMED, contribution="share", share_cents=400)
    url = f"/bookings/{booking.pk}/received"

    client.force_login(diner)
    assert client.post(url).status_code == 403
    client.force_login(f.user(first="Sam"))
    assert client.post(url).status_code == 404
    booking.refresh_from_db()
    assert booking.contribution_received_at is None

    client.force_login(offering.cook.user)
    assert "Mark contribution received" in page(client, f"/bookings/{booking.pk}")
    assert client.post(url).status_code == 303
    booking.refresh_from_db()
    assert booking.contribution_received_at is not None
    assert client.post(url).status_code == 409  # already received

    for status, cancelled_by in ((S.REQUESTED, None), (S.CANCELLED, "diner")):
        extra = {"status": status, "cancelled_by": cancelled_by, "contribution": "share", "share_cents": 400}
        other = f.booking(offering, f.user(first="Nia"), **extra)
        assert client.post(f"/bookings/{other.pk}/received").status_code == 409
        other.refresh_from_db()
        assert other.contribution_received_at is None


@pytest.mark.django_db
def test_contrib_09_kitchen_panel_shows_groceries_and_chip_ins_received_of_expected(client, offering, diner):
    f.booking(offering, diner, status=S.CONFIRMED, seats=2, contribution="share", share_cents=800)
    received = f.booking(offering, f.user(first="Sam"), status=S.CONFIRMED, contribution="share", share_cents=400)
    received.contribution_received_at = received.allergen_ack_at
    received.save()
    f.booking(offering, f.user(first="Nia"), status=S.REQUESTED, contribution="share", share_cents=400)
    client.force_login(offering.cook.user)
    totals = "Groceries $20.00. Chip-ins received $4.00 of $12.00 from confirmed diners."
    assert totals in page(client, "/me")
    kitchen = page(client, "/kitchen")
    assert "Groceries $20.00, $4.00 share per seat. Chip-ins received $4.00 of $12.00 from confirmed diners." in kitchen
    assert "Expected" not in kitchen


@pytest.mark.django_db
def test_contrib_11_custom_terms_are_recorded_seen_by_the_cook_and_agreed(client, offering, diner):
    client.force_login(diner)
    data = {"seats": "1", "contribution": "custom", "amount": "3.00", "allergen_ack": "on"}
    response = client.post(f"/offerings/{offering.pk}/book", {**data, "terms": ""})
    assert response.status_code == 200 and "terms" in response.context["form"].errors
    assert not Booking.objects.exists()

    client.post(f"/offerings/{offering.pk}/book", {**data, "terms": "I'll bring drinks"})
    booking = Booking.objects.get()
    assert (booking.contribution, booking.share_cents, booking.terms) == ("custom", 300, "I'll bring drinks")
    assert "Offered: $3.00 + I'll bring drinks" in page(client, f"/bookings/{booking.pk}")

    cook = offering.cook.user
    client.force_login(cook)
    assert "Offered: $3.00 + I'll bring drinks" in page(client, "/me")  # before confirming
    client.post(f"/bookings/{booking.pk}/transition", {"to": "confirmed"})

    agreed = "Agreed: $3.00 + I'll bring drinks"
    assert agreed in page(client, f"/bookings/{booking.pk}")
    client.force_login(diner)
    assert agreed in page(client, f"/bookings/{booking.pk}")

    client.force_login(f.user(first="Sam"))
    assert client.get(f"/bookings/{booking.pk}").status_code == 404
    for url in (f"/offerings/{offering.pk}", "/me", f"/cooks/{offering.cook_id}"):
        assert "bring drinks" not in page(client, url)
    client.logout()
    assert "bring drinks" not in page(client, f"/offerings/{offering.pk}")


@pytest.mark.django_db
def test_contrib_12_custom_amount_is_capped_by_the_no_profit_rule(client, offering, diner):
    client.force_login(diner)
    data = {"seats": "1", "contribution": "custom", "terms": "Cash", "amount": "5.25", "allergen_ack": "on"}
    response = client.post(f"/offerings/{offering.pk}/book", data)
    assert response.status_code == 200
    assert "Diners together can't pay more than the groceries cost. The most for 1 seat is $5.00." in html.unescape(
        response.content.decode()
    )
    assert not Booking.objects.exists()
    client.post(f"/offerings/{offering.pk}/book", {**data, "amount": "5.00"})
    assert Booking.objects.get().share_cents == 500
