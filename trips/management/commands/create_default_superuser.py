from getpass import getpass

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create a superuser if it does not already exist."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="admin", help="Superuser username (default: admin)")
        parser.add_argument("--email", default="admin@example.com", help="Superuser email")
        parser.add_argument(
            "--password",
            default=None,
            help="Superuser password. If omitted, you will be prompted unless --no-input is used.",
        )
        parser.add_argument(
            "--no-input",
            action="store_true",
            dest="no_input",
            help="Do not prompt for missing fields.",
        )
        parser.add_argument(
            "--update-existing",
            action="store_true",
            help="Update email/password when the superuser already exists.",
        )

    def handle(self, *args, **options):
        user_model = get_user_model()
        username = options["username"]
        email = options["email"]
        password = options["password"]
        no_input = options["no_input"]
        update_existing = options["update_existing"]

        if not password and not no_input:
            password = self._prompt_for_password()

        if not password and no_input:
            raise CommandError("Password is required when --no-input is used.")

        user = user_model.objects.filter(username=username).first()
        if user:
            if not user.is_superuser:
                raise CommandError(
                    f"User '{username}' already exists but is not a superuser. Choose a different username."
                )

            if update_existing:
                changed_fields = []
                if user.email != email:
                    user.email = email
                    changed_fields.append("email")
                if password:
                    user.set_password(password)
                    changed_fields.append("password")
                if changed_fields:
                    user.save()
                    self.stdout.write(self.style.SUCCESS(f"Updated existing superuser '{username}' ({', '.join(changed_fields)})."))
                else:
                    self.stdout.write(self.style.WARNING(f"Superuser '{username}' already exists. No changes needed."))
            else:
                self.stdout.write(self.style.WARNING(f"Superuser '{username}' already exists. No action taken."))
            return

        user_model.objects.create_superuser(username=username, email=email, password=password)
        self.stdout.write(self.style.SUCCESS(f"Created superuser '{username}'."))

    def _prompt_for_password(self):
        while True:
            password = getpass("Password: ").strip()
            password_confirm = getpass("Password (again): ").strip()
            if not password:
                self.stdout.write(self.style.ERROR("Password cannot be empty."))
                continue
            if password != password_confirm:
                self.stdout.write(self.style.ERROR("Passwords do not match. Try again."))
                continue
            return password
