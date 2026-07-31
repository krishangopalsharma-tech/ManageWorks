#!/bin/bash
# Health-check + self-heal for manageworks.service.
#
# This box appears to suspend/resume after idle periods, which drops the
# Postgres connection out from under Django. Postgres itself recovers fine
# (systemd/pg_lsclusters bring it back in ~1-2s), but `manage.py runserver`
# doesn't always recover from the abrupt disconnect — it can end up alive
# (process still running, systemd sees "active") but not actually bound to
# port 8000 anymore. Since the process never exits, systemd's Restart=always
# never fires. This script pokes it from outside every few minutes and, if
# it's unresponsive, kills it — systemd then restarts it cleanly on its own.
#
# No sudo needed: this only ever kills processes owned by this same user
# (the systemd unit runs as User=adi), which any user can already do.

LOG=/home/adi/ManageWorks/watchdog.log
CODE=$(curl -s -o /dev/null -w "%{http_code}" -m 5 http://127.0.0.1:8000/api/auth/me/)

# Any real HTTP response (even 401/403) means the server is up and answering.
# "000" means curl couldn't connect at all — that's the actual failure mode.
if [ "$CODE" = "000" ]; then
    echo "$(date -Is) backend unresponsive (curl -> $CODE), restarting" >> "$LOG"
    pkill -f "manage.py runserver 127.0.0.1:8000"
fi
