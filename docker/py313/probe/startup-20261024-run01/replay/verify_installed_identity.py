"""Connect frozen sources, writable builds, wheel and installed package bytes."""
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import sys
import zipfile
sys.path.insert(0,'/startup')
from local_input_contract import REGISTRY, verify

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
report={'packages':{},'distributions':[]}
for d in metadata.distributions():
    direct=json.loads(d.read_text('direct_url.json') or '{}')
    report['distributions'].append({'name':d.metadata['Name'],'version':d.version,'direct_url':direct})
    name=Path(direct.get('url','')).name
    if d.metadata['Name']=='djangosaml2idp':name='djangosaml2idp-lt'
    if name not in REGISTRY['packages']:continue
    record=REGISTRY['packages'][name]
    expected=record['files']
    build=Path('/runtime/delivery-sources')/name
    verify(name,build)
    matched={}; unmatched=[]
    for installed in d.files:
        relative=str(installed)
        if '.dist-info/' in relative or '__pycache__' in relative or relative.startswith('../'):continue
        candidates=[p for p in expected if p==relative or p=='src/'+relative]
        if candidates and 'sha256' in expected[candidates[0]]:
            actual=digest(d.locate_file(installed));assert actual==expected[candidates[0]]['sha256'],(name,relative)
            matched[relative]=actual
        elif relative.endswith('.py'):unmatched.append(relative)
    assert matched and not unmatched,(name,unmatched)
    report['packages'][name]={'source':record['source'],'build':str(build),'distribution':d.metadata['Name'],'version':d.version,'matched_installed_files':matched,'source_only_files':sorted(p for p in expected if p not in matched and p.removeprefix('src/') not in matched),'generated':json.loads((build.parent/(name+'.generated.json')).read_text())}
assert set(report['packages'])==set(REGISTRY['packages']),set(REGISTRY['packages'])-set(report['packages'])
Path('/runtime/installed-input-identity.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
print('PASS all 20 registered build trees and installed source bytes; complete distribution metadata recorded')
