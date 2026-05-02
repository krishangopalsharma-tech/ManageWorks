#!/bin/bash
cd /home/adi/ManageWorks/backend
source venv/bin/activate
export DJANGO_SETTINGS_MODULE=config.settings.dev
nohup python manage.py runserver 127.0.0.1:8000 >> /home/adi/ManageWorks/backend.log 2>&1 &
echo $! > /home/adi/ManageWorks/backend.pid
echo "Django started (PID $(cat /home/adi/ManageWorks/backend.pid)) [DEV / SQLite]"
