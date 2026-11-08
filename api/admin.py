import json

from django.contrib import admin

from .models import AuditLog, ParkingSlot, Unit, Visitor

# Note: auth_user (users) is registered by django.contrib.admin automatically
# with the stock UserAdmin — password hashing, staff flags, groups all built in.


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ("unit_number", "owner_name", "active")
    search_fields = ("unit_number", "owner_name")
    list_filter = ("active",)


@admin.register(ParkingSlot)
class ParkingSlotAdmin(admin.ModelAdmin):
    list_display = ("slot_number", "is_occupied", "current_visitor")
    list_filter = ("is_occupied",)


@admin.register(Visitor)
class VisitorAdmin(admin.ModelAdmin):
    list_display = ("full_name", "nric_number", "unit", "parking_slot", "check_in_at", "check_out_at")
    list_filter = ("unit", "parking_slot")
    search_fields = ("full_name", "nric_number")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "action", "entity", "entity_id")
    list_filter = ("action", "entity")
    search_fields = ("user__full_name",)

    def has_add_permission(self, request):
        return False  # audit entries are written by the API only

    def detail_preview(self, obj):
        return json.dumps(obj.detail)[:120]
