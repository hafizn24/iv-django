from django.db import models
from django.utils import timezone


class User(models.Model):
    """Django auth_user table, managed by django.contrib.auth + the admin site."""

    is_authenticated = True  # DRF permission checks expect this

    id = models.BigAutoField(primary_key=True)
    username = models.TextField(unique=True)
    password = models.TextField()
    first_name = models.TextField(default="")
    last_name = models.TextField(default="")
    email = models.TextField(default="", blank=True)
    date_joined = models.DateTimeField(default=timezone.now)
    last_login = models.DateTimeField(null=True, blank=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        managed = False
        db_table = "auth_user"

    @property
    def full_name(self):
        return self.first_name or self.username

    def is_admin(self):
        return self.is_staff or self.is_superuser


class Unit(models.Model):
    id = models.BigAutoField(primary_key=True)
    unit_number = models.TextField(unique=True)
    owner_name = models.TextField(default="")
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "units"


class Visitor(models.Model):
    id = models.BigAutoField(primary_key=True)
    full_name = models.TextField()
    nric_number = models.TextField(default="")
    nric_image_path = models.TextField(default="")
    unit = models.ForeignKey(Unit, null=True, blank=True, on_delete=models.SET_NULL, db_column="unit_id")
    purpose = models.TextField(default="")
    parking_slot = models.ForeignKey(
        "ParkingSlot", null=True, blank=True, on_delete=models.SET_NULL, db_column="parking_slot_id"
    )
    check_in_at = models.DateTimeField(auto_now_add=True)
    check_out_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, db_column="created_by")

    class Meta:
        managed = False
        db_table = "visitors"


class ParkingSlot(models.Model):
    id = models.BigAutoField(primary_key=True)
    slot_number = models.TextField(unique=True)
    is_occupied = models.BooleanField(default=False)
    current_visitor = models.ForeignKey(Visitor, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        managed = False
        db_table = "parking_slots"


class AuditLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.TextField()
    entity = models.TextField()
    entity_id = models.BigIntegerField(null=True, blank=True)
    detail = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "audit_logs"
