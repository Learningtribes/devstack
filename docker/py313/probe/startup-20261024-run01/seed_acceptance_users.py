"""Seed named local acceptance users; never print their passwords."""
import json
from pathlib import Path
from django.contrib.auth import get_user_model
from student.models import UserProfile
credentials = json.loads(Path('/startup/.acceptance-credentials.json').read_text())
for role, values in credentials.items():
    user, created = get_user_model().objects.get_or_create(username=values['username'], defaults={'email': values['email'], 'is_active': True, 'is_staff': role == 'staff'})
    if created:
        user.set_password(values['password'])
        user.save(update_fields=['password'])
    assert user.check_password(values['password']), 'Existing acceptance credentials differ; refusing overwrite'
    UserProfile.objects.get_or_create(user=user, defaults={'name': 'Local acceptance ' + role})
    print('Acceptance role ready:', role, 'created:', created)
