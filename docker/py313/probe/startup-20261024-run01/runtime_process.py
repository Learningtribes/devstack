"""Shared nonsecret Docker options for the registered local runtime."""
import os
from pathlib import Path
import subprocess


def options():
    root = Path(__file__).resolve().parent
    override = os.environ.get('PY313_SECRET_ENV_FILE')
    files = [Path(override)] if override else [root.parents[1] / '.env', root / '.env']
    environment = dict(os.environ)
    for env_file in files:
        for line in env_file.read_text().splitlines():
            if '=' in line and not line.startswith('#'):
                key, value = line.split('=', 1)
                environment[key] = value
    container = environment.get('PY313_RUNTIME_CONTAINER', 'py313-startup-runtime-20261024')
    platform = environment.get('PY313_PLATFORM_ROOT', '/edx/app/edxapp/edx-platform')
    environment['PY313_PLATFORM_ROOT'] = platform
    environment['PYTHONPATH'] = '/startup/settings'
    if subprocess.run(['docker', 'exec', container, 'test', '-s',
                       '/runtime/config/site-ids.json'], check=False).returncode:
        raise SystemExit('Refusing startup before natural-key Site seeding')
    forwarded = []
    for name in sorted(environment):
        if name.startswith('PY313_') or name == 'PYTHONPATH':
            forwarded.extend(['-e', name])
    return container, platform, environment, forwarded
