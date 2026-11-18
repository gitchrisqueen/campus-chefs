"""REV-01..07: reviews of completed bookings (plan 1.2, 3.1, 7.2)."""

from datetime import timedelta

import pytest
from django.utils import timezone

from bookings import services
from bookings.errors import BookingError
from bookings.models import Booking, Review
from tests import factories as f

S = Booking.Status


@pytest.fixture
def completed(offering, diner):
    return f.booking(offering, diner, status=S.COMPLETED, closed_at=timezone.now() - timedelta(days=1))


def url(booking):
    return f"/bookings/{booking.pk}/review"


def average(client, cook):
    return client.get(f"/cooks/{cook.pk}").context["rating"]


@pytest.mark.django_db
def test_rev_01_diner_reviews_a_completed_booking_and_the_average_includes_it(client, completed, diner, offering):
    client.force_login(diner)
    page = client.get(completed.get_absolute_url())
    assert 'name="rating"' in page.content.decode()
    response = client.post(url(completed), {"rating": "5", "the_good": "Fluffy pancakes."})
    assert response.status_code == 303
    review = Review.objects.get()
    assert (review.booking, review.rating, review.hidden_at) == (completed, 5, None)
    assert review.the_good == "Fluffy pancakes."
    cook_page = client.get(f"/cooks/{offering.cook.pk}")
    assert cook_page.context["rating"] == {"average": 5, "count": 1}
    assert "Fluffy pancakes." in cook_page.content.decode()
    assert "Your review" in client.get(completed.get_absolute_url()).content.decode()


@pytest.mark.django_db
def test_rev_02_review_of_a_confirmed_booking_is_403(client, offering, diner):
    booking = f.booking(offering, diner, status=S.CONFIRMED)
    client.force_login(diner)
    assert 'name="rating"' not in client.get(booking.get_absolute_url()).content.decode()
    assert client.post(url(booking), {"rating": "5"}).status_code == 403
    assert Review.objects.count() == 0


@pytest.mark.django_db
def test_rev_03_second_review_is_rejected(client, completed, diner):
    client.force_login(diner)
    assert client.post(url(completed), {"rating": "4"}).status_code == 303
    assert client.post(url(completed), {"rating": "1"}).status_code == 409
    assert list(Review.objects.values_list("rating", flat=True)) == [4]
    assert 'name="rating"' not in client.get(completed.get_absolute_url()).content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize("rating", ["0", "6", "", "x"])
def test_rev_04_rating_outside_1_to_5_shows_a_form_error(client, completed, diner, rating):
    client.force_login(diner)
    response = client.post(url(completed), {"rating": rating, "the_good": "Tasty."})
    assert response.status_code == 200
    assert response.context["review_form"].errors["rating"]
    assert "Please fix the problems below." in response.content.decode()
    assert Review.objects.count() == 0


@pytest.mark.django_db
def test_rev_05_review_after_14_days_is_rejected(offering, diner):
    now = timezone.now()
    booking = f.booking(offering, diner, status=S.COMPLETED, closed_at=now - timedelta(days=14, minutes=1))
    with pytest.raises(BookingError):
        services.submit_review(booking, diner, 5, now=now)
    assert Review.objects.count() == 0
    brunch = f.offering(offering.cook, title="Brunch")
    on_time = f.booking(brunch, diner, status=S.COMPLETED, closed_at=now - timedelta(days=14))
    assert services.submit_review(on_time, diner, 5, now=now).rating == 5


@pytest.mark.django_db
def test_rev_05_view_hides_the_form_and_rejects_a_post_after_14_days(client, offering, diner):
    booking = f.booking(offering, diner, status=S.COMPLETED, closed_at=timezone.now() - timedelta(days=15))
    client.force_login(diner)
    assert 'name="rating"' not in client.get(booking.get_absolute_url()).content.decode()
    assert client.post(url(booking), {"rating": "5"}).status_code == 409
    assert Review.objects.count() == 0


@pytest.mark.django_db
def test_rev_06_hidden_review_is_absent_and_not_in_the_average(client, completed, diner, offering):
    other = f.user(first="Sam", last="Turner")
    second = f.booking(f.offering(offering.cook, title="Brunch"), other, status=S.COMPLETED, closed_at=timezone.now())
    Review.objects.create(booking=completed, rating=5, the_good="Loved it.")
    Review.objects.create(booking=second, rating=1, the_bad="Cold eggs.", hidden_at=timezone.now())
    page = client.get(f"/cooks/{offering.cook.pk}")
    assert page.context["rating"] == {"average": 5, "count": 1}
    body = page.content.decode()
    assert "Loved it." in body and "Cold eggs." not in body
    assert "5.0 out of 5 (1 review)" in body


@pytest.mark.django_db
def test_rev_06_cook_page_lists_reviews_newest_first(client, offering, diner):
    cook = offering.cook
    old = f.booking(offering, diner, status=S.COMPLETED, closed_at=timezone.now())
    new = f.booking(f.offering(cook, title="Brunch"), diner, status=S.COMPLETED, closed_at=timezone.now())
    Review.objects.create(booking=old, rating=3, the_good="First one.")
    Review.objects.create(booking=new, rating=4, the_good="Second one.")
    body = client.get(f"/cooks/{cook.pk}").content.decode()
    assert body.index("Second one.") < body.index("First one.")


@pytest.mark.django_db
def test_rev_06_admin_hide_action_hides_selected_reviews(client, completed):
    admin = f.user(first="Staff", last="Person", is_staff=True, is_superuser=True)
    review = Review.objects.create(booking=completed, rating=2)
    client.force_login(admin)
    response = client.post("/admin/bookings/review/", {"action": "hide_reviews", "_selected_action": [review.pk]})
    assert response.status_code == 302
    review.refresh_from_db()
    assert review.hidden_at is not None


@pytest.mark.django_db
def test_rev_07_unrelated_user_gets_404_and_the_cook_gets_403(client, completed, offering):
    client.force_login(f.user(first="Sam", last="Turner"))
    assert client.post(url(completed), {"rating": "5"}).status_code == 404
    client.force_login(offering.cook.user)
    assert client.post(url(completed), {"rating": "5"}).status_code == 403
    assert 'name="rating"' not in client.get(completed.get_absolute_url()).content.decode()
    assert Review.objects.count() == 0
