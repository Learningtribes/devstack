"""Copy registered local dependency sources into an isolated writable build root."""
import hashlib
import json
from pathlib import Path
import shutil

INPUT_ROOT = Path('/startup/patched')
OUTPUT_ROOT = Path('/runtime/rebuild-sources-20261025')
MANIFEST_PATH = Path('/runtime/rebuild-sources-20261025.manifest.json')
PACKAGES = (
    'externality-xblock',
    'iframe-id-xblock',
    'ilt-xblock',
    'lbmdone-xblock',
    'MongoDBProxy',
    'scormxblock-xblock',
    'xblock-pdf',
)
IGNORED = shutil.ignore_patterns('build', 'dist', '*.egg-info', '__pycache__', '.git', '.DS_Store')


def digest_tree(root):
    entries = {}
    for path in sorted(root.rglob('*')):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in {'build', 'dist', '__pycache__', '.git'} or part.endswith('.egg-info')
               or part == '.DS_Store' for part in relative.parts):
            continue
        entries[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    digest = hashlib.sha256(json.dumps(entries, sort_keys=True).encode()).hexdigest()
    return {'sha256': digest, 'files': entries}


expected = {}
for package in PACKAGES:
    source = INPUT_ROOT / package
    if not (source / 'setup.py').is_file():
        raise SystemExit('Missing registered setup.py for ' + package)
    expected[package] = digest_tree(source)

if OUTPUT_ROOT.exists() or MANIFEST_PATH.exists():
    if not OUTPUT_ROOT.is_dir() or not MANIFEST_PATH.is_file():
        raise SystemExit('Existing partial build input found; preserving it for inspection')
    recorded = json.loads(MANIFEST_PATH.read_text())
    actual = {package: digest_tree(OUTPUT_ROOT / package) for package in PACKAGES}
    if recorded != expected or actual != expected:
        raise SystemExit('Existing build input does not match registered sources; preserving it')
    print('Verified existing writable source copy:', len(PACKAGES), 'packages')
else:
    OUTPUT_ROOT.mkdir(parents=True)
    for package in PACKAGES:
        shutil.copytree(INPUT_ROOT / package, OUTPUT_ROOT / package, ignore=IGNORED)
    actual = {package: digest_tree(OUTPUT_ROOT / package) for package in PACKAGES}
    if actual != expected:
        raise SystemExit('Writable source copy hash mismatch; preserving copy for inspection')
    MANIFEST_PATH.write_text(json.dumps(expected, indent=2, sort_keys=True) + '\n')
    print('Created verified writable source copy:', len(PACKAGES), 'packages')
for package in PACKAGES:
    print(package, expected[package]['sha256'])
