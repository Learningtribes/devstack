"""Verify genuine local UDP transport, UTF-8 tags and wrapper normalization."""
import socket

from dogapi.stats import DogStatsApi
from dogstats_wrapper.wrapper import _clean_tags

with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
    receiver.bind(('127.0.0.1', 0))
    receiver.settimeout(2)
    api = DogStatsApi()
    api.start(statsd=True, statsd_host='127.0.0.1', statsd_port=receiver.getsockname()[1])
    tags = _clean_tags(['课程|发布', b'role:staff', 313, 'x' * 250])
    assert tags == ['课程_发布', 'role:staff', '313', 'x' * 200]
    api.increment('py313.publish', tags=tags)
    packet, _ = receiver.recvfrom(4096)
    assert packet.decode('utf-8') == 'py313.publish:1|c|#' + ','.join(tags)
    with api.timer('py313.duration'):
        pass
    packet, _ = receiver.recvfrom(4096)
    assert packet.startswith(b'py313.duration:') and packet.endswith(b'|h')
    api._aggregator.socket.close()
print('PASS: real UDP counter/timer packets and UTF-8/mixed tag normalization')
