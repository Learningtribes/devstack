"""Create run-scoped browser and role-test identities in a mode-600 file."""
import json
import os
from pathlib import Path
import re
import secrets
import stat

ROLES = ('staff', 'learner', 'learner2', 'other_org')


def provision(config):
    run_id = config['run_id']
    if not re.fullmatch(r'[a-z][a-z0-9]{2,15}', run_id):
        raise SystemExit('run_id must be 3-16 lowercase letters or digits for acceptance usernames')
    target = Path(config['credentials_file'])
    parent = target.parent
    if not parent.is_dir() or parent.is_symlink():
        raise SystemExit('Create a dedicated private directory before provisioning acceptance identities')
    if stat.S_IMODE(parent.stat().st_mode) & 0o077:
        raise SystemExit('Acceptance identity directory must have mode 700 or stricter')
    if target.exists() or target.is_symlink():
        raise SystemExit('Refusing to overwrite an existing acceptance identity file')
    data = {'run_id': run_id}
    for role in ROLES:
        username = f'py313_{run_id}_{role}'
        data[role] = {
            'username': username,
            'email': f'{username}@example.test',
            'password': secrets.token_urlsafe(32),
        }
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, 'w') as stream:
            stream.write(json.dumps(data, indent=2, sort_keys=True) + '\n')
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    print('PASS provisioned run-scoped identities:', ', '.join(ROLES), '; password values withheld')
