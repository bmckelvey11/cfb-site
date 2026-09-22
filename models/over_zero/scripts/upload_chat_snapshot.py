"""Prepare dataset configuration and upload a verified snapshot to private Sites R2."""
import argparse
import hashlib
import json
from pathlib import Path
import os
import urllib.request
import zipfile

def upload(archive: Path, output: Path, site: str | None):
    content=archive.read_bytes()
    if len(content)>10*1024*1024: raise ValueError('Snapshot exceeds the hosted inline attachment limit; do not publish this snapshot')
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None: raise ValueError('Snapshot archive failed verification')
        manifest=json.loads(z.read('manifest.json'))
    config={k:manifest[k] for k in ['exported_at','game_seasons']}
    config.update(sha256=hashlib.sha256(content).hexdigest(),tables=[{'table':t['table'],'rows':t['rows']} for t in manifest['tables']])
    output.write_text(json.dumps(config,indent=2),encoding='utf-8')
    print(f'Verified {len(content):,} bytes; runtime dataset configuration: {output}')
    if site:
        if not site.startswith('https://'): raise ValueError('Use the HTTPS Sites origin')
        token=os.environ.get('CHAT_UPLOAD_TOKEN')
        if not token: raise RuntimeError('CHAT_UPLOAD_TOKEN must be set securely in the process environment')
        request=urllib.request.Request(site.rstrip('/')+'/api/private-chat/dataset',method='PUT',data=content,headers={'Authorization':f'Bearer {token}','Content-Type':'application/zip'})
        with urllib.request.urlopen(request,timeout=120) as response: result=json.load(response)
        if result.get('sha256')!=config['sha256']: raise RuntimeError('Hosted checksum did not match')
        print('Hosted snapshot upload verified')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--site',help='Omit to prepare config first; set CHAT_DATASET and deploy before uploading')
    a=p.parse_args()
    upload(a.archive,a.output,a.site)
