"""Stop and start every container of one run without deleting anything.

`destroy_run.py` removes resources; there was no way to merely stop a run and bring it back.
These actions fill that gap.

The tooling used here is the one frozen inside the run's own export
(`<export_dir>/devstack/.../startup-*/replay`), not this checkout. A run is created together with a
snapshot of the scripts that created it, and those scripts encode that run's layout (where its
Platform source and venv live) and its environment-variable convention. A run created before the
`/runtime` -> `/edx/app/edxapp` layout move or the `PY313_` -> `BRINGUP_` rename must keep being
started by its own snapshot, otherwise the dispatched process looks for `manage.py` in a path that
only exists in the newer layout. Using the snapshot makes this command correct for any run age.

Containers are never deleted and data volumes are untouched. Every container named in the config
must carry this run's `py313.replay.config` label before it is touched, so a foreign container of the
same name is reported and left alone.

Not an evidence-capturing command: stop/start are operator actions with no reproducible output, the
same reasoning as shell.py and restart.py.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

LABEL = 'py313.replay.config'


def docker(*args):
    return subprocess.run(['docker', *args], capture_output=True, text=True)


def run_tooling(config_path):
    """Import core from the run's own frozen export, and return it with the startup directory."""
    raw = json.loads(Path(config_path).read_text())
    probe = Path(raw['export_dir']) / 'devstack' / 'docker' / 'py313' / 'probe'
    candidates = sorted(p for p in probe.glob('startup-*') if (p / 'replay' / 'core.py').is_file())
    if not candidates:
        raise SystemExit('No frozen replay tooling under %s; was this run prepared by run.py?' % probe)
    startup = candidates[-1]
    sys.path.insert(0, str(startup / 'replay'))
    import core  # noqa: E402  (the run's own snapshot, not this checkout)
    return core, startup


def containers(core, config, has_discovery):
    """Infrastructure first, then runtime, then the optional discovery sidecar."""
    names = [config['services'][name]['container'] for name in core.SERVICES]
    names.append(config['runtime_container'])
    if has_discovery:
        import discovery
        names.append(discovery.paths(config)['container'])
    return names


def classify(core, config, has_discovery):
    """Split the configured containers into owned / foreign / absent by the run label."""
    wanted = core.config_hash(config)
    owned, foreign, absent = [], [], []
    for name in containers(core, config, has_discovery):
        result = docker('inspect', '--format', '{{json .Config.Labels}}', name)
        if result.returncode:
            absent.append(name)
            continue
        labels = json.loads(result.stdout) or {}
        (owned if labels.get(LABEL) == wanted else foreign).append(name)
    return owned, foreign, absent


def stop(core, config, has_discovery):
    core.ownership(config)
    owned, foreign, absent = classify(core, config, has_discovery)
    # Runtime first so nothing keeps writing to the services while they shut down.
    for name in reversed(owned):
        docker('stop', name)
        print('stopped', name)
    for name in foreign:
        print('skipped (not owned by this run):', name)
    for name in absent:
        print('absent:', name)


def hearts(core, config, timeout):
    try:
        from http_client import wait_for_heartbeats
        return wait_for_heartbeats(config, timeout)
    except ImportError:
        import time
        import urllib.error
        import urllib.request
        urls = {'lms': 'http://localhost:%d' % config['lms_port'],
                'cms': 'http://localhost:%d' % config['cms_port']}
        deadline = time.monotonic() + timeout
        while True:
            codes = {}
            for name, base in urls.items():
                try:
                    with urllib.request.urlopen(base + '/heartbeat', timeout=5) as response:
                        codes[name] = response.status
                except urllib.error.HTTPError as error:
                    codes[name] = error.code
                except (urllib.error.URLError, OSError):
                    codes[name] = None
            if all(code == 200 for code in codes.values()) or time.monotonic() >= deadline:
                return codes
            time.sleep(3)


def ensure_runtime_log_dirs(config):
    """Recreate /edx/var/log/{lms,cms} without depending on the frozen export's core.

    Older exports lack ensure_runtime_log_dirs; start must still work for any run age.
    """
    result = docker('exec', config['runtime_container'], 'mkdir', '-p', '/edx/var/log/lms', '/edx/var/log/cms')
    if result.returncode:
        raise SystemExit('Failed to create /edx/var/log/{lms,cms}: ' + (result.stderr or result.stdout))


def start(core, config, startup, timeout, has_discovery):
    core.ownership(config)
    owned, foreign, absent = classify(core, config, has_discovery)
    if foreign:
        raise SystemExit('Refusing to start: container(s) not owned by this run: ' + ', '.join(foreign))
    for name in owned:
        docker('start', name)
        print('started', name)
    for name in absent:
        print('absent (run "run.py create" to recreate):', name)
    if config['runtime_container'] in owned:
        ensure_runtime_log_dirs(config)
    # The HTTP/worker processes are docker-exec children, so a stop removed them and they must be
    # dispatched again, with the scripts and environment this run was created with.
    env = core.environment(config)
    for script in ('start_http.py', 'start_worker.py'):
        for system in ('lms', 'cms'):
            result = subprocess.run([sys.executable, '-B', str(startup / script), system],
                                    env=env, capture_output=True, text=True)
            if result.returncode:
                sys.stderr.write(result.stdout + result.stderr)
                raise SystemExit('%s %s failed to dispatch' % (script, system))
            print('dispatched', script[:-3], system)
    if has_discovery:
        import discovery
        discovery.start_http(config)
        print('dispatched discovery')
    codes = hearts(core, config, timeout)
    if not all(code == 200 for code in codes.values()):
        raise SystemExit('Heartbeat failed after start: %s' % codes)
    print('PASS started', config['run_id'], codes)


def runtime_layout(core, config):
    """Source dir and venv python of this run, detected rather than assumed.

    The layout moved (`/runtime` -> `/edx/app/edxapp`) between run generations, so probe the
    container instead of reading a constant that only exists in the newer core.
    """
    env = core.environment(config)
    source = (env.get('BRINGUP_PLATFORM_ROOT') or env.get('PY313_PLATFORM_ROOT')
              or '/edx/app/edxapp/edx-platform')
    for candidate in ('/edx/app/edxapp/venvs/edxapp/bin/python', '/runtime/venv/bin/python'):
        if docker('exec', config['runtime_container'], 'test', '-x', candidate).returncode == 0:
            return source, candidate
    raise SystemExit('No application venv found in ' + config['runtime_container'])


def shell(core, config, system):
    """Interactive shell in the run's runtime, using the run's own layout and environment."""
    core.ownership(config)
    source, python = runtime_layout(core, config)
    env = core.environment(config)
    flags = [f for key in sorted(env) if key.startswith(('PY313_', 'BRINGUP_')) or key == 'PYTHONPATH'
             for f in ('-e', key)]
    argv = ['docker', 'exec', '-it', '-w', source, *flags,
            '-e', 'DJANGO_SETTINGS_MODULE=startup_' + system, '-e', 'TERM',
            '-e', 'PATH=' + str(Path(python).parent) + ':/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
            config['runtime_container'], 'bash', '-c',
            'echo "=== %s shell: %s (settings=startup_%s) ==="; '
            'echo "manage.py: python manage.py %s <command>"; exec bash'
            % (config['run_id'], source, system, system)]
    import os
    os.execvpe(argv[0], argv, env)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--timeout', type=int, default=600)
    parser.add_argument('--system', choices=['lms', 'cms'], help='required for the shell action')
    parser.add_argument('action', choices=['stop', 'start', 'shell'])
    args = parser.parse_args()
    core, startup = run_tooling(args.config)
    has_discovery = False
    try:
        import discovery  # noqa: F401
        has_discovery = 'discovery_repo' in json.loads(Path(args.config).read_text())
    except ImportError:
        pass
    config = core.load_config(args.config)
    if args.action == 'stop':
        stop(core, config, has_discovery)
    elif args.action == 'start':
        start(core, config, startup, args.timeout, has_discovery)
    else:
        if not args.system:
            raise SystemExit('shell requires --system lms|cms')
        shell(core, config, args.system)


if __name__ == '__main__':
    main()
