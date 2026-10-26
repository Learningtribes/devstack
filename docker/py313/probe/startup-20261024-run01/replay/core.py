"""Explicit, local-only replay contract and evidence capture. No run defaults."""
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import datetime

STARTUP_REL = Path('docker/py313/probe/startup-20261024-run01')
SERVICES = ('mysql', 'mongo', 'rabbitmq', 'elasticsearch', 'memcached', 'valkey')
SECRET_KEYS = {'PY313_MYSQL_ROOT_PASSWORD', 'PY313_MYSQL_PASSWORD', 'PY313_MONGO_PASSWORD',
               'PY313_RABBITMQ_PASSWORD', 'PY313_STARTUP_SECRET_KEY', 'PY313_STARTUP_XQUEUE_PASSWORD'}
REQUIRED = {'run_id', 'evidence_dir', 'export_dir', 'platform_repo', 'platform_commit',
            'devstack_repo', 'devstack_commit', 'theme_commit', 'runtime_container', 'runtime_volume',
            'network', 'services', 'images', 'lms_port', 'cms_port', 'database', 'test_database', 'mongo_database',
            'cache_prefix', 'es_prefix', 'queue_prefix', 'course_key', 'secret_env', 'credentials_file', 'jwt_file'}


def fail(message):
    raise ValueError(message)


def read_json(path):
    return json.loads(Path(path).read_text())


def save_new(path, value):
    path = Path(path)
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
        stream.write(json.dumps(value, indent=2, sort_keys=True) + '\n')


def related_paths(left, right):
    return left == right or left in right.parents or right in left.parents


def resolved_path(path):
    try:
        return Path(path).resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        fail('Unable to resolve path: ' + str(path) + ': ' + str(exc))


def validate_path_isolation(config, source_repositories=None):
    paths = {key: resolved_path(config[key]) for key in (
        'evidence_dir', 'export_dir', 'secret_env', 'credentials_file', 'jwt_file'
    )}
    for index, (left_name, left) in enumerate(paths.items()):
        for right_name, right in list(paths.items())[index + 1:]:
            if related_paths(left, right):
                fail('Replay output and protected input paths must be disjoint after resolution: ' +
                     left_name + '=' + str(left) + ' ' + right_name + '=' + str(right))
    sources = source_repositories if source_repositories is not None else {
        key.removesuffix('_repo'): config[key] for key in ('platform_repo', 'devstack_repo')
    }
    sources = {name: resolved_path(path) for name, path in sources.items()}
    for output_name in ('evidence_dir', 'export_dir', 'secret_env'):
        output = paths[output_name]
        for source_name, source in sources.items():
            if related_paths(output, source):
                fail(output_name + ' must be outside ' + source_name + '_repo after path resolution')


def source_repository_roots(config):
    roots = {}
    for key in ('platform', 'devstack'):
        configured = resolved_path(config[key + '_repo'])
        try:
            actual = Path(subprocess.check_output(
                ['git', '-C', str(config[key + '_repo']), 'rev-parse', '--show-toplevel'], text=True
            ).strip()).resolve(strict=True)
        except (OSError, subprocess.CalledProcessError) as exc:
            fail('Unable to identify ' + key + ' repository root: ' + str(exc))
        if configured != actual:
            fail(key + '_repo must name the Git checkout root: ' + str(actual))
        roots[key] = actual
    if related_paths(roots['platform'], roots['devstack']):
        fail('platform_repo and devstack_repo must be separate checkouts')
    return roots


def load_config(path):
    config = read_json(path)
    if set(config) != REQUIRED:
        fail('Configuration keys differ: missing=' + str(sorted(REQUIRED - set(config))) +
             ' extra=' + str(sorted(set(config) - REQUIRED)))
    token = config['run_id']
    if not re.fullmatch(r'[a-z][a-z0-9_-]{2,48}', token):
        fail('Invalid run_id')
    for key in ('evidence_dir', 'export_dir', 'platform_repo', 'devstack_repo', 'secret_env', 'credentials_file', 'jwt_file'):
        value = Path(config[key])
        if not value.is_absolute() or '..' in value.parts:
            fail('Expected absolute normalized path: ' + key)
    validate_path_isolation(config)
    for key in ('platform_commit', 'devstack_commit', 'theme_commit'):
        if not re.fullmatch(r'[0-9a-f]{40}', config[key]):
            fail('Expected full commit SHA: ' + key)
    for key in ('lms_port', 'cms_port'):
        if type(config[key]) is not int or not 1024 <= config[key] <= 65535:
            fail('Invalid port: ' + key)
    if config['lms_port'] == config['cms_port']:
        fail('Ports must differ')
    names = [config[k] for k in ('runtime_container', 'runtime_volume', 'network', 'database', 'test_database',
                                'mongo_database', 'cache_prefix', 'es_prefix', 'queue_prefix')]
    if set(config['services']) != set(SERVICES) or set(config['images']) != {*SERVICES, 'runtime'}:
        fail('Specify all service identities and all images explicitly')
    for service, record in config['services'].items():
        expected = {'container', 'volume'} if service in ('mysql', 'mongo', 'rabbitmq', 'elasticsearch') else {'container'}
        if set(record) != expected:
            fail('Unexpected service fields: ' + service)
        names.extend(record.values())
    for name in names:
        if not re.fullmatch(r'[a-z][a-z0-9_-]{2,100}', name) or token not in name:
            fail('Every resource/namespace must contain run_id and safe characters')
    if not config['database'].startswith('py313_rebuild_'):
        fail('Fresh local schema requires py313_rebuild_ database prefix')
    if len(set(names)) != len(names):
        # SQL/Mongo/cache prefixes can match across physically independent services.
        physical = physical_names(config)
        if len(set(physical)) != len(physical):
            fail('Physical resource names must be distinct')
    for name, image in config['images'].items():
        if not isinstance(image, str) or not image or any(x.isspace() for x in image):
            fail('Invalid image: ' + name)
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', config['images']['runtime']):
        fail('Runtime image must be an explicit sha256 image identity')
    if not re.fullmatch(r'course-v1:[A-Za-z0-9_-]+\+[A-Za-z0-9_-]+\+[A-Za-z0-9_-]+', config['course_key']) or token not in config['course_key']:
        fail('Course key must be explicit and contain run_id')
    return config


def physical_names(config):
    return [config['runtime_container'], config['runtime_volume'], config['network'],
            *[value for record in config['services'].values() for value in record.values()]]


def config_hash(config):
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()


def check_conflicts(config, inventory):
    expected = set(physical_names(config))
    existing = set(inventory['containers']) | set(inventory['volumes']) | set(inventory['networks'])
    conflicts = sorted(expected & existing)
    if conflicts:
        fail('Refusing existing resources: ' + ', '.join(conflicts))


def inventory():
    return {label: subprocess.check_output(['docker', *command, '--format', '{{.Name}}' if label != 'containers' else '{{.Names}}'],
                                         text=True).splitlines()
            for label, command in [('containers', ['ps', '-a']), ('volumes', ['volume', 'ls']), ('networks', ['network', 'ls'])]}


def require_protected(path):
    path = Path(path)
    if not path.is_file() or path.is_symlink() or stat.S_IMODE(path.stat().st_mode) & 0o077:
        fail('Expected private regular file with mode 600 or stricter: ' + str(path))
    return path


def secret_values(config):
    path = require_protected(config['secret_env'])
    values = dict(line.split('=', 1) for line in path.read_text().splitlines() if line and not line.startswith('#'))
    if set(values) != SECRET_KEYS or any(not re.fullmatch(r'[0-9a-f]{48}', value) for value in values.values()):
        fail('Protected env must contain only six generated service secrets; namespaces belong in config')
    return values


def redact_values(config):
    values = list(secret_values(config).values())
    fixture = read_json(require_protected(config['credentials_file']))
    values += [row['password'] for row in fixture.values()]
    values += [line for line in require_protected(config['jwt_file']).read_text().splitlines() if not line.startswith('---')]
    return sorted(set(filter(None, values)), key=len, reverse=True)


def environment(config):
    # Do not inherit any PY313_* from a previously selected run.
    env = {key: value for key, value in os.environ.items() if not key.startswith('PY313_')}
    env.update(secret_values(config))
    env.update(PY313_MYSQL_USER='edxapp', PY313_MONGO_USER='edxapp', PY313_RABBITMQ_USER='edxapp',
               PY313_RUNTIME_CONTAINER=config['runtime_container'], PY313_SECRET_ENV_FILE=config['secret_env'],
               PY313_PLATFORM_ROOT='/runtime/platform-source', PYTHONPATH='/startup/settings',
               PY313_DATABASE_NAME=config['database'], PY313_TEST_DATABASE_NAME=config['test_database'], PY313_MONGO_DB=config['mongo_database'],
               PY313_CACHE_PREFIX=config['cache_prefix'], PY313_ES_INDEX_PREFIX=config['es_prefix'],
               PY313_TASK_QUEUE_PREFIX=config['queue_prefix'], PY313_ACCEPTANCE_COURSE_ID=config['course_key'],
               PY313_XMODULE_BUILD_ROOT='/runtime/xmodule-source-build-v1',
               PY313_LMS_DOMAIN='localhost:' + str(config['lms_port']), PY313_CMS_DOMAIN='localhost:' + str(config['cms_port']),
               PY313_LMS_ROOT_URL='http://localhost:' + str(config['lms_port']),
               PY313_CMS_ROOT_URL='http://localhost:' + str(config['cms_port']))
    return env


def fresh_preflight(config, *, before_prepare):
    repositories = source_repository_roots(config)
    validate_path_isolation(config, repositories)
    check_conflicts(config, inventory())
    if before_prepare:
        if os.path.lexists(config['export_dir']):
            fail('Refusing existing export directory')
        if os.path.lexists(config['evidence_dir']):
            fail('Refusing existing evidence directory')
    for port in (config['lms_port'], config['cms_port']):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', port))
    secret_values(config)
    for key in ('credentials_file', 'jwt_file'):
        require_protected(config[key])
    for key in ('platform', 'devstack'):
        repo = config[key + '_repo']
        actual = subprocess.check_output(['git', '-C', repo, 'rev-parse', 'HEAD'], text=True).strip()
        if actual != config[key + '_commit']:
            fail(key + ' HEAD changed')
        subprocess.run(['git', '-C', repo, 'diff', '--quiet', 'HEAD'], check=True)
    return {'configuration_sha256': config_hash(config), 'run_id': config['run_id'],
            'ports_available': True, 'resources_absent': True, 'commits': commits(config)}


def commits(config):
    return {key: config[key + '_commit'] for key in ('platform', 'devstack', 'theme')}


def ownership(config):
    saved = read_json(Path(config['evidence_dir']) / 'config.json')
    if saved != config:
        fail('Evidence configuration differs from requested configuration')
    actual = json.loads(subprocess.check_output(['docker', 'inspect', '--format', '{{json .Config.Labels}}', config['runtime_container']], text=True))
    if actual.get('py313.replay.config') != config_hash(config):
        fail('Runtime does not belong to this exact replay configuration')


def docker_exec(config, *args, settings=None, detached=False):
    ownership(config)
    env = environment(config)
    flags = [flag for key in sorted(env) if key.startswith('PY313_') or key == 'PYTHONPATH' for flag in ('-e', key)]
    if settings:
        flags += ['-e', 'DJANGO_SETTINGS_MODULE=' + settings]
    return ['docker', 'exec', *(['-d'] if detached else []), '-w', '/runtime/platform-source',
            *flags, config['runtime_container'], *args]


def capture(config, label, command, *, show_output=True):
    if not re.fullmatch(r'[a-zA-Z0-9_-]+', label):
        fail('Invalid output label')
    root = Path(config['evidence_dir'])
    replacements = redact_values(config)
    # Reserve before executing: duplicate outputs must never rerun a mutation.
    path = root / (label + '.txt')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    start = datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        result = subprocess.run(command, env=environment(config), capture_output=True, text=True)
        output = result.stdout + result.stderr
        for value in replacements:
            output = output.replace(value, '<redacted>')
        with os.fdopen(fd, 'w') as stream:
            stream.write(output)
        fd = None
        command_text = json.dumps(command)
        for value in replacements:
            command_text = command_text.replace(value, '<redacted>')
        record = {'start': start, 'end': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  'run_id': config['run_id'], 'configuration_sha256': config_hash(config),
                  'commits': commits(config), 'command': json.loads(command_text), 'output': path.name, 'exit_code': result.returncode}
        with (root / 'commands.jsonl').open('a') as stream:
            stream.write(json.dumps(record, sort_keys=True) + '\n')
        (root / 'commands.jsonl').chmod(0o600)
        print(label, 'exit_code=' + str(result.returncode), output[-1400:] if show_output else '[output captured privately]', flush=True)
        if result.returncode:
            raise SystemExit(result.returncode)
    finally:
        if fd is not None:
            os.close(fd)


def manage(config, system, label, command, settings=None):
    if system not in ('lms', 'cms'):
        fail('Choose lms or cms')
    settings = settings or 'startup_' + system
    if settings not in ('startup_lms', 'startup_cms', 'startup_schema', 'exchange_acceptance'):
        fail('Only registered local settings are permitted')
    capture(config, label, docker_exec(config, '/runtime/venv/bin/python', 'manage.py', system,
                                     *command, settings=settings))


def shell(config, system, label, script, settings=None):
    code = f'from pathlib import Path;exec(compile(Path({script!r}).read_text(),{script!r},"exec"))'
    manage(config, system, label, ['shell', '-c', code], settings=settings)
