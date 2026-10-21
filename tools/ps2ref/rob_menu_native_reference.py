#!/usr/bin/env python3
"""Read-only GS pixel reference for Rob 409/412; requires Pillow/numpy.
Runs finite negative controls on measured data, never changes original captures.
"""
import argparse, hashlib, json
from pathlib import Path
import numpy as np
from PIL import Image

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def measure(p, roi, threshold=180):
    a=np.asarray(Image.open(p).convert('RGB')); x0,y0,x1,y1=roi
    b=a[y0:y1,x0:x1]; m=(b[:,:,0]>threshold)&(b[:,:,1]>threshold)&(b[:,:,2]<80)&(np.abs(b[:,:,0].astype(int)-b[:,:,1].astype(int))<30)&(b[:,:,1].astype(int)-b[:,:,2].astype(int)>100)
    y,x=np.where(m)
    if len(x)==0: raise ValueError('caption absent in ROI')
    colors,counts=np.unique(b[m],axis=0,return_counts=True)
    return dict(frame=int(p.stem[1:]),width=int(x.max()-x.min()+1),height=int(y.max()-y.min()+1),bbox=[int(x.min()+x0),int(y.min()+y0),int(x.max()+x0),int(y.max()+y0)],pixels=int(m.sum()),mode_rgb=colors[counts.argmax()].tolist(),sha256=sha(p),path=str(p),size=[a.shape[1],a.shape[0]])

def series(root, run, lo, hi, roi, threshold=180):
    return [measure(p,roi,threshold) for p in sorted((root/'build/twins/o4'/run/'png').glob('f*.png')) if lo<=int(p.stem[1:])<=hi]

def metrics(rows):
    f=np.array([r['frame'] for r in rows]); w=np.array([r['width'] for r in rows]); h=np.array([r['height'] for r in rows]); d=np.unique(np.diff(f))
    if len(d)!=1: raise ValueError('gap/uneven native frames')
    step=int(d[0]); scores={}
    # Search first fundamental, including possible harmonics; do not call 60 a 30-frame period.
    for lag in range(2,min(len(w)//2,32)):
        scores[lag*step]=float(np.mean((w[lag:]-w[:-lag])**2))
    best=min(scores,key=scores.get)
    near=[k for k,v in scores.items() if v<=scores[best]+1.0]
    fundamental=min(near)
    return dict(samples=len(rows),frame_range=[int(f[0]),int(f[-1])],step=step,width_minmax=[int(w.min()),int(w.max())],height_minmax=[int(h.min()),int(h.max())],min_max_ratio=float(w.min()/w.max()),fundamental_frames=fundamental,period_s=fundamental/50,lag_mse=scores,center_x_minmax=[min((r['bbox'][0]+r['bbox'][2])/2 for r in rows),max((r['bbox'][0]+r['bbox'][2])/2 for r in rows)],all_present=bool(np.all(w>0)))

def accept(rows, expected_period=30):
    m=metrics(rows)
    assert len(rows)>=50 and m['all_present'], 'missing caption/insufficient samples'
    assert m['fundamental_frames']==expected_period, 'wrong fundamental period'
    assert .81<m['min_max_ratio']<.84, 'wrong pulse amplitude'
    assert m['center_x_minmax'][1]-m['center_x_minmax'][0]<=1, 'caption center drifts'
    return m

def outline(root):
    result={}
    for run,roi,lo,hi in [('ps2_rob412_new_load',[310,280,410,345],2,150),('ps2_rob412_new_sw_outline_check',[310,280,410,345],2,148),('ps2_rob412_resume_load',[415,260,615,420],2,150),('ps2_rob412_new_load',[440,210,580,263],200,318)]:
        vals=[]
        for p in sorted((root/'build/twins/o4'/run/'png').glob('f*.png')):
            f=int(p.stem[1:])
            if not lo<=f<=hi:continue
            x0,y0,x1,y1=roi;a=np.asarray(Image.open(p).convert('RGB'))[y0:y1,x0:x1].astype(int)
            mask=(a[:,:,0]>180)&(a[:,:,1]>180)&(a[:,:,2]<120)&(np.abs(a[:,:,0]-a[:,:,1])<30)&(a[:,:,1]-a[:,:,2]>70)
            vals.append([f,int(mask.sum())])
        peaks=[vals[i] for i in range(1,len(vals)-1) if vals[i][1]>vals[i-1][1] and vals[i][1]>=vals[i+1][1] and vals[i][1]>.85*max(v[1] for v in vals)]
        result[run+'_'+str(lo)]=dict(roi=roi,values=vals,peaks=peaks)
    assert [v[0] for v in result['ps2_rob412_new_load_2']['peaks']]==[v[0] for v in result['ps2_rob412_new_sw_outline_check_2']['peaks']], 'GS renderer changes outline peak frames'
    return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2]);ap.add_argument('--out',type=Path);args=ap.parse_args();root=args.root.resolve()
    specs=[('New Game','ps2_rob412_new_load',20,150),('Load Game (new deck)','ps2_rob412_new_load',200,320),('Resume Game','ps2_rob412_resume_load',20,150),('Load Game (resume deck)','ps2_rob412_resume_load',200,320)]
    result=dict(root=str(root),menu=[],title={},red_controls=[])
    for label,run,lo,hi in specs:
        rows=series(root,run,lo,hi,[185,55,500,105]); m=accept(rows)
        # Different yellow thresholds must preserve the conclusion.
        alternative=accept(series(root,run,lo,hi,[185,55,500,105],150))
        report=json.loads((root/'build/twins/o4'/run/'report.json').read_text());assert report['ok'] and report['personal_profile_unchanged'] and not report['focus_violations']
        r=dict(label=label,run=run,roi=[185,55,500,105],threshold=180,metrics=m,threshold150_metrics=alternative,rows=rows,report=report)
        result['menu'].append(r)
        for name,broken,period in [('frozen width',[dict(q,width=rows[0]['width']) for q in rows],30),('missing frame',rows[:20]+rows[21:],30),('wrong period',rows,26)]:
            try: accept(broken,period)
            except (AssertionError,ValueError) as e:result['red_controls'].append(dict(label=label,fault=name,caught=str(e)))
            else:raise AssertionError('negative control survived: '+name)
        try:series(root,run,lo,hi,[0,0,20,20])
        except ValueError as e:result['red_controls'].append(dict(label=label,fault='wrong ROI',caught=str(e)))
        else:raise AssertionError('wrong ROI survived')
    rows=series(root,'ps2_v101_title_arrival',200,1200,[80,400,560,475],100)
    result['title']=dict(roi=[80,400,560,475],threshold=100,metrics=accept(rows),rows=rows)
    try:accept(rows[:20]+rows[21:])
    except ValueError as e:result['red_controls'].append(dict(label='Press Start',fault='blank/missing frame',caught=str(e)))
    else:raise AssertionError('missing title frame survived')
    for q in result['menu']:
        for row in q['rows']:row['path']=str(Path(row['path']).relative_to(root))
    for row in result['title']['rows']:row['path']=str(Path(row['path']).relative_to(root))
    result['outline']=outline(root)
    result['pass']=True
    if args.out:args.out.write_text(json.dumps(result,ensure_ascii=False,indent=1)+'\n')
    print(json.dumps(dict(pass_=True,menu=[dict(label=q['label'],metrics={k:v for k,v in q['metrics'].items() if k!='lag_mse'}) for q in result['menu']],title={k:v for k,v in result['title']['metrics'].items() if k!='lag_mse'},red_caught=len(result['red_controls'])),ensure_ascii=False))
if __name__=='__main__':main()
