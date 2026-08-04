#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

import json
import re
import sys
from collections import Counter


PARAMETER_SUFFIX = re.compile(r'(::test_[^:]+?)_[0-9]+_.+$')
NODE_PREFIXES = ('test_', 'common/', 'lms/', 'openedx/')


def collection_nodes(path):
    with open(path, 'r') as collection_file:
        return [
            line.strip()
            for line in collection_file
            if line.startswith(NODE_PREFIXES) and '::' in line
        ]


def canonical_counts(nodes):
    return Counter(PARAMETER_SUFFIX.sub(r'\1', node) for node in nodes)


def main():
    if len(sys.argv) != 3:
        raise SystemExit('usage: compare-p1b-ora2-collections.py PY36_COLLECTION PY27_COLLECTION')

    py36_nodes = collection_nodes(sys.argv[1])
    py27_nodes = collection_nodes(sys.argv[2])
    py36_counts = canonical_counts(py36_nodes)
    py27_counts = canonical_counts(py27_nodes)
    all_ids = sorted(set(py36_counts) | set(py27_counts))
    differences = [
        {
            'canonical_id': canonical_id,
            'py36_count': py36_counts[canonical_id],
            'py27_count': py27_counts[canonical_id],
        }
        for canonical_id in all_ids
        if py36_counts[canonical_id] != py27_counts[canonical_id]
    ]
    result = {
        'status': 'COLLECTIONS_MATCH' if not differences and len(py36_nodes) == len(py27_nodes) else 'MISMATCH',
        'py36_raw_count': len(py36_nodes),
        'py27_raw_count': len(py27_nodes),
        'canonical_group_count': len(all_ids),
        'differences': differences,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    if result['status'] != 'COLLECTIONS_MATCH':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
