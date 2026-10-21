#!/usr/bin/env python3
"""Read existing PS2/captured port evidence only. Never launches an emulator or native engine.
Control --wrong-column proves legacy car/anchored hero matrices cannot replace Husk mx/mz.
--broken-native reads the saved real broken-repair controls, not invented success logs.
No pickup, current-player pointer or simultaneous oldCar repair is inferred from a run name.
"""
import argparse,csv,hashlib,json,math,re,struct,sys
from pathlib import Path
if sys.version_info < (3,14):sys.exit('Python >=3.14 required for original .p2s Zstandard, using existing dig.load_ee')
ROOT=Path(__file__).resolve().parents[2];MAIN=ROOT.parent/'shar-psp'
ap=argparse.ArgumentParser();ap.add_argument('--wrong-column',choices=['legacy','hero']);ap.add_argument('--broken-native',action='store_true');a=ap.parse_args()
out=ROOT/'build/wreck355-c3/trace-review';out.mkdir(parents=True,exist_ok=True)
variant=a.wrong_column or ('broken-native' if a.broken_native else 'new');checks=[];artifacts=[];measure=[]
def check(n,v):checks.append(dict(name=n,pass_=bool(v)))
def read(p):
 b=p.read_bytes();artifacts.append(dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest()));return b
def rows(p):return list(csv.DictReader(read(p).decode().splitlines(),delimiter='\t'))
legacy=rows(MAIN/'build/twins/o4/a355_huskdrive/t.tsv')
legacy_move=math.hypot(float(legacy[-1]['x'])-float(legacy[0]['x']),float(legacy[-1]['z'])-float(legacy[0]['z']))
hero_move=math.hypot(float(legacy[-1]['гx'])-float(legacy[0]['гx']),float(legacy[-1]['гz'])-float(legacy[0]['гz']))
check('legacy matrix is distinct from walking hero',legacy_move==0 and hero_move>30)
for name,sha in [('a355_huskwrench','19fc7b08d59b92bd3e523487a338c38b171a9a6bb7d5c0dded13529d08efe446'),('a355_huskwrench2','73bf17041dbc248870074312fbc72ad27885b21187878e6babe792a72811b901')]:
 d=MAIN/'build/twins/o4'/name;b=rows(d/'t.tsv');script=read(d/'script.txt').decode()
 check(name+' immutable trace',artifacts[-2]['sha256']==sha)
 check(name+' traced Husk matrix',all(k in script for k in ['83f070:f32','83f074:f32','83f078:f32']))
 check(name+' strictly spaced PAL frames',all(int(v['кадр'])-int(u['кадр'])==2 for u,v in zip(b,b[1:])))
 if a.wrong_column:
  for q in b:
   q['mx'],q['mz']=(legacy[0]['x'],legacy[0]['z']) if a.wrong_column=='legacy' else (q['гx'],q['гz'])
 drive=[q for q in b if q['фаза'].startswith('ехать')]
 path=sum(math.hypot(float(v['mx'])-float(u['mx']),float(v['mz'])-float(u['mz'])) for u,v in zip(drive,drive[1:]))
 endpoint=math.hypot(float(drive[-1]['mx'])-float(drive[0]['mx']),float(drive[-1]['mz'])-float(drive[0]['mz']))
 errors=[]
 for u,v in zip(b,b[1:]):
  dt=(int(v['кадр'])-int(u['кадр']))/50
  speed=math.hypot(float(v['mx'])-float(u['mx']),float(v['mz'])-float(u['mz']))/dt
  errors.append(abs(speed-float(v['v'])))
 # Coordinates and reported speed rounded to .01: differential position error
 # <= sqrt(2)*.01 per .04 s plus .005 speed rounding. This is not a fitted tolerance.
 bound=math.sqrt(2)*.01/.04+.005
 check(name+' moving Husk drive phase',path>50 and endpoint>10)
 check(name+' v matches mx/mz differential',max(errors)<=bound+1e-6)
 measure.append(dict(run=name,car_path_m=path,endpoint_m=endpoint,max_v_mps=max(float(q['v']) for q in b),speed_quantization_bound=bound,max_speed_error=max(errors)))
 for f in [0,150,600]:read(d/'png'/f'f{f:05d}.png')
# Existing reader consumes just saved RAM; no Original/PCSX2 constructor is imported.
sys.path.insert(0,str(MAIN/'tools/ps2ref'));import dig
snap=MAIN/'build/twins/o4/a355_huskdrive2/snap_1000.p2s';read(snap);ee=bytes(dig.load_ee(snap))
old=struct.unpack_from('<3f',ee,0xa218a0);husk=struct.unpack_from('<3f',ee,0x83f070)
check('saved RAM separates old and Husk matrix',math.hypot(old[0]-husk[0],old[2]-husk[2])>30)
native=MAIN/'build/twins/scen/full/a355_s2';t=read(native/'smoke.txt').decode();sc=read(native/'scenario.txt').decode()
check('archived native uses authored wrench without repair flag','foot 211.5 142.4' in sc and 'flag repair' not in sc and '7:211.5,5.7,142.4' in t)
def shot(n):
 m=re.search(r'SHOT '+n+r' [\d.]+ pos ([\d.-]+) [\d.-]+ ([\d.-]+)',t);return tuple(map(float,m.groups())) if m else None
p,q=shot('a355_enter'),shot('a355_drive');native_delta=math.dist(p,q) if p and q else 0
check('archived native repaired player drives',native_delta>10 and 'END' in t)
for n in ['a355_wrench','a355_enter','a355_drive']:read(native/(n+'.png'))
for L in range(1,8):
 p=ROOT/f"build/wreck355-c3/l{L}-{'red1' if a.broken_native else 'new'}.log"
 s=read(p).decode();check(f'current native L{L} repaired/entry/NPC solid',all(f'CHECK {k} PASS' in s for k in ['repaired-state','fresh-entry-allowed','triangle-actually-seated','NPC-solid-after-repair']))
result=dict(variant=variant,checks=checks,measure=measure,legacy_old_matrix_displacement_m=legacy_move,legacy_hero_matrix_displacement_m=hero_move,
 saved_ram_matrices={'old_a21870':old,'husk_83f040':husk},archived_native_primary_drive_m=native_delta,
 limits=['No post-wrench RAM snapshot or pickup counter binding; run name does not prove repair','No bound current-player vehicle pointer; matrices only','NPC collision and oldCar hijack/return not measured by these PS2 traces','Existing flat native Husk speed is not accepted as a match to these different routes'],artifacts=artifacts)
(out/(variant+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
fail=[c['name'] for c in checks if not c['pass_']];print('RESULT', 'FAIL' if fail else 'PASS','checks='+str(len(checks)),'failures='+str(len(fail)));print('\n'.join(fail));sys.exit(bool(fail))
