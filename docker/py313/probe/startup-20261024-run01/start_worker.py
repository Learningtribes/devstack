"""Start the real LMS Celery worker against the isolated RabbitMQ vhost."""
import os
import subprocess
from pathlib import Path


root = Path(__file__).resolve().parent
base_env = root.parents[1] / ".env"
protected = {}
for env_file in (base_env, root / ".env"):
    protected.update(
        line.split("=", 1)
        for line in env_file.read_text().splitlines()
        if "=" in line and not line.startswith("#")
    )

if subprocess.run(["docker", "exec", "py313-startup-runtime-20261024",
                   "test", "-s", "/runtime/config/site-ids.json"], check=False).returncode:
    raise SystemExit("Refusing to start worker before natural-key Site seeding")

command = (
    "umask 077; mkdir -p /runtime/logs; "
    "exec /runtime/venv/bin/celery -A lms.celery:APP worker "
    "--loglevel=INFO --pool=solo --hostname=py313-lms@%h "
    ">> /runtime/logs/lms-worker.log 2>&1"
)
subprocess.run(
    [
        "docker",
        "exec",
        "-d",
        "-e",
        "DJANGO_SETTINGS_MODULE=startup_lms",
        "-e",
        "PY313_STARTUP_SECRET_KEY",
        "-e",
        "PY313_MYSQL_PASSWORD",
        "-e",
        "PY313_MYSQL_USER",
        "-e",
        "PY313_MONGO_PASSWORD",
        "-e",
        "PY313_RABBITMQ_PASSWORD",
        "-e",
        "PY313_RABBITMQ_USER",
        "-e",
        "PY313_STARTUP_XQUEUE_PASSWORD",
        "py313-startup-runtime-20261024",
        "sh",
        "-c",
        "cd /edx/app/edxapp/edx-platform; " + command,
    ],
    env={**os.environ, **protected},
    check=True,
)
print("LMS worker dispatched; inspect /runtime/logs/lms-worker.log")
