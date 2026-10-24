"""Install the registered externality source from a writable temporary copy."""
from pathlib import Path
import shutil
import subprocess
import tempfile

source = Path('/startup/patched/externality-xblock')
with tempfile.TemporaryDirectory(prefix='externality-build-') as directory:
    target = Path(directory) / source.name
    shutil.copytree(source, target, ignore=shutil.ignore_patterns('*.egg-info', '__pycache__'))
    subprocess.run([
        '/opt/venv/bin/uv', 'pip', 'install', '--python', '/runtime/venv/bin/python',
        '--reinstall', '--no-deps', str(target)
    ], check=True)
