"""Offering search (plan 3.2). ORM only; `icontains` escapes `%` and `_` (SRCH-03, SRCH-09)."""

from datetime import date, datetime

from django.db.models import Q, QuerySet
from django.utils import timezone

from .models import Offering, OfferingItem


def search_offerings(
    q: str = "",
    *,
    campus: str = "",
    meal_type: str = "",
    on_date: date | None = None,
    diet: str = "",
    exclude_allergens: list[str] | tuple[str, ...] = (),
    max_share_cents: int | None = None,
    now: datetime | None = None,
) -> QuerySet[Offering]:
    """Open offerings whose booking cutoff is still ahead, ordered by serve time.

    The text matches a dish's name, description or ingredients, or the cook's first name.
    Last names are never searched, so search cannot reveal a surname that pages show only
    as an initial (SRCH-10).
    """
    now = now or timezone.now()
    offerings = Offering.objects.filter(
        status=Offering.Status.OPEN, booking_cutoff_at__gt=now, cook__user__is_active=True
    )
    if q:
        offerings = offerings.filter(
            Q(items__name__icontains=q)
            | Q(items__description__icontains=q)
            | Q(items__ingredients__icontains=q)
            | Q(cook__user__first_name__icontains=q)
        )
    if campus:
        offerings = offerings.filter(cook__user__campus__slug=campus)
    if meal_type:
        offerings = offerings.filter(meal_type=meal_type)
    if on_date:
        offerings = offerings.filter(serve_at__date=on_date)
    if diet:
        # Every dish must carry the tag: drop offerings with any dish that lacks it.
        lacking = OfferingItem.objects.exclude(item__dietary_tags__contains=[diet]).values("offering")
        offerings = offerings.exclude(pk__in=lacking)
    if exclude_allergens:
        containing = OfferingItem.objects.filter(item__allergens__overlap=list(exclude_allergens)).values("offering")
        offerings = offerings.exclude(pk__in=containing)
    if max_share_cents is not None:
        offerings = offerings.filter(share_per_seat_cents__lte=max_share_cents)
    return offerings.distinct().order_by("serve_at", "pk")
