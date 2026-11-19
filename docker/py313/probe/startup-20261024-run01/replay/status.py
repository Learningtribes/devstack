"""Report container states, published ports and heartbeat codes of one run. Read-only."""
import argparse
import json
from pathlib import Path
import subprocess

from core import SERVICES, discovery_enabled, discovery_url, load_config
from http_client import base_urls, heartbeat
import discovery


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
    if discovery_enabled(config):
        row, _ = discovery.status(config)
        rows.append({'name': row['name'], 'state': row['state'], 'health': None, 'ports': row['ports']})
    heartbeats = {system: heartbeat(url) for system, url in base_urls(config).items()}
    if discovery_enabled(config):
        heartbeats['discovery'] = discovery.http_status(discovery_url(config))
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
    if discovery_enabled(config):
        print('DISCOVERY %s/health/ -> %s' % (discovery_url(config), heartbeats['discovery']))
    raise SystemExit(0 if healthy(rows, heartbeats) else 1)


if __name__ == '__main__':
    main()
