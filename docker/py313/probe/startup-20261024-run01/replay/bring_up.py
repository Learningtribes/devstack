"""Run the complete local bring-up of one run config, stopping at the first failing stage.

Stages: unit tests, provision-secrets, provision-acceptance, preflight, prepare, create, install,
schema, assets, services, heartbeats, course build, course seed, superuser, HTTP smoke, superuser login.
Per-stage logs go to <run root>/stage-logs/, a summary to stage-logs/summary.txt and the outcome to
<run root>/bring-up-result.json. Passwords are never printed.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from core import load_config
from http_client import base_urls, run_root, wait_for_heartbeats

HERE = Path(__file__).resolve().parent
TEST_STAGE = 'unittest'


def script_stage(script, *arguments):
    return [sys.executable, '-B', str(HERE / script), *arguments]


def stages(config_path, skip_unit_tests):
    config = str(config_path)
    plan = []
    if not skip_unit_tests:
        plan.append((TEST_STAGE, [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', str(HERE),
                                  '-p', 'test_*.py']))
    plan += [(action, script_stage('run.py', '--config', config, action))
             for action in ('provision-secrets', 'provision-acceptance', 'preflight', 'prepare', 'create', 'install')]
    plan += [(phase, script_stage('replay_after_install.py', '--config', config, phase))
             for phase in ('schema', 'assets', 'services')]
    plan.append(('heartbeats', None))
    plan += [('course-build', script_stage('acceptance_course.py', '--config', config, 'build')),
             ('course-seed', script_stage('acceptance_course.py', '--config', config, 'seed')),
             ('superuser', script_stage('ensure_superuser.py', '--config', config)),
             ('smoke', script_stage('smoke_http.py', '--config', config, 'smoke')),
             ('superuser-login', script_stage('smoke_http.py', '--config', config, 'superuser'))]
    return plan


def run_stage(name, command, config, logs, heartbeat_timeout):
    log = logs / (name + '.log')
    started = time.monotonic()
    with open(log, 'x') as stream:
        if command is None:
            codes = wait_for_heartbeats(config, heartbeat_timeout)
            stream.write(json.dumps(codes) + '\n')
            returncode = 0 if all(code == 200 for code in codes.values()) else 1
        else:
            # The replay tools resolve their own imports; run from the script directory for `-m unittest`.
            returncode = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, cwd=HERE).returncode
    seconds = round(time.monotonic() - started)
    line = 'stage=%s rc=%d dur=%ds' % (name, returncode, seconds)
    with open(logs / 'summary.txt', 'a') as summary:
        summary.write(line + '\n')
    print(line, flush=True)
    return {'name': name, 'rc': returncode, 'seconds': seconds}


def smoke_totals(root, suite, filename):
    path = root / filename
    if not path.is_file():
        return None
    rows = json.loads(path.read_text())
    return {'suite': suite, 'total': len(rows), 'failed': sum(1 for row in rows if row[1] != 'PASS')}


def bring_up(config_path, skip_unit_tests=False, heartbeat_timeout=600):
    config = load_config(config_path)
    root = run_root(config)
    logs = root / 'stage-logs'
    logs.mkdir(mode=0o755, exist_ok=False)
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    results = []
    for name, command in stages(Path(config_path).resolve(), skip_unit_tests):
        results.append(run_stage(name, command, config, logs, heartbeat_timeout))
        if results[-1]['rc']:
            break
    failed = next((stage['name'] for stage in results if stage['rc']), None)
    urls = base_urls(config)
    outcome = {
        'run_id': config['run_id'], 'status': 'FAIL' if failed else 'PASS', 'failed_stage': failed,
        'started': started, 'finished': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'stages': results, 'lms_url': urls['lms'], 'cms_url': urls['cms'], 'config': str(config_path),
        'credentials_file': config['credentials_file'],
        'smoke': smoke_totals(root, 'smoke', 'smoke-result.json'),
        'superuser_login': smoke_totals(root, 'superuser', 'superuser-result.json'),
        'runtime_image': config['images']['runtime'],
    }
    target = root / 'bring-up-result.json'
    with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644), 'w') as stream:
        stream.write(json.dumps(outcome, indent=2) + '\n')
    if failed:
        print('FAIL at stage %s; see %s' % (failed, logs / (failed + '.log')), file=sys.stderr)
    else:
        print('PASS %s' % config['run_id'])
        print('LMS    %s' % urls['lms'])
        print('Studio %s' % urls['cms'])
        print('Credentials (acceptance roles): %s' % config['credentials_file'])
        print('Local superuser: see ensure_superuser.py (local devstack default; password not printed)')
        print('Result: %s' % target)
    return outcome


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--skip-unit-tests', action='store_true', help='skip the replay unittest stage')
    parser.add_argument('--heartbeat-timeout', type=int, default=600, help='seconds to wait for LMS/CMS /heartbeat')
    args = parser.parse_args()
    outcome = bring_up(args.config, args.skip_unit_tests, args.heartbeat_timeout)
    raise SystemExit(1 if outcome['status'] != 'PASS' else 0)


if __name__ == '__main__':
    main()
