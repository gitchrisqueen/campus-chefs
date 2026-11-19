from django import template

from meals.money import format_cents

register = template.Library()


@register.filter
def money(cents) -> str:
    """{{ offering.share_per_seat_cents|money }} -> "$4.00"."""
    return format_cents(int(cents))
