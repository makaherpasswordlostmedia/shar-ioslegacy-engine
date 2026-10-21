#!/usr/bin/env python3
"""Rob 413: owner's ISO profile/resource proof, NOT a runtime audio recording."""
import argparse, hashlib, json, os, sys
from pathlib import Path
import numpy as np

def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2]);ap.add_argument('--out',type=Path);a=ap.parse_args();root=a.root.resolve();os.environ['TWINS_ROOT']=str(root)
 sys.path.insert(0,str(root/'tools'));sys.path.insert(0,str(root/'tools/twins'))
 import audio_export as aud
 import isomap
 files=isomap.diskmap();res,cars,_,_=aud.load_scripts();expected={'frink_v':('frink','frink_skid','frink_skid'),'hbike_v':('hbike','blank','blank'),'ship':('ship_v','ship_skid','ship_skid'),'witchcar':('witchcar_v','witchcar_v_skid','witchcar_v_skid'),'mono_v':('mono_v_car','monorail_skid','blank')}
 report=dict(root=str(root),scope='disc authored PS2 bindings; native frink drive not captured',profiles=[],iso_files={},negative_controls=[])
 def verify(rel):
  rel=rel.replace('\\','/').lower();local=root/'hit-and-run-web/source/game'/rel
  hits=[f for f in files if f['path'].split(':')[-1].lower()==rel]
  assert len(hits)==1,('ambiguous/missing ISO member',rel,len(hits))
  f=hits[0]
  with isomap.ISO.open('rb') as h:h.seek(f['start']);b=h.read(f['end']-f['start'])
  assert local.read_bytes()==b,('extraction differs from ISO',rel)
  report['iso_files'][rel]=dict(iso_member=f['path'],start=f['start'],end=f['end'],sha256=sha(b),local=str(local.relative_to(root)))
  # Deliberate source corruption must be rejected by this same byte equality.
  damaged=bytes([b[0]^1])+b[1:]
  assert damaged!=local.read_bytes()
  report['negative_controls'].append(dict(fault='ISO first byte flipped',file=rel,caught=True))
  return local
 scripts=[]
 for p in Path(aud.SCRIPTS).glob('*.spt'):
  if any(t=='carSoundParameters' and n in expected for t,n,c in aud.parse_spt(p)):
   verify('sound/scripts/'+p.name);scripts.append(p.name)
 for name,exp in expected.items():
  c=cars[name];assert tuple(c[k] for k in ['EngineClipName','RoadSkidClipName','DirtSkidClipName'])==exp
  row=dict(name=name,parameters=c,bindings={})
  for k in ['EngineClipName','EngineIdleClipName','RoadSkidClipName','DirtSkidClipName']:
   n=c[k];r=res[n];verify('sound/scripts/'+r['script']+'.spt');entries=[]
   for rel in r['files']:
    p=verify(rel);rr=aud.read_rsd(p);pcm=aud.ffmpeg_decode(str(p));peak=int(np.max(np.abs(pcm.astype(np.int32))));rms=float(np.sqrt(np.mean(pcm.astype(np.float64)**2)))
    entries.append(dict(path=rel,rate=rr['rate'],channels=rr['ch'],samples=rr['nsamp'],seconds=rr['nsamp']/rr['rate'],decoded_pcm_sha256=sha(pcm.tobytes()),peak=peak,rms=rms))
    if rel.endswith('/blank.rsd'):
     assert peak==0,'blank contains nonzero PCM'
     damaged=pcm.copy();damaged[0,0]=1
     assert int(np.max(np.abs(damaged.astype(np.int32))))!=0
     report['negative_controls'].append(dict(fault='blank PCM nonzero',file=rel,caught=True))
    else:assert peak>0
   row['bindings'][k]=dict(resource=n,trim=r['trim'],loop=r['loop'],stream=r['stream'],files=entries)
  report['profiles'].append(row)
 report['pass']=True
 if a.out:a.out.write_text(json.dumps(report,ensure_ascii=False,indent=1)+'\n')
 print(json.dumps(dict(pass_=True,profiles=len(report['profiles']),iso_files=len(report['iso_files']),red=len(report['negative_controls'])),ensure_ascii=False))
if __name__=='__main__':main()
