"""Capture a fresh LT-02 process, without restarting or patching HTTP services."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

parser = argparse.ArgumentParser(__doc__)
parser.add_argument('--run-dir', type=Path, required=True)
parser.add_argument('--label', required=True)
args = parser.parse_args()
root = args.run_dir.resolve()
assert root.is_dir()
output_path = root / (args.label + '.txt')
assert not output_path.exists(), output_path
container = os.environ['PY313_RUNTIME_CONTAINER']
secret_path = Path(os.environ['PY313_SECRET_ENV_FILE'])
env = dict(os.environ)
flags = ['-e', 'PYTHONPATH=/startup/settings', '-e', 'PY313_PLATFORM_ROOT=/runtime/platform-source',
         '-e', 'DJANGO_SETTINGS_MODULE=exchange_acceptance']
values = []
for line in secret_path.read_text().splitlines():
    if '=' in line and not line.startswith('#'):
        key, value = line.split('=', 1)
        env[key] = value
        flags += ['-e', key]
        if value:
            values.append(value)
command = ['docker', 'exec', '-w', '/runtime/platform-source', *flags, container,
           '/runtime/venv/bin/python', '-u', '-c',
           "import runpy; runpy.run_path('/startup/test_auth_exchange_runtime.py', run_name='__main__')"]
start = datetime.datetime.now(datetime.timezone.utc).isoformat()
result = subprocess.run(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
end = datetime.datetime.now(datetime.timezone.utc).isoformat()
output = result.stdout
for value in sorted(values, key=len, reverse=True):
    output = output.replace(value, '<redacted>')
with output_path.open('x') as stream:
    stream.write(output)
output_path.chmod(0o600)
record = {'start': start, 'end': end, 'host_cwd': str(Path.cwd()),
          'container_cwd': '/runtime/platform-source', 'command': command,
          'role': 'anonymous requests; read-only existing ordinary fixture owner',
          'secret_source': str(secret_path), 'secret_values_archived': False,
          'exit_code': result.returncode, 'output': output_path.name,
          'input_sha256': {str(p.relative_to(Path(__file__).parent)): hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in (Path(__file__), Path(__file__).with_name('test_auth_exchange_runtime.py'),
                                     Path(__file__).parent / 'settings/exchange_acceptance.py')}}
with (root / 'commands.jsonl').open('a') as stream:
    stream.write(json.dumps(record, sort_keys=True) + '\n')
(root / 'commands.jsonl').chmod(0o600)
print('exit_code=' + str(result.returncode), 'output=' + str(output_path))
print(output[-2500:])
raise SystemExit(result.returncode)
