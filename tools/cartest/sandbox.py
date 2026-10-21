#!/usr/bin/env python3
"""Local live viewer + durable evidence for the native PSP physics swarm. Stdlib only.
Run: python3 tools/cartest/sandbox.py --level build/level.shr --roads build/sandbox/roads-l1.bin
The server binds only to loopback and exposes only this tool's resources, never the repo.
"""
import argparse
import array
import collections
import ctypes
import hashlib
import http.server
import json
import math
import os
from pathlib import Path
import secrets
import signal
import struct
import subprocess
import threading
import time
from urllib.parse import urlparse
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
ENGINE = [ROOT/"viewer"/(name+".c") for name in ("car","col","props","stateprops","coins")]

def campaign_status():
    pointer=ROOT/'build/sandbox/soak-current.json'
    if not pointer.exists():return None
    try:
        path=Path(json.loads(pointer.read_text())['path']).resolve()
        if not path.is_relative_to(ROOT/'build/sandbox/soaks'):raise ValueError('invalid campaign path')
        state=json.loads((path/'status.json').read_text())
        if state['status']=='running' and time.time()-state['updatedAt']>10:state['status']='stale'
        return state
    except (OSError,ValueError,KeyError):return dict(status='unavailable')

class MacMeter:
    """Kernel CPU tick deltas for the whole Mac, independent of simulation counters."""
    def __init__(self):
        self.lib=ctypes.CDLL('/usr/lib/libSystem.B.dylib')
        self.lib.mach_host_self.restype=ctypes.c_uint
        self.lib.host_statistics.argtypes=[ctypes.c_uint,ctypes.c_int,ctypes.POINTER(ctypes.c_uint),ctypes.POINTER(ctypes.c_uint)]
        self.host=self.lib.mach_host_self();self.previous=None
    def sample(self):
        ticks=(ctypes.c_uint*4)();count=ctypes.c_uint(4)
        if self.lib.host_statistics(self.host,3,ticks,ctypes.byref(count))!=0:raise OSError('host_statistics CPU failed')
        current=list(ticks);previous=self.previous;self.previous=current
        if previous is None:return None
        diff=[(b-a)&0xffffffff for a,b in zip(previous,current)];total=sum(diff)
        return 100*(total-diff[2])/total if total else None

def atomic(path, data):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    tmp.replace(path)

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def geometry(level, out):
    data = level.read_bytes()
    if len(data) < 104 or data[:4] != b'SHR7':
        raise ValueError('Not a current SHR7 level')
    co = struct.unpack_from('<I', data, 92)[0]
    h = struct.unpack_from('<4s3f8I', data, co)
    if h[0] != b'COL1': raise ValueError('Missing COL1')
    ox, oz, cell = h[1:4]
    w, height, nt, nb, nc, ns = h[4:10]
    groups = [array.array('f') for _ in range(4)]
    def tri(group, a, b, c, color):
        for p in (a,b,c): groups[group].extend((*p,*color))
    def box(c, axes, half, color, group=1):
        v=[]
        for i in range(8):
            v.append([c[k]+sum(axes[j][k]*half[j]*(1 if i&(1<<j) else -1) for j in range(3)) for k in range(3)])
        for ids, light in [((0,1,3,2),.7),((4,6,7,5),.8),((0,4,5,1),.6),((2,3,7,6),1),((0,2,6,4),.85),((1,5,7,3),.75)]:
            a,b,c,d=[v[i] for i in ids];col=[x*light for x in color]
            tri(group,a,b,c,col);tri(group,a,c,d,col)
    p=co+48
    for _ in range(nt):
        v=struct.unpack_from('<12f',data,p);p+=48
        ny=v[10];light=.65+.35*abs(ny)
        color=(.30,.37,.40) if ny>.5 else (.23,.29,.34)
        tri(0,v[:3],v[3:6],v[6:9],[x*light for x in color])
    for _ in range(nb):
        v=struct.unpack_from('<16f',data,p);p+=64
        foliage=v[15]==1
        box(v[:3],[v[3:6],v[6:9],v[9:12]],v[12:15],(.25,.53,.34) if foliage else (.43,.49,.52),2 if foliage else 1)
    for _ in range(nc):
        v=struct.unpack_from('<8fI3f',data,p);p+=48
        c=v[:3];axis=v[3:6];r,hl,flat=v[6:9];foliage=v[9]==1
        # Low polygon visual only; native physics uses the exact capsule query.
        ref=(1,0,0) if abs(axis[0])<.8 else (0,1,0)
        cross=lambda a,b:(a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
        u=cross(axis,ref);n=math.sqrt(sum(x*x for x in u));u=[x/n for x in u];vv=cross(axis,u)
        rings=[]
        if flat and hl>0:
            dims=[(-hl,0),(-hl,r),(hl,r),(hl,0)]
        else:
            dims=[(-hl-r,0),(-hl-r*.707,r*.707),(-hl,r),(hl,r),(hl+r*.707,r*.707),(hl+r,0)]
        for y,rr in dims:
            rings.append([[c[k]+axis[k]*y+rr*(u[k]*math.cos(a*math.tau/12)+vv[k]*math.sin(a*math.tau/12)) for k in range(3)] for a in range(12)])
        color=(.25,.53,.34) if foliage else (.43,.49,.52);g=2 if foliage else 1
        for a,b in zip(rings,rings[1:]):
            for i in range(12):
                j=(i+1)%12;col=[x*(.7+.3*i/12) for x in color]
                tri(g,a[i],b[i],b[j],col);tri(g,a[i],b[j],a[j],col)
    for _ in range(ns):
        ax,az,bx,bz,nx,nz,y0,y1=struct.unpack_from('<8f',data,p);p+=32
        a=(ax,y0,az);b=(bx,y0,bz);c=(bx,y0+45,bz);d=(ax,y0+45,az)
        tri(3,a,b,c,(.85,.27,.20));tri(3,a,c,d,(.85,.27,.20))
    counts=[len(g)//6 for g in groups]
    with out.open('wb') as f:
        for g in groups:
            if os.sys.byteorder != 'little':g.byteswap()
            g.tofile(f)
    return dict(counts=counts, bounds=[ox,oz,w*cell,height*cell], triangles=nt,boxes=nb,capsules=nc,boundaries=ns)

class Run:
    def __init__(self,a):
        self.args=a;self.lock=threading.Lock();self.save_lock=threading.Lock();self.frame=None;self.events=collections.deque(maxlen=100)
        self.finished=False;self.returncode=None;self.token=secrets.token_hex(24);self.error=None
        self.started=time.monotonic();self.seen=0
        self.metrics=dict(cores=os.cpu_count(),systemCpu=None,physicsCpu=None,rssMiB=None)
        self.metric_history=collections.deque(maxlen=60)
        self.out=ROOT/'build/sandbox/runs'/ (time.strftime('%Y%m%d-%H%M%S')+'-'+secrets.token_hex(3))
        self.out.mkdir(parents=True)
        self.mesh=geometry(a.level,self.out/'scene.bin')
        binary=self.out/'swarm'  # Keep the exact executable for this run's replay.
        subprocess.run(['cc','-std=c99','-O2','-Wall','-Wextra','-Wno-unused-parameter',str(HERE/'sandbox.c'),*[str(p) for p in ENGINE],'-lm','-o',str(binary)],check=True)
        cmd=[str(binary),'--level',str(a.level),'--cars',str(a.cars),'--seed',str(a.seed)]
        if a.roads:cmd += ['--roads',str(a.roads)]
        self.meta=dict(command=cmd,seed=a.seed,cars=a.cars,level=str(a.level),created=time.strftime('%Y-%m-%dT%H:%M:%S%z'),
                       hashes={str(p.relative_to(ROOT) if p.is_relative_to(ROOT) else p):sha(p) for p in
                               [a.level,binary,HERE/'sandbox.c',HERE/'cartest.c',*ENGINE]+([a.roads] if a.roads else [])},
                       notes=['Journal stores one in 60 display frames plus every event; replay needs binary, seed, fleet, arguments and matching level/roads', 'Mac CPU timings are not PSP predictions','Seeded surfaces do not establish access from the player spawn',
                              'carHitCar currently resolves horizontal contacts; dynamic roof landings are not implemented',
                              'Four .con parameter sets; the current engine still uses famil_v chassis dimensions for all cars',
                              'Observations require replay; hitting a known wall is not itself a defect'])
        atomic(self.out/'manifest.json',self.meta)
        self.log=(self.out/'native.log').open('w')
        self.proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.log,text=True,bufsize=1)
        self.collector=threading.Thread(target=self.collect,daemon=True);self.collector.start()
        threading.Thread(target=self.limit,daemon=True).start()
        threading.Thread(target=self.measure,daemon=True).start()
    def measure(self):
        try:meter=MacMeter()
        except Exception as e:self.metrics['error']=str(e);return
        lastTime=time.monotonic();lastCpu=None;lastTick=None
        while not self.finished:
            try:
                system=meter.sample();currentTime=time.monotonic();frame=self.frame
                cpu=frame.get('cpuSeconds') if frame else None
                rate=None if cpu is None or lastCpu is None else max(0,100*(cpu-lastCpu)/(currentTime-lastTime))
                tick=frame.get('tick') if frame else None
                steps=None if tick is None or lastTick is None else tick-lastTick
                rss=subprocess.check_output(['/bin/ps','-o','rss=','-p',str(self.proc.pid)+','+str(os.getpid())],text=True)
                self.metrics=dict(cores=os.cpu_count(),systemCpu=system,physicsCpu=rate,rssMiB=sum(int(x) for x in rss.split())/1024,
                                  sampledAt=time.time(),loadAverage=os.getloadavg()[0],tick=tick,
                                  actualRate=None if steps is None else steps/60/(currentTime-lastTime),
                                  stepCpuMs=None if not steps or cpu is None or lastCpu is None else (cpu-lastCpu)*1000/steps)
                self.metric_history.append(self.metrics)
                with (self.out/'metrics.ndjson').open('a') as log:log.write(json.dumps(self.metrics)+'\n')
                lastTime=currentTime;lastCpu=cpu;lastTick=tick
            except Exception as e:self.metrics['error']=str(e)
            time.sleep(1)
    def collect(self):
        size=0
        try:
            with (self.out/'frames.ndjson').open('w') as trace, (self.out/'events.ndjson').open('w') as events:
                for line in self.proc.stdout:
                    obj=json.loads(line)
                    if obj['type']=='frame':
                        if not obj['cars']:raise ValueError('empty fleet')
                        with self.lock:self.frame=obj;self.seen+=1
                    else:
                        with self.lock:self.events.append(obj)
                        events.write(line);events.flush()
                    if obj['type']!='frame' or self.seen%60==1:
                        trace.write(line);trace.flush();size+=len(line)
                    if self.seen and self.seen%900==0:self.save()
                    if size>256*1024*1024:self.command('stop')
                self.returncode=self.proc.wait()
        except Exception as e:
            self.error=str(e);self.proc.terminate();self.returncode=self.proc.wait()
        finally:
            self.finished=True;self.log.close();self.save()
    def limit(self):
        while not self.finished:
            time.sleep(1)
            if time.monotonic()-self.started>self.args.minutes*60:
                self.command('stop');return
    def command(self,cmd):
        if self.finished:return
        try:self.proc.stdin.write(cmd+'\n');self.proc.stdin.flush()
        except (BrokenPipeError,ValueError):pass
    def save(self):
        with self.save_lock:
            atomic(self.out/'summary.json',dict(frame=self.frame,finished=self.finished,returncode=self.returncode,error=self.error,
                  frames=self.seen,wallSeconds=time.monotonic()-self.started,metrics=self.metrics,metricHistory=list(self.metric_history),
                  manifest='manifest.json',result='observations, not an all-level pass'))
    def state(self):
        with self.lock:return dict(runId=self.out.name,frame=self.frame,events=list(self.events)[-24:],metrics=self.metrics,campaign=campaign_status(),finished=self.finished,error=self.error,returncode=self.returncode)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--level',type=Path,default=ROOT/'build/level.shr');ap.add_argument('--roads',type=Path)
    ap.add_argument('--cars',type=int,default=64);ap.add_argument('--seed',type=int,default=7)
    ap.add_argument('--port',type=int,default=8794);ap.add_argument('--minutes',type=float,default=30)
    ap.add_argument('--reuse',action='store_true',help='Reuse an existing sandbox at the selected port')
    ap.add_argument('--open',action='store_true',help='Open the live view in the default browser')
    a=ap.parse_args();a.level=a.level.resolve();a.roads=a.roads.resolve() if a.roads else None
    if not 1<=a.cars<=1024 or not 0<a.minutes<=240:ap.error('cars 1..1024; minutes >0 and <=240')
    if a.reuse and a.port:
        try:
            with urlopen(f'http://127.0.0.1:{a.port}/config',timeout=2) as response:existing=json.load(response)
        except (OSError,ValueError):existing={}
        if existing.get('app')=='shar-physics-sandbox':
            print(f'LIVE http://127.0.0.1:{a.port}\nEVIDENCE {existing["path"]}',flush=True)
            if a.open:subprocess.run(['open',f'http://127.0.0.1:{a.port}'],check=False)
            return
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def allowed(self):
            return self.headers.get('Host') in (f'127.0.0.1:{a.port}',f'localhost:{a.port}')
        def respond(self,data,mime='application/json',code=200):
            if not isinstance(data,bytes):data=json.dumps(data,ensure_ascii=False).encode()
            self.send_response(code);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(data)))
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers()
            try:self.wfile.write(data)
            except (BrokenPipeError,ConnectionResetError):pass
        def do_GET(self):
            if not self.allowed():return self.respond({'error':'host'},code=403)
            path=urlparse(self.path).path
            if path=='/':return self.respond((HERE/'sandbox.html').read_bytes(),'text/html; charset=utf-8')
            if path=='/scene.bin':return self.respond((run.out/'scene.bin').read_bytes(),'application/octet-stream')
            if path=='/config':return self.respond(dict(app='shar-physics-sandbox',runId=run.out.name,mesh=run.mesh,token=run.token,path=str(run.out),seed=a.seed,cars=a.cars,minutes=a.minutes))
            if path=='/state':return self.respond(run.state())
            if path=='/report':
                run.save();return self.respond(dict(manifest=run.meta,summary=json.loads((run.out/'summary.json').read_text()),events=list(run.events),campaign=campaign_status()))
            if path=='/favicon.ico':return self.respond(b'','image/x-icon',204)
            return self.respond({'error':'not found'},code=404)
        def do_POST(self):
            if not self.allowed() or self.headers.get('X-Sandbox')!=run.token:return self.respond({'error':'token'},code=403)
            if self.path!='/control':return self.respond({'error':'not found'},code=404)
            try:
                n=int(self.headers.get('Content-Length','0'))
                if not 0<n<256:raise ValueError()
                obj=json.loads(self.rfile.read(n));cmd=obj['command']
                if cmd not in ('pause 0','pause 1','speed 1','speed 4','speed 20','stop','stop campaign'):raise ValueError()
            except (ValueError,KeyError):return self.respond({'error':'command'},code=400)
            if cmd=='stop campaign':
                state=campaign_status()
                if state and state.get('path'):(Path(state['path'])/'STOP').touch()
            else:run.command(cmd)
            return self.respond({'ok':True})
    # Reserve the address before compiling or spawning any simulation.
    server=http.server.ThreadingHTTPServer(('127.0.0.1',a.port),Handler)
    a.port=server.server_address[1]
    try:run=Run(a)
    except BaseException:server.server_close();raise
    def stop(*_):
        run.command('stop')
        try:run.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:run.proc.terminate();run.proc.wait(timeout=5)
        run.collector.join(timeout=5);run.save()
        raise SystemExit(0)
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    print(f'LIVE http://127.0.0.1:{a.port}\nEVIDENCE {run.out}',flush=True)
    if a.open:subprocess.run(['open',f'http://127.0.0.1:{a.port}'],check=False)
    try:server.serve_forever()
    finally:run.command('stop');server.server_close()

if __name__=='__main__':main()
