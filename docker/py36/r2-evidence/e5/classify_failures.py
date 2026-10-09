"""Attribute each pytest failure to its deepest Platform frame and check that
line against master: classify_failures.py <pytest-output> <platform-repo>."""
from __future__ import print_function

import collections
import re
import subprocess
import sys

MASTER = '6750b5331809c510dd36133ca8223b4a32f13ed8'
HEAD = '0ac3bfa6d099916cc58fc258db17221801f49d48'
PREFIX = '/edx/app/edxapp/edx-platform/'
FRAME = re.compile(r'^' + re.escape(PREFIX) + r'(\S+?):(\d+): in (\S+)')


def git(repo, *args):
    return subprocess.run(('git', '-C', repo) + args, stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL, universal_newlines=True).stdout


def main(output_path, repo):
    text = open(output_path, errors='replace').read()
    parts = re.split(r'\n_+ (\S[^\n]*?) _+\n', text)
    changed = set(git(repo, 'diff', '--name-only', MASTER, HEAD).split())
    master_cache = {}
    head_cache = {}

    def lines(cache, rev, path):
        if path not in cache:
            cache[path] = git(repo, 'show', '{}:{}'.format(rev, path)).splitlines()
        return cache[path]

    rows = []
    for i in range(1, len(parts) - 1, 2):
        name, body = parts[i], parts[i + 1].split('\n= ')[0]
        frames = [FRAME.match(l) for l in body.splitlines()]
        frames = [m for m in frames if m]
        errors = [l for l in body.splitlines() if l.startswith('E ')]
        error = re.sub(r'0x[0-9a-f]+', '0x..', errors[-1][4:].strip()) if errors else '(no E line)'
        if not frames:
            rows.append((name, '-', error, '-', '-'))
            continue
        path, lineno = frames[-1].group(1), int(frames[-1].group(2))
        src = lines(head_cache, HEAD, path)
        code = src[lineno - 1].strip() if 0 < lineno <= len(src) else ''
        in_master = code in (l.strip() for l in lines(master_cache, MASTER, path))
        kind = 'test' if '/tests/' in path or '/test/' in path or path.endswith('tests.py') else 'product'
        origin = 'master-line' if in_master else 'R2-changed-line'
        if path in changed:
            origin += '/file-in-R2-delta'
        rows.append((name, '{}:{}'.format(path, lineno), error, kind, origin))

    for row in rows:
        print('FAILURE {} | {} | {} | {} | {}'.format(*row))
    print('SUMMARY sections={}'.format(len(rows)))
    for key, count in collections.Counter((r[3], r[4]) for r in rows).most_common():
        print('SUMMARY {} {} {}'.format(count, key[0], key[1]))
    for key, count in collections.Counter((r[1], r[2][:90]) for r in rows).most_common():
        print('SITE {:3d} {} | {}'.format(count, key[0], key[1]))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
