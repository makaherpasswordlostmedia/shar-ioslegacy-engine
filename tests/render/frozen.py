"""Compare one retained game frame, independently enabling bits 1, 2, 4.
Same-state baseline replay must match exactly; a real camera fault must fail.
The measured emulator render time is not a PSP speed claim.
"""
import argparse,hashlib,json,re,sys
from pathlib import Path
from PIL import Image,ImageChops,ImageDraw
MASKS=[7,6,5,3,7]

def check(run,scenes):
    text=(run/'smoke.txt').read_text(errors='replace');bad=[];rows=[];summary=[]
    if 'END' not in text.split():bad.append('scenario has no END')
    if 'RF_ABORT' in text:bad.append('snapshot failed')
    for l in text.splitlines():
        if l.startswith('RF_FRAME '):rows.append(dict(re.findall(r'(\w+)=(\S+)',l)))
    images=[]
    for sc in scenes:
        r=[x for x in rows if x.get('sc')==sc]
        if len(r)!=5 or [int(x['mask']) for x in r]!=MASKS or [int(x['pass']) for x in r]!=list(range(5)):
            bad.append(sc+': missing or incorrect policy sequence');continue
        for key in ('frame','t','hash','eye','dir','fovy','near'):
            if len({x[key] for x in r})!=1:bad.append(sc+': changed '+key)
        snap=run/f'rfsnap_{sc}.bin'
        meta=[dict(re.findall(r'(\w+)=(\S+)',l)) for l in text.splitlines() if l.startswith('RF_SNAPSHOT ') and 'sc='+sc+' ' in l]
        if len(meta)!=1 or meta[0].get('ok')!='1' or not snap.exists() or snap.stat().st_size!=int(meta[0]['bytes']):
            bad.append(sc+': snapshot missing, incomplete, or failed')
        else:r[0]['snapshot_sha256']=hashlib.sha256(snap.read_bytes()).hexdigest()
        try:
            im=[Image.open(run/f'rf_{sc}_{i}.png').convert('RGB') for i in range(5)]
        except FileNotFoundError:
            bad.append(sc+': missing screenshot');continue
        diffs=[]
        for i in range(1,5):
            if im[i].size!=im[0].size:bad.append(sc+': image size changed');continue
            d=ImageChops.difference(im[0],im[i]);pixels=sum(1 for p in d.getdata() if p!=(0,0,0))
            diffs.append(pixels)
            if pixels:bad.append(f'{sc}: mask {MASKS[i]} differs in {pixels} pixels')
        for key in ('cars','park','peds'):
            if len({x[key] for x in r})!=1:bad.append(sc+': submitted '+key+' changed')
        summary.append(dict(scene=sc,frame=r[0]['frame'],time=r[0]['t'],state=r[0]['hash'],rows=r,pixel_differences=diffs))
        images.append((sc,im))
    # A control must actually exercise each switch in at least one scene.
    for i,key in ((1,'gglist'),(2,'dlskip'),(3,'spcut')):
        if not any(int(s['rows'][i][key])>0 for s in summary):bad.append('not exercised: '+key)
    return bad,summary,images

def main():
    a=argparse.ArgumentParser();a.add_argument('run',type=Path);a.add_argument('--scenes',default='rfspawn,rfnear,rfprops');a.add_argument('--out',type=Path);x=a.parse_args()
    bad,summary,images=check(x.run,x.scenes.split(','));out=x.out or x.run;out.mkdir(parents=True,exist_ok=True)
    (out/'frozen-results.json').write_text(json.dumps(dict(run=str(x.run),status='FAIL' if bad else 'PASS',failures=bad,scenes=summary,PSP='speed and cache untested'),indent=2)+'\n')
    if images:
        w,h=images[0][1][0].size; sheet=Image.new('RGB',(w*5,(h+22)*len(images)), '#f6f5f2');draw=ImageDraw.Draw(sheet)
        for y,(sc,ims) in enumerate(images):
            for i,im in enumerate(ims):sheet.paste(im,(i*w,y*(h+22)+22));draw.text((i*w+5,y*(h+22)+5),sc+' mask '+str(MASKS[i]),fill='#1a1a1a')
        sheet.save(out/'contact.png')
    for s in summary:print(s['scene'], 'pixel diffs',s['pixel_differences'],'render us',[r['render_us'] for r in s['rows']], 'binds',[r['binds'] for r in s['rows']])
    for b in bad:print('FAIL',b)
    print('FAIL' if bad else 'PASS');return bool(bad)
if __name__=='__main__':sys.exit(main())
