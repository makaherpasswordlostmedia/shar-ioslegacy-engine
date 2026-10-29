"""(№394, только для сборки -DGROUND_SHADE_HALFTONE=1; с №398 по умолчанию — tests/ui/ground_shade.py) Check real native-resolution captures from the shadow394 scene, including old-renderer control.
Usage: python tests/ui/ground_stipple.py build/twins/scen/full/rob394_shadows
"""
import sys
from pathlib import Path
from PIL import Image

p=Path(sys.argv[1])
assert 'END' in (p/'smoke.txt').read_text(), 'scene incomplete'
a,b,old=[Image.open(p/f'{s}.png').convert('RGB') for s in ('stipple0','stipple1','old')]
if '--red' in sys.argv: a=b=old # feed the captured previous renderer through the same pixel gate
assert all(im.size==(480,272) for im in (a,b,old)), 'must be native PSP pixels'
# Road beside the feet, outside the animated character; same stationary camera
box=(248,174,256,181)
delta=[[],[]]
for y in range(box[1],box[3]):
    for x in range(box[0],box[2]):
        av,bv,ov=[im.getpixel((x,y)) for im in (a,b,old)]
        assert av==bv, f'halftone/background flickered at {x},{y}'
        delta[(x+y)&1].append(sum(av)-sum(ov))
means=[sum(v)/len(v) for v in delta]
assert means[0]<-10 and means[1]>10, f'no native-pixel checker versus old soft shadow: {means}'
print('PASS 56/56 stable road pixels, alternating darker/lighter coverage versus old shadow',means)
