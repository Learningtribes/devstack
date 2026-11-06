"""Operator teardown of ONE run: remove only the Docker resources named in its config that it owns.

This is an explicit, separate operator action. The replay stages themselves never clean up
(see README "Failure and ownership semantics"). A container is removed only if its
`py313.replay.config` label equals this config's hash; a volume or the network is removed only
if it carries that label too and every container using it is owned by this run. Resources that
fail the check are reported and left alone. The run directory (evidence) is kept unless
--purge-dir, which deletes only the run's known output paths, never a parent directory.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from core import SERVICES, config_hash, load_config
from http_client import run_root

ARTIFACTS = ('bring-up-result.json', 'acceptance-course.json', 'smoke-result.json', 'superuser-result.json')
LABEL = 'py313.replay.config'


def docker(*args):
    return subprocess.run(['docker', *args], capture_output=True, text=True)


def labels(kind, name):
    """Label map of an existing resource, or None when it does not exist."""
    template = '{{json .Config.Labels}}' if kind == 'container' else '{{json .Labels}}'
    result = docker(kind, 'inspect', '--format', template, name)
    if result.returncode:
        return None
    return json.loads(result.stdout) or {}


def users_of(kind, name):
    """Names of all containers (running or not) attached to a volume or network."""
    flag = 'volume' if kind == 'volume' else 'network'
    result = docker('ps', '-a', '--filter', flag + '=' + name, '--format', '{{.Names}}')
    return result.stdout.split()


def plan(config):
    expected = config_hash(config)
    containers = [config['runtime_container'], *(config['services'][name]['container'] for name in SERVICES)]
    volumes = [config['runtime_volume'], *(record['volume'] for record in config['services'].values()
                                           if 'volume' in record)]
    owned, foreign, absent = [], [], []
    for name in containers:
        found = labels('container', name)
        (absent if found is None else owned if found.get(LABEL) == expected else foreign).append(name)
    return expected, containers, volumes, owned, foreign, absent


def destroy(config, dry_run=False):
    expected, containers, volumes, owned, foreign, absent = plan(config)
    report = {'containers_removed': [], 'containers_skipped_foreign': foreign, 'containers_absent': absent,
              'volumes_removed': [], 'volumes_skipped': [], 'network_removed': False, 'network_skipped': None}
    for name in owned:
        if not dry_run and docker('rm', '-f', name).returncode:
            raise SystemExit('Failed to remove container ' + name)
        report['containers_removed'].append(name)
    removed = set(owned)
    for kind, names in (('volume', volumes), ('network', [config['network']])):
        for name in names:
            found = labels(kind, name)
            if found is None:
                continue
            others = [user for user in users_of(kind, name) if user not in removed]
            if found.get(LABEL) != expected:
                reason = 'ownership label differs'
            elif others:
                reason = 'in use by containers not owned by this run: ' + ', '.join(others)
            else:
                reason = None
            if reason:
                if kind == 'volume':
                    report['volumes_skipped'].append({'name': name, 'reason': reason})
                else:
                    report['network_skipped'] = reason
                continue
            if not dry_run and docker(kind, 'rm', name).returncode:
                raise SystemExit('Failed to remove %s %s' % (kind, name))
            if kind == 'volume':
                report['volumes_removed'].append(name)
            else:
                report['network_removed'] = True
    return report


def make_writable(function, path, excinfo):
    Path(path).chmod(0o700)
    function(path)


def purge(config, config_path):
    root = run_root(config)
    for key in ('evidence_dir', 'export_dir'):
        if Path(config[key]).exists():
            shutil.rmtree(config[key], onexc=make_writable)
    shutil.rmtree(root / 'stage-logs', ignore_errors=True)
    private = Path(config['secret_env']).parent
    for key in ('secret_env', 'credentials_file', 'jwt_file'):
        Path(config[key]).unlink(missing_ok=True)
    for name in ARTIFACTS:
        (root / name).unlink(missing_ok=True)
    if Path(config_path).resolve().parent == root:
        Path(config_path).unlink(missing_ok=True)
    for directory in (private, root):
        try:
            directory.rmdir()  # non-recursive: anything unexpected stays
        except OSError:
            pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--dry-run', action='store_true', help='report what would be removed')
    parser.add_argument('--purge-dir', action='store_true', help='also delete the run directory contents')
    args = parser.parse_args()
    config = load_config(args.config)
    report = destroy(config, dry_run=args.dry_run)
    print(json.dumps(report, indent=2))
    if args.purge_dir and not args.dry_run:
        purge(config, args.config)
        print('purged run directory contents')
    raise SystemExit(1 if report['containers_skipped_foreign'] or report['volumes_skipped'] or report['network_skipped'] else 0)


if __name__ == '__main__':
    main()
