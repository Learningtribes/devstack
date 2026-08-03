#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Render temporary setuptools metadata for a read-only Platform checkout."""

from __future__ import absolute_import, division, print_function, unicode_literals

import ast
import io
import os
import re
import shutil
import sys


class MetadataError(Exception):
    pass


def _node_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _node_name(node.value)
        return "%s.%s" % (parent, node.attr) if parent else node.attr
    return None


def _evaluate(node, assignments):
    """Evaluate only literals and named literal lists used by setup.py."""
    if isinstance(node, ast.Str):
        return node.s
    if isinstance(node, ast.Num):
        return node.n
    if isinstance(node, ast.List):
        return [_evaluate(item, assignments) for item in node.elts]
    if isinstance(node, ast.Tuple):
        return tuple(_evaluate(item, assignments) for item in node.elts)
    if isinstance(node, ast.Dict):
        return dict(
            (_evaluate(key, assignments), _evaluate(value, assignments))
            for key, value in zip(node.keys, node.values)
        )
    if isinstance(node, ast.Name) and node.id in assignments:
        return _evaluate(assignments[node.id], assignments)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _evaluate(node.left, assignments) + _evaluate(node.right, assignments)
    raise MetadataError("unsupported setup.py expression: %s" % ast.dump(node))


def _parse_setup(path):
    # ast.parse in Python 2 requires the original bytes when the source has an
    # encoding declaration; parsing decoded Unicode raises a false syntax
    # error before setup.py can be inspected.
    with io.open(path, "rb") as source_file:
        tree = ast.parse(source_file.read(), filename=path)

    assignments = {}
    setup_call = None
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assignments[target.id] = node.value
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            if _node_name(node.value.func) == "setup":
                setup_call = node.value

    if setup_call is None:
        raise MetadataError("no setup(...) call in %s" % path)

    values = {}
    for keyword in setup_call.keywords:
        if keyword.arg in ("name", "version", "entry_points", "install_requires"):
            values[keyword.arg] = _evaluate(keyword.value, assignments)

    missing = set(("name", "version")) - set(values)
    if missing:
        raise MetadataError("missing setup values in %s: %s" % (path, sorted(missing)))
    return values


def _safe_name(name):
    # Egg-info directory names use setuptools' filename form. Leaving a dash
    # here makes pkg_resources parse ``xblock-discussion-0.1.egg-info`` as a
    # distribution named ``xblock`` and shadows the real XBlock package.
    return re.sub(r"[^A-Za-z0-9.]+", "_", name)


def _write(path, contents):
    with io.open(path, "w", encoding="utf-8", newline="\n") as output_file:
        output_file.write(contents)


def _write_distribution(metadata_root, setup_values):
    name = setup_values["name"]
    version = setup_values["version"]
    distribution_dir = os.path.join(
        metadata_root, "%s-%s.egg-info" % (_safe_name(name), version)
    )
    if os.path.isdir(distribution_dir):
        shutil.rmtree(distribution_dir)
    os.makedirs(distribution_dir)

    _write(
        os.path.join(distribution_dir, "PKG-INFO"),
        "Metadata-Version: 1.0\nName: %s\nVersion: %s\n" % (name, version),
    )

    entry_points = setup_values.get("entry_points", {}) or {}
    entry_point_text = []
    for group in sorted(entry_points):
        entry_point_text.append("[%s]" % group)
        for entry_point in sorted(entry_points[group]):
            entry_point_text.append(entry_point)
        entry_point_text.append("")
    _write(os.path.join(distribution_dir, "entry_points.txt"), "\n".join(entry_point_text))

    requirements = setup_values.get("install_requires", []) or []
    _write(os.path.join(distribution_dir, "requires.txt"), "\n".join(requirements))
    _write(os.path.join(distribution_dir, "dependency_links.txt"), "")

    return distribution_dir


def main(argv):
    if len(argv) < 3:
        raise MetadataError("usage: py27_source_metadata.py OUTPUT_ROOT SETUP.PY [SETUP.PY ...]")
    metadata_root = os.path.abspath(argv[1])
    if os.path.exists(metadata_root):
        for entry in os.listdir(metadata_root):
            path = os.path.join(metadata_root, entry)
            if os.path.isdir(path) and entry.endswith(".egg-info"):
                shutil.rmtree(path)
    else:
        os.makedirs(metadata_root)

    rendered = [_write_distribution(metadata_root, _parse_setup(path)) for path in argv[2:]]
    for path in rendered:
        print("rendered source metadata: %s" % path)


if __name__ == "__main__":
    try:
        main(sys.argv)
    except (IOError, OSError, SyntaxError, MetadataError) as error:
        print("source metadata generation failed: %s" % error, file=sys.stderr)
        sys.exit(1)
