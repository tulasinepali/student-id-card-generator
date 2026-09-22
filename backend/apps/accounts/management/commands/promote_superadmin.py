from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = "Promotes any user account to Platform Super Administrator (strictly for the /platform-admin/ portal)."

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Username of the account to promote to Platform Super Admin')

    def handle(self, *args, **options):
        username = options['username']
        user = User.objects.filter(username=username).first()
        if not user:
            raise CommandError(f"User with username '{username}' does not exist.")

        user.role = 'SUPER_ADMIN'
        user.is_superuser = True
        user.is_staff = True
        user.organization = None
        user.save()

        self.stdout.write(self.style.SUCCESS(
            f"Successfully promoted '{username}' to Platform Super Administrator!\n"
            f" - Role: SUPER_ADMIN\n"
            f" - is_superuser: True\n"
            f" - is_staff: True\n"
            f" - Organization: None (Independent Platform Owner)\n"
            f" - Access Portal: http://<domain>/platform-admin/login/"
        ))
