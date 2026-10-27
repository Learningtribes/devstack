"""Seed named local acceptance users; never print their passwords."""
import json
import os
from pathlib import Path
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from student.models import UserProfile
from student.roles import STUDIO_ADMIN_ACCESS_GROUP
credentials = json.loads(Path('/startup/.acceptance-credentials.json').read_text())
run_id = os.environ['PY313_REPLAY_ID']
roles = {'staff': False, 'learner': False, 'learner2': False, 'other_org': False}
studio_login_roles = {'staff', 'other_org'}
assert credentials.get('run_id') == run_id, 'Protected acceptance identities belong to another run'
assert set(credentials) == {'run_id', *roles}, 'Unexpected acceptance identity set'
for role, should_be_django_staff in roles.items():
    values = credentials[role]
    assert values['username'] == f'py313_{run_id}_{role}'
    assert values['email'] == values['username'] + '@example.test'
    user, created = get_user_model().objects.get_or_create(
        username=values['username'],
        defaults={'email': values['email'], 'is_active': True, 'is_staff': should_be_django_staff},
    )
    if created:
        user.set_password(values['password'])
        user.save(update_fields=['password'])
    assert user.email == values['email'] and user.is_active
    assert user.is_staff is should_be_django_staff and not user.is_superuser, 'Acceptance role differs; refusing escalation'
    if role in studio_login_roles:
        studio_group, _ = Group.objects.get_or_create(name=STUDIO_ADMIN_ACCESS_GROUP)
        user.groups.add(studio_group)
    else:
        assert not user.groups.filter(name=STUDIO_ADMIN_ACCESS_GROUP).exists(), 'Learner acceptance identity has Studio login access'
    assert user.check_password(values['password']), 'Existing acceptance credentials differ; refusing overwrite'
    UserProfile.objects.get_or_create(user=user, defaults={'name': 'Local acceptance ' + role})
    print('Acceptance role ready:', role, 'created:', created)
