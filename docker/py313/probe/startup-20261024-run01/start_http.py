"""Start a real Django development HTTP process in the registered runtime."""
import os
from pathlib import Path
import subprocess
import sys
root=Path(__file__).resolve().parent
base_env=root.parents[1] / '.env'
system=sys.argv[1]
if system not in {'lms','cms'}:
    raise SystemExit('Choose lms or cms')
port=int(os.environ.get('PY313_LMS_CONTAINER_PORT' if system == 'lms' else 'PY313_CMS_CONTAINER_PORT',
                        18000 if system == 'lms' else 18010))
protected={}
for env_file in (base_env, root/'.env'):
    protected.update(line.split('=',1) for line in env_file.read_text().splitlines() if '=' in line and not line.startswith('#'))
# Refuse to serve an unseeded DB with Django's unrelated default Site.
if subprocess.run(['docker', 'exec', 'py313-startup-runtime-20261024',
                   'test', '-s', '/runtime/config/site-ids.json'], check=False).returncode:
    raise SystemExit('Refusing to start HTTP before natural-key Site seeding')
# Fail on an occupied port; runserver must not replace an existing process.
command=f'umask 077; mkdir -p /runtime/logs; exec /runtime/venv/bin/python manage.py {system} runserver 0.0.0.0:{port} --noreload --insecure >> /runtime/logs/{system}-http.log 2>&1'
subprocess.run(['docker','exec','-d','-e','DJANGO_SETTINGS_MODULE=startup_'+system,'-e','PY313_STARTUP_XQUEUE_PASSWORD',
    '-e','PY313_RABBITMQ_USER','-e','PY313_RABBITMQ_PASSWORD',
    'py313-startup-runtime-20261024','sh','-c',command],env={**os.environ,**protected},check=True)
print(system+' HTTP process dispatched; health and business verification required')
