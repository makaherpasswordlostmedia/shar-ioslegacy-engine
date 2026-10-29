#!/usr/bin/env python3
"""CPU acceptance of observer 413 assignments on immutable copies of seven banks.
Usage: .venv/bin/python tests/hover/authored_skid.py /path/to/shar-psp/build
No emulator; does not claim PS2 audible driving or PSP timing.
"""
import hashlib, json, shutil, struct, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import audio_export as A
from sab_cars import cars

def main():
    source = Path(sys.argv[1]).resolve()
    out = ROOT / 'build/authored-skid'
    out.mkdir(parents=True, exist_ok=True)
    res, profiles, _, _ = A.load_scripts()
    names = ['frink_v', 'hbike_v', 'witchcar', 'ship', 'mono_v']
    ex = {n: [profiles[n][k] for k in ('EngineClipName','RoadSkidClipName','DirtSkidClipName')] for n in names}
    # Pin observer facts independently of the exporter's parsed assignments.
    assert ex == {'frink_v':['frink','frink_skid','frink_skid'], 'hbike_v':['hbike','blank','blank'],
                  'witchcar':['witchcar_v','witchcar_v_skid','witchcar_v_skid'], 'ship':['ship_v','ship_skid','ship_skid'],
                  'mono_v':['mono_v_car','monorail_skid','blank']}, ex
    bins = {}
    for old in (False, True):
        exe = out / ('old' if old else 'green')
        subprocess.run(['cc','-O2','-DAUDIO_HOST',f'-DCARSND_OLD={int(old)}','-Iviewer',
                        'tests/hover/authored_skid.c','-lm','-o',str(exe)],cwd=ROOT,check=True)
        bins[old] = exe
    report = {'banks':[], 'runtime':[], 'source_blocks':0, 'old_red':0}
    for level in range(1,8):
        src = source / ('audio/sfx.sab' if level==1 else f'levels/l{level}/audio/sfx.sab')
        pack = out / f'l{level}'; pack.mkdir(exist_ok=True)
        shutil.copyfile(src,pack/'sfx.sab')
        b=(pack/'sfx.sab').read_bytes()
        report['banks'].append({'level':level,'sha256':hashlib.sha256(b).hexdigest()})
        # Check every profile, including ordinary neighbours, against authored scripts.
        subprocess.run([sys.executable,'tests/hover/sab_cars.py',str(pack/'sfx.sab'),'--check'],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
        for row in cars(pack/'sfx.sab'):
            if row['name'] not in names: continue
            name=row['name']
            for old in (False,True):
                run=subprocess.run([str(bins[old]),str(pack)+'/',name,*ex[name]],capture_output=True,text=True)
                (pack/f'{name}-{"old" if old else "green"}.txt').write_text(run.stdout+run.stderr)
                assert run.returncode==(1 if old else 0),(level,name,old,run.stdout,run.stderr)
                report['old_red']+=int(old)
            report['runtime'].append([level,name])
        # Each resident special resource is byte-for-byte its authored VAG source.
        _,nr,_,_,ro,vo,fo,_,do=struct.unpack_from('<9I',b,4)
        wanted={r for row in cars(pack/'sfx.sab') if row['name'] in names for r in ex[row['name']]}
        for i in range(nr):
            o=ro+48*i; name=b[o:o+24].split(b'\0')[0].decode()
            if name not in wanted: continue
            first,count=struct.unpack_from('<HH',b,o+24)
            assert count==len(res[name]['files'])
            for j,path in enumerate(res[name]['files']):
                fi=struct.unpack_from('<H',b,vo+2*(first+j))[0]
                off,nb=struct.unpack_from('<II',b,fo+32*fi)
                ch=b[fo+32*fi+22]
                raw=A.read_rsd(A.game_path(path))['data']
                assert b[do+off:do+off+nb*16*ch]==raw,(level,name,path)
                report['source_blocks']+=1
    assert report['runtime'] and report['old_red']==len(report['runtime'])
    report['not_in_level_banks']=sorted(set(names)-{r[1] for r in report['runtime']})
    # Mono is not assigned to a level; exercise its real exported disc profile too.
    pack=out/'all-special'
    A.build_pack(str(pack),'famil_v',['skid','dirt_skid'],[],[],[],extra_cars=names,quiet=True)
    for name in ['famil_v',*names]:
        p=profiles[name]
        expected=ex.get(name,[p['EngineClipName'],'skid','dirt_skid'])
        r=subprocess.run([str(bins[False]),str(pack)+'/',name,*expected],capture_output=True,text=True)
        (pack/f'{name}.txt').write_text(r.stdout+r.stderr)
        assert r.returncode==0,(name,r.stdout,r.stderr)
    exe=out/'alias-old'
    subprocess.run(['cc','-O2','-DAUDIO_HOST','-DCARSND_BLANK_ALIAS_OLD=1','-Iviewer',
                    'tests/hover/authored_skid.c','-lm','-o',str(exe)],cwd=ROOT,check=True)
    r=subprocess.run([str(exe),str(pack)+'/','witchcar',*ex['witchcar']],capture_output=True,text=True)
    (out/'alias-old.txt').write_text(r.stdout+r.stderr)
    assert r.returncode==1 and r.stdout.count('FAIL blank does not allocate voice')==2,r.stdout
    report['alias_old_failures']=2
    report['all_special_plus_ordinary']=6
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__': main()
