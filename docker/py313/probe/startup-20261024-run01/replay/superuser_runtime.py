"""Create or update the local devstack superuser inside the runtime (LMS settings).

LOCAL DEVSTACK ONLY: the default credentials edx / edx@example.com / edx are the conventional
open-source devstack login and are not secret. Override with PY313_DEV_SUPERUSER_USERNAME,
PY313_DEV_SUPERUSER_EMAIL and PY313_DEV_SUPERUSER_PASSWORD on the host; ensure_superuser.py
forwards them by name, so the password never appears on a command line. Never prints the password.
"""
import os

from django.contrib.auth import get_user_model
from student.models import UserProfile

username = os.environ.get('PY313_DEV_SUPERUSER_USERNAME', 'edx')
email = os.environ.get('PY313_DEV_SUPERUSER_EMAIL', 'edx@example.com')
password = os.environ.get('PY313_DEV_SUPERUSER_PASSWORD', 'edx')
assert username and email and password, 'Superuser username, email and password must be non-empty'
user, created = get_user_model().objects.get_or_create(username=username, defaults={'email': email})
user.email = email
user.is_active = user.is_staff = user.is_superuser = True
user.set_password(password)
user.save()
UserProfile.objects.get_or_create(user=user, defaults={'name': username})
assert get_user_model().objects.get(username=username).check_password(password)
print('Local devstack superuser ready:', username, email, 'created:', created)
