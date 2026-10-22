"""Static PyPI-metadata matrix for the Hawthorn pin roster (step 2a-0).

Reads requirements/edx/base.txt and testing.txt from a platform checkout,
queries PyPI JSON for each pinned name, and writes a JSON + Markdown matrix.
Resolves nothing and installs nothing.

    uv run --with packaging python static_matrix.py PLATFORM_DIR OUT_PREFIX
"""
import json
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name
from packaging.version import Version, InvalidVersion

TARGET_PY = Version("3.13")
TARGET_DJANGO = Version("5.2.18")
NOW = datetime.now(timezone.utc)
PIN_RE = re.compile(r"^([A-Za-z0-9_.\-]+)(\[[^\]]+\])?==([^\s;#]+)\s*(;[^#]*)?")
NAME_RE = re.compile(r"^([A-Za-z0-9_.\-]+)")


def read_pins(path):
    pins = {}
    for line in open(path, encoding="utf-8"):
        m = PIN_RE.match(line.strip())
        if m:
            pins[canonicalize_name(m.group(1))] = {
                "pinned": m.group(3),
                "marker": (m.group(4) or "").strip("; ").strip(),
            }
    return pins


def read_names(path):
    names = set()
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith(("#", "-", "git+")):
            continue
        m = NAME_RE.match(line)
        if m:
            names.add(canonicalize_name(m.group(1)))
    return names


def fetch(name):
    url = "https://pypi.org/pypi/%s/json" % name
    for _ in range(3):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                return json.load(r)
        except Exception as exc:  # noqa: BLE001
            err = str(exc)
    return {"error": err}


def upload(releases, ver):
    files = releases.get(ver) or []
    times = [f["upload_time_iso_8601"] for f in files if not f.get("yanked")]
    return min(times)[:10] if times else None


def latest_stable(releases):
    best = None
    for ver, files in releases.items():
        if not files or all(f.get("yanked") for f in files):
            continue
        try:
            v = Version(ver)
        except InvalidVersion:
            continue
        if v.is_prerelease or v.is_devrelease:
            continue
        if best is None or v > best:
            best = v
    return str(best) if best else None


def analyse(name, pin, direct, data):
    row = {"name": name, "pinned": pin["pinned"], "marker": pin["marker"], "direct": direct}
    if "error" in data:
        row.update(status="未在 PyPI 找到", error=data["error"])
        return row
    releases = data["releases"]
    latest = latest_stable(releases)
    info = data["info"]
    row["latest"] = latest
    row["pinned_date"] = upload(releases, pin["pinned"])
    row["latest_date"] = upload(releases, latest) if latest else None
    ver_info = info
    if latest and latest != info.get("version"):
        try:
            with urllib.request.urlopen("https://pypi.org/pypi/%s/%s/json" % (name, latest), timeout=30) as r:
                ver_info = json.load(r)["info"]
        except Exception:  # noqa: BLE001
            pass
    rp = ver_info.get("requires_python") or ""
    row["requires_python"] = rp
    try:
        row["py313_ok"] = TARGET_PY in SpecifierSet(rp) if rp else None
    except Exception:  # noqa: BLE001
        row["py313_ok"] = None
    row["classifier_313"] = any(c.endswith("Python :: 3.13") for c in ver_info.get("classifiers") or [])
    django_reqs = []
    allows = None
    for raw in ver_info.get("requires_dist") or []:
        try:
            req = Requirement(raw)
        except Exception:  # noqa: BLE001
            continue
        if canonicalize_name(req.name) == "django":
            if req.marker and not req.marker.evaluate({"extra": ""}):
                continue
            django_reqs.append(str(req.specifier) or "*")
            ok = TARGET_DJANGO in req.specifier if str(req.specifier) else True
            allows = ok if allows is None else (allows and ok)
    row["django_req"] = ",".join(django_reqs)
    row["allows_django52"] = allows
    row["age_years"] = round((NOW - datetime.fromisoformat(row["latest_date"] + "T00:00:00+00:00")).days / 365, 1) if row["latest_date"] else None
    row["status"] = classify(row)
    return row


def classify(r):
    if r["marker"] and 'python_version == "2.7"' in r["marker"]:
        return "移除（Py2 专用）"
    if r.get("py313_ok") is False:
        return "最新版不支持 3.13，需替换"
    if r.get("allows_django52") is False:
        return "最新版仍卡 Django 上限，需替换或打补丁"
    if r.get("age_years") is not None and r["age_years"] >= 5:
        return "停更 5 年以上（是否能用待验证）"
    if r["latest"] == r["pinned"]:
        return "已是最新"
    if r.get("django_req") and r.get("allows_django52"):
        return "可升级（Django 耦合，需验证 API）"
    return "可升级"


def main(platform, out):
    base = read_pins(platform + "/requirements/edx/base.txt")
    testing = read_pins(platform + "/requirements/edx/testing.txt")
    direct = set()
    for f in ("edx/base.in", "edx/paver.in", "edx-sandbox/shared.in", "edx/testing.in"):
        direct |= read_names(platform + "/requirements/" + f)
    roster = {}
    for layer, pins in (("base", base), ("testing", testing)):
        for n, p in pins.items():
            if n not in roster:
                roster[n] = dict(p, layer=layer)
    names = sorted(roster)
    with ThreadPoolExecutor(12) as ex:
        data = list(ex.map(fetch, names))
    rows = []
    for n, d in zip(names, data):
        row = analyse(n, roster[n], n in direct, d)
        row["layer"] = roster[n]["layer"]
        rows.append(row)
    json.dump(rows, open(out + ".json", "w"), ensure_ascii=False, indent=1)

    counts = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    with open(out + ".md", "w", encoding="utf-8") as f:
        f.write("# 静态元数据矩阵（原始输出）\n\n生成时间：%s；名单：base.txt %d 个 + testing.txt 独有 %d 个；目标：Python %s、Django %s。\n\n"
                % (NOW.strftime("%Y-%m-%d %H:%M UTC"), len(base), len([r for r in rows if r["layer"] == "testing"]), TARGET_PY, TARGET_DJANGO))
        f.write("## 统计\n\n| 状态 | 数量 |\n|---|---|\n")
        for k, v in sorted(counts.items(), key=lambda kv: -kv[1]):
            f.write("| %s | %d |\n" % (k, v))
        order = ["最新版不支持 3.13，需替换", "最新版仍卡 Django 上限，需替换或打补丁", "停更 5 年以上（是否能用待验证）",
                 "移除（Py2 专用）", "未在 PyPI 找到", "可升级（Django 耦合，需验证 API）", "可升级", "已是最新"]
        for status in order:
            grp = [r for r in rows if r["status"] == status]
            if not grp:
                continue
            f.write("\n## %s（%d）\n\n| 包 | 层 | 直接 | 现钉 | 最新 | 最新发布 | 最新版 requires_python | Django 要求 |\n|---|---|---|---|---|---|---|---|\n" % (status, len(grp)))
            for r in grp:
                f.write("| %s | %s | %s | %s | %s | %s | %s | %s |\n" % (
                    r["name"], r["layer"], "是" if r["direct"] else "", r["pinned"], r.get("latest", ""),
                    r.get("latest_date", ""), r.get("requires_python", ""), r.get("django_req", "")))
    print(json.dumps(counts, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
