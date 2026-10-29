#!/usr/bin/env python3
"""Seven-level obstacle census. No game writes, no emulator, no network.
Every suspect retains its measured evidence, exact data hashes and reproduction.
"""
import argparse, collections, concurrent.futures, contextlib, hashlib, html, io, json, math, os, struct, subprocess, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'hit-and-run-web/tools'),str(Path(__file__).parent)]
from walls_map import code
ANCHORS={1:[],2:[],3:[],4:['K12-2'],5:[],6:['C7-4','D7-6','H7-8','H9-6','B7-6'],7:['J10-8']}
FAMILIES={'invisible':'прозрачная','curb':'бордюр','breakable':'несбиваемое','foliage':'куст','animation':'анимация','allowed':'разрешённая','visible':'видимая','step':'ступень'}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run(cmd,log,stdin=None):
    marker=Path(str(log)+'.done.json');marker.write_text(json.dumps({'ok':False}))
    with Path(log).open('w') as f:
        p=subprocess.run(list(map(str,cmd)),cwd=ROOT,text=True,input=stdin,stdout=f,stderr=subprocess.PIPE)
    Path(str(log)+'.stderr').write_text(p.stderr)
    if p.returncode:raise RuntimeError(f'{cmd[0]} rc={p.returncode}: {p.stderr[-800:]}')
    marker.write_text(json.dumps(dict(ok=True,command=list(map(str,cmd)),inputs={str(x):sha(x) for x in cmd if Path(str(x)).is_file()},output_sha=sha(log))))
def completed(log):
    marker=Path(str(log)+'.done.json')
    if not marker.exists():return False
    m=json.loads(marker.read_text())
    return m.get('ok') and m.get('output_sha')==sha(log) and all(Path(p).is_file() and sha(p)==h for p,h in m.get('inputs',{}).items())
def bounds(c):
    col='ABCDEFGHJKLM'.index(c[0]);row,sub=map(int,c[1:].split('-'));sx=(sub-1)%3;sz=(sub-1)//3
    return -700+100*col+100*sx/3,-700+100*(row-1)+100*sz/3,100/3

def names(level,lv):
    import prp2_export as P, psp_export as E, animobj_export as A
    with contextlib.redirect_stdout(io.StringIO()):
        sp=P.StateProps(level,E.GAME/'art',lambda f,m:[],lambda f,s:-1,verbose=False)
        prp=list(E.prop_entities([p.stem for p in P.level_files(E.GAME/'art',level)],E.GAME/'art'))+['coinShape_000']
        base=[dict(name=t['name'],kind=t.get('kind',0),bindex=t.get('bindex',0),cls=t.get('cls',0)) for t in sp.types]
        ao=A.AnimObjects(level,E.GAME/'art',sp,verbose=False)
    # Guard the source/type association against a different exported type order.
    b=lv.read_bytes();po=struct.unpack_from('<I',b,96)[0];so=po+struct.unpack_from('<I',b,po+32)[0]
    u=struct.unpack_from('<15I',b,so+4);off=64
    for n in (u[11],u[12],u[2]*40):off=(off+n+15)&~15
    matched={}
    for i,t in enumerate(base):
        if i>=u[0]:break
        kind,bi=struct.unpack_from('<HH',b,so+off+i*84+20);cls=b[so+off+i*84+24]
        if (kind,bi,cls)!=(t['kind'],t['bindex'],t['cls']):raise ValueError(f'L{level} SPR type {i} source order mismatch')
        matched[i]=t['name']
    aoff=po+struct.unpack_from('<I',b,po+52)[0];actor={}
    if b[aoff:aoff+4]==b'ANM1':
        n=struct.unpack_from('<I',b,aoff+8)[0]
        if n==len(ao.objs):
            for i,o in enumerate(ao.objs):
                actor[i]=f"{Path(o['file']).stem}/{o['name']}"
    return prp,matched,actor

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--minutes',type=float,default=.25);ap.add_argument('--procs',type=int,default=2);ap.add_argument('--out',type=Path);ap.add_argument('--reuse',action='store_true');ap.add_argument('--data-root',type=Path);ap.add_argument('--reference',type=Path,help='reuse per-level simulation seconds/seeds/cars for comparable counts');ap.add_argument('--levels',default='1,2,3,4,5,6,7');a=ap.parse_args()
    if not 1<=a.procs<=3:ap.error('--procs must be 1..3 (memory limit)')
    common=Path(subprocess.check_output(['git','rev-parse','--git-common-dir'],cwd=ROOT,text=True).strip());common=(ROOT/common).resolve().parent
    data=a.data_root or common/'build/qa-final-75226ea'
    out=(a.out or ROOT/'build/sandbox/walls_all'/time.strftime('%Y%m%d-%H%M%S')).resolve();out.mkdir(parents=True,exist_ok=True)
    previous=json.loads((out/'manifest.json').read_text()) if (out/'manifest.json').exists() else {}
    src=['car.c','col.c','props.c','stateprops.c','coins.c'];bins={}
    for tag,source in [('probe','obstacles_probe.c'),('props','obstacles_props.c')]:
        exe=out/('obstacles-'+tag);cmd=['cc','-std=c11','-O2','-DSKIN_HOST','-I','viewer','tools/cartest/'+source]+[('tools/cartest/obstacles_car.c' if tag=='probe' and s=='car.c' else 'viewer/'+s) for s in src]+(['viewer/animobj.c'] if tag=='probe' else [])+['-lm','-o',str(exe)]
        run(cmd,out/(tag+'-compile.txt'));bins[tag]=exe
    run(['cc','-std=c11','-O2','-DSKIN_HOST','-Iviewer','tests/bot_rules/anim_pose.c']+['viewer/'+s for s in src]+['viewer/animobj.c','-lm','-o',out/'anim-pose-check'],out/'pose-compile.txt')
    manifest=dict(commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),dirty=subprocess.check_output(['git','status','--porcelain','--','viewer','tools/cartest'],cwd=ROOT,text=True).strip(),sources={str(p.relative_to(ROOT)):sha(p) for p in list((ROOT/'tools/cartest').glob('obstacles*'))+[ROOT/'tools/cartest/walls.c']+[ROOT/'viewer'/s for s in src]+[ROOT/'viewer/animobj.c']},data_root=str(data),minutes=a.minutes,procs=a.procs)
    stable_props=all(previous.get('sources',{}).get(str(p.relative_to(ROOT)))==sha(p) for p in [ROOT/'viewer'/s for s in src]+[ROOT/'tools/cartest/obstacles_props.c'])
    if previous:(out/'manifest.previous.json').write_text(json.dumps(previous,ensure_ascii=False,indent=2))
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2));summaries=[];failed=[]
    for level in map(int,a.levels.split(',')):
        od=out/f'l{level}';od.mkdir(exist_ok=True);lv=data/('level.shr' if level==1 else f'l{level}/level.shr');roads=common/f'build/sandbox/roads-l{level}.bin'
        print(f'L{level}: CPU census',flush=True)
        try:
            from walls import SRC
            sm=json.loads((od/'swarm/manifest.json').read_text()) if (od/'swarm/manifest.json').exists() else {}
            reference=json.loads((a.reference/f'l{level}/swarm/manifest.json').read_text()) if a.reference else {}
            fixed=['--seconds',reference['secs'],'--cars',reference['cars'],'--seed0',reference['seeds'][0]] if reference else []
            if reference and len(reference['seeds'])!=a.procs:raise ValueError('reference process/seed count differs')
            stable_swarm=(not reference or sm.get('secs')==reference['secs']) and sm.get('levelSha')==sha(lv)[:16] and all(sm.get('sources',{}).get(p.name)==sha(p)[:16] for p in SRC)
            if not(a.reuse and stable_swarm and (od/'swarm/walls.json').exists()):run([sys.executable,ROOT/'tools/cartest/walls.py','--level',lv,'--level-id',level,'--roads',roads,'--procs',a.procs,'--minutes',a.minutes,'--out',od/'swarm',*fixed],od/'swarm.log')
            res=json.loads((od/'swarm/walls.json').read_text());prp,sp,actors=names(level,lv)
            targets=[]
            for cell in ANCHORS[level]:
                x,z,w=bounds(cell)
                for ix in range(3):
                    for iz in range(3):
                        for direction in range(4):
                            for speed in (40,90):targets.append(f'{x+(ix+.5)*w/3} {z+(iz+.5)*w/3} 0 {direction*1.5707963} {speed}')
            # Obtain the actual walkable ground height rather than assume sea level.
            # C probe performs the ground lookup; broad upper search selected by y=100.
            targets=[line.replace(' 0 ',' 100 ',1) for line in targets]
            if level==7:targets.append('155 286 3.3 1.5707963 20')
            modes=['foliage','animation','targets']
            speed_targets=[]
            if level==6:
                # Rob's exact speed ranges, in addition to the broad anchor grid.
                for cell,speeds in [('H7-8',(80,120)),('H9-6',(30,60))]:
                    x,z,w=bounds(cell)
                    for ix in range(3):
                        for iz in range(3):
                            for direction in range(4):
                                for speed in speeds:speed_targets.append(f'{x+(ix+.5)*w/3} {z+(iz+.5)*w/3} 100 {direction*1.5707963} {speed}')
                modes.append('targets-speeds')
                (od/'targets-speeds.txt').write_text('\n'.join(speed_targets)+'\n')
            for mode in modes:
                p=od/(mode+'.jsonl')
                if p.exists() and not completed(p) and not p.with_suffix('.previous.jsonl').exists():p.rename(p.with_suffix('.previous.jsonl'))
            (od/'targets.txt').write_text('\n'.join(targets)+'\n')
            with concurrent.futures.ThreadPoolExecutor(max_workers=a.procs) as ex:
                jobs=[ex.submit(run,[bins['probe'],lv,'targets' if mode=='targets-speeds' else mode],od/(mode+'.jsonl'),'\n'.join(speed_targets if mode=='targets-speeds' else targets)+'\n' if mode.startswith('targets') else None) for mode in modes if not(a.reuse and completed(od/(mode+'.jsonl')))]
                if not(a.reuse and stable_props and completed(od/'props.jsonl')):jobs.append(ex.submit(run,[bins['props'],lv],od/'props.jsonl'))
                for job in jobs:job.result()
            run([out/'anim-pose-check',lv],od/'pose.txt')
            records=[];coverage={'pose':{'result':(od/'pose.txt').read_text().splitlines()[-1]}}
            for mode in modes+['props']:
                rows=[json.loads(l) for l in (od/(mode+'.jsonl')).read_text().splitlines() if l.startswith('{')]
                coverage[mode]=dict(records=len(rows),statuses=dict(collections.Counter(r.get('status','observation') for r in rows)))
                for line in Path(str(od/(mode+'.jsonl'))+'.stderr').read_text().splitlines():
                    if line.startswith('{'):coverage[mode].update(json.loads(line))
                for row in rows:
                    if row['family']=='curb' and row.get('still',0)<.8:row['family']='step'
                    row['origin']='прицельный';row['probe']=mode;row['source']='';row['family']=FAMILIES[row['family']]
                    if mode=='props':
                        row['source']=(prp[row['type']] if row['kind']=='P' and row['type']<len(prp) else sp.get(row['type'],f"SPR type {row['type']}"))
                        if row['status']!='candidate':continue
                    elif row.get('actor',-1)>=0:row['source']=actors.get(row['actor'],f"ANM1 #{row['actor']}")
                    else:
                        t,i=row['ptype'],row['pidx'];ns=json.loads((od/'swarm/colnames.json').read_text());key={1:'box',2:'cyl'}.get(t)
                        row['source']='/'.join(str(x) for x in reversed(ns[key][i])) if key and i<len(ns[key]) else ('изгородь/граница №421' if t==3 else 'COL triangle')
                    row['repro']=f"{bins['probe' if mode!='props' else 'props']} {lv}"+(f" {'targets' if mode=='targets-speeds' else mode}" if mode!='props' else '')+(f' < {od}/{mode}.txt' if mode.startswith('targets') else '')+f" ; raw {mode}.jsonl"
                    row['nNat']=0;row['n']=1;row['evidence']=dict(row);records.append(row)
            for r in res['clusters']:
                r['origin']='дорога' if r.get('nNat') else 'случайный стресс';records.append(r)
            grouped={}
            for r in records:
                key=(r['family'],r.get('source'),int(r['x']//3),int(r['z']//3),r.get('actor',-1))
                if key not in grouped:r['samples']=[r.get('evidence',{})];grouped[key]=r
                else:grouped[key]['n']+=r.get('n',1);grouped[key]['samples'].append(r.get('evidence',{}))
            res.update(clusters=list(grouped.values()),coverage=coverage,level=level,levelSha=sha(lv),anchors=ANCHORS[level],data=str(lv),scope='Кандидаты для разбора; измерение не является приёмкой игры. Данные PSP 75226ea, до интеграции №445.')
            (od/'walls.json').write_text(json.dumps(res,ensure_ascii=False,indent=1))
            run([sys.executable,ROOT/'tools/cartest/walls_map.py',lv,od,'--title',f'L{level}'],od/'map.log')
            summaries.append((level,len(res['clusters']),coverage));print(f'L{level}: ready, {len(res["clusters"])} clusters',flush=True)
        except Exception as e:
            failed.append(dict(level=level,error=str(e)));(od/'ERROR.txt').write_text(str(e));print(f'L{level}: ERROR {e}',flush=True)
    links=''.join(f'<li><a href="l{l}/report.html">L{l}</a> · {n} наблюдений</li>' for l,n,c in summaries)
    errs=''.join(f'<li>L{r["level"]}: {html.escape(r["error"])}</li>' for r in failed)
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Песочница препятствий</title><style>body{font:16px system-ui;background:#f6f5f2;color:#1a1a1a;max-width:950px;margin:40px auto;padding:20px}a{color:#b52b21}li{margin:14px 0}</style><h1>Всё, обо что ударяешься</h1><p>CPU-рой и прицельные заезды · L1–L7 · кандидаты, без исправлений игры</p><p>На картах: фильтры семейств, поиск по клетке/объекту, измерения и повтор каждого наблюдения. Серые дома, границы и изгороди скрыты по умолчанию</p><ul>'+links+'</ul><ul>'+errs+'</ul><p>Полные сырые пробы, включая отсутствие контакта: в папках уровней. Ненайденное замечание Роба не считается исправленным</p>')
    (out/'result.json').write_text(json.dumps(dict(status='PASS' if not failed and len(summaries)==7 else 'INCOMPLETE',levels=summaries,errors=failed),ensure_ascii=False,indent=2));print('INDEX '+str(out/'index.html'),flush=True)
    return bool(failed)
if __name__=='__main__':sys.exit(main())
