"""Check a resolved-*.txt against PyPI metadata for a target Python.

uv pip compile does not reject releases whose Requires-Python excludes the target
(observed: scipy 1.10.1, <3.12, selected under --python-version 3.13), so the
resolver output has to be re-checked.

    uv run --with packaging python check_resolved.py resolved-313-L2.txt 3.13 OUT_PREFIX
"""
import json
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from packaging.specifiers import SpecifierSet
from packaging.version import Version

path, py, out = sys.argv[1], sys.argv[2], sys.argv[3]
TARGET = Version(py)
tag = "cp" + py.replace(".", "")
pin = re.compile(r"^([A-Za-z0-9_.\-]+)(\[[^\]]+\])?==([^\s;#]+)")
pins = []
for line in open(path, encoding="utf-8"):
    m = pin.match(line.strip())
    if m:
        pins.append((m.group(1), m.group(3)))


def get(item):
    name, ver = item
    for _ in range(3):
        try:
            with urllib.request.urlopen("https://pypi.org/pypi/%s/%s/json" % (name, ver), timeout=30) as r:
                d = json.load(r)
            break
        except Exception as exc:  # noqa: BLE001
            d = {"error": str(exc)}
    if "error" in d:
        return dict(name=name, ver=ver, kind="metadata-error", rp="", err=d["error"])
    rp = d["info"].get("requires_python") or ""
    ok = True
    if rp:
        try:
            ok = TARGET in SpecifierSet(rp)
        except Exception:  # noqa: BLE001
            ok = None
    files = d["urls"]
    wheels = [f["filename"] for f in files if f["packagetype"] == "bdist_wheel"]
    pure = [w for w in wheels if w.endswith("-none-any.whl")]
    abi3 = [w for w in wheels if "-abi3-" in w and "linux" in w and "aarch64" in w]
    native = [w for w in wheels if ("-%s-" % tag) in w and "linux" in w and "aarch64" in w]
    sdist = [f for f in files if f["packagetype"] == "sdist"]
    if ok is False:
        kind = "requires-python-excludes-target"
    elif pure:
        kind = "pure-wheel"
    elif native or abi3:
        kind = "native-wheel"
    elif sdist:
        kind = "sdist-only"
    else:
        kind = "no-files"
    return dict(name=name, ver=ver, kind=kind, rp=rp)


with ThreadPoolExecutor(12) as ex:
    rows = list(ex.map(get, pins))
json.dump(rows, open(out + ".json", "w"), indent=1)
by = {}
for r in rows:
    by.setdefault(r["kind"], []).append(r)
with open(out + ".md", "w", encoding="utf-8") as f:
    f.write("# %s 对 Python %s 的复核\n\n| 类别 | 数量 |\n|---|---|\n" % (path, py))
    for k, v in sorted(by.items(), key=lambda kv: -len(kv[1])):
        f.write("| %s | %d |\n" % (k, len(v)))
    for k in ("requires-python-excludes-target", "sdist-only", "no-files", "metadata-error"):
        if k in by:
            f.write("\n## %s\n\n" % k)
            for r in by[k]:
                f.write("- `%s==%s`（requires_python `%s`）\n" % (r["name"], r["ver"], r["rp"]))
print({k: len(v) for k, v in by.items()})
