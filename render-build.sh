#!/usr/bin/env bash
set -o errexit

# Install dependencies (Render runs this in a fresh build environment)
pip install -r requirements.txt

# Collect static files for Django admin + app
python manage.py collectstatic --noinput

# Apply migrations
python manage.py migrate --noinput
