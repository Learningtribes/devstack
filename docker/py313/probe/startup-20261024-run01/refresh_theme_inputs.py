"""Write the verified theme input snapshot for one theme commit (host tool, stdlib only).

    python3 refresh_theme_inputs.py --theme-repo <checkout> --commit <sha> [--destination <startup dir>]

Creates theme-inputs/<12-hex>/hawthorn/ with every git-tracked file of the commit and
theme-inputs/<12-hex>/source-sha256.json with the commit and the SHA-256 of each file. The
runtime verifies this tree byte for byte before staging it (prepare_theme_inputs.py).
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

REGULAR_FILE_MODES = {'100644', '100755'}


def git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True).stdout


def refresh(repo, commit, destination):
    full = git(repo, 'rev-parse', '--verify', commit + '^{commit}').decode().strip()
    entries = git(repo, 'ls-tree', '-r', '-z', full).decode().split('\0')
    root = Path(destination) / 'theme-inputs' / full[:12]
    if root.exists():
        sys.exit(f'refusing existing snapshot: {root}')
    files = {}
    for entry in filter(None, entries):
        meta, path = entry.split('\t', 1)
        mode, kind, _ = meta.split()
        if kind != 'blob' or mode not in REGULAR_FILE_MODES:
            sys.exit(f'unsupported tree entry {mode} {kind}: {path}')
        content = git(repo, 'cat-file', 'blob', full + ':' + path)
        target = root / 'hawthorn' / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        if mode == '100755':
            target.chmod(0o755)
        files[path] = hashlib.sha256(content).hexdigest()
    record = {'commit': full, 'files': dict(sorted(files.items()))}
    (root / 'source-sha256.json').write_text(json.dumps(record, indent=2) + '\n')
    return full, len(files)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--theme-repo', required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--destination', default=str(Path(__file__).resolve().parent))
    args = parser.parse_args()
    full, count = refresh(args.theme_repo, args.commit, args.destination)
    print(full, count, 'files')


if __name__ == '__main__':
    main()
