from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Prepare the database on every `docker compose up`: migrate, cache tables, expired sessions."

    def handle(self, *args, **options):
        call_command("migrate", interactive=False, verbosity=1)
        call_command("createcachetable", verbosity=1)
        call_command("clearsessions", verbosity=1)
        # Phase 2 adds: seed_demo --if-empty
        self.stdout.write(self.style.SUCCESS("bootstrap_demo: done"))
