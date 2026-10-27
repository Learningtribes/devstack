"""Resolve and install all public and registered sources together, without bypasses."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from local_input_contract import REGISTRY, stage

parser = argparse.ArgumentParser(__doc__)
parser.add_argument('action', choices=['resolve', 'install'])
args = parser.parse_args()
platform = Path('/runtime/platform-source')
source = Path('/input/platform')
if not platform.exists():
    shutil.copytree(source, platform, symlinks=True)
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
    if not lock.is_file():
        raise SystemExit('Resolve the complete graph before installing')
    subprocess.run(['uv', 'pip', 'sync', '--python', python, '--build-constraint',
                    '/startup/build-constraints.txt', '--no-binary-package', 'lxml',
                    '--no-binary-package', 'xmlsec', str(lock)], check=True)
    subprocess.run(['uv', 'pip', 'check', '--python', python], check=True)
    subprocess.run(['uv', 'pip', 'list', '--python', python, '--format', 'json'], check=True)
