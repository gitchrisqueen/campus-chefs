"""Art-director rules on the later-phase screens: no eyebrow labels, no middle-dot strings."""

import re

import pytest

from bookings.models import Booking
from tests import factories as f

S = Booking.Status


def _visible(client, url: str) -> str:
    """The page body with the <title> (where ' · ' is allowed), scripts and tags removed."""
    html = client.get(url).content.decode("utf-8")
    html = re.sub(r"<title>.*?</title>|<script.*?</script>|<style.*?</style>", "", html, flags=re.S)
    return re.sub(r"<[^>]+>", " ", html)


@pytest.mark.django_db
def test_design_rules_no_middle_dot_and_no_eyebrow_on_later_screens(client, settings, offering, diner):
    settings.CC_DEMO_MODE = True  # demo-only markup (banner, footer) renders in demo mode
    booking = f.booking(offering, diner, status=S.CONFIRMED, seats=2, contribution="share", share_cents=800)
    pages = [
        (diner, f"/bookings/{booking.pk}"),
        (diner, "/me"),
        (offering.cook.user, f"/bookings/{booking.pk}"),
        (offering.cook.user, "/me"),
        (offering.cook.user, "/kitchen"),
        (diner, f"/offerings/{offering.pk}"),
        (offering.cook.user, f"/offerings/{offering.pk}"),
    ]
    for user, url in pages:
        client.force_login(user)
        raw = client.get(url).content.decode("utf-8")
        assert 'class="eyebrow"' not in raw, url
        assert "·" not in _visible(client, url), url
    client.force_login(diner)
    detail = client.get(f"/bookings/{booking.pk}").content.decode("utf-8")
    assert re.search(r'class="badge"[^>]*data-booking-status[^>]*>\s*Confirmed\s*<', detail)
