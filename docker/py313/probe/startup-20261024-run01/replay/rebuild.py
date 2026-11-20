"""Rebuild front-end assets and/or locale catalogs in an existing run.

The assets phase of replay_after_install.py is one-shot: capture() reserves each
output label with O_EXCL and refuses to repeat a mutation. Day-to-day rebuilds after
editing Sass, JS, XModule sources or .po files therefore cannot reuse that path.

Same builders as bring-up (npm ci when needed, build_xmodule_assets.py with a fresh
BRINGUP_XMODULE_BUILD_ROOT, build_frontend.sh, locale_static.py). Leaves no evidence.
Afterward: make restart if templates or static are cached in the running servers.

collectstatic: locale_static.py runs it; rebuild-assets does not. On the local runtime
(DEBUG=False, DevelopmentStorage) that is enough for Sass/JS: build_frontend writes Sass
into the Platform tree (served by the staticfiles finders) and webpack into STATIC_ROOT,
and build_xmodule_assets copies into common/static/xmodule. Use rebuild-translations (or
rebuild-all) when locale catalogs / static i18n / collectstatic-only package files change.
"""
import argparse
import datetime
import subprocess

from core import (APP_PYTHON, APP_SOURCE, APP_STATE, docker_exec, environment, load_config,
                  ownership)
from replay_after_install import NPM_FETCH_TOLERANCE

WEBPACK = APP_SOURCE + '/node_modules/.bin/webpack'


def run(config, command, *, extra_env=None):
    env = environment(config)
    if extra_env:
        env = {**env, **extra_env}
    subprocess.run(command, env=env, check=True)


def run_shell(config, system, script, *, settings=None, extra_env=None):
    code = 'from pathlib import Path;exec(compile(Path(%r).read_text(),%r,"exec"))' % (script, script)
    settings = settings or ('startup_' + system)
    command = docker_exec(config, APP_PYTHON, 'manage.py', system, 'shell', '-c', code,
                          settings=settings, extra_env=extra_env)
    run(config, command, extra_env=extra_env)


def ensure_npm(config):
    """Install node_modules when webpack is missing (common after a live Platform remount).

    Presence of webpack is the only gate: package-lock.json changes do not trigger npm ci.
    Use action `npm` (or remove node_modules) after lockfile updates.
    """
    probe = subprocess.run(
        ['docker', 'exec', config['runtime_container'], 'test', '-x', WEBPACK],
        capture_output=True)
    if probe.returncode == 0:
        print('node_modules present')
        return
    print('node_modules missing; running npm ci (writes ignored files under the Platform tree)')
    run(config, docker_exec(config, 'npm', 'ci', '--legacy-peer-deps', '--ignore-scripts',
                            '--no-audit', '--no-fund', extra_env=NPM_FETCH_TOLERANCE),
        extra_env=NPM_FETCH_TOLERANCE)
    subprocess.run(['docker', 'exec', config['runtime_container'], 'test', '-x', WEBPACK], check=True)


def prune_xmodule_build_dirs(config):
    """Drop leftover exclusive xmodule staging dirs from earlier rebuilds or a crashed run."""
    subprocess.run(
        ['docker', 'exec', config['runtime_container'], 'bash', '-c',
         'rm -rf %s/xmodule-source-build-*' % APP_STATE],
        check=True)


def rebuild_translations(config):
    for system in ('lms', 'cms'):
        print('locale_static', system)
        run_shell(config, system, '/startup/locale_static.py')
    print('PASS translations', config['run_id'])


def rebuild_assets(config):
    ensure_npm(config)
    prune_xmodule_build_dirs(config)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d%H%M%S')
    build_root = APP_STATE + '/xmodule-source-build-' + stamp
    extra = {'BRINGUP_XMODULE_BUILD_ROOT': build_root}
    print('xmodule assets ->', build_root)
    run_shell(config, 'lms', '/startup/build_xmodule_assets.py', extra_env=extra)
    print('frontend assets')
    run(config, docker_exec(config, 'bash', '/startup/build_frontend.sh'))
    # Generated tree was copied into Platform common/static/xmodule; staging is disposable.
    subprocess.run(
        ['docker', 'exec', config['runtime_container'], 'rm', '-rf', build_root],
        check=True)
    print('PASS assets', config['run_id'])


def rebuild(config, action):
    ownership(config)
    if action == 'npm':
        ensure_npm(config)
        print('PASS npm', config['run_id'])
    elif action == 'translations':
        rebuild_translations(config)
    elif action == 'assets':
        rebuild_assets(config)
    elif action == 'all':
        rebuild_assets(config)
        rebuild_translations(config)
        print('PASS all', config['run_id'])
    else:
        raise SystemExit('Unknown action: ' + action)


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('action', choices=['translations', 'assets', 'all', 'npm'])
    args = parser.parse_args()
    rebuild(load_config(args.config), args.action)


if __name__ == '__main__':
    main()
