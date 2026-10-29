#!/usr/bin/env python3
"""Native race runtime and baked UIP1 glyph; old runtime and old export must fail."""
import argparse, json, os, struct, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def glyph(path):
    b=Path(path).read_bytes(); h=struct.unpack_from('<32I',b)
    assert b[:4]==b'UIP1' and h[1]==1 and h[13]+h[12]*3072<=len(b)
    items=[h[5]+64*i for i in range(h[4]) if b[h[5]+64*i]==4 and b[h[5]+64*i+1]==0 and b[h[5]+64*i+3]==8]
    assert len(items)==1, 'real HUD POSITION numeric field missing'
    sf=b[items[0]+26]; assert sf<h[12]
    ti,u,v,w,hh,left,advance,flags=struct.unpack_from('<HHHBBbBH',b,h[13]+3072*sf+12*ord('?'))
    return bool(flags&1 and ti<h[2] and w and hh and advance)
def run(binary, source, stage):
    out=[]
    for n in range(1,8):
        d=stage if n==1 else stage/f'l{n}'
        env=dict(os.environ,BW_TRAFFIC=str(d/'traffic.shr'),BW_MSNCARS=str(source/f'msncars-l{n}.shr'))
        p=subprocess.run([str(binary),str(d/'level.shr'),str(source/'homer.shr'),str(d/f'level0{n}.msn')],env=env,text=True,capture_output=True)
        row=dict(level=n,rc=p.returncode,out=p.stdout.strip(),fixture=p.stderr.strip()); out.append(row)
        print(row['out'],row['fixture'])
    return out
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--source',type=Path,required=True);a.add_argument('--stage',type=Path,default=ROOT/'build/ship_stage');a.add_argument('--out',type=Path,default=ROOT/'build/race-unknown');v=a.parse_args()
    rows=run(v.out/'host',v.source.resolve(),v.stage.resolve());red=run(v.out/'old',v.source.resolve(),v.stage.resolve())
    ng=glyph(v.out/'ui.shr');og=glyph(v.out/'ui-old.shr')
    ok=all(x['rc']==0 for x in rows) and all(x['rc']==1 for x in red) and ng and not og
    (v.out/'report.json').write_text(json.dumps(dict(new=rows,old=red,newGlyph=ng,oldGlyph=og,passGate=ok),ensure_ascii=False,indent=2)+'\n')
    print(f'GLYPH new={ng} old={og}'); print('PASS' if ok else 'FAIL');raise SystemExit(0 if ok else 1)
