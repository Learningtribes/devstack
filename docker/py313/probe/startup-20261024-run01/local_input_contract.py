"""Frozen local source contract; runtime never derives expected from host state."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent
REGISTRY = json.loads((ROOT / 'frozen-local-inputs.json').read_text())


def identity(path):
    if path.is_symlink():
        return {'link': os.readlink(path)}
    return {'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def excluded(relative):
    parts = relative.parts
    return (relative.suffix == '.mo' or any(
        (part == 'build' and parts[:i] != ('pdf', 'public'))
        or part in {'dist', '__pycache__', '.git', '.DS_Store'}
        or part.endswith('.egg-info') for i, part in enumerate(parts)))


def verify(name, source=None):
    record = REGISTRY['packages'][name]
    source = Path(source) if source else ROOT / record['source']
    actual = {str(p.relative_to(source)): identity(p) for p in source.rglob('*')
              if (p.is_file() or p.is_symlink()) and (str(p.relative_to(source)) in record['files'] or not excluded(p.relative_to(source)))}
    expected = record['files']
    if actual != expected:
        missing = sorted(expected.keys() - actual.keys())
        extra = sorted(actual.keys() - expected.keys())
        changed = sorted(k for k in actual.keys() & expected.keys() if actual[k] != expected[k])
        raise SystemExit(f'Frozen input mismatch {name}: missing={missing}, extra={extra}, changed={changed}')
    return expected


def stage(name, destination):
    record = REGISTRY['packages'][name]
    source = ROOT / record['source']
    verify(name)
    destination = Path(destination)
    if destination.exists():
        # Do not remove, refresh, or silently overwrite build state.
        verify(name, destination)
        return
    destination.mkdir(parents=True)
    for relative, expected in record['files'].items():
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if 'link' in expected:
            target.symlink_to(expected['link'])
        else:
            shutil.copy2(source / relative, target)
    verify(name, destination)
    generated = {}
    for po in sorted(destination.rglob('*.po')):
        mo = po.with_suffix('.mo')
        subprocess.run(['msgfmt', '--check', '-o', str(mo), str(po)], check=True)
        generated[str(mo.relative_to(destination))] = identity(mo)
    (destination.parent / (name + '.generated.json')).write_text(json.dumps(generated, indent=2) + '\n')


if __name__ == '__main__':
    for name in REGISTRY['packages']:
        verify(name)
    print('PASS frozen local source preflight:', len(REGISTRY['packages']), 'packages')
