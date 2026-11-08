from rest_framework import serializers

from .models import ParkingSlot, Unit, User, Visitor


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="first_name", required=False, allow_blank=True)
    role = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "full_name", "role", "is_active"]

    def get_role(self, obj) -> str:
        return "admin" if obj.is_staff or obj.is_superuser else "guard"


class UnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unit
        fields = ["id", "unit_number", "owner_name", "active", "created_at"]


class ParkingSlotSerializer(serializers.ModelSerializer):
    current_visitor_id = serializers.IntegerField(read_only=True, allow_null=True)

    class Meta:
        model = ParkingSlot
        fields = ["id", "slot_number", "is_occupied", "current_visitor_id"]


class VisitorSerializer(serializers.ModelSerializer):
    unit_number = serializers.CharField(source="unit.unit_number", read_only=True, default=None)
    parking_slot_number = serializers.CharField(source="parking_slot.slot_number", read_only=True, default=None)
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True, default=None)
    nric_image_url = serializers.SerializerMethodField()

    class Meta:
        model = Visitor
        fields = [
            "id", "full_name", "nric_number", "nric_image_path", "nric_image_url",
            "unit_id", "unit_number", "purpose", "parking_slot_id", "parking_slot_number",
            "check_in_at", "check_out_at", "created_by_name",
        ]

    def get_nric_image_url(self, obj):
        if not obj.nric_image_path:
            return None
        from django.conf import settings
        return f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1/object/public/{settings.SUPABASE_BUCKET}/{obj.nric_image_path}"


class CheckInSerializer(serializers.Serializer):
    nric_image_path = serializers.CharField()
    full_name = serializers.CharField(max_length=200)
    nric_number = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    unit_id = serializers.IntegerField(required=False, allow_null=True)
    purpose = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    parking_slot_id = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, data):
        from .models import ParkingSlot, Unit
        if data.get("parking_slot_id"):
            slot = ParkingSlot.objects.filter(id=data["parking_slot_id"], is_occupied=False).first()
            if not slot:
                raise serializers.ValidationError("Parking slot unavailable")
        if data.get("unit_id") and not Unit.objects.filter(id=data["unit_id"]).exists():
            raise serializers.ValidationError("Unit not found")
        return data
