"""Start the real LMS Celery worker in the registered local runtime."""
import subprocess

from runtime_process import options

container, platform, environment, forwarded = options()
command = ('umask 077; mkdir -p /runtime/logs; '
           'exec /runtime/venv/bin/celery -A lms.celery:APP worker '
           '--loglevel=INFO --pool=solo --hostname=py313-lms@%h '
           '>> /runtime/logs/lms-worker.log 2>&1')
subprocess.run(['docker', 'exec', '-d', '-w', platform, *forwarded,
                '-e', 'DJANGO_SETTINGS_MODULE=startup_lms', container,
                'sh', '-c', command], env=environment, check=True)
print('LMS worker dispatched; inspect /runtime/logs/lms-worker.log')
