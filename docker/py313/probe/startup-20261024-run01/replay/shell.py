"""Interactive shell in the run-owned runtime; no container or evidence-directory fallback.

Not an evidence-capturing command: a terminal session has no reproducible output,
so there is no label and nothing is written to the evidence directory.
"""
import argparse
import os
from pathlib import Path

from core import docker_exec, environment, load_config

RUNTIME_PATH = '/runtime/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'


def command(config, system):
    return docker_exec(config, 'env', 'PATH=' + RUNTIME_PATH, 'bash',
                       settings='startup_' + system, interactive=True)


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('system', choices=['lms', 'cms'])
    args = parser.parse_args()
    config = load_config(args.config)
    argv = command(config, args.system)
    os.execvpe(argv[0], argv, environment(config))


if __name__ == '__main__':
    main()
