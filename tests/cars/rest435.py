#!/usr/bin/env python3
"""Actual car.c/audio.c: Marge and family idle on L4 K10-9 and L1; genuine OLD must fail."""
import argparse,hashlib,json,math,re,subprocess,wave
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def main():
 p=argparse.ArgumentParser();p.add_argument('--stage',type=Path,required=True);p.add_argument('--out',type=Path,default=ROOT/'build/rest435-gate');a=p.parse_args();out=a.out;out.mkdir(parents=True,exist_ok=True);report=[]
 for variant,flags in [('green',[]),('old',['-DCAR_REST_TYRE_OLD=1']),('mesh-old',['-DCAR_REST_TYRE_OLD=1','-DCAR_WHEEL_RADIUS_MESH_OLD=1']),('drop-old',['-DCAR_REST_TYRE_OLD=1','-DCAR_DROP_RESTITUTION_OLD=1']),('air-old',['-DCAR_REST_TYRE_OLD=1','-DCAR_AIR_PITCH_OLD=1']),('native-old',['-DCAR_REST_TYRE_OLD=1','-DCAR_NATIVE_PHYSICS_OLD=1'])]:
  exe=out/variant;subprocess.run(['cc','-std=c11','-O2','-DAUDIO_HOST','-DSKIN_HOST','-I',str(ROOT/'viewer'),*flags,str(ROOT/'tests/cars/rest435.c'),str(ROOT/'viewer/car.c'),str(ROOT/'viewer/col.c'),'-lm','-o',str(exe)],check=True)
  for label,level,x,z in [('flat','flat',0,0),('L4-K10-9',str(a.stage/'l4/level.shr'),283.333333,283.333333),('L1-road',str(a.stage/'level.shr'),188,279.9)]:
   headings=[0,1.5707963,3.1415926] if variant in ('green','old') else [0]
   for h in headings:
    capture=variant in ('green','old') and label=='L4-K10-9' and h==0
    prefix=out/(variant+'-L4-skid')
    result=subprocess.run([str(exe),level,str(x),str(z),'trace',str(a.stage/'l4/audio')+'/',str(a.stage/'audio')+'/',str(h)]+([str(prefix)] if capture else []),capture_output=True,text=True,check=True)
    if capture:
     for name in ['marge_v','famil_v']:
      raw=Path(str(prefix)+'-'+name+'.s16le')
      with wave.open(str(raw.with_suffix('.wav')),'wb') as wav:wav.setnchannels(2);wav.setsampwidth(2);wav.setframerate(44100);wav.writeframes(raw.read_bytes());(out/f'{variant}-{label}-h{h:.3f}.tsv').write_text(result.stdout)
    rows=[]
    for line in result.stdout.splitlines():
     if not line.startswith('REST '):continue
     fields=line.split();v={k:float(n) for k,n in (s.split('=') for s in fields[2:])};jitter=math.sqrt(sum(v[n]**2 for n in ['dx','dy','dz']))+3*math.sqrt(sum(v[n]**2 for n in ['pitch','roll','yaw']));ok=jitter<.001 and v['skidFrames']==0 and v['audioStarts']==0;row=dict(variant=variant,place=label,heading=h,car=fields[1],jitterMetres=jitter,pass_=ok,**v);rows.append(row);report.append(row);print(variant,label,fields[1],f'jitter={jitter*1000:.4f}mm skidFrames={v["skidFrames"]:.0f} actualSkidStarts={v["audioStarts"]:.0f} '+('GREEN' if ok else 'RED'),flush=True)
    assert len(rows)==2
    if variant=='green':assert all(r['pass_'] and r['pcmPeak']==0 for r in rows),rows
    if variant=='old':
     assert not rows[0]['pass_'],rows
     if h==0:assert rows[0]['audioStarts']>0 and rows[0]['pcmPeak']>0,rows
 out.joinpath('report.json').write_text(json.dumps({'sourceSha256':hashlib.sha256((ROOT/'viewer/car.c').read_bytes()).hexdigest(),'rows':report},indent=2)+'\n')
 print('REST435 GREEN: 30s idle, <1mm, zero actual skid starts; actual OLD RED')
if __name__=='__main__':main()
