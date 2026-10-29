import sys
from PIL import Image
out, *names = sys.argv[1:]
ims = [Image.open(n) for n in names]; w, h = ims[0].size
cols = 2 if len(ims) > 2 else len(ims); rows = (len(ims) + cols - 1) // cols
s = Image.new("RGB", (w * cols, h * rows))
for i, im in enumerate(ims): s.paste(im, ((i % cols) * w, (i // cols) * h))
s.save(out)
