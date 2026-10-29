"""Final rendered eye versus the real parked bus hull, after both camera guards.
The former driving scene stays above the roof and cannot be a negative control.
Headless PPSSPP only; CAMCARS_TAG keeps earlier evidence intact.
"""
import hashlib,json,os,re,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
DATA=Path(os.environ.get('SCEN_ROOT','/Users/USER/Downloads/shar-psp'))
SCEN=Path.home()/'.claude/skills/shar-level-polish/scripts/scen.py'
TAG=os.environ.get('CAMCARS_TAG','camcars_final')

def scen(old):
    lines=['flag carcamlog','wait 3']
    if old: lines += ['flag camcarsold 1','flag camsafeold 1']
    return '\n'.join(lines+['scene bus_foot','foot 289.5 178 -1.5708','wait 3','shot cam','wait 1','end'])+'\n'

def run(eboot,old):
    name=TAG+('_red' if old else '_green')
    with tempfile.NamedTemporaryFile('w',suffix='.txt',delete=False) as f:
        f.write(scen(old)); path=f.name
    r=subprocess.run([sys.executable,str(SCEN),name,path],cwd=DATA,
        env=dict(os.environ,SCEN_EBOOT=str(eboot)),capture_output=True,text=True,timeout=300)
    p=DATA/'build/twins/scen/full'/name/'smoke.txt'
    text=p.read_text(errors='replace') if p.exists() else ''
    if r.returncode or 'END' not in text.split(): raise RuntimeError('scenario did not finish: '+r.stdout+r.stderr)
    rows=[dict(re.findall(r'(\w+)=(\S+)',l)) for l in text.splitlines() if l.startswith('CAM_EYE ') and 'sc=bus_foot ' in l]
    if len(rows)<4: raise RuntimeError('too few final eye samples')
    if old and not all(x.get('carsold')=='1' and x.get('safeold')=='1' for x in rows): raise RuntimeError('negative guards not disabled')
    return rows,p

def main():
    eb=Path(sys.argv[1] if len(sys.argv)>1 else ROOT/'viewer/build/EBOOT.PBP').resolve()
    red,rp=run(eb,True);green,gp=run(eb,False)
    nr=sum(int(x['incar']) for x in red); ng=sum(int(x['incar']) for x in green)
    print(f'red: final eye INSIDE actual hull {nr}/{len(red)}; green: {ng}/{len(green)}')
    ok=nr>=4 and ng==0
    out=DATA/'build/codex-terminal/f3';out.mkdir(parents=True,exist_ok=True)
    (out/'camera-manifest.json').write_text(json.dumps(dict(eboot=str(eb),sha256=hashlib.sha256(eb.read_bytes()).hexdigest(),red=str(rp),green=str(gp),red_samples=nr,green_samples=ng,scenario=scen(False),seed='original deterministic start',command='CAMCARS_TAG='+TAG+' python tests/camera/cam_cars.py EBOOT',PSP='not deployed'),indent=2)+'\n')
    print('PASS' if ok else 'FAIL');return 0 if ok else 1
if __name__=='__main__':sys.exit(main())
