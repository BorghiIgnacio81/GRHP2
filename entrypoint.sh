#!/bin/bash
set -e

# Esperar a la base de datos (simple netcat loop si se provee DB_HOST/DB_PORT)
if [ -n "$DB_HOST" ] && [ -n "$DB_PORT" ]; then
  echo "Esperando a la base de datos $DB_HOST:$DB_PORT..."
  until nc -z "$DB_HOST" "$DB_PORT"; do
    sleep 1
  done
fi

python manage.py migrate --noinput
if [ "$DJANGO_DEBUG" = "True" ] || [ "$DJANGO_DEBUG" = "1" ]; then
  python manage.py collectstatic --noinput || true
  python manage.py runserver 0.0.0.0:8000
else
  gunicorn gestion_rrhh.wsgi:application --bind 0.0.0.0:8000 --workers 2
fi
