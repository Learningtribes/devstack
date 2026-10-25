"""Stage only frozen source inputs; preserve old opaque and SAML directories."""
import json
from pathlib import Path
from local_input_contract import REGISTRY, stage, verify

OUTPUT_ROOT = Path('/runtime/rebuild-sources-20261025-run25')
# Check every required input before creating any build state.
for name in REGISTRY['packages']:
    verify(name)
for name in REGISTRY['prepared']:
    stage(name, OUTPUT_ROOT / name)
manifest = {name: REGISTRY['packages'][name] for name in REGISTRY['prepared']}
(OUTPUT_ROOT.parent / (OUTPUT_ROOT.name + '.manifest.json')).write_text(
    json.dumps(manifest, indent=2, sort_keys=True) + '\n')
print('PASS frozen source staging:', len(manifest), 'packages')
