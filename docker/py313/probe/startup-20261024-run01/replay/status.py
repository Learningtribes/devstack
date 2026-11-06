"""Report container states, published ports and heartbeat codes of one run. Read-only."""
import argparse
import json
from pathlib import Path
import subprocess

from core import SERVICES, load_config
from http_client import base_urls, heartbeat


def container_names(config):
    return [config['runtime_container'], *(config['services'][name]['container'] for name in SERVICES)]


def inspect_container(name):
    result = subprocess.run(['docker', 'inspect', '--type', 'container', '--format',
                             '{"state":{{json .State.Status}},"health":{{json .State.Health}},'
                             '"ports":{{json .NetworkSettings.Ports}}}', name], capture_output=True, text=True)
    if result.returncode:
        return None
    return json.loads(result.stdout)


def published(ports):
    return ', '.join(sorted('%s:%s->%s' % (binding['HostIp'], binding['HostPort'], port)
                            for port, bindings in (ports or {}).items() for binding in bindings or []))


def collect(config):
    rows = []
    for name in container_names(config):
        info = inspect_container(name)
        rows.append({'name': name, 'state': info['state'] if info else 'absent',
                     'health': ((info['health'] or {}).get('Status') if info else None),
                     'ports': published(info['ports']) if info else ''})
    heartbeats = {system: heartbeat(url) for system, url in base_urls(config).items()}
    return rows, heartbeats


def healthy(rows, heartbeats):
    return all(row['state'] == 'running' for row in rows) and all(code == 200 for code in heartbeats.values())


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--config', required=True, type=Path)
    args = parser.parse_args()
    config = load_config(args.config)
    rows, heartbeats = collect(config)
    for row in rows:
        print('%-36s %-8s %-10s %s' % (row['name'], row['state'], row['health'] or '-', row['ports'] or '-'))
    urls = base_urls(config)
    for system in ('lms', 'cms'):
        print('%s %s/heartbeat -> %s' % (system.upper(), urls[system], heartbeats[system]))
    raise SystemExit(0 if healthy(rows, heartbeats) else 1)


if __name__ == '__main__':
    main()
