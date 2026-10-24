"""Verify the exact registered theme commit and stage it before Django setup."""
import hashlib
import json
from pathlib import Path
import shutil

source = Path('/startup/theme-inputs/7c0dbec1b0a7/hawthorn')
theme = Path('/runtime/themes-7c0dbec1b0a7/hawthorn')
record = json.loads((source.parent / 'source-sha256.json').read_text())
actual = {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest()
          for p in source.rglob('*') if p.is_file()}
assert actual == record['files'], 'Theme input tree differs from registered commit'
for name, digest in actual.items():
    target = theme / name
    if target.exists():
        assert hashlib.sha256(target.read_bytes()).hexdigest() == digest, target
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / name, target)
print('Verified/staged theme source:', record['commit'], len(actual), 'files', flush=True)
