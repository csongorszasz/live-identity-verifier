#!/bin/sh

echo "Applying database migrations..."
python manage.py makemigrations
python manage.py migrate
echo "Migrations done"

echo "Starting Gunicorn..."
exec "$@"
