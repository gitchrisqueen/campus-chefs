import logging

from django.contrib import admin, messages
from django.utils import timezone

from .models import Booking, Review

logger = logging.getLogger(__name__)


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ["id", "offering", "diner", "seats", "status", "contribution", "share_cents"]
    list_filter = ["status", "contribution"]
    readonly_fields = ["created_at"]


@admin.action(description="Hide selected reviews")
def hide_reviews(modeladmin, request, queryset):
    now = timezone.now()
    hidden = 0
    for review in queryset.filter(hidden_at__isnull=True):
        review.hidden_at = now
        review.save(update_fields=["hidden_at"])
        modeladmin.log_change(request, review, "Hidden from the cook page and the average.")
        logger.info("review hidden: review %s by staff %s", review.pk, request.user.pk)
        hidden += 1
    modeladmin.message_user(request, f"Hid {hidden} review{'' if hidden == 1 else 's'}.", messages.SUCCESS)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["id", "booking", "rating", "hidden_at"]
    list_filter = ["rating"]
    readonly_fields = ["booking", "rating"]
    actions = [hide_reviews]
