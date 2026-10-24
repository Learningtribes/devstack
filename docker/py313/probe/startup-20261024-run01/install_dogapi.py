"""Replay the registered dogapi UDP serialization repair."""
from pathlib import Path
import shutil
import subprocess
import tempfile

with tempfile.TemporaryDirectory(prefix='dogapi-build-') as temporary:
    target = Path(temporary) / 'dogapi'
    shutil.copytree('/startup/patched/dogapi-1.11.1', target,
                    ignore=shutil.ignore_patterns('build', '*.egg-info', '__pycache__'))
    subprocess.run(['/opt/venv/bin/uv', 'pip', 'install', '--python',
                    '/runtime/venv/bin/python', '--reinstall', '--no-deps', str(target)], check=True)
