"""Create a new, empty py313 run: directory layout, private inputs and an explicit config.json.

Nothing is started and no Docker resource is created. Existing paths are refused. The only
stdout is the absolute config path (informational lines go to stderr); no secret is printed.
"""
import argparse
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from core import SERVICES, docker_network_subnets, fail, load_config, read_json, validate_network_subnet

HERE = Path(__file__).resolve().parent
EXAMPLE = HERE / 'current-config.example.json'
RUN_ID_RE = re.compile(r'[a-z][a-z0-9]{2,15}')  # also the limit for acceptance usernames
COMMIT_RE = re.compile(r'[0-9a-f]{40}')


def default_runs_root():
    return Path(os.environ.get('PY313_RUNS_ROOT') or Path.home() / 'workspace/hawthorn/py313-runs')


def git_output(repo, *args):
    env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
    return subprocess.check_output(['git', '-C', str(repo), *args], text=True, env=env).strip()


def clean_head(repo, requested, label):
    """HEAD of a clean checkout; an explicit commit must already be that HEAD (preflight requires it)."""
    repo = Path(repo)
    if not repo.is_absolute():
        fail(label + ' repository must be an absolute path')
    try:
        head = git_output(repo, 'rev-parse', 'HEAD')
        subprocess.run(['git', '-C', str(repo), 'diff', '--quiet', 'HEAD'], check=True,
                       env={k: v for k, v in os.environ.items() if not k.startswith('GIT_')})
    except (OSError, subprocess.CalledProcessError):
        fail(label + ' repository is not a Git checkout with a clean tracked tree: ' + str(repo))
    if requested and requested != head:
        fail('%s commit %s is not the checked-out HEAD %s' % (label, requested, head))
    if not COMMIT_RE.fullmatch(head):
        fail('Cannot resolve ' + label + ' HEAD')
    return head


def parse_routes(text):
    """IPv4 networks from `netstat -rn -f inet` (macOS) or `ip -4 route` output."""
    networks = []
    for line in text.splitlines():
        destination = line.split(None, 1)[0] if line.strip() else ''
        if not re.fullmatch(r'\d+(?:\.\d+){0,3}(?:/\d+)?', destination):
            continue
        address, _, prefix = destination.partition('/')
        octets = address.split('.')
        # netstat abbreviates "172.30.245/24" and bare "127" by dropping trailing zero octets.
        length = int(prefix) if prefix else 8 * len(octets)
        try:
            networks.append(ipaddress.ip_network('.'.join(octets + ['0'] * (4 - len(octets))) + '/%d' % length,
                                                 strict=False))
        except ValueError:
            continue
    return networks


def host_routes():
    for command in (['ip', '-4', 'route', 'show'], ['netstat', '-rn', '-f', 'inet']):
        try:
            return parse_routes(subprocess.check_output(command, text=True, stderr=subprocess.DEVNULL))
        except (OSError, subprocess.CalledProcessError):
            continue
    return []


def pick_subnet(docker_subnets, routes):
    """First 172.30.X.0/24 that overlaps neither a Docker network nor a host route."""
    # A route shorter than /8 is a default-route fragment (a TUN VPN/proxy splits 0/0 into 1, 2/7, 4/6, ... 128/1),
    # not a network that owns addresses; counting it would make every candidate "taken".
    taken = [ipaddress.ip_network(value, strict=False) for value in docker_subnets] + [
        network for network in routes if network.prefixlen >= 8]
    for third in range(1, 255):
        candidate = ipaddress.ip_network('172.30.%d.0/24' % third)
        if not any(candidate.overlaps(network) for network in taken if network.version == 4):
            return str(candidate)
    fail('No free 172.30.X.0/24 subnet; pass --subnet')


def build_config(args, root, platform_commit, devstack_commit, subnet):
    example = read_json(EXAMPLE)
    run_id = args.run_id
    images = dict(example['images'])
    if args.runtime_image:
        images['runtime'] = args.runtime_image
    prefix = run_id
    services = {name: {'container': '%s-%s' % (prefix, name),
                       **({'volume': '%s-%s-data' % (prefix, name)}
                          if name in ('mysql', 'mongo', 'rabbitmq', 'elasticsearch') else {})}
                for name in SERVICES}
    private = root / 'private'
    return {
        'run_id': run_id, 'evidence_dir': str(root / 'evidence'), 'export_dir': str(root / 'export'),
        'platform_repo': args.platform_repo, 'platform_commit': platform_commit,
        'devstack_repo': args.devstack_repo, 'devstack_commit': devstack_commit,
        'theme_commit': example['theme_commit'],
        'runtime_container': run_id + '-runtime', 'runtime_volume': run_id + '-runtime-data',
        'network': run_id + '-network', 'network_subnet': subnet,
        'lms_port': args.lms_port, 'cms_port': args.cms_port,
        'database': 'py313_rebuild_' + run_id, 'test_database': 'py313_rebuild_%s_test' % run_id,
        'mongo_database': run_id + '_mongo', 'cache_prefix': run_id + '_cache', 'es_prefix': run_id + '_es',
        'queue_prefix': run_id + '_queue', 'course_key': 'course-v1:PY313+%s+2026' % run_id,
        'secret_env': str(private / 'services.env'), 'credentials_file': str(private / 'acceptance.json'),
        'jwt_file': str(private / 'jwt.pem'), 'services': services, 'images': images,
        **({'platform_mount': 'live'} if getattr(args, 'live_platform', False) else {}),
        **({'theme_repo': args.theme_repo} if getattr(args, 'theme_repo', None) else {}),
    }


def write_private(path, data):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(data)


def generate_jwt_key():
    return subprocess.run(['openssl', 'genrsa', '2048'], check=True, capture_output=True).stdout


def create_run(args):
    if not RUN_ID_RE.fullmatch(args.run_id or ''):
        fail('run_id must be 3-16 lowercase letters or digits starting with a letter')
    root = Path(args.root) if args.root else default_runs_root() / args.run_id
    if not root.is_absolute() or '..' in root.parts:
        fail('Run root must be an absolute normalized path')
    if os.path.lexists(root):
        fail('Refusing existing run directory: ' + str(root))
    args.platform_repo = str(Path(args.platform_repo).resolve())
    args.devstack_repo = str(Path(args.devstack_repo).resolve())
    if getattr(args, 'theme_repo', None):
        args.theme_repo = str(Path(args.theme_repo).resolve())
        if not any((Path(args.theme_repo) / system).is_dir() for system in ('lms', 'cms')):
            fail('theme_repo must be the root of a theme checkout (it contains lms/ and/or cms/): ' + args.theme_repo)
    platform_commit = clean_head(args.platform_repo, args.platform_commit, 'Platform')
    devstack_commit = clean_head(args.devstack_repo, args.devstack_commit, 'Devstack')
    subnet = validate_network_subnet(args.subnet, docker_network_subnets()) if args.subnet \
        else pick_subnet(docker_network_subnets(), host_routes())
    config = build_config(args, root, platform_commit, devstack_commit, subnet)
    # Validate the whole contract (names, ports, path isolation, locked images) before touching disk.
    with tempfile.TemporaryDirectory() as scratch:
        probe = Path(scratch) / 'config.json'
        probe.write_text(json.dumps(config))
        load_config(probe)
    root.mkdir(mode=0o755, parents=True)
    private = root / 'private'
    private.mkdir(mode=0o700)
    write_private(private / 'jwt.pem', generate_jwt_key())
    target = root / 'config.json'
    with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644), 'w') as stream:
        stream.write(json.dumps(config, indent=2) + '\n')
    return target, config


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--lms-port', required=True, type=int)
    parser.add_argument('--cms-port', required=True, type=int)
    parser.add_argument('--platform-repo', required=True, help='clean Platform worktree')
    parser.add_argument('--platform-commit', help='default: Platform HEAD (must equal it)')
    parser.add_argument('--devstack-repo', default=str(HERE.parents[4]), help='default: this Devstack checkout')
    parser.add_argument('--devstack-commit', help='default: Devstack HEAD (must equal it)')
    parser.add_argument('--root', help='new run directory (default: $PY313_RUNS_ROOT/<run-id>)')
    parser.add_argument('--subnet', help='dedicated private /24 (default: first free 172.30.X.0/24)')
    parser.add_argument('--live-platform', action='store_true',
                        help='development run: bind-mount the Platform checkout read-write instead of running a copy')
    parser.add_argument('--theme-repo', required=True, help='triboo-theme checkout, bind-mounted read-write as theme '
                                                           '`hawthorn` (the theme is not packaged with Platform or Devstack)')
    parser.add_argument('--runtime-image', help='override images.runtime (local sha256 ID or the locked reference)')
    args = parser.parse_args(argv)
    try:
        target, config = create_run(args)
    except ValueError as error:
        raise SystemExit('new_run: ' + str(error))
    print('run %s: %s lms=%d cms=%d subnet=%s runtime=%s' % (
        config['run_id'], target.parent, config['lms_port'], config['cms_port'], config['network_subnet'],
        config['images']['runtime']), file=sys.stderr)
    print(target)


if __name__ == '__main__':
    main()
