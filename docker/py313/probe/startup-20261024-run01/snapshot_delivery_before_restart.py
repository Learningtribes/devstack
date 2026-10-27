"""Capture a synthetic delivery-state baseline before the isolated restart."""
from pathlib import Path
source = Path('/startup/test_delivery_persistence_runtime.py')
exec(compile(source.read_text(), str(source), 'exec'), {'PHASE': 'before'})
