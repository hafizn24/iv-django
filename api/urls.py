from django.urls import path

from . import views

urlpatterns = [
    path("auth/login", views.login),
    path("auth/me", views.me),
    # guard
    path("visitors/ocr", views.nric_ocr),
    path("visitors/upload", views.upload_image),
    path("visitors/check-in", views.check_in),
    path("visitors/<int:pk>/check-out", views.check_out),
    path("visitors", views.visitor_list),
    path("parking-slots/available", views.slots_available),
    path("parking-slots", views.parking_slots, name="parking-slots"),
    path("parking-slots/<int:pk>", views.parking_slots, name="parking-slot"),
    # admin
    path("units", views.units, name="units"),
    path("units/<int:pk>", views.units, name="unit"),
    path("users", views.users, name="users"),
    path("users/<int:pk>", views.users, name="user"),
    path("audit-logs", views.audit_logs),
]
