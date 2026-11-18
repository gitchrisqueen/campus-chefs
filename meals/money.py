"""Money is integer cents everywhere (plan 3.1, 3.5). The app records grocery amounts; it never moves money."""


def format_cents(cents: int) -> str:
    """Render cents as dollars: 400 -> "$4.00"."""
    return f"${cents // 100}.{cents % 100:02d}"


def suggested_share_cents(estimate_cents: int, capacity: int) -> int:
    """The grocery estimate divided by (seats + 1), because the cook eats too, rounded down to $0.25."""
    return estimate_cents // (capacity + 1) // 25 * 25
