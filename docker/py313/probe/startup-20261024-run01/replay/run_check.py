"""Parameterized manage.py entry; no container or evidence-directory fallback."""
import argparse
from core import load_config, manage


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--settings', choices=['startup_lms', 'startup_cms', 'startup_schema', 'exchange_acceptance'])
    parser.add_argument('system', choices=['lms', 'cms'])
    parser.add_argument('label')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    manage(load_config(args.config), args.system, args.label, args.command or ['check'], settings=args.settings)


if __name__ == '__main__':
    main()
