#!/usr/bin/env python3
"""Read-only clone of the shared Elasticsearch 1.5 indices for E6 stacks.

usage: r2-e6-es-clone.py dump <source-container> <snapshot.json>
       r2-e6-es-clone.py restore <target-container> <snapshot.json>

Both sides are reached with `docker exec <container> curl`. `dump` issues GET
requests only. Indices whose primaries are unassigned (red) cannot be read, so
only their settings and mappings are cloned. The single-node target gets zero
replicas.
"""
import json
import subprocess
import sys

COPIED_INDEX_SETTINGS = ('number_of_shards', 'analysis')


def curl(container, method, path, body=None):
    cmd = ['docker', 'exec', '-i', container, 'curl', '-sS', '-X', method,
           'http://localhost:9200' + path]
    if body is not None:
        cmd[5:5] = ['-H', 'Content-Type: application/json', '--data-binary', '@-']
    out = subprocess.run(cmd, input=None if body is None else body.encode('utf-8'),
                         stdout=subprocess.PIPE, check=True).stdout
    return json.loads(out.decode('utf-8'))


def dump(source, path):
    settings = curl(source, 'GET', '/_settings')
    mappings = curl(source, 'GET', '/_mapping')
    aliases = curl(source, 'GET', '/_aliases')
    health = curl(source, 'GET', '/_cluster/health?level=indices')['indices']
    indices = {}
    for name in sorted(settings):
        index_settings = settings[name]['settings']['index']
        entry = {
            'health': health[name]['status'],
            'settings': dict({k: index_settings[k] for k in COPIED_INDEX_SETTINGS if k in index_settings},
                             number_of_replicas='0'),
            'dropped_settings': sorted(set(index_settings) - set(COPIED_INDEX_SETTINGS)),
            'mappings': mappings.get(name, {}).get('mappings', {}),
            'aliases': aliases.get(name, {}).get('aliases', {}),
            'docs': None,
        }
        if entry['health'] != 'red':
            result = curl(source, 'GET', '/{}/_search?size=10000'.format(name))
            hits = result['hits']['hits']
            if result['hits']['total'] != len(hits):
                raise SystemExit('{}: {} of {} documents returned'.format(name, len(hits), result['hits']['total']))
            entry['docs'] = [{'_type': h['_type'], '_id': h['_id'], '_source': h['_source']} for h in hits]
        indices[name] = entry
    with open(path, 'w') as snapshot:
        json.dump({'indices': indices}, snapshot, sort_keys=True, indent=1)
    for name, entry in sorted(indices.items()):
        docs = 'unreadable' if entry['docs'] is None else len(entry['docs'])
        print('E6_ES_DUMP index={} health={} docs={} types={}'.format(
            name, entry['health'], docs, ','.join(sorted(entry['mappings']))))


def restore(target, path):
    with open(path) as snapshot:
        indices = json.load(snapshot)['indices']
    for name, entry in sorted(indices.items()):
        body = {'settings': entry['settings'], 'mappings': entry['mappings'], 'aliases': entry['aliases']}
        response = curl(target, 'PUT', '/' + name, json.dumps(body))
        if response.get('acknowledged') is not True:
            raise SystemExit('{}: create failed: {}'.format(name, response))
        docs = entry['docs'] or []
        if docs:
            lines = []
            for doc in docs:
                lines.append(json.dumps({'index': {'_index': name, '_type': doc['_type'], '_id': doc['_id']}}))
                lines.append(json.dumps(doc['_source']))
            response = curl(target, 'POST', '/_bulk', '\n'.join(lines) + '\n')
            if response.get('errors'):
                raise SystemExit('{}: bulk errors: {}'.format(name, response))
    curl(target, 'POST', '/_refresh')
    for name, entry in sorted(indices.items()):
        count = curl(target, 'GET', '/{}/_count'.format(name))['count']
        expected = len(entry['docs'] or [])
        if count != expected:
            raise SystemExit('{}: {} documents after restore, expected {}'.format(name, count, expected))
        print('E6_ES_RESTORE index={} docs={}'.format(name, count))


if __name__ == '__main__':
    if len(sys.argv) != 4 or sys.argv[1] not in ('dump', 'restore'):
        raise SystemExit(__doc__)
    {'dump': dump, 'restore': restore}[sys.argv[1]](sys.argv[2], sys.argv[3])
