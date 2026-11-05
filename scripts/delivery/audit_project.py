"""Inventory and static packaging audit of the released research project.

Reads bytes and schemas only. Does not run tests, execute model code or call APIs.
Credential matches are reported by path/count, never by secret value.
"""
from pathlib import Path
import ast,csv,gzip,hashlib,io,json,re,zipfile
from datetime import datetime, timezone
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'project.json').is_file())
SKIP={'build','submission','runtime','dist','__pycache__','node_modules','artifacts','.git','.impeccable'}
KEY=re.compile(rb'(?:sk-[A-Za-z0-9_-]{24,}|gh[pousr]_[A-Za-z0-9]{30,}|AKIA[A-Z0-9]{16})')
ALIAS=re.compile(r'(?i)(?<![a-z])(?:zzy|fwl|zyt)(?![a-z])')
TEXT={'.py','.js','.mjs','.json','.md','.txt','.csv','.tsv','.html','.css','.sh','.command','.srt','.svg','.prompt'}
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def stream_scan(f):
 found=False;tail=b''
 for b in iter(lambda:f.read(1048576),b''):
  if KEY.search(tail+b):found=True
  tail=b[-256:]
 return found

def main():
 files=[p for p in ROOT.rglob('*') if p.is_file() and not any(x in SKIP for x in p.relative_to(ROOT).parts)]
 bad_names=[];secrets=[];syntax=[];inventory=[]
 for i,p in enumerate(sorted(files),1):
  rel=str(p.relative_to(ROOT))
  if ALIAS.search(rel):bad_names.append(rel)
  if p.suffix=='.py' and 'vendor' not in p.parts:
   try:ast.parse(p.read_text())
   except SyntaxError:syntax.append(rel)
  if 'vendor' not in p.parts and 'logos' not in p.parts:
   if p.suffix=='.gz':
    with gzip.open(p,'rb') as f:
     if stream_scan(f):secrets.append(rel)
   elif p.suffix=='.zip':
    with zipfile.ZipFile(p) as z:
     for name in z.namelist():
      if Path(name).suffix in TEXT:
       with z.open(name) as f:
        if stream_scan(f):secrets.append(rel+'::'+name)
   elif p.suffix in TEXT or p.name=='.env.example':
    with p.open('rb') as f:
     if stream_scan(f):secrets.append(rel)
  inventory.append({'path':rel,'bytes':p.stat().st_size,'sha256':sha(p)})
  if i%200==0:print('indexed',i,flush=True)
 raw=json.loads((ROOT/'data/inventory/raw_files.json').read_text())['files'];bad_raw=[r['path'] for r in raw if not (ROOT/r['path']).exists() or sha(ROOT/r['path'])!=r['sha256']]
 quality=json.loads((ROOT/'data/quality/quality_report.json').read_text());total=quality['total_physical_responses']
 report={'schema':'research-project-release-audit-v1','physical_responses':total,'response_counts':quality['counts'],'raw_artifacts':len(raw),'raw_hash_mismatches':bad_raw,'author_abbreviation_paths':bad_names,'credential_pattern_files':secrets,'python_syntax_errors':syntax,'model_api_requests':0,'generated_code_executed':False,'scope':'File byte inventory, static source parsing, source hashes, recorded schema/row counts. Not unit tests or browser visual verification.'}
 out=ROOT/'data/quality/release_audit.json';out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 # Exclude self-hashing inventories to avoid a circular digest.
 inventory=[v for v in inventory if v['path'] not in ['data/inventory/current_files.json','data/quality/release_audit.json']]
 inventory.append({'path':'data/quality/release_audit.json','bytes':out.stat().st_size,'sha256':sha(out)})
 (ROOT/'data/inventory/current_files.json').write_text(json.dumps({'schema_version':1,'date':datetime.now(timezone.utc).date().isoformat(),'files':inventory},ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:v for k,v in report.items() if k!='scope'},ensure_ascii=False))
 if bad_names or secrets or syntax or bad_raw or total!=248586:raise SystemExit('Packaging audit has unresolved findings; see data/quality/release_audit.json')
if __name__=='__main__':main()
