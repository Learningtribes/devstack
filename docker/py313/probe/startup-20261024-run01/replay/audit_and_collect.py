"""Collect selected non-secret evidence and verify export/runtime source identity."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from core import (STARTUP_REL, capture, config_hash, docker_exec, load_config, ownership,
                  read_json, redact_values, save_new)


def entries(base):
    return {str(path.relative_to(base)): ({'link': os.readlink(path)} if path.is_symlink()
            else {'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
            for path in base.rglob('*') if path.is_file() or path.is_symlink()}


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--label', required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[a-zA-Z0-9_-]+', args.label):
        parser.error('Invalid evidence label')
    config = load_config(args.config)
    ownership(config)
    root = Path(config['evidence_dir'])
    # Reserve the whole audit before any sub-command. Never partially overwrite.
    reservation = root / (args.label + '-audit-start.json')
    save_new(reservation, {'configuration_sha256': config_hash(config)})
    source = Path(config['export_dir'])
    identity = read_json(source / 'export-identity.json')
    for key, base in [('startup', source / 'devstack' / STARTUP_REL), ('platform', source / 'platform')]:
        actual = entries(base)
        expected = identity['trees'][key]
        assert all(actual.get(path) == value for path, value in expected.items()), key
        extra = set(actual) - set(expected)
        assert extra == ({'.acceptance-credentials.json', 'jwt-private.pem'} if key == 'startup' else set()), (key, extra)
    code = '''import hashlib,json,os
from pathlib import Path
base=Path('/runtime/platform-source')
out={str(p.relative_to(base)):({'link':os.readlink(p)} if p.is_symlink() else {'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}) for p in base.rglob('*') if p.is_file() or p.is_symlink()}
print(json.dumps(out))'''
    capture(config, args.label + '-runtime-identity', docker_exec(config, '/runtime/venv/bin/python', '-c', code))
    runtime = read_json(root / (args.label + '-runtime-identity.txt'))
    expected = identity['trees']['platform']
    changed = [path for path, value in expected.items() if runtime.get(path) != value]
    assert not changed, changed
    selected = json.loads(subprocess.check_output(['docker', 'inspect', '--format',
        '{"id":{{json .Id}},"image":{{json .Image}},"mounts":{{json .Mounts}},"ports":{{json .NetworkSettings.Ports}}}', config['runtime_container']], text=True))
    save_new(root / (args.label + '-selected-inspect.json'), selected)
    for system in ('lms', 'cms'):
        capture(config, args.label + '-' + system + '-worker', docker_exec(config, 'cat', '/runtime/logs/' + system + '-worker.log'))
    # Never collect HTTP logs, which may include authentication request bodies.
    values = redact_values(config)
    patterns = [rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
                rb'\b(?:ghp_|github_pat_|sk-proj-)[A-Za-z0-9_-]{20,}', rb'\bAKIA[A-Z0-9]{16}\b']
    findings = []
    for path in root.rglob('*'):
        if not path.is_file():
            continue
        raw = path.read_bytes()
        if any(value.encode() in raw for value in values) or any(re.search(pattern, raw) for pattern in patterns):
            findings.append(str(path.relative_to(root)))
    report = {'run_id': config['run_id'], 'configuration_sha256': config_hash(config),
              'platform_original_files_equal': len(expected), 'generated_extras': len(set(runtime) - set(expected)),
              'http_logs_exported': False, 'secret_findings': findings}
    save_new(root / (args.label + '-audit.json'), report)
    assert not findings, findings
    manifest = {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in root.rglob('*') if path.is_file()}
    save_new(root / (args.label + '-sha256.json'), manifest)
    print('PASS export and runtime sources, selected identity, worker logs, protected-value/pattern scan')


if __name__ == '__main__':
    main()
