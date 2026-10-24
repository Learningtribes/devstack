"""Copy registered local dependency sources into an isolated writable build root."""
import hashlib
import json
from pathlib import Path
import shutil

INPUT_ROOT = Path('/startup/patched')
OUTPUT_ROOT = Path('/runtime/rebuild-sources-20261025-run25')
MANIFEST_PATH = Path('/runtime/rebuild-sources-20261025-run25.manifest.json')
PACKAGES = (
    'edx-opaque-keys-0.4.4-lt',
    'django-splash-1.3.0',
    'django-require-1.0.11',
    'jazkarta-edx-jsme-690dbf7',
    'django-ratelimit-backend-2.0',
    'edx_completion-5.0.0',
    'djangosaml2idp-da3798e',
    'pysaml2-7.5.5',
    'edx-sga-0.28.0',
    'edx-search-5.0.0-lt',
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
    source = (INPUT_ROOT.parent / 'patched' / package
              if package == 'edx-opaque-keys-0.4.4-lt' else INPUT_ROOT.parent / 'dependencies' / package
              if package in {'django-splash-1.3.0', 'django-require-1.0.11', 'jazkarta-edx-jsme-690dbf7', 'django-ratelimit-backend-2.0', 'edx_completion-5.0.0', 'pysaml2-7.5.5', 'edx-sga-0.28.0', 'edx-search-5.0.0-lt'} else INPUT_ROOT.parent / 'dependencies' / package / 'source' if package == 'djangosaml2idp-da3798e' else INPUT_ROOT / package)
    setup_file = source / 'setup.py'
    if package == 'pysaml2-7.5.5':
        setup_file = source / 'pyproject.toml'
    if not setup_file.is_file():
        raise SystemExit('Missing registered setup.py for ' + package)
    expected[package] = digest_tree(source)

if OUTPUT_ROOT.exists() or MANIFEST_PATH.exists():
    if not OUTPUT_ROOT.is_dir() or not MANIFEST_PATH.is_file():
        raise SystemExit('Existing partial build input found; preserving it for inspection')
    recorded = json.loads(MANIFEST_PATH.read_text())
    actual = {package: digest_tree(OUTPUT_ROOT / package) for package in PACKAGES}
    if recorded != expected or actual != expected:
        raise SystemExit('Existing build input does not match registered sources; preserving it')
    shutil.rmtree(OUTPUT_ROOT)
    for package in PACKAGES:
        source = (INPUT_ROOT.parent / 'patched' / package
                  if package == 'edx-opaque-keys-0.4.4-lt' else INPUT_ROOT.parent / 'dependencies' / package
                  if package in {'django-splash-1.3.0', 'django-require-1.0.11', 'jazkarta-edx-jsme-690dbf7', 'django-ratelimit-backend-2.0', 'edx_completion-5.0.0', 'pysaml2-7.5.5', 'edx-sga-0.28.0', 'edx-search-5.0.0-lt'} else INPUT_ROOT.parent / 'dependencies' / package / 'source' if package == 'djangosaml2idp-da3798e' else INPUT_ROOT / package)
        shutil.copytree(source, OUTPUT_ROOT / package, ignore=IGNORED)
    actual = {package: digest_tree(OUTPUT_ROOT / package) for package in PACKAGES}
    if actual != expected:
        raise SystemExit('Refreshed writable source copy hash mismatch; preserving copy')
    print('Verified existing writable source copy:', len(PACKAGES), 'packages')
else:
    OUTPUT_ROOT.mkdir(parents=True)
    for package in PACKAGES:
        source = (INPUT_ROOT.parent / 'patched' / package
              if package == 'edx-opaque-keys-0.4.4-lt' else INPUT_ROOT.parent / 'dependencies' / package
              if package in {'django-splash-1.3.0', 'django-require-1.0.11', 'jazkarta-edx-jsme-690dbf7', 'django-ratelimit-backend-2.0', 'edx_completion-5.0.0', 'pysaml2-7.5.5', 'edx-sga-0.28.0', 'edx-search-5.0.0-lt'} else INPUT_ROOT.parent / 'dependencies' / package / 'source' if package == 'djangosaml2idp-da3798e' else INPUT_ROOT / package)
        shutil.copytree(source, OUTPUT_ROOT / package, ignore=IGNORED)
    actual = {package: digest_tree(OUTPUT_ROOT / package) for package in PACKAGES}
    if actual != expected:
        raise SystemExit('Writable source copy hash mismatch; preserving copy for inspection')
    MANIFEST_PATH.write_text(json.dumps(expected, indent=2, sort_keys=True) + '\n')
    print('Created verified writable source copy:', len(PACKAGES), 'packages')
for package in PACKAGES:
    print(package, expected[package]['sha256'])
