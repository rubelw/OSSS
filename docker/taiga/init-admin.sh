#!/bin/bash
set -e

cd /taiga-back

echo "Checking for existing Taiga admin..."

python manage.py shell <<'EOF'
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(is_superuser=True).exists():
    print("Creating default admin user...")
    User.objects.create_superuser(
        username="admin",
        email="admin@example.com",
        password="admin123"
    )
else:
    print("Admin already exists.")
EOF
