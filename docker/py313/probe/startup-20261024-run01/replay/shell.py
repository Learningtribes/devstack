"""Interactive shell in the run-owned runtime; no container or evidence-directory fallback.

Not an evidence-capturing command: a terminal session has no reproducible output,
so there is no label and nothing is written to the evidence directory.
"""
import argparse
import os
from pathlib import Path
import subprocess
import time

import core
from core import APP_ROOT, APP_SOURCE, docker_exec, environment, load_config

# node_modules/.bin carries rtlcss, which `paver update_assets` calls by name.
RUNTIME_PATH = (APP_ROOT + '/venvs/edxapp/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:'
                + APP_SOURCE + '/node_modules/.bin')
# lms.envs.test / cms.envs.test connect to an unauthenticated Mongo, while the run's Mongo requires
# credentials. A second mongod on this port, inside the run's own Mongo container, serves the tests.
TEST_MONGO_PORT = 27018
# What `paver test_system` / `test_lib` / `update_assets` need from a shell: no prerequisite install, the nose stub
# that shadows nose 1.3.7 (it imports the stdlib `imp`, removed in 3.13), and the webpack heap size the bring-up uses.
PAVER_ENVIRONMENT = ('TESTING=True', 'NO_PREREQ_INSTALL=True', 'SKIP_NPM_INSTALL=True', 'VIRTUAL_ENV=' + APP_ROOT + '/venvs/edxapp',
                     'EDXAPP_TEST_MONGO_HOST=mongo', 'EDXAPP_TEST_MONGO_PORT=%d' % TEST_MONGO_PORT,
                     'NODE_OPTIONS=--max-old-space-size=2048', 'PAVER_DEVSTACK_SETTINGS=devstack_local',
                     'PYTHONPATH=/startup/settings:' + APP_SOURCE + '/ci/py313/test-stubs')


def test_mongo_listening(container):
    probe = subprocess.run(['docker', 'exec', container, 'bash', '-c',
                            'exec 3<>/dev/tcp/127.0.0.1/%d' % TEST_MONGO_PORT], capture_output=True)
    return probe.returncode == 0


def ensure_test_mongo(config, timeout=30):
    core.ownership(config)
    container = config['services']['mongo']['container']
    if test_mongo_listening(container):
        return
    subprocess.run(['docker', 'exec', container, 'mkdir', '-p', '/tmp/py313-test-mongo'], check=True)
    subprocess.run(['docker', 'exec', '-d', container, 'mongod', '--port', str(TEST_MONGO_PORT), '--bind_ip_all',
                    '--dbpath', '/tmp/py313-test-mongo', '--nounixsocket'], check=True)
    deadline = time.monotonic() + timeout
    while not test_mongo_listening(container):
        if time.monotonic() > deadline:
            raise SystemExit('Test Mongo did not start on port %d' % TEST_MONGO_PORT)
        time.sleep(0.5)


def ensure_npx(config):
    # The runtime image links npm into /usr/local/bin but not npx, which Paver's webpack task calls.
    core.ownership(config)
    subprocess.run(['docker', 'exec', config['runtime_container'], 'sh', '-c',
                    'test -e /usr/local/bin/npx || ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx'],
                   check=True)


def command(config, system):
    return docker_exec(config, 'env', 'PATH=' + RUNTIME_PATH, *PAVER_ENVIRONMENT, 'bash',
                       settings='startup_' + system, interactive=True)


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('system', choices=['lms', 'cms'])
    args = parser.parse_args()
    config = load_config(args.config)
    ensure_test_mongo(config)
    ensure_npx(config)
    argv = command(config, args.system)
    os.execvpe(argv[0], argv, environment(config))


if __name__ == '__main__':
    main()
