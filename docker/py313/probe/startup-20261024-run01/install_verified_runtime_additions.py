"""Install registered runtime repairs from hash-verified writable sources."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

SOURCES = {
    'fs-2.4.16': Path('/startup/dependencies/fs-2.4.16'),
    'xblock_poll-1.15.1': Path('/startup/dependencies/xblock_poll-1.15.1'),
    'edx_drf_extensions-10.6.0': Path('/startup/dependencies/edx_drf_extensions-10.6.0'),
    'dogapi-1.11.1': Path('/startup/patched/dogapi-1.11.1'),
}
DESTINATION = Path('/runtime/verified-runtime-additions-v1')
IGNORED = shutil.ignore_patterns('build', 'dist', '*.egg-info', '__pycache__', '.git', '.DS_Store')


def hashes(root):
    result = {}
    for entry in sorted(root.rglob('*')):
        relative = entry.relative_to(root)
        if any(part in {'build', 'dist', '__pycache__', '.git', '.DS_Store'}
               or part.endswith('.egg-info') for part in relative.parts):
            continue
        if entry.is_file():
            result[relative.as_posix()] = hashlib.sha256(entry.read_bytes()).hexdigest()
    return result


manifest = {}
for name, source in SOURCES.items():
    if not (source / 'setup.py').is_file():
        raise SystemExit('Missing registered package source: ' + name)
    expected = hashes(source)
    target = DESTINATION / name
    if target.exists():
        if hashes(target) != expected:
            raise SystemExit('Preserving mismatched existing build source: ' + name)
    else:
        shutil.copytree(source, target, ignore=IGNORED)
    if hashes(target) != expected:
        raise SystemExit('Build source hash mismatch: ' + name)
    manifest[name] = expected
    subprocess.run(['uv', 'pip', 'install', '--python', '/runtime/venv/bin/python',
                    '--no-deps', str(target)], check=True)

(DESTINATION / 'source-hashes.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
subprocess.run(['uv', 'pip', 'check', '--python', '/runtime/venv/bin/python'], check=True)
