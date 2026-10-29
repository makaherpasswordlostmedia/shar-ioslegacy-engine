#!/usr/bin/env python3
"""Every mission's real presentation callback + exported RGBA vs owned disc sprite.
--old-runtime compiles BRIEFCARDS_423_OLD; --old-packages reads immutable MSA2 files exported with the old scope.
"""
import argparse, contextlib, hashlib, io, json, os, struct, subprocess, sys
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[2];os.chdir(ROOT);OUT=ROOT/'build/briefcards-c3';OUT.mkdir(parents=True,exist_ok=True)
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tools/missions'),str(ROOT/'hit-and-run-web/tools')]
import briefcards_source as BS
import mfk
from p3d import read
from ui_export import decode_sprite_image
ap=argparse.ArgumentParser();ap.add_argument('--old-runtime',action='store_true');ap.add_argument('--old-packages',action='store_true');args=ap.parse_args()
exe=OUT/('host-old' if args.old_runtime else 'host');cmd=['cc','-std=c11','-O2','-Iviewer']
if args.old_runtime:cmd+=['-DBRIEFCARDS_423_OLD=1']
with (OUT/'compile.log').open('w') as f:
 if subprocess.run(cmd+['tests/briefcards/host.c','viewer/mission/msn_game.c','viewer/mission/msn_run.c','viewer/mission/msn_file.c','viewer/mission/msn_ops.c','-lm','-o',str(exe)],stdout=f,stderr=subprocess.STDOUT).returncode:sys.exit('FAIL compilation')
builtins=BS.builtin_mappings();GAME=ROOT/'hit-and-run-web/source/game';failed=0;cases=[];images={}
normalize=lambda p:p.replace('\\','/').lower()
def entries(path):
 b=path.read_bytes();assert b[:4]==b'MSA2';n,table,size=struct.unpack_from('<III',b,4);assert size==len(b)
 return {b[table+96*i:table+96*i+80].split(b'\0')[0].decode():b[off:off+sz] for i in range(n) for off,sz in [struct.unpack_from('<II',b,table+96*i+80)]}
def picture(blob,stem):
 nt,nd,ni,ot,od,oi=struct.unpack_from('<6I',blob)
 for i in range(ni):
  row=blob[oi+48*i:oi+48*(i+1)];name=row[:32].split(b'\0')[0].decode()
  if name.lower()!=stem:continue
  ti,w,h=struct.unpack_from('<III',row,32);tw,th,off=struct.unpack_from('<HHI',blob,ot+16*ti)
  assert off+tw*th*4<=len(blob)
  return (tw,th),(w,h),blob[off:off+tw*th*4]
 raise AssertionError('image entry absent: '+stem)
for level in range(1,8):
 givers={r.args[3]:r.args[0] for r in mfk.parse_file(GAME/f'scripts/missions/level{level:02d}/leveli.mfk')[0] if r.op=='AddNPCCharacterBonusMission'}
 pack=ROOT/'build/ship_stage' if level==1 else ROOT/f'build/ship_stage/l{level}'
 artifact=OUT/f'ref-old-msnart-l{level}.shr' if args.old_packages else pack/'msnart.shr'
 blobs=entries(artifact)
 runtime=subprocess.check_output([str(exe),str(pack/f'level{level:02d}.msn')],text=True)
 (OUT/f'l{level}-runtime{"-old" if args.old_runtime else ""}.log').write_text(runtime)
 actual={p[2]:(int(p[3]),int(p[4]),normalize(p[5])) for line in runtime.splitlines() if (p:=line.split(maxsplit=5)) and p[0]=='CASE'}
 total=0;bad=0;bitmaps={}
 script_dir=GAME/f'scripts/missions/level{level:02d}'
 for script in sorted(script_dir.glob('*.mfk')):
  calls=mfk.parse_file(script)[0];selected=next((str(k.args[0]) for k in calls if k.op=='SelectMission'),None)
  if not selected:continue
  mid=selected[:-2] if selected.endswith('sd') else selected
  for k in calls:
   if k.op=='SetPresentationBitmap':bitmaps.setdefault(mid,[]).append(normalize(k.args[0]))
 scheduled={str(k.args[0]) for k in mfk.parse_file(script_dir/'level.mfk')[0] if k.op in ('AddMission','AddBonusMission')}|set(givers)
 assert set(actual)==scheduled, 'runtime mission list differs from disc schedule'
 for mid in actual:
  scripted=bitmaps.get(mid,[])
  expected=scripted[0] if scripted else builtins.get(str(givers.get(mid,'')))
  flags,titles,path=actual[mid];ok=(path==expected if expected else path=='-') and (titles>0 or flags&16)
  detail=''
  if expected:
   total+=1
   try:
    assert expected in blobs,'missing P3D record'
    shape,size,data=picture(blobs[expected],Path(expected).stem)
    source=next(decode_sprite_image(v)[1].convert('RGBA') for v in read(GAME/expected).children if v.id==0x19005)
    scale=min(1.,256/source.width,128/source.height);expected_size=(round(source.width*scale),round(source.height*scale))
    assert shape==(256,128) and size==expected_size,'image dimensions violate briefing 256x128/aspect contract'
    canvas=Image.new('RGBA',shape);canvas.paste(source.resize(expected_size,Image.Resampling.LANCZOS),(0,0));assert data==canvas.tobytes(),'actual RGBA differs from disc'
    images[f'L{level}/{mid}']=Image.frombytes('RGBA',shape,data).crop((0,0,*size))
   except (AssertionError,StopIteration) as e:ok=False;detail=str(e)
  bad+=not ok;cases.append({'level':level,'mission':mid,'expected':expected,'runtime':path,'pass':bool(ok),'detail':detail})
  print(f'CHECK L{level}/{mid} {"PASS" if ok else "FAIL"} expected={expected or "no presentation (disc)"} actual={path} {detail}')
 for path in BS.builtin_paths():
  if '/misxx_' not in path:continue
  try:
   assert path in blobs,'missing built-in P3D record'
   shape,size,data=picture(blobs[path],Path(path).stem)
   source=next(decode_sprite_image(v)[1].convert('RGBA') for v in read(GAME/path).children if v.id==0x19005)
   scale=min(1.,256/source.width,128/source.height);expected_size=(round(source.width*scale),round(source.height*scale))
   assert shape==(256,128) and size==expected_size,'wrong built-in dimensions'
   canvas=Image.new('RGBA',shape);canvas.paste(source.resize(expected_size,Image.Resampling.LANCZOS),(0,0))
   assert data==canvas.tobytes(),'wrong built-in pixels'
   print(f'BUILTIN L{level}/{Path(path).stem} PASS')
  except (AssertionError,StopIteration) as e:
   bad+=1;print(f'BUILTIN L{level}/{Path(path).stem} FAIL {e}')
 failed+=bad;print(f'L{level} cards={total} failures={bad}')
# A reviewable image of actual exported pixels, not an imitation of the UI.
if not args.old_runtime and not args.old_packages and images:
 thumbw,thumbh=247,150;cols=7;rows=(len(images)+cols-1)//cols
 from PIL import ImageDraw
 sheet=Image.new('RGB',(cols*thumbw,rows*thumbh),(246,245,242));draw=ImageDraw.Draw(sheet)
 for i,(label,img) in enumerate(images.items()):
  x=(i%cols)*thumbw;y=(i//cols)*thumbh;sheet.paste(img,(x,y),img);draw.text((x+3,y+130),label,fill=(26,26,26))
 sheet.save(OUT/'all-cards.png')
(OUT/('report-old-runtime.json' if args.old_runtime else 'report-old-packages.json' if args.old_packages else 'report.json')).write_text(json.dumps({'sles_sha256':hashlib.sha256(BS.DISC.read_bytes()).hexdigest(),'builtin_mappings':builtins,'cases':cases,'failures':failed},ensure_ascii=False,indent=2)+'\n')
print(f'RESULT {"PASS" if not failed else "FAIL"} cases={len(cases)} failures={failed}');sys.exit(bool(failed))
