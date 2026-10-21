#!/usr/bin/env python3
"""Full decode -> measurement -> independent expectations, RED first, GREEN second.
Fixtures use a local extracted icon and synthetic backgrounds/audio, kept only in build/ps2ref.
Never mark original-game acceptance.
"""
import json
from pathlib import Path
import subprocess
import sys
import wave
import numpy as np
from PIL import Image
from p2m2 import write, IDLE
from ui_templates import extract

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'build/ps2ref/golden-e2e'


def main():
    OUT.mkdir(parents=True,exist_ok=True);extract(OUT/'templates')
    icon=Image.open(OUT/'templates/action.png').convert('RGBA')
    rate=16000;audio=np.zeros(rate,np.float32);audio[4800:6400]=.2*np.sin(np.arange(1600)*2*np.pi*500/rate)
    with wave.open(str(OUT/'beep.wav'),'wb') as w:
        w.setparams((1,2,rate,rate,'NONE','not compressed'));w.writeframes((audio*32767).astype('<i2').tobytes())
    write(OUT/'input.p2m2',[IDLE]*50)
    expected=dict(positions=[dict(first_frame=0,last_frame=49,x=100,y=70,tolerance_px=3,min_score=.8)],sounds=[dict(from_s=.28,to_s=.32)])
    (OUT/'expected.json').write_text(json.dumps(expected))
    outcomes={}
    for kind in ('misplaced','silent','valid'):
        video=OUT/(kind+'.mp4')
        args=['ffmpeg','-y','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s','320x240','-r','50','-i','pipe:0','-i',str(OUT/'beep.wav'),
              '-c:v','libx264','-crf','16','-pix_fmt','yuv420p','-c:a','aac']
        if kind=='silent':args+=['-af','volume=0']
        p=subprocess.Popen(args+['-shortest',str(video)],stdin=subprocess.PIPE)
        for i in range(50):
            im=Image.new('RGB',(320,240),(35,43,48));im.paste(icon,(180 if kind=='misplaced' and i==25 else 100,70),icon)
            p.stdin.write(im.tobytes())
        p.stdin.close()
        if p.wait()!=0:raise RuntimeError('fixture encoding failed')
        cmd=[sys.executable,str(ROOT/'tools/ps2ref/golden_analyze.py'),'--video',str(video),'--input',str(OUT/'input.p2m2'),
             '--out',str(OUT/kind),'--expect',str(OUT/'expected.json')]
        r=subprocess.run(cmd,capture_output=True,text=True);(OUT/(kind+'.log')).write_text(r.stdout+r.stderr)
        outcomes[kind]=dict(exit=r.returncode,expected=0 if kind=='valid' else 1)
        print(kind,r.returncode,'expected',outcomes[kind]['expected'],flush=True)
    ok=all(r['exit']==r['expected'] for r in outcomes.values())
    (OUT/'gate.json').write_text(json.dumps(dict(ok=ok,outcomes=outcomes,original_game=False),indent=2)+'\n')
    return 0 if ok else 1


if __name__=='__main__':sys.exit(main())
