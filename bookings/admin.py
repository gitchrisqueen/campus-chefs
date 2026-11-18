from django.contrib import admin
from django.utils import timezone

from .models import Booking, Review


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ["id", "offering", "diner", "seats", "status", "contribution", "share_cents"]
    list_filter = ["status", "contribution"]
    readonly_fields = ["created_at"]


@admin.action(description="Hide selected reviews")
def hide_reviews(modeladmin, request, queryset):
    queryset.filter(hidden_at__isnull=True).update(hidden_at=timezone.now())


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["id", "booking", "rating", "hidden_at"]
    list_filter = ["rating"]
    actions = [hide_reviews]
