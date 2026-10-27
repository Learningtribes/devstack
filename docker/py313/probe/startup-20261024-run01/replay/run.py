"""Create new local resources and dispatch replay using a required JSON contract."""
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

from core import (SECRET_KEYS, SERVICES, STARTUP_REL, capture, config_hash, environment,
                  docker_exec, fresh_preflight, load_config, ownership, read_json,
                  save_new, shell, source_repository_roots, validate_path_isolation)


def compose(config):
    specs = {
        'mysql': ('/var/lib/mysql', {'MYSQL_ROOT_PASSWORD': '${PY313_MYSQL_ROOT_PASSWORD}',
            'MYSQL_DATABASE': config['database'], 'MYSQL_USER': 'edxapp', 'MYSQL_PASSWORD': '${PY313_MYSQL_PASSWORD}'}),
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
    # Registered non-secret RabbitMQ policy, independent of mutable host files.
    policy = Path(config['export_dir']) / 'devstack' / STARTUP_REL / 'replay/rabbitmq.conf'
    services['rabbitmq']['volumes'].append(str(policy) + ':/etc/rabbitmq/conf.d/20-local-replay.conf:ro')
    return {'name': config['network'], 'services': services, 'volumes': volumes,
            'networks': {'default': {'name': config['network'], 'external': True}}}


def prepare(config):
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
    theme = read_json(startup / 'theme-inputs/7c0dbec1b0a7/source-sha256.json')
    assert theme['commit'] == config['theme_commit']
    for name in ('.acceptance-credentials.json', 'jwt-private.pem'):
        (startup / name).touch(mode=0o600, exist_ok=False)
    save_new(root / 'compose.json', compose(config))
    save_new(root / 'prepared.json', {'configuration_sha256': config_hash(config)})


def create(config):
    root = Path(config['evidence_dir'])
    assert read_json(root / 'config.json') == config
    assert read_json(root / 'prepared.json')['configuration_sha256'] == config_hash(config)
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
    capture(config, 'create-infra', ['docker', 'compose', '--env-file', config['secret_env'], '-f', str(root / 'compose.json'), 'up', '-d'])
    startup = Path(config['export_dir']) / 'devstack' / STARTUP_REL
    mounts = ['--mount', f'type=volume,src={config["runtime_volume"]},dst=/runtime',
              '--mount', f'type=bind,src={startup},dst=/startup,readonly',
              '--mount', f'type=bind,src={config["export_dir"]}/platform,dst=/input/platform,readonly']
    for source, target in [('credentials_file', '.acceptance-credentials.json'), ('jwt_file', 'jwt-private.pem')]:
        mounts += ['--mount', f'type=bind,src={config[source]},dst=/startup/{target},readonly']
    capture(config, 'create-runtime', ['docker', 'run', '-d', '--name', config['runtime_container'],
        '--label', 'py313.replay.config=' + config_hash(config), '--network', config['network'],
        '-p', f'127.0.0.1:{config["lms_port"]}:18000', '-p', f'127.0.0.1:{config["cms_port"]}:18010',
        *mounts, '-e', 'PATH=/opt/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
        config['images']['runtime'], 'tail', '-f', '/dev/null'])


def install(config):
    ownership(config)
    capture(config, 'input-preflight', ['docker', 'exec', config['runtime_container'], 'python3', '-B', '/startup/test_local_input_contract.py'])
    capture(config, 'install', ['docker', 'exec', '-e', 'PY313_PLATFORM_SOURCE_ROOT=/input/platform', config['runtime_container'],
                              'bash', '-c', 'test ! -e /runtime/venv && /usr/local/bin/python3.13 -B /startup/install_internal_delivery.py install'])
    capture(config, 'installed-source-identity', docker_exec(
        config, '/runtime/venv/bin/python', '/startup/replay/verify_installed_identity.py'))
    capture(config, 'installed-source-report', docker_exec(
        config, 'cat', '/runtime/installed-input-identity.json'), show_output=False)


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
            '/runtime/venv/bin/python',
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
        capture(config, args.arguments[0], docker_exec(config, '/runtime/venv/bin/python', '-u', '-c',
            "import runpy;runpy.run_path('/startup/test_auth_exchange_runtime.py',run_name='__main__')", settings='exchange_acceptance'))


if __name__ == '__main__':
    main()
