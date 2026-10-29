#!/usr/bin/env python3
"""Actual headless frame image vs owned-disc art. Same gate must reject old blank briefing frames.
The image rectangle comes from the emitted UIP1 external-image item; no guessed screen coordinates.
"""
import json, struct, sys
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'hit-and-run-web/tools')]
from p3d import read
from ui_export import decode_sprite_image
from briefcards_source import builtin_mappings
stage=Path(sys.argv[1]);screens=Path(sys.argv[2]);mapping=builtin_mappings();failed=0;rows=[]
for shot,npc,level in [('brief_tt','milhouse',1),('brief_ct','nelson',1),('brief_cp','ralph',1),('brief_gb','louie',1),('brief_hw_l7','zmale3',7)]:
 ui=stage/'ui.shr' if level==1 else stage/f'l{level}/ui.shr'
 b=ui.read_bytes();h=struct.unpack_from('<4sI20I',b);n,off=h[4:6]
 ext=[r for i in range(n) if (r:=struct.unpack_from('<8B4h2I4B2H3fIf3I',b,off+64*i))[-3]&1 and r[1]==3]
 assert len(ext)==1,'external briefing image slot missing or ambiguous'
 x,y,w,height=ext[0][8:12]
 source=next(decode_sprite_image(c)[1].convert('RGBA') for c in read(ROOT/'hit-and-run-web/source/game'/mapping[npc]).children if c.id==0x19005)
 scale=min(1.,256/source.width,128/source.height);size=(round(source.width*scale),round(source.height*scale))
 expected=np.array(source.resize(size,Image.Resampling.LANCZOS).resize((w,height),Image.Resampling.BILINEAR))
 actual=np.array(Image.open(screens/(shot+'.png')).convert('RGB'))[y:y+height,x:x+w]
 mask=expected[:,:,3]>250
 mae=float(np.abs(actual.astype(float)-expected[:,:,:3]).mean(axis=2)[mask].mean())
 correlation=float(np.corrcoef(actual[mask].flatten(),expected[:,:,:3][mask].flatten())[0,1])
 ok=mae<=3 and correlation>=.99
 failed+=not ok;rows.append(dict(shot=shot,rect=[x,y,w,height],mae=mae,correlation=correlation,pass_=bool(ok)))
 print(f'{shot} {"PASS" if ok else "FAIL"} MAE={mae:.3f}/3 correlation={correlation:.5f}/.99')
(screens/'pixels.json').write_text(json.dumps(rows,indent=2)+'\n')
print(f'RESULT {"PASS" if not failed else "FAIL"} failures={failed}');sys.exit(bool(failed))
