"""Celery 5.6 / RabbitMQ 4.3 pidbox matrix.

Runs the same worker + client round trip against the permit broker (`rabbitmq`) and the
default-policy control broker (`rabbitmq-noperm`) with different Celery control settings.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import uuid

import kombu

USER = os.environ.get("PY313_RABBITMQ_USER", "edxapp")
PASSWORD = os.environ["PY313_RABBITMQ_PASSWORD"]
RESULT_BACKEND = "redis://valkey:6379/1"

TASKS = """
import json, os
from celery import Celery
app = Celery('matrix_tasks', broker=os.environ['MX_BROKER'], backend=os.environ['MX_BACKEND'])
app.conf.task_default_queue = os.environ['MX_QUEUE']
app.conf.update(json.loads(os.environ['MX_CONF']))
@app.task
def add(a, b):
    return a + b
"""

CLIENT = """
import json, os, time
import matrix_tasks as t
out = {}
if os.environ['MX_PING'] == '1':
    deadline = time.time() + 40
    out['ping'] = False
    while time.time() < deadline and not out['ping']:
        out['ping'] = bool(t.app.control.ping(timeout=2))
else:
    time.sleep(10)
out['result'] = t.add.delay(2, 3).get(timeout=25)
print('RESULT ' + json.dumps(out))
"""

WORKER_FLAGS = ["--without-mingle", "--without-gossip", "--without-heartbeat"]

CASES = [
    # (name, broker host, celery conf, extra worker flags, ping through pidbox)
    ("permit broker, default conf", "rabbitmq", {}, [], True),
    ("default broker, default conf", "rabbitmq-noperm", {}, [], True),
    ("default broker, control_queue_exclusive", "rabbitmq-noperm", {"control_queue_exclusive": True}, [], True),
    ("default broker, remote control off", "rabbitmq-noperm",
     {"worker_enable_remote_control": False}, WORKER_FLAGS, False),
]


def run_case(name, host, conf, flags, ping):
    url = "amqp://%s:%s@%s:5672//" % (USER, PASSWORD, host)
    queue = "py313_mx_%s" % uuid.uuid4().hex[:8]
    workdir = tempfile.mkdtemp()
    with open(os.path.join(workdir, "matrix_tasks.py"), "w") as fh:
        fh.write(TASKS)
    env = dict(os.environ, MX_BROKER=url, MX_BACKEND=RESULT_BACKEND, MX_QUEUE=queue, MX_CONF=json.dumps(conf),
               MX_PING="1" if ping else "0", PYTHONPATH=workdir)
    log_path = os.path.join(workdir, "worker.log")
    with open(log_path, "w") as log:
        worker = subprocess.Popen([sys.executable, "-m", "celery", "-A", "matrix_tasks", "worker", "-c", "1"] + flags,
                                  cwd=workdir, env=env, stdout=log, stderr=subprocess.STDOUT)
    try:
        proc = subprocess.run([sys.executable, "-c", CLIENT], cwd=workdir, env=env, capture_output=True, text=True,
                              timeout=90)
        line = [x for x in proc.stdout.splitlines() if x.startswith("RESULT ")]
        if line:
            return "PASS " + line[0][7:]
        reason = " / ".join((proc.stderr.strip().splitlines() or ["no output"])[-3:])
        worker_state = "worker exited %s" % worker.poll() if worker.poll() is not None else "worker alive"
        hint = [x.strip() for x in open(log_path).read().splitlines() if "transient_nonexcl" in x]
        return "FAIL client: %s | %s | worker log: %s" % (
            reason[:200], worker_state, hint[0][:200] if hint else "no transient_nonexcl refusal")
    except subprocess.TimeoutExpired:
        return "FAIL client timeout"
    finally:
        worker.terminate()
        try:
            worker.wait(timeout=20)
        except subprocess.TimeoutExpired:
            worker.kill()
        with kombu.Connection(url) as conn:
            kombu.Queue(queue)(conn.default_channel).delete(if_unused=False, if_empty=False)
        time.sleep(1)


print("celery/kombu matrix, result backend %s" % RESULT_BACKEND)
for case in CASES:
    if sys.argv[1:] and not any(a in case[0] for a in sys.argv[1:]):
        continue
    print("%-42s %s" % (case[0], run_case(*case)))
