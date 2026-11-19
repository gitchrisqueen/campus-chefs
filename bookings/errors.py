"""Booking errors and the HTTP status each maps to (plan 3.3, the status-code rule)."""


class BookingError(Exception):
    """An edge that does not exist, or a failed time guard: 409."""

    status = 409

    def __init__(self, message: str, field: str | None = None):
        super().__init__(message)
        self.message = message
        self.field = field


class Forbidden(BookingError):
    """A participant whose role is not allowed on an edge that exists: 403."""

    status = 403


class NotParticipant(BookingError):
    """Neither the diner nor the cook: 404."""

    status = 404


class BookingRejected(BookingError):
    """A booking request that breaks a rule. The form shows the message next to `field`."""
