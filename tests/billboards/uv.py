#!/usr/bin/env python3
"""370: render the nuclear-plant neon texture through the actual SPR1 vertex UV helper.
Native P3DI rows are bottom-up (as in the city exporter); local +Y is top.
--red reproduces the old top-v=0 mapping and must reject the flipped lettering.
"""
import ctypes,sys,subprocess,tempfile
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import psp_export as P,texq
from convert import Converter
from PIL import Image
conv=Converter();conv.resources(P.read(P.GAME/'art/l1z6.p3d'))
url=conv.textures[conv.shaders['spp_m']['texture']]
assert url not in P.PNG_SRC, 'fixture must remain native P3DI'
cache,blob={},[];idx=P.load_tex(url,cache,blob,blend=True)
image=texq.decode(blob[idx])[0][...,:3]
raw=np.asarray(Image.open(P.ASSETS/url).convert('RGB').resize((image.shape[1],image.shape[0]),Image.Resampling.LANCZOS),float)
with tempfile.TemporaryDirectory(prefix='shar-uv-') as td:
 c=Path(td)/'uv.c';lib=Path(td)/'uv.so'
 c.write_text('#include "stateprops.h"\nfloat top(int old){return spBillTexV(2,old);}')
 subprocess.run(['cc','-shared','-fPIC','-DSKIN_HOST','-I'+str(ROOT/'viewer'),str(c),'-o',str(lib)],check=True)
 fn=ctypes.CDLL(str(lib)).top;fn.argtypes=[ctypes.c_int];fn.restype=ctypes.c_float
 # Raster from the top vertex to bottom: increasing v reads the stored rows forward.
 got=image if fn('--red' in sys.argv)==0 else image[::-1]
 upright=np.abs(got.astype(float)-raw[::-1]).mean()
 flipped=np.abs(got.astype(float)-raw).mean()
 print('neon upright error',round(upright,3),'flipped error',round(flipped,3))
 sys.exit(0 if upright<flipped else 1)
