"""Offline negative preflight checks against the frozen registry."""
from pathlib import Path
import shutil
import tempfile
from local_input_contract import ROOT, REGISTRY, verify

assert 'edx-opaque-keys-0.4.4-lt' not in REGISTRY['packages']
assert 'djangosaml2idp-da3798e' not in REGISTRY['packages']
for name in REGISTRY['packages']:
    verify(name)
name = 'djangosaml2idp-lt'
with tempfile.TemporaryDirectory() as temporary:
    copy = Path(temporary) / name
    shutil.copytree(ROOT / REGISTRY['packages'][name]['source'], copy)
    path = copy / 'djangosaml2idp/views.py'
    original = path.read_bytes()
    for action in ('missing', 'changed', 'extra'):
        if action == 'missing':
            path.unlink()
        elif action == 'changed':
            path.write_bytes(original + b'\n# tampered\n')
        else:
            path.write_bytes(original)
            (copy / 'unexpected.js').write_text('unregistered')
        try:
            verify(name, copy)
        except SystemExit as error:
            assert action + '=' in str(error)
        else:
            raise AssertionError(action + ' accepted')
print('PASS frozen preflight: complete source, missing/changed/extra rejection, no obsolete opaque/SAML source')
