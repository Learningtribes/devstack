"""Strictly load registered course tabs/tools/XBlocks; never swallow errors."""
import importlib.metadata
import platform
import sys
import traceback

sys.path.insert(0, '/edx/app/edxapp/edx-platform')
import django

django.setup()
print('Python', platform.python_version(), 'Django', django.get_version())
failures = []
for group in ['openedx.course_tab', 'openedx.course_tool', 'xblock.v1']:
    entries = list(importlib.metadata.entry_points(group=group))
    assert entries, group
    for entry in sorted(entries, key=lambda item: item.name):
        try:
            loaded = entry.load()
            print('LOADED', group, entry.name, loaded.__module__, loaded.__name__)
        except Exception as exc:
            traceback.print_exc()
            failures.append((group, entry.name, type(exc).__name__, str(exc)))
print('FAILURES', failures)
assert not failures, failures
