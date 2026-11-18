"""Bounded local schema, genuine assets, and service replay from explicit config."""
import argparse
from pathlib import Path
import sys
from core import (APP_PYTHON, STARTUP_REL, capture, discovery_enabled, docker_exec, load_config, manage, ownership, shell)
import discovery

# `npm ci` installs ~1500 packages in one transaction and aborts the whole stage on a single
# socket timeout, of which several were observed on this link. npm parses these four, and its
# cache under /root/.npm survives a failed attempt, so a retry resumes instead of restarting.
NPM_FETCH_TOLERANCE = {
    'npm_config_fetch_retries': '5',
    'npm_config_fetch_retry_mintimeout': '20000',
    'npm_config_fetch_retry_maxtimeout': '180000',
    'npm_config_fetch_timeout': '600000',
}


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('phase', choices=['schema', 'assets', 'services'])
    args = parser.parse_args()
    config = load_config(args.config)
    ownership(config)
    if args.phase == 'schema':
        capture(config, 'local-runtime-log-dirs', docker_exec(config, 'mkdir', '-p', '/edx/var/log/lms', '/edx/var/log/cms'))
        capture(config, 'saml-contract', docker_exec(config, APP_PYTHON, '/startup/test_saml_processor_contract.py'))
        capture(config, 'stage-theme', docker_exec(config, APP_PYTHON, '/startup/prepare_theme_inputs.py'))
        shell(config, 'lms', 'initialize-schema', '/startup/initialize_schema.py', settings='startup_schema')
        shell(config, 'lms', 'natural-sites', '/startup/seed_local_host_sites.py')
        shell(config, 'lms', 'acceptance-users', '/startup/seed_acceptance_users.py')
        shell(config, 'lms', 'completion-tracking', '/startup/seed_completion_tracking.py')
        shell(config, 'lms', 'site-themes', '/startup/seed_themes.py')
        for system in ('lms', 'cms'):
            manage(config, system, system + '-check', ['check'])
        if discovery_enabled(config):
            # The LMS-side half of the discovery contract: register the DOT Application that
            # discovery authenticates with, then provision discovery's own database and seed.
            shell(config, 'lms', 'seed-discovery-oauth-app', '/startup/seed_discovery_oauth_app.py')
            discovery.schema(config)
    elif args.phase == 'assets':
        capture(config, 'npm-ci', docker_exec(config, 'npm', 'ci', '--legacy-peer-deps', '--ignore-scripts',
                                             '--no-audit', '--no-fund', extra_env=NPM_FETCH_TOLERANCE))
        shell(config, 'lms', 'xmodule-assets', '/startup/build_xmodule_assets.py')
        capture(config, 'frontend-assets', docker_exec(config, 'bash', '/startup/build_frontend.sh'))
        for system in ('lms', 'cms'):
            shell(config, system, system + '-locale-static', '/startup/locale_static.py')
    elif args.phase == 'services':
        startup = Path(config['export_dir']) / 'devstack' / STARTUP_REL
        for script in ('start_http.py', 'start_worker.py'):
            for system in ('lms', 'cms'):
                capture(config, script[:-3] + '-' + system, [sys.executable, '-B', str(startup / script), system])
        if discovery_enabled(config):
            discovery.services(config)
    print('PASS', args.phase, config['run_id'], '; business acceptance is separate')


if __name__ == '__main__':
    main()
