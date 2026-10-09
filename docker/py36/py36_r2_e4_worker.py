# -*- coding: utf-8 -*-
"""Run the R2-preview E4 LMS worker on the isolated default queue."""
from __future__ import absolute_import, division, print_function, unicode_literals

import os
import socket
import sys

import django

django.setup()

from celery import bootsteps  # noqa: E402
from celery.apps.worker import install_worker_int_handler, install_worker_term_handler  # noqa: E402
from celery.worker import WorkController, state  # noqa: E402
from django.conf import settings  # noqa: E402

from lms.celery import APP  # noqa: E402
from openedx.core.djangoapps.heartbeat.tasks import sample_task  # noqa: E402

WORKER_NAME = os.environ.get('PY36_R2_E4_WORKER_HOSTNAME', 'py36-r2-worker')


@APP.task(name='py36_r2_e4.success')
def success():
    return {'status': 'ok', 'worker': WORKER_NAME}


@APP.task(name='py36_r2_e4.controlled_failure')
def controlled_failure():
    raise RuntimeError('py36-r2-e4-controlled-failure')


def sync_loop(obj, connection, consumer, blueprint, hub, qos, heartbeat, clock,
              hbrate=2.0, **kwargs):
    """Consume with a timeout so the py-amqp 1.4 connection keeps sending heartbeats."""
    consumer.register_callback(obj.create_task_handler())
    consumer.consume()
    obj.on_ready()
    while blueprint.state == bootsteps.RUN and obj.connection:
        state.maybe_shutdown()
        if qos.prev != qos.value:
            qos.update()
        connection.heartbeat_check(rate=hbrate)
        try:
            connection.drain_events(timeout=1.0)
        except socket.timeout:
            pass
        except socket.error:
            if blueprint.state == bootsteps.RUN:
                raise


def main():
    required = (sample_task.name, success.name, controlled_failure.name)
    missing = [name for name in required if name not in APP.tasks]
    if missing:
        raise RuntimeError('missing required tasks: {}'.format(missing))
    controller = WorkController(
        app=APP,
        hostname='{}@{}'.format(WORKER_NAME, socket.gethostname()),
        loglevel='INFO',
        pool='solo',
        concurrency=1,
        use_eventloop=False,
        queues=(settings.CELERY_DEFAULT_QUEUE,),
        without_mingle=True,
        without_gossip=True,
        without_heartbeat=False,
    )
    controller.consumer.amqheartbeat = settings.BROKER_HEARTBEAT
    controller.consumer.loop = sync_loop
    # A bare WorkController installs no signal handlers, and as container PID 1
    # the process would ignore docker stop's SIGTERM until SIGKILL.
    install_worker_term_handler(controller)
    install_worker_int_handler(controller)
    sys.stdout.write('PY36_R2_E4_WORKER_READY queue={} registered={} broker_heartbeat={}\n'.format(
        settings.CELERY_DEFAULT_QUEUE, len(APP.tasks), settings.BROKER_HEARTBEAT,
    ))
    sys.stdout.flush()
    controller.start()


if __name__ == '__main__':
    main()
