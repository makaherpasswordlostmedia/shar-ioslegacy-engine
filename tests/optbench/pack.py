"""Pack independent, immutable optimization probes. Never writes the game or its level."""
import sys
sys.dont_write_bytecode = True
import argparse,ctypes as C,hashlib,json,struct,shutil
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
R=Path('/Users/USER/_backups/shar-psp-audit-2026-09-27_122213/research-2026-09-27')
sys.path.insert(0,str(ROOT/'tools'))
import strips
NSET=4
REC=np.dtype([('bb','<f4',6),('tex','<i4'),('flags','<u4'),('nv','<u4'),('ni','<u4'),('owner','<u4'),('o','<f4',3),('sc','<f4'),('off','<u4'),('nf','<u4'),('cell','<u4'),('pad','<u4',2)])
CEL=np.dtype([('bb','<f4',6),('first','<u4'),('n','<u4'),('owner','<u4'),('off','<u4'),('size','<u4'),('pad','<u4')])
lib=C.CDLL(str(R/'libmeshopt-stripifier-audit.dylib'));P=C.POINTER(C.c_uint32)
lib.meshopt_stripify.argtypes=[P,P,C.c_size_t,C.c_size_t,C.c_uint32];lib.meshopt_stripify.restype=C.c_size_t
lib.meshopt_stripifyBound.argtypes=[C.c_size_t];lib.meshopt_stripifyBound.restype=C.c_size_t
lib.meshopt_optimizeVertexCacheStrip.argtypes=[P,P,C.c_size_t,C.c_size_t];lib.meshopt_optimizeVertexCacheStrip.restype=None
def align(n):return (n+15)&~15
def fnv(b):
    h=2166136261
    for x in b:h=((h^x)*16777619)&0xffffffff
    return h
def canonical(tri):
    tri=tri[(tri[:,0]!=tri[:,1])&(tri[:,1]!=tri[:,2])&(tri[:,2]!=tri[:,0])]
    k=tri.argmin(1);t=np.take_along_axis(tri,(k[:,None]+np.arange(3))%3,1)
    return t[np.lexsort((t[:,2],t[:,1],t[:,0]))]
def expanded(seq):
    t=np.stack([seq[:-2],seq[1:-1],seq[2:]],1);t[1::2,:2]=t[1::2,1::-1];return t
def source(path):
    d=path.read_bytes();assert d[:4]==b'SHR7'
    nt,np_=struct.unpack_from('<II',d,4);hw,hh=struct.unpack_from('<II',d,68)
    table,nc,co,pvs=struct.unpack_from('<4I',d,76)
    rec=np.frombuffer(d,REC,np_,table);cells=np.frombuffer(d,CEL,nc,co)
    off=align(align(104+hw*hh*8)+hw*hh*4);tex=[]
    for i in range(nt):
        w,h,n,fmt,swz=struct.unpack_from('<HHHBB',d,off);assert fmt==0 and swz==1
        start=off;off+=1040;levels=[]
        for l in range(n):
            lw,lh=max(1,w>>l),max(1,h>>l);sz=lw*((lh+7)&~7)
            levels.append(d[off:off+sz]);off=align(off+sz)
        tex.append((w,h,n,d[start+16:start+1040],levels))
    assert off==table
    return d,rec,cells,tex,pvs
def choose(d,rec,eye,at,dist,pvsoff):
    f=np.asarray(at)-eye;f=f/np.linalg.norm(f);pl=strips.planes(f)
    allowed=None
    if pvsoff:
        ox,oz,cs=struct.unpack_from('<3f',d,pvsoff+4);W,H,pool=struct.unpack_from('<3I',d,pvsoff+16)
        gx,gz=int(np.floor((eye[0]-ox)/cs)),int(np.floor((eye[2]-oz)/cs))
        if 0<=gx<W and 0<=gz<H:
            st,n=struct.unpack_from('<II',d,pvsoff+32+(gz*W+gx)*8)
            if n!=0xffffffff:allowed=set(np.frombuffer(d,'<u2',n,pvsoff+32+W*H*8+st*2).tolist())
    chosen=[]
    for i,r in enumerate(rec):
        if r['owner'] or r['flags']&3:continue
        dd=strips.box_d2(r['bb'],eye)
        if dd>dist*dist or not strips.vis_box(r['bb'],pl,eye):continue
        if allowed is not None and dd<=115*115 and i not in allowed:continue
        far=dd>50*50;count=int(r['nf'] if far else r['ni'])
        if count:chosen.append((i,far))
    return sorted(chosen,key=lambda x:int(rec[x[0]]['tex']))
def pack(path,out,name,eye,at,dist):
    d,rec,cells,textures,pvs=source(path);chosen=choose(d,rec,np.array(eye),at,dist,pvs)
    ids=sorted({int(rec[i]['tex']) for i,_ in chosen if rec[i]['tex']>=0});tm={t:i for i,t in enumerate(ids)}
    blob=bytearray(128+48*len(ids)+128*len(chosen))
    def add(b):
        off=len(blob);blob.extend(b);blob.extend(bytes((-len(blob))%16));return off
    for ti,src in enumerate(ids):
        w,h,n,pal,lv=textures[src];po=add(pal);offsets=[add(x) for x in lv]+[0]*(8-n)
        struct.pack_into('<4H10I',blob,128+48*ti,w,h,n,0,po,*offsets,0)
    counts=[0]*4;vertsbytes=[0]*4;tris=0
    for pi,(i,far) in enumerate(chosen):
        r=rec[i];assert r['flags']&16
        vs=12 if r['flags']&32 else 16;n=int(r['nf'] if far else r['ni']);off=int(cells[int(r['cell'])]['off'])+int(r['off'])+(int(r['ni'])*vs if far else 0)
        raw=np.frombuffer(d,f'V{vs}',n,off);unique,first,ix=np.unique(raw,return_index=True,return_inverse=True)
        order=first.argsort();remap=np.empty(len(order),np.uint32);remap[order]=np.arange(len(order));unique=unique[order];ix=remap[ix].astype(np.uint32)
        assert len(unique)<65536 and n%3==0
        expected=canonical(ix.reshape(-1,3));tris+=n//3
        reordered=np.empty_like(ix);lib.meshopt_optimizeVertexCacheStrip(reordered.ctypes.data_as(P),ix.ctypes.data_as(P),n,len(unique))
        seq=np.empty(lib.meshopt_stripifyBound(n),np.uint32);ns=lib.meshopt_stripify(seq.ctypes.data_as(P),reordered.ctypes.data_as(P),n,len(unique),0);seq=seq[:ns]
        greedy=np.asarray(strips.join(strips.stripify(ix.reshape(-1,3))),np.uint32)
        assert np.array_equal(expected,canonical(expanded(seq))) and np.array_equal(expected,canonical(expanded(greedy)))
        if len(expected):assert not np.array_equal(expected,canonical(expanded(seq))[:-1])
        variants=[(raw,0,None),(unique[seq],1,None) if len(seq)<n else (raw,0,None),(unique,0,ix.astype('<u2')),(unique[greedy],1,None) if len(greedy)<n else (raw,0,None)]
        pos=128+48*len(ids)+128*pi
        struct.pack_into('<iI4f2I',blob,pos,tm.get(int(r['tex']),-1),int(r['flags']),float(r['sc']),*r['o'],i,int(far))
        for vi,(v,prim,idx) in enumerate(variants):
            vo=add(v.tobytes());io=add(idx.tobytes()) if idx is not None else 0;cnt=len(idx) if idx is not None else len(v)
            struct.pack_into('<6I',blob,pos+32+vi*24,cnt,vs,prim,vo,io,len(v));counts[vi]+=cnt;vertsbytes[vi]+=len(v)*vs+(len(idx)*2 if idx is not None else 0)
    struct.pack_into('<4s4I6fIfI',blob,0,b'OPB1',1,len(ids),len(chosen),4,*eye,*at,0x929292,float(dist),len(blob))
    dest=out/name;dest.write_bytes(blob)
    return dict(name=name,bytes=len(blob),fnv1a=fnv(blob),sha256=hashlib.sha256(blob).hexdigest(),pieces=len(chosen),triangles=tris,textures=len(ids),eye=eye,at=at,distance=dist,vertices_sent=counts,geometry_bytes=vertsbytes)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);ap.add_argument('--finalize',action='store_true');ap.add_argument('--reuse-data',type=Path);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    if a.reuse_data:
        manifest=json.loads((a.reuse_data/'package.json').read_text())
        for item in manifest['files']:
            n=item['path']
            if n in ('EBOOT.PBP','READ_ME.txt'):continue
            b=(a.reuse_data/n).read_bytes();assert hashlib.sha256(b).hexdigest()==item['sha256']
            p=a.out/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
        if not a.finalize:return
    if a.finalize:
        shutil.copy2(ROOT/'tests/optbench/build/EBOOT.PBP',a.out/'EBOOT.PBP')
        (a.out/'READ_ME.txt').write_text('SHAR Optimization Bench R2 / OB2-20260927\n\nOpen from Game > Memory Stick. The run starts automatically.\nWait for DONE - results saved. Press X or HOME, then connect USB.\nEach run creates run0001, run0002, ... and never overwrites earlier results.\n\nMeasurements: memory; sequential/random reads; many files; three city views\nwith current lists, meshoptimizer hybrid, indexed control, greedy hybrid.\nNo game simulation, audio, sky or transparency. This does not certify the game.\nR2 copies captures into RAM, writes 16 KiB chunks, reads files back.\nNo maximum-allocation stress; benchmark heap is capped at 12 MiB.\nA STOPPED screen preserves partial results; report it to Codex.\nRaw frame captures are 512x272 little-endian RGB565, visible area 480x272.\n\nSources: tests/optbench/ in the local shar-psp project.\nResearch and interpretation: audit document, sections 10-11.\n',encoding='utf-8')
        names=['EBOOT.PBP','READ_ME.txt','dataset.json','view115.bin','view250.bin','spawn250.bin','io.bin']+[f'small/{i:02d}.bin' for i in range(32)]
        files=[dict(path=n,bytes=(a.out/n).stat().st_size,sha256=hashlib.sha256((a.out/n).read_bytes()).hexdigest()) for n in names]
        sources={n:hashlib.sha256((Path(__file__).parent/n).read_bytes()).hexdigest() for n in ('main.c','frame_io.h','host_psp.h','regression.py','pack.py','data_ids.h','CMakeLists.txt','verify.py','collect.py')}
        (a.out/'package.json').write_text(json.dumps(dict(version='OB2-20260927',files=files,source_sha256=sources),indent=2)+'\n');print('Finalized',len(files),'files,',sum(x['bytes'] for x in files),'bytes');return
    src=ROOT/'build/level_ni.shr'
    old=(ROOT/'build/gebench/cell.bin').read_bytes();h=struct.unpack_from('<4s3I3f3fII',old)
    views=[('view115.bin',list(h[4:7]),list(h[7:10]),115),('view250.bin',list(h[4:7]),list(h[7:10]),250),('spawn250.bin',[212.5,6.7,172.0],[220.0,4.9,172.0],250)]
    scenes=[pack(src,a.out,*v) for v in views]
    data=(np.arange(8*1024*1024//4,dtype='<u4')^np.uint32(0x93a51c7d)).astype('<u4').tobytes();(a.out/'io.bin').write_bytes(data)
    (a.out/'small').mkdir(exist_ok=True)
    for i in range(32):(a.out/'small'/f'{i:02d}.bin').write_bytes(data[i*16384:(i+1)*16384])
    header='/* Generated by pack.py; dataset identity, no game code. */\n#define OPTBENCH_VERSION "OB2-20260927"\n#define SCENE_COUNT 3\n'
    header+='static const struct { const char *name; unsigned size, fnv; const char *sha; } sceneInfo[SCENE_COUNT] = {\n'
    for s in scenes:header+='  {"%s", %du, 0x%08xu, "%s"},\n'%(s['name'],s['bytes'],s['fnv1a'],s['sha256'])
    header+='};\n';(Path(__file__).parent/'data_ids.h').write_text(header)
    report=dict(version='OB2-20260927',source=str(src),source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),meshoptimizer_commit='9e1f07b159d3cb777f1c67ed31fc11fd117986f4',scenes=scenes,geometry_oracle='oriented triangle multiset and attributes equal for all scenes; deleted triangle negative control rejected',scope='Opaque static city only; no simulation, streaming, sky, transparency or sound')
    (a.out/'dataset.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
