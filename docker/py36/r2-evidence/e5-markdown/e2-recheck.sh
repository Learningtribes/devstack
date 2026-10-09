#!/bin/bash
# Re-run the identity-sensitive E2 checks on the Markdown 2.6.11 rebuild.
# Source 0ac3bfa6d09 fixed the duplicate edx_proctoring label, so plain
# lms|cms.envs.test replace E2's probe settings. Usage: e2-recheck.sh <out-dir>
set -u
OUT=$1
IMAGE=ltdps/edxapp:py36-r2-20261009
OLD_FREEZE=$(dirname "$0")/../e2/freeze.txt
SOURCE=/Users/noahwang/workspace/hawthorn/platform-r2-py36-src
SRC=/edx/app/edxapp/edx-platform
mkdir -p "${OUT}"

run() {
    docker run --rm --read-only --tmpfs /tmp:rw,exec,size=512m \
        --mount "type=bind,src=${SOURCE},dst=/edx/app/edxapp/edx-platform,readonly" \
        --env PYTHONPATH=${SRC}:${SRC}/common/lib/xmodule:${SRC}/common/lib/capa:${SRC}/openedx/core/lib/xblock_builtin/xblock_discussion:${SRC}/common/lib/calc:${SRC}/common/lib/safe_lxml:${SRC}/common/lib/symmath:${SRC}/common/lib/chem:${SRC}/common/lib/dogstats \
        --workdir /tmp --entrypoint sh "${IMAGE}" -c "$1"
}

docker image inspect "${IMAGE}" --format '{{.Id}} {{.Architecture}} {{.Os}} created={{.Created}}' > "${OUT}/image.txt"

run 'pip check; echo "pip check exit=$?"' > "${OUT}/pip-check.txt" 2>&1

run 'pip freeze --all 2>/dev/null | grep -v -E "^(pip|setuptools|wheel)=="' > "${OUT}/freeze.txt"
{
    echo "lines $(wc -l < "${OUT}/freeze.txt") sha256 $(shasum -a 256 "${OUT}/freeze.txt" | cut -d' ' -f1)"
    diff <(sort -f "${OLD_FREEZE}") <(sort -f "${OUT}/freeze.txt")
    echo "diff exit=$?"
} > "${OUT}/freeze-diff-vs-e2.txt"

run 'python -m compileall -q /usr/local/lib/python3.6/site-packages > /tmp/c.log 2>&1; echo "compileall exit=$?"; grep -o "^\*\*\* Error compiling .*" /tmp/c.log | sed "s/^\*\*\* Error compiling .//; s/.\.\.\.$//" | sort' \
    > "${OUT}/site-packages-compile.txt" 2>&1
{
    sed -n '2,$p' "${OUT}/site-packages-compile.txt" | shasum -a 256 | cut -d' ' -f1
} > "${OUT}/site-packages-compile-paths.sha256"

for service in lms cms; do
    echo "### ${service} (plain ${service}.envs.test, source read-only)"
    run "mkdir -p /tmp/test_root/log && DJANGO_SETTINGS_MODULE=${service}.envs.test python -W ignore -c '
import django
django.setup()
from django.apps import apps
print(\"edx_proctoring apps:\", [a.name for a in apps.get_app_configs() if a.label == \"edx_proctoring\"])
import pkg_resources
failures = []
eps = list(pkg_resources.iter_entry_points(\"xmodule.v1\"))
loaded = {}
for ep in eps:
    try:
        loaded[ep.name] = ep.load().__name__
    except Exception as exc:
        failures.append((ep.name, repr(exc)))
print(\"course=%s;hidden=%s\" % (loaded.get(\"course\"), loaded.get(\"hidden\")))
print(\"xmodule.v1 entry points:\", len(eps), \"load failures:\", len(failures), failures)
print(\"openedx.course_tool loaded:\", sorted(\"%s=%s\" % (ep.name, ep.load().__name__) for ep in pkg_resources.iter_entry_points(\"openedx.course_tool\")))
import markdown
from wiki.plugins.links.mdx.urlize import makeExtension
from course_wiki.plugins.markdownedx import mdx_mathjax, mdx_video
html = markdown.markdown(\"see www.example.com and \$x\$\", extensions=[makeExtension(), mdx_mathjax.MathJaxExtension(), mdx_video.VideoExtension()])
print(\"markdown\", markdown.version, \"render ok:\", \"href\" in html)
'; echo exit=\$?"
done > "${OUT}/entry-points.txt" 2>&1
