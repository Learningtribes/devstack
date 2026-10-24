"""Start a real Django HTTP process in the registered local runtime."""
import subprocess
import sys

from runtime_process import options

container, platform, environment, forwarded = options()
system = sys.argv[1]
if system not in {'lms', 'cms'}:
    raise SystemExit('Choose lms or cms')
port = int(environment.get('PY313_LMS_CONTAINER_PORT' if system == 'lms'
                           else 'PY313_CMS_CONTAINER_PORT',
                           18000 if system == 'lms' else 18010))
if not 1024 <= port <= 65535:
    raise SystemExit('Invalid local runtime port')
command = ('umask 077; mkdir -p /runtime/logs; '
           f'exec /runtime/venv/bin/python manage.py {system} runserver '
           f'0.0.0.0:{port} --noreload --insecure '
           f'>> /runtime/logs/{system}-http.log 2>&1')
subprocess.run(['docker', 'exec', '-d', '-w', platform, *forwarded,
                '-e', 'DJANGO_SETTINGS_MODULE=startup_' + system,
                container, 'sh', '-c', command], env=environment, check=True)
print(system + ' HTTP dispatched; health and business verification required')
