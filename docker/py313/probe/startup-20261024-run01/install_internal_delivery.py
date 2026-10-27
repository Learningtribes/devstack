"""Resolve and install all public and registered sources together, without bypasses."""
import argparse
import json
from pathlib import Path
import hashlib
import subprocess

from local_input_contract import REGISTRY, stage

parser = argparse.ArgumentParser(__doc__)
parser.add_argument('action', choices=['resolve', 'install'])
args = parser.parse_args()
platform = Path('/runtime/platform-source')
source = Path('/input/platform')
marker = Path('/runtime/internal-delivery-platform.sha256')
identity = hashlib.sha256((source / 'requirements/py313-internal/runtime-public.in').read_bytes()).hexdigest()
if platform.exists() and (not marker.is_file() or marker.read_text() != identity):
    raise SystemExit('Existing platform source has no matching staging marker; preserve and use a new runtime')
if not platform.exists():
    # cp -a preserves dangling Git links across Docker Desktop bind mounts.
    subprocess.run(["cp", "-a", str(source), str(platform)], check=True)
    marker.write_text(identity)
root = Path('/runtime/delivery-sources')
for name in REGISTRY['packages']:
    stage(name, root / name)
# All 20 sources are required and installed in the same dependency transaction.
local = [str(root / name) for name in sorted(REGISTRY['packages'])]
for package in ('common/lib/calc', 'common/lib/capa', 'common/lib/chem',
                'common/lib/dogstats', 'common/lib/safe_lxml',
                'common/lib/sandbox-packages', 'common/lib/symmath',
                'common/lib/xmodule', 'openedx/core/lib/xblock_builtin/xblock_discussion', '.'):
    local.append('-e ' + str(platform / package))
requirements = Path('/runtime/delivery.in')
requirements.write_text('-r ' + str(platform / 'requirements/py313-internal/runtime-public.in')
                        + '\n' + '\n'.join(local) + '\n')
venv = Path('/runtime/venv')
if not venv.exists():
    subprocess.run(['uv', 'venv', '--python', '/usr/local/bin/python3.13', str(venv)], check=True)
python = str(venv / 'bin/python')
lock = Path('/runtime/delivery.lock.txt')
if args.action == 'resolve':
    subprocess.run(['uv', 'pip', 'compile', '--python', python, '--build-constraint',
                    '/startup/build-constraints.txt', '--no-emit-index-url',
                    str(requirements), '-o', str(lock)], check=True)
else:
    # Supported replay installs the reviewed lock, never resolves newer inputs.
    lock = Path('/startup/internal-delivery.lock.txt')
    if not lock.is_file():
        raise SystemExit('Missing committed complete dependency lock')
    subprocess.run(['uv', 'pip', 'sync', '--python', python, '--build-constraint',
                    '/startup/build-constraints.txt', '--no-binary', 'lxml',
                    '--no-binary', 'xmlsec', str(lock)], check=True)
    subprocess.run(['uv', 'pip', 'check', '--python', python], check=True)
    subprocess.run(['uv', 'pip', 'list', '--python', python, '--format', 'json'], check=True)
