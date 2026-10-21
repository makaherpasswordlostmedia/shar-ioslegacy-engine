"""Independent decoder and integrity check of the deployable bench package."""
import argparse,hashlib,json,struct
from pathlib import Path
from collections import Counter
def fnv(b):
    h=2166136261
    for x in b:h=(h^x)*16777619&0xffffffff
    return h
def triangles(v,indices,strip):
    seq=indices if indices is not None else list(range(len(v)))
    out=Counter()
    for i in range(len(seq)-2) if strip else range(0,len(seq),3):
        a,b,c=(v[seq[j]] for j in (i,i+1,i+2))
        if strip and i%2:a,b=b,a
        if a==b or b==c or a==c:continue
        out[min((a,b,c),(b,c,a),(c,a,b))]+=1
    return out
def check_scene(d,meta):
    assert len(d)==meta['bytes'] and hashlib.sha256(d).hexdigest()==meta['sha256'] and fnv(d)==meta['fnv1a'],'identity'
    magic,ver,nt,np_,ns=struct.unpack_from('<4s4I',d);assert (magic,ver,ns)==(b'OPB1',1,4)
    assert struct.unpack_from('<I',d,52)[0]==len(d)
    def region(off,count,stride):
        assert off>=128 and off%16==0 and count*stride<=len(d)-off
        return d[off:off+count*stride]
    for i in range(nt):
        t=struct.unpack_from('<4H10I',d,128+i*48);w,h,levels=t[:3]
        assert w>=16 and not w&(w-1) and h and not h&(h-1) and 1<=levels<=8
        region(t[4],256,4)
        for l in range(levels):region(t[5+l],(w>>l)*((max(1,h>>l)+7)&~7),1)
    total=0
    for i in range(np_):
        pos=128+nt*48+i*128;tex,flags=struct.unpack_from('<iI',d,pos);assert -1<=tex<nt and not flags&3
        reference=None
        for j in range(4):
            n,vs,prim,vo,io,nv=struct.unpack_from('<6I',d,pos+32+j*24);assert vs in (12,16) and prim in (0,1)
            raw=region(vo,nv,vs);v=[raw[k*vs:(k+1)*vs] for k in range(nv)]
            ix=list(struct.unpack('<'+'H'*n,region(io,n,2))) if io else None
            assert max(ix,default=0)<nv if ix is not None else n==nv
            got=triangles(v,ix,prim)
            if j==0:reference=got;total+=n//3
            else:assert got==reference,(i,j,'triangle/attribute mismatch')
    assert total==meta['triangles'];return np_
def check_pbp(p):
    b=p.read_bytes();assert b[:4]==b'\0PBP';offs=struct.unpack_from('<8I',b,8);sfo=b[offs[0]:offs[1]]
    magic,version,ko,do,n=struct.unpack_from('<5I',sfo);assert magic==0x46535000
    fields={}
    for i in range(n):
        k,fmt,length,capacity,off=struct.unpack_from('<HHIII',sfo,20+i*16)
        end=sfo.index(0,ko+k);key=sfo[ko+k:end].decode();raw=sfo[do+off:do+off+length]
        fields[key]=struct.unpack('<I',raw)[0] if fmt==0x0404 else raw.rstrip(b'\0').decode(errors='replace')
    assert fields['MEMSIZE']==1 and fields['TITLE']=='SHAR Optimization Bench R2';return fields
def main():
    ap=argparse.ArgumentParser();ap.add_argument('package',type=Path);a=ap.parse_args();root=a.package
    package=json.loads((root/'package.json').read_text());dataset=json.loads((root/'dataset.json').read_text())
    for f in package['files']:
        b=(root/f['path']).read_bytes();assert len(b)==f['bytes'] and hashlib.sha256(b).hexdigest()==f['sha256'],f['path']
    count=sum(check_scene((root/s['name']).read_bytes(),s) for s in dataset['scenes'])
    assert fnv(b'hello')==0x4f9f2cab
    bad=bytearray((root/dataset['scenes'][0]['name']).read_bytes());bad[-1]^=1
    try:check_scene(bad,dataset['scenes'][0])
    except AssertionError:pass
    else:raise AssertionError('negative control accepted damaged scene')
    print(json.dumps(dict(files=len(package['files']),pieces=count,scenes=3,variants=4,independent_geometry='pass',corruption_negative_control='pass',sfo=check_pbp(root/'EBOOT.PBP')),indent=2))
if __name__=='__main__':main()
