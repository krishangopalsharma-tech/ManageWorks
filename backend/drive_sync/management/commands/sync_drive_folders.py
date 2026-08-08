from django.core.management.base import BaseCommand
from drive_sync.services.sync import sync_all_folders


class Command(BaseCommand):
    help = 'Sync every connected consignee\'s Drive Workbills/CRN folders. Run via cron at 7am.'

    def handle(self, *args, **options):
        totals = sync_all_folders()
        self.stdout.write(self.style.SUCCESS(
            f"Drive sync done — users={totals['users_synced']} "
            f"bills={totals['bills_synced']} receipts={totals['receipts_synced']} "
            f"needs_review={totals['needs_review']} errors={totals['errors']}"
        ))
