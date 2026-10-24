"""Compatibility entry point; host-specific Site setup uses natural keys."""
from pathlib import Path

seed_script = Path('/startup/seed_local_host_sites.py')
exec(compile(seed_script.read_text(), str(seed_script), 'exec'))
