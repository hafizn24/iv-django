import json

from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .auth import jwt_encode
from .models import AuditLog, ParkingSlot, Unit, User, Visitor
from .serializers import (
    CheckInSerializer,
    ParkingSlotSerializer,
    UnitSerializer,
    UserSerializer,
    VisitorSerializer,
)
from .services import log_action, ocr_nric, upload_nric_image


def admin_only(user):
    return user.is_authenticated and user.is_admin()


# ---------- auth ----------

@api_view(["POST"])
@permission_classes([AllowAny])
def login(request):
    user = User.objects.filter(username=request.data.get("username", ""), is_active=True).first()
    if not user or not check_password(request.data.get("password", ""), user.password):
        return Response({"detail": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)
    role = "admin" if user.is_staff else "guard"
    token = jwt_encode({"uid": user.id, "role": role, "username": user.username})
    log_action(user, "login", "user", user.id)
    return Response({"token": token, "user": UserSerializer(user).data})


@api_view(["GET"])
def me(request):
    return Response(UserSerializer(request.user).data)


# ---------- visitors ----------

@api_view(["POST"])
def nric_ocr(request):
    file = request.FILES.get("image")
    if not file:
        return Response({"detail": "image file required"}, status=400)
    try:
        data = ocr_nric(file.read(), file.content_type)
    except Exception as e:
        return Response({"detail": f"OCR failed: {e}"}, status=502)
    log_action(request.user, "ocr_nric", "visitor", None, {"extracted": bool(data.get("full_name"))})
    return Response(data)


@api_view(["POST"])
def check_in(request):
    ser = CheckInSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    data = ser.validated_data
    with transaction.atomic():
        visitor = Visitor.objects.create(
            full_name=data["full_name"],
            nric_number=data.get("nric_number") or "",
            nric_image_path=data["nric_image_path"],
            unit_id=data.get("unit_id"),
            purpose=data.get("purpose") or "",
            parking_slot_id=data.get("parking_slot_id"),
            created_by=request.user,
        )
        if data.get("parking_slot_id"):
            slot = ParkingSlot.objects.select_for_update().get(id=data["parking_slot_id"])
            if slot.is_occupied:
                raise RuntimeError("Parking slot taken")
            slot.is_occupied = True
            slot.current_visitor = visitor
            slot.save(update_fields=["is_occupied", "current_visitor"])
        log_action(request.user, "checkin", "visitor", visitor.id,
                   {"full_name": visitor.full_name, "slot": data.get("parking_slot_id")})
    return Response(VisitorSerializer(visitor).data, status=201)


@api_view(["POST"])
def upload_image(request):
    """Upload NRIC image before check-in; returns storage path."""
    file = request.FILES.get("image")
    if not file:
        return Response({"detail": "image file required"}, status=400)
    if file.size > 10 * 1024 * 1024:
        return Response({"detail": "image too large (max 10MB)"}, status=400)
    path = upload_nric_image(file, f"{request.user.id}-{request.user.username}")
    log_action(request.user, "upload_nric", "visitor", None, {"path": path})
    return Response({"nric_image_path": path})


@api_view(["POST"])
def check_out(request, pk):
    visitor = Visitor.objects.filter(id=pk, check_out_at__isnull=True).first()
    if not visitor:
        return Response({"detail": "Visitor not checked in"}, status=404)
    from django.utils import timezone
    with transaction.atomic():
        Visitor.objects.filter(id=pk).update(check_out_at=timezone.now())
        slot = ParkingSlot.objects.filter(current_visitor_id=pk).first()
        if slot:
            slot.is_occupied = False
            slot.current_visitor = None
            slot.save(update_fields=["is_occupied", "current_visitor"])
        log_action(request.user, "checkout", "visitor", pk, {"full_name": visitor.full_name})
    visitor.refresh_from_db()
    return Response(VisitorSerializer(visitor).data)


@api_view(["GET"])
def visitor_list(request):
    qs = Visitor.objects.all().order_by("-check_in_at")
    if not admin_only(request.user):
        qs = qs.filter(check_out_at__isnull=True)
    search = request.query_params.get("search", "").strip()
    if search:
        from django.db.models import Q
        qs = qs.filter(Q(full_name__icontains=search) | Q(nric_number__icontains=search))
    date = request.query_params.get("date", "").strip()
    if date:
        qs = qs.extra(where=["date(check_in_at) = %s"], params=[date])
    return Response(VisitorSerializer(qs[:500], many=True).data)


# ---------- parking ----------

@api_view(["GET"])
def slots_available(request):
    qs = ParkingSlot.objects.filter(is_occupied=False).order_by("slot_number")
    return Response(ParkingSlotSerializer(qs, many=True).data)


# ---------- admin CRUD ----------

def _admin_view(serializer_cls, model, request, pk=None, search_fields=("unit_number",)):
    if request.method == "POST":
        ser = serializer_cls(data=request.data)
        ser.is_valid(raise_exception=True)
        obj = ser.save()
        log_action(request.user, f"create_{model.__name__.lower()}", model.__name__.lower(), obj.id, ser.data)
        return Response(ser.data, status=201)
    if request.method == "PUT" or request.method == "PATCH":
        obj = model.objects.filter(id=pk).first()
        if not obj:
            return Response({"detail": "Not found"}, status=404)
        ser = serializer_cls(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        log_action(request.user, f"update_{model.__name__.lower()}", model.__name__.lower(), obj.id, ser.data)
        return Response(ser.data)
    if request.method == "DELETE":
        obj = model.objects.filter(id=pk).first()
        if not obj:
            return Response({"detail": "Not found"}, status=404)
        detail = {"deleted": serializer_cls(obj).data}
        obj.delete()
        log_action(request.user, f"delete_{model.__name__.lower()}", model.__name__.lower(), pk, detail)
        return Response(status=204)
    return Response({"detail": "Method not allowed"}, status=405)


@api_view(["GET", "POST", "PUT", "PATCH", "DELETE"])
def units(request, pk=None):
    if request.method == "GET":
        # any logged-in user (guards need units for the check-in dropdown)
        qs = Unit.objects.filter(active=True).order_by("unit_number")
        return Response(UnitSerializer(qs, many=True).data)
    if not admin_only(request.user):
        return Response({"detail": "Admin only"}, status=403)
    return _admin_view(UnitSerializer, Unit, request, pk)


@api_view(["GET", "POST", "PUT", "PATCH", "DELETE"])
def parking_slots(request, pk=None):
    if request.method == "GET":
        qs = ParkingSlot.objects.all().order_by("slot_number")
        if not admin_only(request.user):
            return Response(ParkingSlotSerializer(qs, many=True).data)
        return Response(ParkingSlotSerializer(qs, many=True).data)
    if not admin_only(request.user):
        return Response({"detail": "Admin only"}, status=403)
    return _admin_view(ParkingSlotSerializer, ParkingSlot, request, pk)


@api_view(["GET", "POST", "PUT", "PATCH", "DELETE"])
def users(request, pk=None):
    if not admin_only(request.user):
        return Response({"detail": "Admin only"}, status=403)
    if request.method == "GET":
        return Response(UserSerializer(User.objects.all().order_by("username"), many=True).data)
    if request.method == "POST":
        ser = UserSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        password = request.data.get("password")
        if not password or len(password) < 6:
            return Response({"password": ["min 6 chars"]}, status=400)
        role = request.data.get("role", "guard")
        if role not in ("admin", "guard"):
            return Response({"role": ["must be admin or guard"]}, status=400)
        user = User.objects.create(
            username=ser.validated_data["username"],
            password=make_password(password),
            first_name=ser.validated_data.get("first_name", ""),
            is_staff=role == "admin",
            is_superuser=False,
        )
        log_action(request.user, "create_user", "user", user.id, {"username": user.username, "role": role})
        return Response(UserSerializer(user).data, status=201)
    if request.method in ("PUT", "PATCH"):
        user = User.objects.filter(id=pk).first()
        if not user:
            return Response({"detail": "Not found"}, status=404)
        ser = UserSerializer(user, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        updates = {k: v for k, v in ser.validated_data.items()}
        if "username" in updates and updates["username"] != user.username:
            if User.objects.filter(username=updates["username"]).exclude(id=pk).exists():
                return Response({"username": ["already exists"]}, status=400)
        if request.data.get("password"):
            updates["password"] = make_password(request.data["password"])
        role = request.data.get("role")
        if role in ("admin", "guard"):
            updates["is_staff"] = role == "admin"
        for k, v in updates.items():
            setattr(user, k, v)
        user.save()
        log_action(request.user, "update_user", "user", user.id, {"changes": list(updates)})
        return Response(UserSerializer(user).data)
    if request.method == "DELETE":
        user = User.objects.filter(id=pk).first()
        if not user:
            return Response({"detail": "Not found"}, status=404)
        if user.id == request.user.id:
            return Response({"detail": "Cannot delete yourself"}, status=400)
        user.is_active = False
        user.save(update_fields=["is_active"])
        log_action(request.user, "deactivate_user", "user", user.id, {"username": user.username})
        return Response(status=204)


@api_view(["GET"])
def audit_logs(request):
    if not admin_only(request.user):
        return Response({"detail": "Admin only"}, status=403)
    qs = AuditLog.objects.select_related("user").all().order_by("-created_at")[:500]
    data = [
        {
            "id": a.id,
            "user": a.user.full_name if a.user else None,
            "action": a.action,
            "entity": a.entity,
            "entity_id": a.entity_id,
            "detail": a.detail,
            "created_at": a.created_at,
        }
        for a in qs
    ]
    return Response(data)
