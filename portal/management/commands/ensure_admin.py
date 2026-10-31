import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create or promote the initial superuser from environment variables."

    def handle(self, *args, **options):
        username = (os.environ.get("DJANGO_SUPERUSER_USERNAME") or "").strip()
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD") or ""
        email = (os.environ.get("DJANGO_SUPERUSER_EMAIL") or "").strip()

        if not username or not password:
            self.stdout.write("Admin bootstrap skipped: set DJANGO_SUPERUSER_USERNAME and DJANGO_SUPERUSER_PASSWORD.")
            return

        User = get_user_model()
        user = User.objects.filter(username__iexact=username).first()

        if user:
            changed = []
            if not user.is_staff:
                user.is_staff = True
                changed.append("is_staff")
            if not user.is_superuser:
                user.is_superuser = True
                changed.append("is_superuser")
            if email and user.email != email:
                user.email = email
                changed.append("email")
            if changed:
                user.save(update_fields=changed)
                self.stdout.write(self.style.SUCCESS(f"Updated superuser {username} ({', '.join(changed)})."))
            else:
                self.stdout.write(f"Superuser {username} already exists.")
            return

        User.objects.create_superuser(username=username, email=email, password=password)
        self.stdout.write(self.style.SUCCESS(f"Created superuser {username}."))
