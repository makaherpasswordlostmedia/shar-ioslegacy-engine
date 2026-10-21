#!/usr/bin/env python3
"""Read-only integrated FE control/status gate, not a waveform capture.

Natural preparation is classified by actual FEGAG forced=0 + clock samples.
Forced debug 180/181 calls may be simultaneous and never prove a 2s prefill.
Source expectations come from the original observer and actual shipped SAP.
"""
import argparse,hashlib,json,re,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def fields(line):return dict(re.findall(r'(\w+)=([^\s]+)',line))
def number(row,key,default=-999):return int(row.get(key,default))
def inspect(log,observer,asset):
 data=log.read_bytes();lines=data.decode(errors='replace').splitlines();records=[(i,line.split()[0],fields(line)) for i,line in enumerate(lines) if line.startswith(('FEAUDIO ','FEGAG ','FEGCLOCK '))]
 original=json.loads(observer.read_text());expect={r['index']:r['name'] for r in original['sound_keys'] if r['index']};homer={r['segment']:r['name'] for r in original['homer_sound_keys']}
 packet=asset.read_bytes();magic,version,n,off=struct.unpack_from('<4sIII',packet);names=[packet[off+i*64:off+i*64+28].split(b'\0')[0].decode() for i in range(n)];ids={name:0x4000+i for i,name in enumerate(names)}
 checks=[];natural=[];forced=[]
 def ck(label,ok,detail=''):checks.append(dict(label=label,passCase=bool(ok),detail=detail))
 ck('complete_integrated_log','END' in lines)
 ck('actual_shipped_SAP1_12',magic==b'SAP1' and version==1 and n==12 and len(set(names))==12)
 ck('actual_FEAUDIO_load12',any(tag=='FEAUDIO' and number(r,'load')==12 for _,tag,r in records))
 starts=[(i,r) for i,tag,r in records if tag=='FEGAG' and lines[i].startswith('FEGAG start ')]
 last_start=-1
 for ordinal,(startline,start) in enumerate(starts):
  ix=number(start,'i');seg=number(start,'seg');debug=number(start,'forced')==1;label=('forced' if debug else 'natural')+str(ordinal)
  want=homer.get(seg) if ix==0 else expect.get(ix)
  event181=[(i,r) for i,tag,r in records if last_start<i<startline and tag=='FEAUDIO' and number(r,'event')==181 and number(r,'index')==ix and number(r,'segment')==seg]
  play=event181[-1] if event181 else None
  ck(label+'_181_callback_present',play is not None)
  if not play:last_start=startline;continue
  playline,p=play
  event180=[(i,r) for i,tag,r in records if last_start<i<playline and tag=='FEAUDIO' and number(r,'event')==180 and number(r,'index')==ix and number(r,'segment')==seg]
  prep=event180[-1] if event180 else None
  ck(label+'_180_callback_present',prep is not None)
  ck(label+'_181_original_name_and_track',want is not None and p.get('name')==want and number(p,'track')==ids.get(want,-1),f'actual={p.get("name")} original={want} track={p.get("track")}')
  ck(label+'_181_accepted_release',number(p,'status')==1 and number(p,'prepared')==0,f'status={p.get("status")} prepared_after={p.get("prepared")}')
  if not prep:last_start=startline;continue
  prepline,q=prep;rounded_wall=float(p['t'])-float(q['t'])
  ck(label+'_180_original_name_and_track',q.get('name')==want and number(q,'track')==ids.get(want,-1))
  ck(label+'_180_accepted',number(q,'status')==1)
  ck(label+'_request_unchanged',number(q,'req')>0 and number(q,'req')==number(p,'req')==number(p,'before_req'),f'180_req={q.get("req")} 181_before={p.get("before_req")} 181_req={p.get("req")}')
  result=dict(index=ix,segment=seg,name=want,rounded_wall_delta=round(rounded_wall,3),prepare=q,play=p)
  if debug:
   # Debug acceptance is useful, but no natural prefill credit is awarded.
   result['proof']='forced callback/release only; not natural two-second preparation'
   forced.append(result)
  else:
   preparetag=[(i,r) for i,tag,r in records if prepline<i<playline and tag=='FEGAG' and lines[i].startswith('FEGAG prepare ') and number(r,'i')==ix and number(r,'seg')==seg]
   ck(label+'_natural_clock_prepare_present',bool(preparetag))
   clock=[r for i,tag,r in records if prepline<i<playline and tag=='FEGCLOCK']
   ck(label+'_natural_clock_samples',len(clock)>2)
   if preparetag and len(clock)>2:
    phase=preparetag[-1][1];elapsed=number(phase,'elapsed_ms');threshold=number(phase,'next_ms');ms=[number(r,'ms') for r in clock];steps=[b-a for a,b in zip(ms,ms[1:]) if b>a];step=max(steps) if steps else 0;lead=threshold-elapsed
    ck(label+'_clock_prepares_at_threshold_minus2000',step>0 and 2000-step<=lead<=2000,f'elapsed={elapsed} threshold={threshold} lead={lead} observed_step={step}')
    ck(label+'_clock_waits_until_threshold',ms[0]==elapsed and all(a<=b for a,b in zip(ms,ms[1:])) and threshold-step<=ms[-1]<threshold,f'first={ms[0]} last={ms[-1]} threshold={threshold}')
    ck(label+'_natural_in_active_main_menu',all(number(r,'active')==1 and number(r,'flying')==0 for r in clock))
    ck(label+'_rounded_wall_not_same_frame',rounded_wall>=1.7,f'rounded_delta={rounded_wall:.3f}s; upper bound omitted for legitimate menu pauses')
    result.update(menu_clock_lead_ms=lead,menu_clock_observed_delta_ms=ms[-1]-ms[0],last_before_play_ms=ms[-1],observed_step_ms=step)
   ck(label+'_prefill_ready_before181',number(p,'ready_before')==1,f'ready_before={p.get("ready_before")}')
   result['proof']='natural menu-clock preparation + backend ring readiness + release request; no post-mix PCM in this log'
   natural.append(result)
  last_start=startline
 ck('at_least_one_natural_prepare_pair',bool(natural))
 ck('forced_debug_reported_separately',bool(forced))
 return dict(input=str(log),input_sha256=hashlib.sha256(data).hexdigest(),observer_sha256=hashlib.sha256(observer.read_bytes()).hexdigest(),asset_sha256=hashlib.sha256(packet).hexdigest(),checks=checks,natural=natural,forced=forced,failures=sum(not r['passCase'] for r in checks),limits='FEAUDIO track includes about-to-play; status1 at181 accepts release, not recorded sound. smkT is rounded0.1s; menu clock samples carry millisecond evidence. No original PS2 final mix/waveform assertion.')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('log',type=Path);ap.add_argument('--asset',type=Path);ap.add_argument('--observer',type=Path,default=ROOT.parent/'shar-psp-ps2-w/knowledge/facts/ps2-main-menu-runtime.yaml');ap.add_argument('--out',type=Path);a=ap.parse_args();r=inspect(a.log,a.observer,a.asset or a.log.parent/'fe_audio.sap')
 if a.out:a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(r,indent=2)+'\n')
 for row in r['checks']:print('CHECK',row['label'],'PASS' if row['passCase'] else 'FAIL',row['detail'])
 print('RESULT','FAIL' if r['failures'] else 'PASS',f'failures={r["failures"]} natural={len(r["natural"])} forced={len(r["forced"])}');return bool(r['failures'])
if __name__=='__main__':raise SystemExit(main())
