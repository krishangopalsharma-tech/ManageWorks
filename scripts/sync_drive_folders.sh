#!/bin/bash
# Daily 7am Drive sync — pulls new bills/receipts from every connected
# consignee's Workbills/CRN folders. Same code path as the manual "Sync Data"
# button (drive_sync/services/sync.py::sync_all_folders), just looped over
# every user instead of one. Safe to run manually too.

cd /home/adi/ManageWorks/backend || exit 1

export DJANGO_SETTINGS_MODULE=config.settings.prod
export DB_NAME=manageworks
export DB_USER=managework
export DB_PASSWORD=Admin@123
export DB_HOST=localhost
export DB_PORT=5432

LOG=/home/adi/ManageWorks/backend/drive_sync.log
echo "$(date -Is) starting drive sync" >> "$LOG"
./venv/bin/python manage.py sync_drive_folders >> "$LOG" 2>&1
echo "$(date -Is) drive sync finished" >> "$LOG"
