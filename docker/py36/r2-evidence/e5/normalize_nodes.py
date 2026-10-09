import re, sys
for line in sys.stdin:
    line = line.strip()
    if '::' not in line:
        continue
    print(re.sub(r'(::test\w*?_\d+)(_.*)?$', r'\1', line))
