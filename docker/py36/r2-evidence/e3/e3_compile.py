# Compile every path listed on stdin in memory; no .pyc is written.
from __future__ import print_function

import sys
import warnings

errors = []
warned = []
paths = [line.strip() for line in sys.stdin if line.strip()]
for path in paths:
    with open(path, 'rb') as source:
        data = source.read()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        try:
            compile(data, path, 'exec', dont_inherit=True)
        except SyntaxError as exc:
            errors.append('{}:{}: {}'.format(path, exc.lineno, exc.msg))
    for item in caught:
        warned.append('{}:{}: {}: {}'.format(path, item.lineno, item.category.__name__, item.message))

print('python', sys.version.split()[0])
print('files', len(paths))
print('syntax_errors', len(errors))
for line in errors:
    print('  ERROR', line)
print('compile_warnings', len(warned))
for line in warned:
    print('  WARN', line)
sys.exit(1 if errors else 0)
