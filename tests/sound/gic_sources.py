#!/usr/bin/env python3
"""Disc source audit, not an entry-event absence claim. --old drops one actual GIC record."""
from pathlib import Path
import struct,json,hashlib,re,sys
old='--old' in sys.argv
root=Path(__file__).resolve().parents[2];disc=root/'hit-and-run-web/source/disc';rows=[]
for p in sorted(disc.glob('DIALOG*.RCF')):
 with p.open('rb') as f:
  header=f.read(0x28);assert header.startswith(b'RADCORE CEMENT LIBRARY\0');table=struct.unpack_from('<I',header,0x24)[0];f.seek(table);count,names=struct.unpack('<II',f.read(8));f.seek(table+16);entries=sorted([struct.unpack('<III',f.read(12)) for i in range(count)],key=lambda v:v[1]);f.seek(names+8);nr=[]
  for crc,offset,size in entries:
   ln=struct.unpack('<I',f.read(4))[0];nm=f.read(ln).rstrip(b'\0').decode('ascii').replace('\\','/').lower();f.read(4);nr.append(dict(path=nm,offset=offset,bytes=size))
  if old and p.name=='DIALOG.RCF': nr=[x for x in nr if x['path']!='homer/w_gic_hom_01.rsd']
  heroes={h:[x for x in nr if x['path'].startswith(h+'/')] for h in ['homer','bart','lisa','marge','apu']}
  alternatives=[x for x in nr if x['path'].startswith('apu/') and re.search(r'/(?:[dw]_door|w_activate|w_askride|w_ridereply)_',x['path'])]
  rows.append(dict(archive=p.name,entries=count,heroes={h:dict(total=len(v),gic=[x for x in v if '/w_gic_' in x['path']],alternatives=alternatives if h=='apu' else []) for h,v in heroes.items()},generic_gic=[x for x in nr if 'generic' in x['path'] and 'gic' in x['path']]))
script=root/'hit-and-run-web/source/game/sound/scripts/dialog.spt';s=script.read_text(errors='replace')
result=dict(archives=rows,dialog_sha256=hashlib.sha256(script.read_bytes()).hexdigest(),script_gic=re.findall(r'create\s+daSoundResourceData\s+named\s+(W_GIC_\S+)',s,re.I),limitation='Only GIC family absence proved. Apu entry event NOT identified; waived by Rob 2026-10-09 (V93), absence of voice NOT proved.')
out=root/'build/gic-audit';out.mkdir(parents=True,exist_ok=True)
(out/('archive-inventory-old.json' if old else 'archive-inventory.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
for r in rows:print(r['archive'],r['entries'],[(h,v['total'],len(v['gic'])) for h,v in r['heroes'].items()],'apu alternatives',len(r['heroes']['apu']['alternatives']),'generic GIC',len(r['generic_gic']))
assert len(rows)==4 and all(len(r['heroes']['apu']['gic'])==0 for r in rows)
print('PASS 4 archives: exact entries audited; Apu candidates retained, no voice-absence claim')

# Cross-check against independent script references and extracted raw payloads.
refs=re.findall(r'create\s+daSoundResourceData\s+named\s+(W_GIC_\S+)\s*\{(.*?)\}',s,re.I|re.S)
english=next(r for r in rows if r['archive']=='DIALOG.RCF')
lookup={x['path']:x for v in english['heroes'].values() for x in v['gic']}
expected=[]
for name,body in refs:
 files=re.findall(r'AddFilename\s*\(\s*"([^"]+)"',body)
 for fn in files:
  rel=fn.replace('\\','/').lower();expected.append(rel)
  assert rel in lookup,('missing archived GIC',rel)
  record=lookup[rel]
  with (disc/'DIALOG.RCF').open('rb') as f:f.seek(record['offset']);raw=f.read(record['bytes'])
  extracted=(root/'hit-and-run-web/source/game'/rel).read_bytes()
  assert raw==extracted,('extracted payload differs',rel)
  record['payload_sha256']=hashlib.sha256(raw).hexdigest()
assert len(expected)==len(set(expected)) and set(expected)==set(lookup),'script/archive discrepancy'
(out/('archive-inventory-old.json' if old else 'archive-inventory.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print('PASS raw RSD/script cross-check',len(expected),'records; Apu V93 waived by Rob 2026-10-09')
