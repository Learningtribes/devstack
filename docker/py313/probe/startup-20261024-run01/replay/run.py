"""Create new local resources and dispatch replay using a required JSON contract."""
import argparse
import json
import os
import re
from pathlib import Path
import secrets
import subprocess
import sys

from export_identity import verify_export_identity

from core import (APP_PYTHON, APP_ROOT, APP_SOURCE, APP_STATE, LIVE_PLATFORM_MOUNT, LIVE_THEME_MOUNT, SECRET_KEYS, SERVICES, STARTUP_REL, capture, config_hash, environment,
                  docker_exec, fresh_preflight, load_config, ownership, read_json,
                  save_new, shell, source_repository_roots, validate_path_isolation)


def compose(config):
    specs = {
        'mysql': ('/var/lib/mysql', {'MYSQL_ROOT_PASSWORD': '${PY313_MYSQL_ROOT_PASSWORD}',
            'MYSQL_DATABASE': config['database'], 'MYSQL_USER': 'edxapp', 'MYSQL_PASSWORD': '${PY313_MYSQL_PASSWORD}',
            'PY313_TEST_DATABASE': config['test_database']}),
        'mongo': ('/data/db', {'MONGO_INITDB_ROOT_USERNAME': 'edxapp', 'MONGO_INITDB_ROOT_PASSWORD': '${PY313_MONGO_PASSWORD}'}),
        'rabbitmq': ('/var/lib/rabbitmq', {'RABBITMQ_DEFAULT_USER': 'edxapp', 'RABBITMQ_DEFAULT_PASS': '${PY313_RABBITMQ_PASSWORD}'}),
        'elasticsearch': ('/usr/share/elasticsearch/data', {'discovery.type': 'single-node', 'xpack.security.enabled': 'false', 'ES_JAVA_OPTS': '-Xms256m -Xmx256m'}),
        'memcached': (None, {}), 'valkey': (None, {}),
    }
    services, volumes = {}, {}
    for name in SERVICES:
        target, env = specs[name]
        identity = config['services'][name]
        services[name] = {'image': config['images'][name], 'container_name': identity['container'],
                          'environment': env, 'labels': {'py313.replay.config': config_hash(config)}}
        if target:
            volumes[name] = {'name': identity['volume'], 'external': True}
            services[name]['volumes'] = [name + ':' + target]
    services['mysql']['command'] = '--character-set-server=utf8mb4 --collation-server=utf8mb4_unicode_ci'
    # Bound JVM and native memory so a single-node search service cannot starve
    # the paired LMS/CMS runtime or the isolated Docker engine.
    services['elasticsearch'].update({'mem_limit': '2g', 'memswap_limit': '3g'})
    # Registered non-secret RabbitMQ policy, independent of mutable host files.
    policy = Path(config['export_dir']) / 'devstack' / STARTUP_REL / 'replay/rabbitmq.conf'
    services['rabbitmq']['volumes'].append(str(policy) + ':/etc/rabbitmq/conf.d/20-local-replay.conf:ro')
    grant = Path(config['export_dir']) / 'devstack' / STARTUP_REL / 'replay/mysql-grant-test-database.sh'
    services['mysql']['volumes'].append(str(grant) + ':/docker-entrypoint-initdb.d/20-grant-test-database.sh:ro')
    return {'name': config['network'], 'services': services, 'volumes': volumes,
            'networks': {'default': {'name': config['network'], 'external': True}}}


def prepare(config):
    if not config.get('theme_repo'):
        raise ValueError('The theme is not packaged any more: create the run with --theme-repo <triboo-theme checkout>')
    baseline = fresh_preflight(config, before_prepare=True)
    root = Path(config['evidence_dir'])
    root.mkdir(mode=0o700, parents=False, exist_ok=False)
    save_new(root / 'config.json', config)
    save_new(root / 'preflight.json', baseline)
    exporter = Path(config['devstack_repo']) / STARTUP_REL / 'export_closed_inputs.py'
    capture(config, 'export', [sys.executable, '-B', str(exporter), '--destination', config['export_dir'],
                               '--platform', config['platform_repo']])
    startup = Path(config['export_dir']) / 'devstack' / STARTUP_REL
    identity = read_json(Path(config['export_dir']) / 'export-identity.json')
    assert identity['repositories']['devstack']['commit'] == config['devstack_commit']
    assert identity['repositories']['platform']['commit'] == config['platform_commit']
    export_digest = verify_export_identity(Path(config['export_dir']), STARTUP_REL)
    for name in ('.acceptance-credentials.json', 'jwt-private.pem'):
        (startup / name).touch(mode=0o600, exist_ok=False)
    save_new(root / 'compose.json', compose(config))
    save_new(root / 'prepared.json', {'configuration_sha256': config_hash(config),
                                      'export_identity_sha256': export_digest})


def verify_prepared_export(config):
    prepared = read_json(Path(config['evidence_dir']) / 'prepared.json')
    if not isinstance(prepared, dict) or prepared.get('configuration_sha256') != config_hash(config):
        raise ValueError('Prepared configuration identity differs')
    digest = prepared.get('export_identity_sha256')
    if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
        raise ValueError('Prepared export identity digest is missing or invalid')
    verify_export_identity(Path(config['export_dir']), STARTUP_REL,
                           expected_sha256=digest, allow_placeholders=True)


def create(config):
    root = Path(config['evidence_dir'])
    assert read_json(root / 'config.json') == config
    verify_prepared_export(config)
    fresh_preflight(config, before_prepare=False)
    # Docker volume create is otherwise idempotent. Verify our unique ownership
    # label before Compose can mount any data volume, including a creation race.
    volumes = {'runtime': config['runtime_volume'], **{key: value['volume'] for key, value in config['services'].items() if 'volume' in value}}
    for name, volume in volumes.items():
        capture(config, 'create-volume-' + name, ['docker', 'volume', 'create', '--label', 'py313.replay.config=' + config_hash(config), volume])
        labels = json.loads(subprocess.check_output(['docker', 'volume', 'inspect', '--format', '{{json .Labels}}', volume], text=True))
        assert labels.get('py313.replay.config') == config_hash(config), 'Volume ownership mismatch'
    capture(config, 'create-network', ['docker', 'network', 'create', '--label',
        'py313.replay.config=' + config_hash(config), '--subnet', config['network_subnet'], config['network']])
    # Explicit project name: `make` exports COMPOSE_PROJECT_NAME=devstack, which beats the file's own `name`
    # and would make every run share one project, so a second run recreated the first run's services.
    capture(config, 'create-infra', ['docker', 'compose', '-p', config['network'], '--env-file', config['secret_env'],
                                     '-f', str(root / 'compose.json'), 'up', '-d'])
    startup = Path(config['export_dir']) / 'devstack' / STARTUP_REL
    mounts = ['--mount', f'type=volume,src={config["runtime_volume"]},dst={APP_ROOT}',
              '--mount', f'type=bind,src={startup},dst=/paired-startup,readonly',
              '--mount', f'type=bind,src={config["export_dir"]}/platform,dst=/input/platform,readonly']
    mounts += ['--mount', f'type=bind,src={config["export_dir"]}/platform/ci/py313,dst=/canary,readonly']
    if config.get('platform_mount') == 'live':
        # Writable on purpose: the running LMS/Studio executes the host checkout, not a copy.
        mounts += ['--mount', f'type=bind,src={config["platform_repo"]},dst={LIVE_PLATFORM_MOUNT}']
    if config.get('theme_repo'):
        # Writable on purpose: theme edits and the Sass output (git-ignored static/css) live in the host checkout.
        mounts += ['--mount', f'type=bind,src={config["theme_repo"]},dst={LIVE_THEME_MOUNT}']
    for source, target in [('credentials_file', '.acceptance-credentials.json'), ('jwt_file', 'jwt-private.pem')]:
        mounts += ['--mount', f'type=bind,src={config[source]},dst=/startup/{target},readonly']
    capture(config, 'create-runtime', ['docker', 'run', '-d', '--name', config['runtime_container'],
        '--label', 'py313.replay.config=' + config_hash(config), '--network', config['network'],
        '-p', f'127.0.0.1:{config["lms_port"]}:18000', '-p', f'127.0.0.1:{config["cms_port"]}:18010',
        *mounts, '-e', 'PATH=/opt/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
        config['images']['runtime'], 'tail', '-f', '/dev/null'])


def install(config):
    ownership(config)
    verify_prepared_export(config)
    capture(config, 'prepare-install-inputs', ['docker', 'exec', config['runtime_container'],
        '/usr/local/bin/python3.13', '-B', '/canary/bringup/prepare_current_install.py'])
    capture(config, 'install', ['docker', 'exec', config['runtime_container'],
        '/usr/local/bin/python3.13', '-B', '/canary/install.py'])
    capture(config, 'platform-identity', docker_exec(config,
        APP_PYTHON, '-B', '/canary/verify-platform-identity.py'))
    for label, path in [('installed-companion-report', APP_STATE + '/installed-companion-identity.json'),
                        ('platform-identity-report', APP_STATE + '/platform-identity.json'),
                        ('install-receipt', APP_STATE + '/install-receipt.json'),
                        ('resolved-lock', APP_STATE + '/resolved-ci.lock'),
                        ('complete-lock', '/input/ci.lock')]:
        capture(config, label, docker_exec(config, 'cat', path), show_output=False)
    verify_prepared_export(config)
    if config.get('platform_mount') == 'live':
        # After every identity report: from here the editable installs, cwd and settings all see the host tree.
        capture(config, 'link-live-platform', ['docker', 'exec', config['runtime_container'], 'sh', '-c',
                'rm -rf %s && ln -s %s %s' % (APP_SOURCE, LIVE_PLATFORM_MOUNT, APP_SOURCE)])


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('action', choices=['provision-secrets', 'provision-acceptance', 'preflight', 'prepare', 'create', 'install', 'check', 'test', 'exchange'])
    parser.add_argument('arguments', nargs='*')
    args = parser.parse_args()
    config = load_config(args.config)
    if args.action == 'provision-secrets':
        validate_path_isolation(config, source_repository_roots(config))
        target = Path(config['secret_env'])
        with os.fdopen(os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), 'w') as stream:
            stream.write(''.join(key + '=' + secrets.token_hex(24) + '\n' for key in sorted(SECRET_KEYS)))
        print('PASS created protected secrets; values withheld')
    elif args.action == 'provision-acceptance':
        from provision_acceptance import provision
        provision(config)
    elif args.action == 'preflight':
        print(json.dumps(fresh_preflight(config, before_prepare=True), indent=2))
    elif args.action == 'prepare':
        prepare(config)
    elif args.action == 'create':
        create(config)
    elif args.action == 'install':
        install(config)
    elif args.action == 'check':
        from core import manage
        system, label, *command = args.arguments
        manage(config, system, label, command or ['check'])
    elif args.action == 'test':
        if len(args.arguments) < 3:
            parser.error('test requires a system, unique label, and test selector')
        system, label, *selectors = args.arguments
        if system not in ('lms', 'cms'):
            parser.error('test system must be lms or cms')
        ownership(config)
        capture(config, label, docker_exec(
            config,
            APP_PYTHON,
            '/startup/run_py313_legacy_tests.py',
            system,
            'test',
            *selectors,
            settings='startup_' + system,
        ))
    elif args.action == 'exchange':
        if len(args.arguments) != 1:
            parser.error('exchange requires a unique label')
        ownership(config)
        capture(config, args.arguments[0], docker_exec(config, APP_PYTHON, '-u', '-c',
            "import runpy;runpy.run_path('/startup/test_auth_exchange_runtime.py',run_name='__main__')", settings='exchange_acceptance'))


if __name__ == '__main__':
    main()
