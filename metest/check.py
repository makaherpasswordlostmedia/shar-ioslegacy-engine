#!/usr/bin/env python3
"""Host semantic proof + native ME code closure. Real speed/correctness PASS is PSP-only."""
import hashlib,importlib.util,json,os,struct,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/metest/check';OUT.mkdir(parents=True,exist_ok=True)
def run(args,**kwargs):return subprocess.run(args,cwd=ROOT,text=True,capture_output=True,check=True,**kwargs)
# Frozen pre-change maths, from the task's starting commit; no candidate-as-own-reference
old=run(['git','show','f92d065:viewer/mixdsp.h']).stdout
(OUT/'previous.h').write_text(old)
(OUT/'previous.c').write_text('#include "previous.h"\nvoid previousMix(void*j){mixDspRun(j);}\nvoid previousPoint(const int*l,const int*r,const void*p,int*a,int*b){MixJob j={0};for(int i=0;i<3;i++)j.listener[i]=l[i];for(int i=0;i<2;i++)j.right[i]=r[i];mixSpatialGains(&j,p,a,b);}\n')
run(['cc','-O2','-ffp-contract=off','-DFXD_EXPF=expf','metest/host.c','viewer/fxdsp.c',str(OUT/'previous.c'),'-lm','-o',str(OUT/'host')])
green=run([str(OUT/'host')]);red=subprocess.run([str(OUT/'host'),'--red'],text=True,capture_output=True)
assert red.returncode==1 and 'negative=1' in red.stdout,'negative must fail'
run(['cc','-O2','metest/boot_host.c','-o',str(OUT/'boot')])
boot=run([str(OUT/'boot')]);bootred=subprocess.run([str(OUT/'boot'),'--no-writeback'],text=True,capture_output=True)
assert bootred.returncode==1 and 'failures=1000' in bootred.stdout,'missing publication must fail'
run(['cc','-O2','metest/controls_host.c','-o',str(OUT/'controls')])
controls=run([str(OUT/'controls')]);controlsred=subprocess.run([str(OUT/'controls'),'--old-sweep-overwrite'],text=True,capture_output=True)
assert controlsred.returncode==1,'old manual overwrite must fail'
run(['cc','-O2','metest/output_host.c','-o',str(OUT/'output')]);output=run([str(OUT/'output')])
run(['cc','-O2','-DPCM_OUTPUT_BUFFERS=1','metest/output_host.c','-o',str(OUT/'output_red')]);outputred=subprocess.run([str(OUT/'output_red')],capture_output=True,text=True)
assert outputred.returncode==1 and 'overwritten-queued=999' in outputred.stdout,'single queued PCM buffer must fail'
run(['cc','-O2','-DME_FX_MAX_ELEMENTS=400','metest/output_host.c','-o',str(OUT/'budget_red')]);budgetred=subprocess.run([str(OUT/'budget_red')],capture_output=True,text=True)
assert budgetred.returncode==1 and 'FX-budget=FAIL' in budgetred.stdout,'unguarded 400 FX must fail'
run(['cc','-O2','metest/tone_host.c','-lm','-o',str(OUT/'tone')]);tone=run([str(OUT/'tone')])
tonered=subprocess.run([str(OUT/'tone'),'--reset-phase'],capture_output=True,text=True)
assert tonered.returncode==1 and 'negative=1' in tonered.stdout,'reset PCM tone phase must fail'
# Real-time contract: screen and logging are absent from the producer, even in
# its failure path. Breaking this guard deliberately must be rejected.
def producer_ok(source):
    worker=source.split('static int auditionAudio(',1)[1].split('static void audition(void)',1)[0]
    bad=('pspDebugScreen','logLine(', 'save(', 'sceIo')
    failure=source.split('static int fail(',1)[1].split('// Total wall latency',1)[0]
    return not any(x in worker for x in bad) and failure.index('if(audioActive)')<failure.index('logLine(')
source=(ROOT/'metest/main.c').read_text()
assert producer_ok(source),'audio producer contains blocking UI or file I/O'
assert not producer_ok(source.replace('fpuThreadInit();AudView','pspDebugScreenClear();fpuThreadInit();AudView')),'negative UI producer must fail'
spec=importlib.util.spec_from_file_location('gate',ROOT/'tests/me/run.py');gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
kernel=gate.objdump_funcs(ROOT/'viewer/me/sharme.elf');kc,ke=gate.me_code_errs(kernel);assert not ke,ke
pub=kernel['module_start'];indices=[i for i,(_,op,arg) in enumerate(pub) if op=='jal' and '<sceKernelDcacheWritebackRange>' in arg]
assert any(any(op=='sw' and ',0(' in arg for _,op,arg in pub[max(0,i-6):i]) and any(op=='sync' for _,op,_ in pub[i+1:i+4]) for i in indices),'native startup lacks result store/writeback/sync publication'
user=gate.objdump_funcs(ROOT/'build/metest/native/sharme_test');assert user,'missing native ELF'
uc,ue=gate.me_code_errs(user,'meGameTask','meGameFinish');assert not ue,ue
game=gate.objdump_funcs(ROOT/'viewer/build/sharview');gc,ge=gate.me_code_errs(game,'meGameTask','meGameFinish');assert not ge,ge
fin=' '.join(f'{op} {arg}' for _,op,arg in user['meGameFinish'])
assert '0x8830' in fin and '1216' in fin and '-567' in fin and 'jr' in fin,fin
assert any('mixSpatialBatchRun' in n or 'mixPointGains' in n for n in uc),'spatial code absent'
# Native unsafe build must actually fail the instruction audit (division trap / libc call)
run([str(ROOT/'pspdev/bin/psp-gcc'),'-O2','-G0','-fno-pic','-fno-math-errno','-fsingle-precision-constant','-c','viewer/me_gametask.c','-o',str(OUT/'unsafe.o')])
unsafe=gate.objdump_funcs(OUT/'unsafe.o');unsafe['meTask']=unsafe['meGameTask'];unsafe['meSafeTaskMistFinish']=unsafe['meGameFinish']
unsafeErr=gate.me_code_errs(unsafe)[1];assert any('break' in e or 'memset' in e for e in unsafeErr),unsafeErr
pbp=(ROOT/'build/metest/native/EBOOT.PBP').read_bytes();header=struct.unpack_from('<4s9I',pbp);assert header[0]==b'\0PBP'
offsets=header[2:];assert offsets[0]==40 and list(offsets)==sorted(offsets) and offsets[-1]==len(pbp)
sfo=pbp[offsets[0]:offsets[1]];assert b'SHAR ME Test\0' in sfo and offsets[6]<offsets[7]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
result=dict(host=green.stdout.strip(),negative=red.stdout.strip(),boot_publication=boot.stdout.strip(),boot_negative=bootred.stdout.strip(),controls=controls.stdout.strip(),controls_negative=controlsred.stdout.strip(),pcm=output.stdout.strip(),pcm_negative=outputred.stdout.strip(),budget_negative=budgetred.stdout.strip(),tone=tone.stdout.strip(),tone_negative=tonered.stdout.strip(),producer_io='PASS no screen or file I/O; inserted UI negative rejected',kernel_functions=len(kc),user_functions=len(uc),game_functions=len(gc),hardware='v1.5 real PSP10/10; PCM4447 empty0 clipped0 on ME/CPU; v1.6 stereo music listening pending',closures='PASS game/test/kernel no external/syscall/gp/traps; FPU only FX/libm',unsafe_negative=unsafeErr[:5],eboot_sha256=sha(ROOT/'build/metest/native/EBOOT.PBP'),prx_sha256=sha(ROOT/'viewer/me/sharme.prx'),game_eboot_sha256=sha(ROOT/'viewer/build/EBOOT.PBP'),pbp='PASS title/offsets/nonempty executable')
(OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
