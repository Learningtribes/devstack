# -*- coding: utf-8 -*-
"""E6 grading worker: the R1 grade/progress consumer on the stack's own broker."""
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
from lms.djangoapps.grades.tasks import (  # noqa: E402
    calculate_course_progress,
    recalculate_subsection_grade_v3,
)

WORKER_NAME = os.environ.get('PY36_R2_E6_WORKER_HOSTNAME', 'py36-r2-e6-worker')


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
    required = (recalculate_subsection_grade_v3.name, calculate_course_progress.name)
    missing = [name for name in required if name not in APP.tasks]
    if missing:
        raise RuntimeError('missing required grading tasks: {}'.format(missing))
    controller = WorkController(
        app=APP,
        hostname='{}@{}'.format(WORKER_NAME, socket.gethostname()),
        loglevel='INFO',
        pool='solo',
        concurrency=1,
        use_eventloop=False,
        queues=(settings.GRADING_QUEUES['grade'], settings.GRADING_QUEUES['progress']),
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
    sys.stdout.write('PY36_R2_E6_WORKER_READY queues={} required={} broker_heartbeat={}\n'.format(
        settings.GRADING_QUEUES, required, settings.BROKER_HEARTBEAT,
    ))
    sys.stdout.flush()
    controller.start()


if __name__ == '__main__':
    main()
