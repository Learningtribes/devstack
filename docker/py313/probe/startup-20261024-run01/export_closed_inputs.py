"""Export committed inputs only to a new directory, retaining symlink identity.

Use after committing executable input changes. No working-tree copy or old run
is consulted. Explicit vendor archives are verified before extraction.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

parser = argparse.ArgumentParser(__doc__)
parser.add_argument('--destination', type=Path, required=True)
parser.add_argument('--platform', type=Path, required=True)
args = parser.parse_args()
args.destination.mkdir(parents=True, exist_ok=False)
devstack = Path(__file__).resolve().parents[4]
startup_relative = Path(__file__).resolve().parent.relative_to(devstack)
identities = {}
for label, repo, prefix in [('devstack', devstack, startup_relative), ('platform', args.platform, None)]:
    commit = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
    command = ['git', '-C', str(repo), 'archive', commit]
    if prefix:
        command.append(str(prefix))
    data = subprocess.check_output(command)
    target = args.destination / label
    target.mkdir()
    # Git archives contain audited repository symlinks, including intentionally
    # dangling developer-skill links. Preserve their literal target; never follow.
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        archive.extractall(target, filter='fully_trusted')
    identities[label] = {'commit': commit, 'archive_sha256': hashlib.sha256(data).hexdigest()}
startup = args.destination / 'devstack' / startup_relative
registry = json.loads((startup / 'frozen-local-inputs.json').read_text())
for record in registry['archives']:
    source = startup / record['path']
    assert hashlib.sha256(source.read_bytes()).hexdigest() == record['sha256']
    with tarfile.open(source) as archive:
        assert sorted(archive.getnames()) == record['members']
        assert all(m.isfile() for m in archive.getmembers())
        archive.extractall(startup / record['destination'], filter='data')
subprocess.run(['python3', '-B', str(startup / 'local_input_contract.py')], check=True)
entries = {}
for label, base in [('startup', startup), ('platform', args.destination / 'platform')]:
    files = {}
    for path in sorted(base.rglob('*')):
        relative = str(path.relative_to(base))
        if path.is_symlink():
            files[relative] = {'link': str(path.readlink())}
        elif path.is_file():
            files[relative] = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    entries[label] = files
(args.destination / 'export-identity.json').write_text(json.dumps({'repositories': identities, 'trees': entries}, indent=2, sort_keys=True) + '\n')
print('PASS committed export, frozen packages, literal symlinks; files:', {k: len(v) for k,v in entries.items()})
print('startup:', startup)
