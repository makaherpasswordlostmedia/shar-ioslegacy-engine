#!/usr/bin/env python3
"""N2.4 local video/audio measurement. No network or model calls.
Produces frame PTS, template position/scale/confidence, visual-cut candidates and audio onsets.
These are observations, not inferred mission/easing labels. Unknown remains unknown.
"""
import argparse
import csv
import hashlib
import json
import math
import html
import os
from pathlib import Path
import struct
import subprocess
import sys
import time
import numpy as np
from PIL import Image
from ui_templates import extract

ROOT=Path(__file__).resolve().parents[2]


def probe(path):
    r=subprocess.run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)],capture_output=True,text=True,check=True)
    return json.loads(r.stdout)


def recording(path):
    b=path.read_bytes()
    if len(b)<570 or b[0]!=1:raise ValueError('invalid p2m2 header')
    frames,rerecords,state=struct.unpack_from('<IIB',b,561)
    if frames<1 or (len(b)-570)%36 or (len(b)-570)//36<frames:raise ValueError('truncated/empty p2m2')
    if state not in (0,1):raise ValueError('invalid recording type')
    st=Path(str(path)+'_SaveState.p2s')
    if state and not st.is_file():raise ValueError('missing paired savestate')
    return dict(frames=frames,rerecords=rerecords,from_state=bool(state),sha256=hashlib.sha256(b).hexdigest(),
                trailing_frames=(len(b)-570)//36-frames,video_offset_seconds=None)


def gray(rgb):return np.asarray(rgb,dtype=np.float32)[...,:3] @ np.array([.299,.587,.114],np.float32)


class Matcher:
    """Alpha-masked zero-mean normalized correlation, full search at selected scales.
    No knowledge of where the element SHOULD be enters detection (avoids self-confirming gates).
    """
    def __init__(self,rgba,scales=(.65,.8,1.,1.2,1.45)):
        self.templates=[]
        for scale in scales:
            w=max(6,round(rgba.width*scale));h=max(6,round(rgba.height*scale))
            t=np.asarray(rgba.resize((w,h),Image.Resampling.BILINEAR),np.float32)
            mask=(t[:,:,3]>180).astype(np.float32);n=mask.sum()
            if n<8:continue
            g=gray(t);centered=(g-(g*mask).sum()/n)*mask
            power=(centered*centered).sum()
            if power<1:continue
            self.templates.append((scale,mask,centered,n,power))

    def find(self,frame):
        im=gray(frame);H,W=im.shape;best=dict(score=-1.,x=0,y=0,w=0,h=0,scale=0.)
        for scale,mask,template,n,power in self.templates:
            h,w=mask.shape
            if h>H or w>W:continue
            shape=(H+h-1,W+w-1)
            fi=np.fft.rfft2(im,s=shape); fm=np.fft.rfft2(mask[::-1,::-1],s=shape)
            sums=np.fft.irfft2(fi*fm,s=shape)[h-1:H,w-1:W]
            squares=np.fft.irfft2(np.fft.rfft2(im*im,s=shape)*fm,s=shape)[h-1:H,w-1:W]
            num=np.fft.irfft2(fi*np.fft.rfft2(template[::-1,::-1],s=shape),s=shape)[h-1:H,w-1:W]
            den=np.sqrt(np.maximum(squares-sums*sums/n,0)*power)
            score=np.divide(num,den,out=np.full_like(num,-1.),where=den>1)
            iy,ix=np.unravel_index(np.argmax(score),score.shape);v=float(score[iy,ix])
            if v>best['score']:best=dict(score=v,x=int(ix),y=int(iy),w=w,h=h,scale=scale)
        return best


def audio_onsets(samples,rate=16000):
    a=np.asarray(samples,np.float32);size=round(rate*.01)
    if len(a)<size:return [],0.
    blocks=a[:len(a)//size*size].reshape(-1,size)
    rms=np.sqrt(np.mean(blocks*blocks,axis=1));peak=float(np.max(np.abs(a)))
    floor=float(np.percentile(rms,20));threshold=max(.003,floor*3)
    # Sudden energy changes only; continuous music is not interpreted as individual cue identities.
    baseline=np.maximum(np.concatenate(([0.],rms[:-1])),.0005)
    candidates=np.flatnonzero((rms>threshold)&(rms>baseline*1.8))
    times=[]
    for i in candidates:
        t=float(i)*size/rate
        if not times or t-times[-1]>=.08:times.append(t)
    return times,peak


def test_gate(out):
    out.mkdir(parents=True,exist_ok=True)
    # Procedural test symbol, no copyrighted assets in tests or commits.
    t=Image.new('RGBA',(18,18));a=np.asarray(t).copy()
    a[2:16,3:6]=[250,40,30,255];a[11:15,3:15]=[30,230,120,255];t=Image.fromarray(a)
    def frame(x):
        im=Image.new('RGB',(120,80),(26,35,42));im.paste(t,(x,20),t);return np.asarray(im)
    m=Matcher(t,scales=(1.,));checks={}
    bad=m.find(frame(78));good=m.find(frame(18))
    def accepted(r):return r['score']>.9 and abs(r['x']-18)<=1 and abs(r['y']-20)<=1
    checks['misplaced_rejected']=not accepted(bad);print('RED: displaced element rejected',checks['misplaced_rejected'])
    silence=np.zeros(16000,np.float32);events,peak=audio_onsets(silence)
    checks['silence_rejected']=not events and peak==0;print('RED: silence rejected',checks['silence_rejected'])
    checks['correct_accepted']=accepted(good)
    audio=silence.copy();audio[4800:6400]=.2*np.sin(np.arange(1600)*2*np.pi*500/16000)
    events,peak=audio_onsets(audio);checks['sound_onset']=bool(events) and abs(events[0]-.3)<=.01
    # Bad/valid p2m2 headers exercise fail-closed input validation.
    broken=out/'broken.p2m2';broken.write_bytes(bytes(570))
    try:recording(broken)
    except ValueError:checks['bad_recording_rejected']=True
    else:checks['bad_recording_rejected']=False
    result=dict(ok=all(checks.values()),checks=checks,negative_location=bad,positive_location=good,audio_events=events,
                actual_game_recording_analyzed=False)
    (out/'gate.json').write_text(json.dumps(result,indent=2)+'\n');print(result)
    return result['ok']


def analyze(video,inputs,out):
    out.mkdir(parents=True,exist_ok=True)
    (out/'report.json').write_text(json.dumps(dict(status='running',started=time.time()))+'\n')
    meta=probe(video)
    vs=next(s for s in meta['streams'] if s['codec_type']=='video')
    aus=next((s for s in meta['streams'] if s['codec_type']=='audio'),None)
    if aus is None:raise ValueError('recording has no audio stream')
    rec=recording(inputs)
    templates=out/'templates';extract(templates)
    matcher=Matcher(Image.open(templates/'action.png').convert('RGBA'))
    width=320;height=round(int(vs['height'])*width/int(vs['width'])/2)*2
    # Keep every decoded video frame and its original timestamp; never synthesize constant FPS.
    times=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_frames',
       '-show_entries','frame=best_effort_timestamp_time','-of','json',str(video)]))['frames']
    pts=[float(f['best_effort_timestamp_time']) for f in times]
    if len(pts)<2 or any(y<=x for x,y in zip(pts,pts[1:])):raise ValueError('invalid video timestamps')
    command=['ffmpeg','-v','error','-i',str(video),'-map','0:v:0','-vf',f'scale={width}:{height}',
             '-fps_mode','passthrough','-f','rawvideo','-pix_fmt','rgb24','pipe:1']
    p=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=(out/'ffmpeg-video.log').open('w'))
    count=0;previous=None;found=0;cuts=[];started=time.time()
    try:
        with (out/'frames.tsv').open('w') as f:
            wr=csv.writer(f,delimiter='\t');wr.writerow(['frame','video_pts_s','element','x','y','width','height','scale','confidence','visual_change','status'])
            while True:
                data=p.stdout.read(width*height*3)
                if not data:break
                if len(data)!=width*height*3 or count>=len(pts):raise ValueError('truncated frame or timestamp mismatch')
                im=np.frombuffer(data,np.uint8).reshape(height,width,3);r=matcher.find(im)
                g=gray(im);change=float(np.mean(abs(g-previous))/255) if previous is not None else 0.;previous=g
                status='candidate' if r['score']>=.8 else 'unknown';found+=status=='candidate'
                if change>.22:cuts.append(pts[count])
                wr.writerow([count,f'{pts[count]:.6f}','action',r['x'],r['y'],r['w'],r['h'],r['scale'],f"{r['score']:.5f}",f'{change:.5f}',status])
                count+=1
        if p.wait()!=0 or count!=len(pts):raise ValueError('video decoding incomplete')
    finally:
        p.stdout.close()
        if p.poll() is None:p.terminate();p.wait()
    audio=subprocess.check_output(['ffmpeg','-v','error','-i',str(video),'-map','0:a:0','-ac','1','-ar','16000','-f','f32le','pipe:1'])
    onsets,peak=audio_onsets(np.frombuffer(audio,dtype='<f4'))
    if peak<1e-5:raise ValueError('audio track is silent; cannot confirm sound synchronization')
    audio_start=float(aus.get('start_time',0));timeline=[(t,'audio_onset_candidate') for t in (audio_start+x for x in onsets)]
    timeline += [(t,'visual_cut_candidate') for t in cuts]
    with (out/'timeline.tsv').open('w') as f:
        wr=csv.writer(f,delimiter='\t');wr.writerow(['media_pts_s','event','confidence_note'])
        for t,kind in sorted(timeline):wr.writerow([f'{t:.6f}',kind,'measurement; semantic label unconfirmed'])
    result=dict(status='observations_only',video=str(video.resolve()),video_sha256=hashlib.sha256(video.read_bytes()).hexdigest(),
                input=rec,frames=count,action_candidates=found,audio_onsets=len(onsets),visual_cuts=len(cuts),
                measurement_size=[width,height],audio_start_pts=audio_start,elapsed_seconds=time.time()-started,
                caveats=['Input/video offset is not established; do not compare input latency yet',
                         'Template scale is sampled, not a proven easing function; alpha is not inferred',
                         'Visual change can be camera motion, HUD change or a cut; candidates require classification'])
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    # Local-only references; no embedded game resources in tracked files.
    (out/'index.html').write_text('''<!doctype html><meta charset="utf-8"><title>Наблюдатель PS2</title>
<style>body{font:16px system-ui;background:#f6f5f2;margin:32px;max-width:1000px}video{width:100%}pre{white-space:pre-wrap}</style>
<h1>Наблюдения оригинала</h1><p>Кандидаты событий. Имена звуков, easing и сдвиг времени ввода ещё не подтверждены</p>
<p><a href="frames.tsv">Каждый кадр</a> · <a href="timeline.tsv">Общая шкала времени</a> · <a href="report.json">Доказательства и ограничения</a></p>
'''+ '<video controls preload="metadata" src="'+html.escape(os.path.relpath(video.resolve(),out.resolve()),quote=True)+'"></video><pre>'+html.escape(json.dumps(result,ensure_ascii=False,indent=2))+'</pre>')
    print(json.dumps(result,ensure_ascii=False,indent=2))


def check_expected(out, expected):
    """Explicit external oracle, never inferred from the measured locations themselves."""
    rows=list(csv.DictReader((out/'frames.tsv').open(),delimiter='\t'));errors=[]
    for e in expected.get('positions',[]):
        selected=[r for r in rows if e['first_frame']<=int(r['frame'])<=e['last_frame']]
        if len(selected)!=e['last_frame']-e['first_frame']+1:errors.append('missing expected frames')
        for r in selected:
            if float(r['confidence'])<e.get('min_score',.8):errors.append('missing element frame '+r['frame'])
            elif math.hypot(float(r['x'])-e['x'],float(r['y'])-e['y'])>e.get('tolerance_px',2):errors.append('displaced element frame '+r['frame'])
    timeline=list(csv.DictReader((out/'timeline.tsv').open(),delimiter='\t'))
    sounds=[float(r['media_pts_s']) for r in timeline if r['event']=='audio_onset_candidate']
    for e in expected.get('sounds',[]):
        if not any(e['from_s']<=t<=e['to_s'] for t in sounds):errors.append('expected sound missing')
    result=dict(ok=not errors,errors=errors)
    (out/'expectations.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--gate',action='store_true');p.add_argument('--video',type=Path);p.add_argument('--input',type=Path)
    p.add_argument('--out',type=Path,default=ROOT/'build/ps2ref/golden-analysis');p.add_argument('--expect',type=Path);a=p.parse_args()
    if a.gate:sys.exit(0 if test_gate(a.out) else 1)
    if not a.video or not a.input:p.error('--video and --input are required')
    try:
        analyze(a.video,a.input,a.out)
        if a.expect:
            result=check_expected(a.out,json.loads(a.expect.read_text()));print('EXPECTATIONS',result)
            if not result['ok']:sys.exit(1)
    except (ValueError,OSError,subprocess.SubprocessError) as e:
        a.out.mkdir(parents=True,exist_ok=True)
        (a.out/'report.json').write_text(json.dumps(dict(status='failed',error=str(e)))+'\n')
        print('FAIL:',e);sys.exit(1)
