import sys
from PIL import Image
d, pref, out = sys.argv[1:4]; a = int(sys.argv[4]); b = int(sys.argv[5]); step = int(sys.argv[6]) if len(sys.argv) > 6 else 1; cols = int(sys.argv[7]) if len(sys.argv) > 7 else 6
idx = list(range(a, b, step)); w, h = 240, 136
ims = [Image.open(f'{d}/{pref}_{i:02d}.png').convert('RGB').resize((w, h)) for i in idx]
rows = (len(ims) + cols - 1) // cols
s = Image.new('RGB', (cols * w, rows * h), (40, 40, 40))
for k, im in enumerate(ims): s.paste(im, ((k % cols) * w, (k // cols) * h))
s.save(out)
