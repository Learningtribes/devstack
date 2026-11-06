"""Stage the replay tooling and run Platform's own complete install input preparation.

All package inputs (git pins, companions, application lock) are owned by Platform;
the paired startup export only supplies the replay scripts copied to /startup.

Only the task-owned container layer (/startup and /input/ci.lock) is writable.
/paired-startup, /input/platform and /canary remain read-only source mounts.
"""
import importlib.util
from pathlib import Path
import subprocess

PLACEHOLDERS = {'.acceptance-credentials.json', 'jwt-private.pem'}


def prepare(paired=Path('/paired-startup'), startup=Path('/startup'),
            runtime=Path('/runtime'), lock=Path('/input/ci.lock'), canary=Path('/canary'),
            platform=Path('/input/platform')):
    if any(runtime.iterdir()):
        raise ValueError('Installation requires an empty runtime volume')
    if lock.exists() or lock.is_symlink():
        raise ValueError('Refusing existing generated complete lock')
    if not startup.is_dir() or {p.name for p in startup.iterdir()} != PLACEHOLDERS:
        raise ValueError('Startup staging must contain only protected mount points')
    required = ['image-inputs.py', 'install.py', 'companion_inputs.py',
                'verify-platform-identity.py', 'paver-tools.lock', 'test-tools.lock']
    for name in required:
        if not (canary / name).is_file():
            raise ValueError('Missing current Platform install contract: ' + name)
    # Validate Platform's archives, lock and requirement pins BEFORE staging.
    spec = importlib.util.spec_from_file_location('current_companions', canary / 'companion_inputs.py')
    companions = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(companions)
    companions.application_lock()
    companions.verify_requirements(platform / 'requirements/py313-internal/runtime-public.in')
    for source in sorted(paired.iterdir()):
        if source.name not in PLACEHOLDERS:
            subprocess.run(['cp', '-a', str(source), str(startup / source.name)], check=True)
    subprocess.run(['/usr/local/bin/python3.13', '-B', str(canary / 'image-inputs.py')], check=True)
    if not lock.is_file():
        raise ValueError('Platform preparation did not produce the complete lock')
    print('PASS current complete application/Paver/test inputs prepared; original exports immutable')


if __name__ == '__main__':
    prepare()
