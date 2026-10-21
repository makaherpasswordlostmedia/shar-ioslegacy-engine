#!/usr/bin/env python3
"""Run the director's saved scenarios verbatim against one immutable staged EBOOT.

The comparison contract is p95 <= reference+1ms, END and zero missed/memory
errors. Ordinary smoke failures are also retained, including old load spikes.
"""
import argparse,csv,hashlib,json,math,os,re,subprocess,sys
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
import smoke_report as SM
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,result):
 temp=p.with_suffix('.tmp');temp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');os.replace(temp,p)
def compare(ref,ended,stats):
 failures=[]
 if not ended:failures.append('нет END')
 if stats is None:return failures+['нет STAT сцены']
 p95=stats.get('p95',float('nan'))
 if not math.isfinite(p95) or p95>float(ref['p95 мс'])+1:failures.append('p95 хуже эталона +1мс')
 for key in ('missed','memfail','allocfail','readerr','gebad','geskip','missvis'):
  if key not in stats:failures.append('нет счётчика '+key)
  elif stats[key]!=0:failures.append(key+'='+str(stats[key]))
 if stats.get('timeout'):failures.append('TIMEOUT')
 return failures
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--library',type=Path,default=ROOT/'knowledge/twins_library');ap.add_argument('--stage',type=Path,required=True);ap.add_argument('--out',type=Path);ap.add_argument('--check-only',action='store_true');a=ap.parse_args()
 cat=a.library/'СЕРИЯ_РЕГРЕССА.tsv';refs=list(csv.DictReader(cat.open(),delimiter='\t'));assert len(refs)==36
 groups={}
 for r in refs:
  scn=a.library/r['сценарий (файл)'];assert scn.is_file(),scn
  groups.setdefault(str(scn),[]).append(r)
  # Every named scene must really occur in its archived scenario.
  assert r['сцена'] in re.findall(r'^scene\s+(\S+)',scn.read_text(),re.M),(r['сцена'],scn)
 if a.check_only:print(f'PASS catalog36 / {len(groups)} unique immutable scenarios');return 0
 stage=a.stage.resolve();eb=stage/'EBOOT.PBP';identity=sha(eb)
 out=a.out or ROOT/'build/twins/regress'/datetime.now().strftime('%Y%m%d-%H%M%S');out.mkdir(parents=True,exist_ok=True)
 result=dict(eboot_sha256=identity,catalog_sha256=sha(cat),criteria='p95<=reference+1ms; END; missed/read/memory/GE/load counters0',rows=[],runs=[])
 for i,(path,rs) in enumerate(groups.items()):
  assert sha(eb)==identity,'staged EBOOT changed during series'
  scn=Path(path);scenario_sha=sha(scn);env=os.environ.copy();env.update(SMOKE_HEADLESS='1',SMOKE_SCN=str(scn.resolve()),SHIP_LEVELS='2 3 4 5 6 7')
  log=out/f'{i:02d}.txt'
  with log.open('w') as f:run=subprocess.run(['bash','tools/smoke.sh',str(stage)],cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT)
  matched=re.search(r'отчёт: (.+?)/summary.txt',log.read_text())
  runpath=(ROOT/matched.group(1)) if matched else None
  ended,_,stats,_=SM.parse(runpath) if runpath else (False,{}, {},[])
  assert sha(scn)==scenario_sha,'archived scenario changed during run'
  result['runs'].append(dict(scenario=path,scenario_sha256=scenario_sha,run=str(runpath),smoke_rc=run.returncode,log=str(log)))
  for ref in rs:
   st=stats.get(ref['сцена']);bad=compare(ref,ended,st)
   row=dict(level=ref['уровень'],scene=ref['сцена'],reference=ref['эталонный прогон'],reference_p95=float(ref['p95 мс']),stats=st,failures=bad,ok=not bad,run=str(runpath));result['rows'].append(row)
   print(('PASS' if row['ok'] else 'FAIL')+f' L{row["level"]} {row["scene"]}: '+str(bad),flush=True)
  result['ok']=len(result['rows'])==36 and all(x['ok'] for x in result['rows'])
  save(out/'result.json',result)
 result['ok']&=sha(eb)==identity
 save(out/'result.json',result)
 print(f'{"PASS" if result["ok"] else "FAIL"}: {sum(x["ok"] for x in result["rows"])}/36; raw smoke failures '+str(sum(x['smoke_rc']!=0 for x in result['runs'])))
 return 0 if result['ok'] else 1
if __name__=='__main__':raise SystemExit(main())
