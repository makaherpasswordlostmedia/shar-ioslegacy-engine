import sys
from PIL import Image
d,pref,out=sys.argv[1:4]; n=int(sys.argv[4]) if len(sys.argv)>4 else 13
box=(0,150,360,272)
ims=[Image.open(f'{d}/{pref}_{i:02d}.png').convert('RGB').crop(box) for i in range(n)]
cols=3; rows=(n+cols-1)//cols; W,H=box[2]-box[0],box[3]-box[1]
s=Image.new('RGB',(cols*W,rows*H),(40,40,40))
for i,im in enumerate(ims): s.paste(im,((i%cols)*W,(i//cols)*H))
s.save(out)
