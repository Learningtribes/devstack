"""Restart LMS/Studio HTTP and workers in an existing run after Platform code changed.

Not an evidence-capturing command: replay_after_install.py reserves one output file per label and
refuses to repeat a mutation, so a restart cannot reuse it. Like shell.py, this leaves no evidence.
"""
import argparse
from pathlib import Path
import subprocess
import sys

from core import STARTUP_REL, environment, load_config, ownership
from http_client import wait_for_heartbeats


def restart(config, timeout):
    ownership(config)
    subprocess.run(['docker', 'restart', config['runtime_container']], check=True, stdout=subprocess.DEVNULL)
    startup = Path(config['export_dir']) / 'devstack' / STARTUP_REL
    env = environment(config)
    for script in ('start_http.py', 'start_worker.py'):
        for system in ('lms', 'cms'):
            subprocess.run([sys.executable, '-B', str(startup / script), system], env=env, check=True)
    codes = wait_for_heartbeats(config, timeout)
    if not all(code == 200 for code in codes.values()):
        raise SystemExit('Heartbeat failed after restart: ' + str(codes))
    print('PASS restarted', config['run_id'], codes)


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--timeout', type=int, default=300)
    args = parser.parse_args()
    restart(load_config(args.config), args.timeout)


if __name__ == '__main__':
    main()
