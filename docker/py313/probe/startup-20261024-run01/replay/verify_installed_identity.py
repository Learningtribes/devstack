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
    build=Path('/runtime/rebuild-sources-20261025-run25' if name in REGISTRY['prepared'] else '/runtime/verified-runtime-additions-v1')/name
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
wheel=next(Path('/runtime/input-wheels').glob('djangosaml2idp-*.whl'))
dist=metadata.distribution('djangosaml2idp')
with zipfile.ZipFile(wheel) as z:
    files={p:hashlib.sha256(z.read(p)).hexdigest() for p in z.namelist() if p.startswith('djangosaml2idp/') and not p.endswith('/')}
    for p,h in files.items():
        assert digest(dist.locate_file(p))==h
        assert REGISTRY['packages']['djangosaml2idp-lt']['files'][p]['sha256']==h
report['saml_wheel']={'path':str(wheel),'sha256':digest(wheel),'source_wheel_installed_equal':files}
Path('/runtime/installed-input-identity.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
print('PASS all 20 frozen local package build trees and installed source files; SAML source/wheel/site-packages equality')
print('SAML wheel SHA256',digest(wheel),'matched local files',sum(len(v['matched_installed_files']) for v in report['packages'].values()))
