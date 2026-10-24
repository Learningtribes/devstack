"""Build the registered read-only MongoDBProxy source in a writable directory."""
from pathlib import Path
import shutil
import subprocess
import tempfile

with tempfile.TemporaryDirectory(prefix='mongodbproxy-build-') as temporary:
    target = Path(temporary) / 'MongoDBProxy'
    shutil.copytree('/startup/patched/MongoDBProxy', target,
                    ignore=shutil.ignore_patterns('build', '*.egg-info', '__pycache__'))
    subprocess.run(['/opt/venv/bin/uv', 'pip', 'install', '--python',
                    '/runtime/venv/bin/python', '--reinstall', '--no-deps', str(target)], check=True)
