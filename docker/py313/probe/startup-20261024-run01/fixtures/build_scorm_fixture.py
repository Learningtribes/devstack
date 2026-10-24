"""Build a real minimal SCORM 1.2 SCO for local upload/runtime acceptance."""
from pathlib import Path
from zipfile import ZipFile
root = Path(__file__).parent
manifest = '''<?xml version="1.0" encoding="UTF-8"?>
<manifest identifier="PY313-SCORM-ACCEPTANCE" version="1.0"
 xmlns="http://www.imsproject.org/xsd/imscp_rootv1p1p2"
 xmlns:adlcp="http://www.adlnet.org/xsd/adlcp_rootv1p2">
 <metadata><schema>ADL SCORM</schema><schemaversion>1.2</schemaversion></metadata>
 <organizations default="ORG"><organization identifier="ORG"><title>Python 3.13 SCORM</title>
 <item identifier="ITEM" identifierref="SCO"><title>Local SCORM acceptance</title></item>
 </organization></organizations><resources>
 <resource identifier="SCO" type="webcontent" adlcp:scormtype="sco" href="index.html"><file href="index.html"/></resource>
 </resources></manifest>'''
html = '''<!doctype html><html lang="en"><meta charset="utf-8"><title>PY313 SCORM</title>
<h1>Python 3.13 SCORM upload acceptance</h1><p>Uploaded ZIP content from shared local storage.</p>
<p id="result">SCORM API pending</p><button id="complete">Complete activity</button>
<script>
function findAPI(w) { for(let i=0;i<10;i++){if(w.API)return w.API;if(w.parent===w)break;w=w.parent;}return null; }
let api=findAPI(window);let ok=api && api.LMSInitialize('');
document.getElementById('result').textContent=ok ? 'SCORM API initialized' : 'SCORM API unavailable';
document.getElementById('complete').onclick=function(){if(api){api.LMSSetValue('cmi.core.lesson_status','completed');api.LMSCommit('');document.getElementById('result').textContent='SCORM completion committed';}};
</script></html>'''
with ZipFile(root/'py313-scorm12.zip','w') as archive:
    archive.writestr('imsmanifest.xml',manifest)
    archive.writestr('index.html',html)
print('Created SCORM 1.2 ZIP with manifest and functional SCO')
