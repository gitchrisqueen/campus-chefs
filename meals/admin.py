from django.contrib import admin

from .models import Campus, CookProfile, MenuItem, Offering, OfferingItem, OfferingNeed


@admin.register(Campus)
class CampusAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "timezone"]
    prepopulated_fields = {"slug": ["name"]}


@admin.register(CookProfile)
class CookProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "food_safety_ack_at"]
    search_fields = ["user__email", "user__first_name"]


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ["name", "cook", "meal_type", "course", "is_specialty", "is_active"]
    list_filter = ["meal_type", "course", "is_specialty", "is_active"]
    search_fields = ["name", "ingredients"]


class OfferingItemInline(admin.TabularInline):
    model = OfferingItem
    extra = 0


class OfferingNeedInline(admin.TabularInline):
    model = OfferingNeed
    extra = 0


@admin.register(Offering)
class OfferingAdmin(admin.ModelAdmin):
    list_display = ["title", "cook", "serve_at", "capacity", "status", "share_per_seat_cents"]
    list_filter = ["status", "meal_type", "fulfillment"]
    inlines = [OfferingItemInline, OfferingNeedInline]
