"""Start a genuine LMS or CMS worker on its isolated service queues."""
import re
import shlex
import subprocess
import sys

from runtime_process import options

container, platform, environment, forwarded = options()
system = sys.argv[1] if len(sys.argv) > 1 else 'lms'
if system not in {'lms', 'cms'}:
    raise SystemExit('Choose lms or cms')
prefix = environment.get('PY313_TASK_QUEUE_PREFIX')
queue_option = ''
if prefix:
    if not re.fullmatch(r'[a-zA-Z0-9_-]+', prefix):
        raise SystemExit('Invalid isolated queue prefix')
    queues = ','.join(prefix + '.' + system + '.' + priority
                      for priority in ('high', 'default', 'low', 'high_mem'))
    queue_option = ' --queues=' + shlex.quote(queues)
command = ('umask 077; mkdir -p /runtime/logs; '
           f'exec /runtime/venv/bin/celery -A {system}.celery:APP worker '
           f'--loglevel=INFO --pool=solo --hostname=py313-{system}@%h'
           + queue_option + f' >> /runtime/logs/{system}-worker.log 2>&1')
subprocess.run(['docker', 'exec', '-d', '-w', platform, *forwarded,
                '-e', 'DJANGO_SETTINGS_MODULE=startup_' + system, container,
                'sh', '-c', command], env=environment, check=True)
print(system.upper() + ' worker dispatched; inspect service worker log and business results')
