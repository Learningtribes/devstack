"""Ensure the local devstack superuser (default edx / edx@example.com / edx) exists in the run.

LOCAL DEVSTACK ONLY. Override with PY313_DEV_SUPERUSER_USERNAME / _EMAIL / _PASSWORD; they reach
the container by name through the environment, never on a command line.
"""
import argparse
from pathlib import Path

from core import load_config, ownership, shell

SCRIPT = '/startup/replay/superuser_runtime.py'


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--label', default='ensure-superuser', help='unique evidence label')
    args = parser.parse_args()
    config = load_config(args.config)
    ownership(config)
    shell(config, 'lms', args.label, SCRIPT)


if __name__ == '__main__':
    main()
