from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.utils import timezone

from api.models import User


class Command(BaseCommand):
    help = "Create or reset a user in the shared auth_user table (used by Django admin AND the frontend)"

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument("--password", required=True)
        parser.add_argument("--name", default="")
        parser.add_argument("--role", default="admin", choices=["admin", "guard"])

    def handle(self, *args, **opts):
        role = opts["role"]
        user, created = User.objects.update_or_create(
            username=opts["username"],
            defaults={
                "password": make_password(opts["password"]),
                "first_name": opts["name"] or opts["username"],
                "last_name": "",
                "email": "",
                "date_joined": timezone.now(),
                "is_staff": role == "admin",
                "is_superuser": role == "admin",
                "is_active": True,
            },
        )
        self.stdout.write(self.style.SUCCESS(
            f"{'created' if created else 'updated'} {role} '{user.username}' (id={user.id})"
        ))
