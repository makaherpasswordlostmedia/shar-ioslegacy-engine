#!/usr/bin/env python3
"""Real street tracks through the shared DSP; 2D negative control must fail."""
import argparse, subprocess
from pathlib import Path

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--pack',default='build/audio/')
    ap.add_argument('--out',default='build/street-spatial')
    a=ap.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    for name,flags,expected in [('green',[],0),('red',['-DSND_STREET_SPATIAL_OLD=1'],1)]:
        cmd=['cc','-std=c11','-O2','-DAUDIO_HOST',*flags,'-I','viewer','tests/sound/street_spatial.c','viewer/sound.c','-lm','-o',str(out/name)]
        subprocess.run(cmd,check=True)
        r=subprocess.run([str(out/name),a.pack],capture_output=True,text=True)
        (out/(name+'.log')).write_text(r.stdout+r.stderr)
        print(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr)
        if r.returncode!=expected:raise SystemExit('Unexpected street spatial gate result')
        if name=='red' and 'checks=26 failures=12' not in r.stdout:raise SystemExit('Negative did not reach the spatial checks')
    print('PASS real street tracks and 2D negative control')

if __name__=='__main__':main()
