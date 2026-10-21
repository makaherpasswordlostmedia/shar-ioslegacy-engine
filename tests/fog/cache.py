#!/usr/bin/env python3
"""Exact cached/OLD horizon on retained frozen frames, using the same framebuffer.

Pass2 is cached and pass4 executes the actual OLD sampler. Both reuse the same
physical buffer after GU state warmup; no crop, pixel tolerance or retouching.
The first two passes are retained, including their pre-existing buffer/UI noise.
"""
import argparse, hashlib, json, re
from pathlib import Path
from PIL import Image, ImageChops

def check(run, scenes):
    text = (run/'smoke.txt').read_text(); bad = []; results = []
    if 'END' not in text.splitlines(): bad.append('missing END')
    for scene in scenes:
        rf = [dict(re.findall(r'(\w+)=(\S+)', l)) for l in text.splitlines() if l.startswith('RF_FRAME sc='+scene+' ')]
        if len(rf) != 5: bad.append(scene+': incomplete retained frame'); continue
        a,b = rf[2],rf[4]
        for key in ('frame','t','hash','eye','dir','fovy','near','mask','cars','park','peds'):
            if a[key] != b[key]: bad.append(scene+': changed '+key)
        level = int(scene.rsplit('l',1)[1]) if scene.startswith('fogfixed_l') else 1
        start = text.index('SCENE '+scene+' '); end = text.find('\nSCENE ', start+1)
        section = text[start:end if end >= 0 else len(text)]
        hz = [dict(re.findall(r'(\w+)=(\S+)', l)) for l in section.splitlines() if l.startswith('HZRF ')]
        if len(hz) != 5 or [int(x['pass']) for x in hz] != list(range(5)):
            bad.append(scene+': missing actual cache calls'); continue
        if any(int(x['level']) != level for x in hz) or len({x['color'] for x in hz}) != 1:
            bad.append(scene+': cached integer RGB differs from actual OLD')
        if int(hz[2]['us']) != 0 or int(hz[4]['us']) <= 0 or int(hz[4]['calc']) != int(hz[2]['calc'])+1:
            bad.append(scene+': cache/OLD not exercised')
        snap = run/f'rfsnap_{scene}.bin'
        if not snap.is_file() or not snap.stat().st_size: bad.append(scene+': raw snapshot missing')
        images = [Image.open(run/f'rf_{scene}_{i}.png').convert('RGB') for i in (2,4)]
        if images[0].size != (480,272) or images[1].size != images[0].size: bad.append(scene+': wrong framebuffer dimensions')
        diff = ImageChops.difference(*images)
        pixels = sum(p != (0,0,0) for p in diff.getdata())
        if pixels: bad.append(f'{scene}: differs in {pixels} pixels')
        results.append(dict(scene=scene,level=level,pixel_differences=pixels,calls=hz,frame=a,snapshot_sha256=hashlib.sha256(snap.read_bytes()).hexdigest() if snap.is_file() else None))
    return bad,results

def main():
    ap=argparse.ArgumentParser();ap.add_argument('run',type=Path);ap.add_argument('--scenes',default=','.join([f'fogfixed_l{n}' for n in range(1,8)]+['fogpalette']));ap.add_argument('--out',type=Path);a=ap.parse_args()
    bad,rows=check(a.run,a.scenes.split(','));out=a.out or a.run;out.mkdir(parents=True,exist_ok=True)
    (out/'cache-proof.json').write_text(json.dumps(dict(ok=not bad,failures=bad,rows=rows),indent=2)+'\n')
    for row in rows: print(row['scene'],'pixels',row['pixel_differences'],'actual OLD us',row['calls'][4]['us'])
    for error in bad: print('FAIL',error)
    print('FAIL' if bad else 'PASS');return bool(bad)

if __name__=='__main__': raise SystemExit(main())
