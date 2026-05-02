#!/bin/bash
# Production backend — PostgreSQL
# Set DB_PASSWORD before running:
#   export DB_PASSWORD=yourpassword
#   bash start_backend_prod.sh

cd /home/adi/ManageWorks/backend
source venv/bin/activate

export DJANGO_SETTINGS_MODULE=config.settings.prod
export DB_NAME=manageworks
export DB_USER=managework
export DB_PASSWORD=Admin@123
export DB_HOST=localhost
export DB_PORT=5432

nohup python manage.py runserver 127.0.0.1:8000 >> /home/adi/ManageWorks/backend.log 2>&1 &
echo $! > /home/adi/ManageWorks/backend.pid
echo "Django started (PID $(cat /home/adi/ManageWorks/backend.pid)) [PROD / PostgreSQL]"
