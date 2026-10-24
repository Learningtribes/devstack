"""Host entry point: register/create a fresh DB, grant only it, initialize models.

Run through uv with Python3.13. Existing unregistered databases are refused.
Registered partial initialization may resume, preserving all rows and tables.
"""
import json
import os
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parent
database = sys.argv[1] if len(sys.argv) == 2 else ''
if database != 'py313_startup_20261024':
    raise SystemExit('Only registered working database is implemented; rebuild configuration pending')
ledger = root / 'created-resources.json'
registered = json.loads(ledger.read_text()) if ledger.exists() else {'mysql_databases': []}
# SQL is passed as a positional argument and never interpolates a credential.
def mysql(sql):
    result = subprocess.run(['docker','exec','py313.mysql','bash','-c',
        'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot -N -e "$1"', 'schema-init', sql],
        capture_output=True,text=True)
    if result.returncode:
        raise SystemExit('MySQL administration failed (credentials withheld)')
    return result.stdout
existing = mysql('SHOW DATABASES').splitlines()
if database in existing and database not in registered['mysql_databases']:
    raise SystemExit('Refusing existing unregistered database')
if database not in existing:
    mysql('CREATE DATABASE `'+database+'` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
    registered['mysql_databases'].append(database)
    ledger.write_text(json.dumps(registered, indent=2)+'\n')
mysql("GRANT ALL PRIVILEGES ON `"+database+"`.* TO 'edxapp'@'%'")
runner = Path('/Users/noahwang/docs/hawthorn/py313-startup-artifacts-2026-10-24/run-02/run_check.py')
iteration = os.environ.get('PY313_SCHEMA_ITERATION')
if not iteration:
    raise SystemExit('Set a fresh PY313_SCHEMA_ITERATION evidence label')
result = subprocess.run([sys.executable,str(runner),'lms',iteration,'shell','-c',
    'exec(open("/startup/initialize_schema.py").read())'],env={**os.environ,'PY313_CHECK_SETTINGS':'startup_schema'})
if result.returncode:
    raise SystemExit(result.returncode)
sites = subprocess.run([sys.executable, str(runner), 'lms', iteration + '-site-seed', 'shell', '-c',
    'exec(open("/startup/seed_local_host_sites.py").read())'],
    env={**os.environ, 'PY313_CHECK_SETTINGS':'startup_lms'})
raise SystemExit(sites.returncode)
