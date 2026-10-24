"""Reinstall registered LT XBlock sources, retaining real resources and handlers."""
from pathlib import Path
import shutil
import subprocess
import tempfile

for name in ('iframe-id-xblock', 'lbmdone-xblock', 'ilt-xblock', 'scormxblock-xblock'):
    with tempfile.TemporaryDirectory(prefix='lt-xblock-build-') as directory:
        target = Path(directory) / name
        shutil.copytree(Path('/startup/patched') / name, target,
                        ignore=shutil.ignore_patterns('*.egg-info', '__pycache__'))
        subprocess.run(['/opt/venv/bin/uv', 'pip', 'install', '--python',
                        '/runtime/venv/bin/python', '--reinstall', '--no-deps', str(target)], check=True)
