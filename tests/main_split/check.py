#!/usr/bin/env python3
"""Structural-only split: exact source, preprocessed tokens and actual PSP object sections."""
import argparse,hashlib,json,re,shlex,subprocess,sys,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from main_source import read_main
ap=argparse.ArgumentParser();ap.add_argument('--base-ref',default='23f94bc');a=ap.parse_args()
out=ROOT/'build/main278';out.mkdir(parents=True,exist_ok=True)
ref=subprocess.check_output(['git','rev-parse',a.base_ref],cwd=ROOT,text=True).strip()
legacy=subprocess.check_output(['git','show',ref+':viewer/main.c'],cwd=ROOT,text=True)
current=read_main(ROOT/'viewer/main.c');assert current==legacy,'assembled source changed'
(out/'legacy.c').write_text(legacy)
# Both compiled routes are the actual main assembly, with identical deterministic date/time.
f=(ROOT/'viewer/build/CMakeFiles/sharview.dir/flags.make').read_text()
flags=shlex.split(re.search(r'^C_FLAGS = (.+)',f,re.M).group(1))+shlex.split(re.search(r'^C_DEFINES = (.+)',f,re.M).group(1))
flags+=['-I'+str(ROOT/'viewer'),'-D__DATE__="Oct 09 2026"','-D__TIME__="00:00:00"']
cc=ROOT/'pspdev/bin/psp-gcc';objcopy=ROOT/'pspdev/bin/psp-objcopy';objdump=ROOT/'pspdev/bin/psp-objdump'
lexer=re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[A-Za-z_][A-Za-z_0-9]*|(?:[0-9][A-Za-z0-9_.]*|\.[0-9][A-Za-z0-9_.]*)|\S')
def compile_route(name,old):
 args=[str(cc),*flags,'-DMAIN_MODULES_OLD='+str(old),str(ROOT/'viewer/main.c')]
 r=subprocess.run([*args,'-E','-P'],capture_output=True,text=True,check=True);(out/(name+'.i')).write_text(r.stdout)
 toks=lexer.findall(r.stdout)
 subprocess.run([*args,'-c','-o',str(out/(name+'.o'))],stdout=subprocess.DEVNULL,stderr=(out/(name+'.stderr')).open('w'),check=True)
 return toks
old=compile_route('old',1);new=compile_route('new',0);assert old==new,'preprocessed tokens differ'
sections=['.text','.data','.rodata','.sdata','.bss','.sbss','.lit4','.lit8']
sections_found={}
for nm in ['old','new']:
 h=subprocess.check_output([str(objdump),'-h',str(out/(nm+'.o'))],text=True)
 sections_found[nm]={m.group(1):int(m.group(2),16) for m in re.finditer(r'^\s*\d+\s+(\S+)\s+([0-9a-f]+)\s',h,re.M) if m.group(1) in sections}
assert sections_found['old']==sections_found['new'],'runtime section sizes differ'
hashes={}
for sec in sections_found['old']:
 if sec in ['.bss','.sbss']:continue
 for nm in ['old','new']:
  subprocess.run([str(objcopy),'-O','binary','--only-section='+sec,str(out/(nm+'.o')),str(out/(nm+sec+'.bin'))],check=True)
 b=(out/('old'+sec+'.bin')).read_bytes();assert b==(out/('new'+sec+'.bin')).read_bytes(),sec+' differs'
 hashes[sec]=hashlib.sha256(b).hexdigest()
r=[]
for nm in ['old','new']:
 cmd=[str(objdump),'-r',str(out/(nm+'.o'))]
 for sec in sections:cmd+=['-j',sec]
 text=subprocess.check_output(cmd,text=True,stderr=subprocess.DEVNULL);r.append(text.split('file format',1)[1])
assert r[0]==r[1],'runtime relocations differ'
# Actual one-constant corruption must fail BOTH source and compiled-code comparisons.
mutant=legacy.replace('#define LOD_DIST 50.f','#define LOD_DIST 51.f');assert mutant!=legacy
(out/'legacy.c').write_text(mutant)
red=compile_route('red',1);assert red!=new,'token negative missed'
subprocess.run([str(objcopy),'-O','binary','--only-section=.text',str(out/'red.o'),str(out/'red.text.bin')],check=True)
assert (out/'red.text.bin').read_bytes()!=(out/'new.text.bin').read_bytes(),'code negative missed'
(out/'legacy.c').write_text(legacy)
env=os.environ.copy();env['SHIP_LEVELS']='2 3 4 5 6 7'
shipping=subprocess.check_output(['bash','tools/ship_files.sh'],cwd=ROOT,env=env,text=True).splitlines()
base=subprocess.check_output(['bash','tools/ship_files.sh'],cwd=ROOT.parent/'shar-psp',env=env,text=True).splitlines()
assert shipping==base,'asset manifest changed'
env['MAIN_FILES_OLD']='1';bad=subprocess.check_output(['bash','tools/ship_files.sh'],cwd=ROOT,env=env,text=True).splitlines();assert bad!=base,'missing-module packaging negative missed'
report=dict(base=ref,source_sha256=hashlib.sha256(current.encode()).hexdigest(),source_bytes=len(current.encode()),tokens=len(new),sections=sections_found['new'],section_sha256=hashes,relocations_sha256=hashlib.sha256(r[0].encode()).hexdigest(),manifest_files=len(shipping),manifest_old_files=len(bad),negative=['LOD token changed','actual PSP text changed','missing module manifest changed'],status='PASS')
(out/'proof.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
