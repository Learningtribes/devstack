"""Course-discovery sidecar for one run: create, install, schema, services, restart, destroy, shell.

Discovery is an optional extension of the same bring-up contract the Platform uses:
  * it reuses this run's MySQL and memcached (one database inside the shared server, as upstream devstack
    does), so enabling it adds a single container instead of a second database server;
  * every resource it creates carries the run's `py313.replay.config` label and the run_id prefix, so
    `destroy_run.py` can remove exactly what this run owns and nothing else;
  * every mutation is captured as evidence through `core.capture`, which refuses to repeat a label, so
    `create`/`install`/`schema`/`services` are one-shot exactly like the Platform stages.

Secrets never enter a docker argv: the container environment is written to a 0600 file that is mounted
read-only and sourced by the entrypoint (`core.DISCOVERY_ENV_MOUNT`).
"""
import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from core import (APP_CMS_PORT, DISCOVERY_ALIAS, DISCOVERY_APP_ROOT, DISCOVERY_COMPANIONS, DISCOVERY_ENV_MOUNT,
                  DISCOVERY_LOCK, DISCOVERY_LOCK_OUTPUT, DISCOVERY_MOUNT, DISCOVERY_PYTHON, DISCOVERY_SETTINGS,
                  DISCOVERY_TEST_SETTINGS, DISCOVERY_VENV,
                  capture, config_hash, discovery_environment, discovery_lms_domain, discovery_names,
                  discovery_test_database, discovery_url, environment, fail, load_config, ownership,
                  require_protected, secret_values)

LABEL = 'py313.replay.config'
RUNSERVER_PORT = 8000
STARTUP_TIMEOUT = 180
HEALTH_TIMEOUT = 300
# Discovery-owned seed script, run from the mounted repo (/workspace) with the app venv.
DISCOVERY_SEED_SCRIPT = 'ci/py313/seed_sites_and_partners.py'


def define(config):
    """Validate that discovery is enabled for this run, or explain why it is not."""
    if 'discovery_repo' not in config:
        fail('This run has no discovery_repo; add discovery_repo and discovery_image to enable discovery')


def paths(config):
    names = discovery_names(config)
    return {'container': names['container'], 'volume': names['volume'], 'database': names['database'],
            'env_file': Path(config['secret_env']).parent / 'discovery.env'}


def write_env_file(config):
    """Write the container environment to a 0600 file; idempotent so retries reuse the same bytes."""
    target = paths(config)['env_file']
    # The file is sourced by `sh`, so every value is quoted: a space, `$`, `;` or quote must stay data.
    body = ''.join('%s=%s\n' % (key, shlex.quote(value)) for key, value in sorted(discovery_environment(config).items()))
    if target.exists():
        if require_protected(target).read_text() != body:
            target.chmod(0o600)
            target.write_text(body)
        return target
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write(body)
    return require_protected(target)


def exec_argv(config, *args, detached=False):
    """docker exec that sources the mounted env file, so no secret value appears in an argv."""
    ownership(config)
    source = 'set -a; . ' + DISCOVERY_ENV_MOUNT + '; set +a; exec "$@"'
    return ['docker', 'exec', *(['-d'] if detached else []), '-w', DISCOVERY_MOUNT,
            paths(config)['container'], 'sh', '-c', source, 'sh', *args]


def create(config):
    """Create the discovery data volume and runtime container inside this run's network."""
    define(config)
    places = paths(config)
    expected = config_hash(config)
    capture(config, 'create-discovery-volume',
            ['docker', 'volume', 'create', '--label', LABEL + '=' + expected, places['volume']])
    labels = json.loads(subprocess.check_output(
        ['docker', 'volume', 'inspect', '--format', '{{json .Labels}}', places['volume']], text=True))
    if labels.get(LABEL) != expected:
        fail('Discovery volume ownership mismatch')
    write_env_file(config)
    capture(config, 'create-discovery', [
        'docker', 'run', '-d', '--name', places['container'], '--label', LABEL + '=' + expected,
        '--network', config['network'],
        # The Platform addresses discovery by this alias (COURSE_CATALOG_API_URL uses
        # http://discovery:8000), so the container name alone is not enough.
        '--network-alias', DISCOVERY_ALIAS,
        '-p', '127.0.0.1:%d:%d' % (config['discovery_port'], RUNSERVER_PORT),
        '--mount', 'type=volume,src=%s,dst=%s' % (places['volume'], DISCOVERY_APP_ROOT),
        '--mount', 'type=bind,src=%s,dst=%s' % (config['discovery_repo'], DISCOVERY_MOUNT),
        '--mount', 'type=bind,src=%s,dst=%s,readonly' % (places['env_file'], DISCOVERY_ENV_MOUNT),
        config['discovery_image'], 'tail', '-f', '/dev/null'])


def install(config):
    """Create the isolated venv and install the locked dependency set into it.

    The lock names its one non-PyPI input with the `@COMPANIONS_DIR@` placeholder rather than an
    absolute path, so it stays valid outside this container layout. `materialize-lock.py` resolves
    it against the mounted repository and refuses to write a lock whose archive does not match
    `ci/py313/companions/manifest.json`; the resolved copy is what pip installs.
    """
    define(config)
    capture(config, 'install-discovery-venv', exec_argv(
        config, 'sh', '-c',
        'test -x %s || uv venv --python /usr/local/bin/python3.13 %s' % (DISCOVERY_PYTHON, DISCOVERY_VENV)))
    capture(config, 'install-discovery-lock', exec_argv(
        config, DISCOVERY_PYTHON, DISCOVERY_MOUNT + '/ci/py313/materialize-lock.py',
        DISCOVERY_MOUNT + '/' + DISCOVERY_LOCK,
        '--companions-dir', DISCOVERY_MOUNT + '/' + DISCOVERY_COMPANIONS,
        '--output-dir', DISCOVERY_LOCK_OUTPUT))
    # `sync`, not `install`: the lock is the definition of this environment, and `install` only
    # adds. Re-installing after a lock change left the packages the lock no longer lists, so the
    # venv silently drifted from the file that is supposed to describe it.
    capture(config, 'install-discovery-deps', exec_argv(
        config, 'uv', 'pip', 'sync', '--python', DISCOVERY_PYTHON,
        DISCOVERY_LOCK_OUTPUT + '/local.txt'))
    capture(config, 'install-discovery-check', exec_argv(
        config, 'uv', 'pip', 'check', '--python', DISCOVERY_PYTHON))


def provision_database(config):
    """Create this run's discovery database in the shared MySQL and grant the application user.

    Runs inside the MySQL container so `$MYSQL_ROOT_PASSWORD` comes from that container's own environment;
    the password never appears in an argv. The SQL goes over stdin instead of `-e '...'` so the quoted
    account name (`'edxapp'@'%'`) cannot terminate the shell's single-quoted argument. Idempotent.
    """
    define(config)
    database = paths(config)['database']
    if not re.fullmatch(r'[a-z][a-z0-9_]{2,100}', database):
        fail('Refusing unsafe database name')
    sql = ("CREATE DATABASE IF NOT EXISTS `{db}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;\n"
           "GRANT ALL PRIVILEGES ON `{db}`.* TO 'edxapp'@'%';\n"
           "FLUSH PRIVILEGES;\n").format(db=database)
    result = subprocess.run(['docker', 'exec', '-i', config['services']['mysql']['container'],
                             'sh', '-c', 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD"'],
                            input=sql, capture_output=True, text=True, env=environment(config))
    if result.returncode:
        sys.stderr.write(result.stdout + result.stderr)
        fail('Failed to provision the discovery database')


def seed(config, *, evidence=False):
    """Seed `django_site` + `core_partner` so discovery can reach this run's LMS.

    `refresh_course_metadata` iterates `Site.objects.all()` and calls
    `{scheme}://{site.domain}/oauth2/access_token`, so without a row it raises
    `CommandError('No valid site records in Table django_site!')`. The domain must be the
    in-network LMS address, not the host loopback mapping, because discovery runs in its
    own container. `seed_sites_and_partners.py` uses `update_or_create`, so re-running is safe.
    """
    define(config)
    domain = discovery_lms_domain(config)
    overrides = {
        'DISCOVERY_SITE_DOMAIN': domain,
        'DISCOVERY_LMS_URL': 'http://' + domain,
        'DISCOVERY_STUDIO_URL': 'http://' + config['runtime_container'] + ':' + str(APP_CMS_PORT),
    }
    assignment = ' '.join('%s=%s' % (key, shlex.quote(value)) for key, value in sorted(overrides.items()))
    argv = exec_argv(config, 'sh', '-c', assignment + ' exec "$@"', 'sh', DISCOVERY_PYTHON, DISCOVERY_SEED_SCRIPT)
    if evidence:
        capture(config, 'seed-discovery-site-partner', argv)
        return
    result = subprocess.run(argv, capture_output=True, text=True, env=environment(config))
    sys.stdout.write(result.stdout + result.stderr)
    if result.returncode:
        fail('Discovery site/partner seed failed')


def schema(config):
    """Provision the database, apply migrations, seed and run Django's system checks."""
    define(config)
    provision_database(config)
    capture(config, 'schema-discovery', exec_argv(config, DISCOVERY_PYTHON, 'manage.py', 'migrate', '--noinput'))
    seed(config, evidence=True)
    check(config, evidence=True)


def test(config, selectors=(), *, label='test-discovery', evidence=True):
    """Run discovery's pytest suite against this run's MySQL, in a dedicated granted database.

    Mirrors the Platform replay's `run.py test`: the suite runs inside the container from the
    isolated venv, never from the image's global site-packages. `settings/test.py` selects MySQL
    through `DB_*` and pins the database name through `DB_TEST_NAME`, because Django's runner
    would otherwise create `test_<name>` and the application user holds no global CREATE.
    """
    define(config)
    database = discovery_test_database(config)
    overrides = {
        'DB_ENGINE': 'django.db.backends.mysql',
        'DB_HOST': config['services']['mysql']['container'],
        'DB_PORT': '3306',
        'DB_USER': 'edxapp',
        'DB_PASSWORD': secret_values(config).get('BRINGUP_MYSQL_PASSWORD', ''),
        'DB_NAME': database,
        'DB_TEST_NAME': database,
    }
    assignment = ' '.join('%s=%s' % (key, shlex.quote(value)) for key, value in sorted(overrides.items()))
    command = ('set -a; . %s; set +a; export %s; exec "$@"'
               % (DISCOVERY_ENV_MOUNT, assignment))
    argv = exec_argv(config, 'sh', '-c', command, 'sh',
                     DISCOVERY_PYTHON, '-m', 'pytest', '-p', 'no:cacheprovider',
                     '--ds=' + DISCOVERY_TEST_SETTINGS, *selectors)
    if evidence:
        capture(config, label, argv)
        return
    result = subprocess.run(argv, capture_output=True, text=True, env=environment(config))
    sys.stdout.write(result.stdout + result.stderr)
    if result.returncode:
        fail('Discovery test suite failed')


def check(config, *, evidence=False):
    """Run Django's system checks: a successful `migrate` does not imply a sound configuration.

    Mirrors the Platform replay, which runs `manage.py <system> check` at the end of its schema
    stage. `--deploy` is deliberately omitted: it asserts production-only settings (HTTPS,
    secure cookies) that a local run does not set.
    """
    define(config)
    argv = exec_argv(config, DISCOVERY_PYTHON, 'manage.py', 'check')
    if evidence:
        capture(config, 'check-discovery', argv)
        return
    result = subprocess.run(argv, capture_output=True, text=True, env=environment(config))
    sys.stdout.write(result.stdout + result.stderr)
    if result.returncode:
        fail('Discovery system check failed')


def migrate(config):
    """Re-apply migrations, re-seed and re-check; no evidence, so `update-db` stays repeatable."""
    define(config)
    provision_database(config)
    result = subprocess.run(exec_argv(config, DISCOVERY_PYTHON, 'manage.py', 'migrate', '--noinput'),
                            capture_output=True, text=True, env=environment(config))
    sys.stdout.write(result.stdout + result.stderr)
    if result.returncode:
        fail('Discovery migrate failed')
    seed(config)
    check(config)


def start_http(config):
    """Dispatch the discovery runserver and wait for /health/, mirroring the Platform's start_http.py.

    A healthy server is left alone: a second `runserver` could not bind port 8000 and would only
    leave an extra failing process behind. `restart()` restarts the container first, so code
    changes still reach a fresh process.
    """
    define(config)
    if http_status(discovery_url(config)) == 200:
        return 200
    places = paths(config)
    command = ('umask 077; mkdir -p /tmp/discovery-logs; '
               'set -a; . %s; set +a; exec %s manage.py runserver 0.0.0.0:%d --noreload '
               '>> /tmp/discovery-logs/runserver.log 2>&1' % (DISCOVERY_ENV_MOUNT, DISCOVERY_PYTHON, RUNSERVER_PORT))
    subprocess.run(['docker', 'exec', '-d', '-w', DISCOVERY_MOUNT, places['container'], 'sh', '-c', command],
                   check=True, env=environment(config))
    return wait_for_health(config)


def http_status(url, path='/health/', timeout=5):
    try:
        with urllib.request.urlopen(url + path, timeout=timeout) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code
    except (urllib.error.URLError, OSError):
        return None


def wait_for_health(config, timeout=HEALTH_TIMEOUT, interval=3, sleep=time.sleep, clock=time.monotonic):
    url = discovery_url(config)
    deadline = clock() + timeout
    while True:
        code = http_status(url)
        if code == 200 or clock() >= deadline:
            if code != 200:
                fail('Discovery /health/ did not return 200 within %ds (last: %s)' % (timeout, code))
            return code
        sleep(interval)


def services(config):
    """Start the HTTP process and assert health; this is the last discovery stage."""
    define(config)
    start_http(config)
    print('PASS discovery services', config['run_id'], discovery_url(config) + '/health/')


def restart(config, timeout=HEALTH_TIMEOUT):
    """Restart the discovery container and re-dispatch the HTTP process after code changes."""
    define(config)
    ownership(config)
    subprocess.run(['docker', 'restart', paths(config)['container']], check=True, stdout=subprocess.DEVNULL)
    return start_http(config)


def status(config):
    """Read-only row describing the discovery container, plus its health code."""
    define(config)
    places = paths(config)
    result = subprocess.run(['docker', 'inspect', '--type', 'container', '--format',
                             '{"state":{{json .State.Status}},"ports":{{json .NetworkSettings.Ports}}}',
                             places['container']], capture_output=True, text=True)
    if result.returncode:
        return {'name': places['container'], 'state': 'absent', 'ports': ''}, None
    info = json.loads(result.stdout)
    published = ', '.join(sorted('%s:%s->%s' % (binding['HostIp'], binding['HostPort'], port)
                                 for port, bindings in (info['ports'] or {}).items()
                                 for binding in bindings or []))
    return {'name': places['container'], 'state': info['state'], 'ports': published}, http_status(discovery_url(config))


def destroy_plan(config):
    """Resources this run owns for discovery, for destroy_run.py to consider."""
    if 'discovery_repo' not in config:
        return [], []
    places = paths(config)
    return [places['container']], [places['volume']]


def shell_argv(config):
    """Interactive discovery shell with the venv first on PATH; leaves no evidence, like shell.py."""
    define(config)
    ownership(config)
    return ['docker', 'exec', '-it', '-w', DISCOVERY_MOUNT, '-e', 'TERM',
            paths(config)['container'], 'sh', '-c',
            'set -a; . %s; set +a; export PATH=%s/bin:$PATH; '
            'echo "=== discovery py313 shell (%s) ==="; exec bash'
            % (DISCOVERY_ENV_MOUNT, DISCOVERY_VENV, DISCOVERY_SETTINGS)]


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('phase', choices=['create', 'install', 'schema', 'migrate', 'seed', 'check', 'test',
                                          'services', 'restart', 'status'])
    parser.add_argument('selectors', nargs='*', help='pytest selectors, for the test phase only')
    args = parser.parse_args()
    config = load_config(args.config)
    if args.phase == 'create':
        create(config)
    elif args.phase == 'install':
        install(config)
    elif args.phase == 'schema':
        schema(config)
    elif args.phase == 'migrate':
        migrate(config)
    elif args.phase == 'seed':
        seed(config)
    elif args.phase == 'check':
        check(config)
    elif args.phase == 'test':
        test(config, args.selectors)
    elif args.phase == 'services':
        services(config)
    elif args.phase == 'restart':
        restart(config)
    elif args.phase == 'status':
        row, code = status(config)
        print('%-36s %-8s %s' % (row['name'], row['state'], row['ports'] or '-'))
        print('DISCOVERY %s/health/ -> %s' % (discovery_url(config), code))
        raise SystemExit(0 if row['state'] == 'running' and code == 200 else 1)
    print('PASS', args.phase, config['run_id'])


if __name__ == '__main__':
    main()
