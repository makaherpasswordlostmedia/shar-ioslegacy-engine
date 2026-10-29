"""Run actual main.c with a hostile file-driver adapter and ASan/UBSan.
This proves save/control-flow behavior, NOT PSP graphics or device stability.
All synthetic reports stay in the explicitly labelled host-test directory.
"""
from pathlib import Path as _MainPath
import sys as _MainSys
_MainSys.path.insert(0, str(_MainPath(__file__).resolve().parents[2]/"tools"))
from main_source import read_main
import argparse,hashlib,importlib.util,json,os,shutil,subprocess
from pathlib import Path

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--data',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    a.out.mkdir(parents=True,exist_ok=False);src=Path(__file__).resolve().parent
    spec=importlib.util.spec_from_file_location('collector',src/'collect.py');collector=importlib.util.module_from_spec(spec);spec.loader.exec_module(collector)
    dataset=json.loads((a.data/'dataset.json').read_text());results={}
    command=['clang','-std=c11','-D_POSIX_C_SOURCE=200809L','-DOB_HOST_TEST','-fsanitize=address,undefined','-fno-omit-frame-pointer','-O1','-g','-Wno-pointer-to-int-cast','-I',str(src)]
    exe=a.out/'hostbench';subprocess.run(command+[str(src/'main.c'),'-o',str(exe)],check=True)
    legacy=read_main(src/'main.c').replace('const unsigned short *p=captureFrame;','const unsigned short *p=vram;')
    assert legacy!=read_main(src/'main.c')
    mutant=a.out/'legacy_vram_path.c';mutant.write_text(legacy)
    badexe=a.out/'legacybench';subprocess.run(command+[str(mutant),'-o',str(badexe)],check=True)
    for case in ('normal','legacy_vram','short_write','readback','frame_alloc','ge_timeout'):
        root=a.out/case;root.mkdir();target=root/'EBOOT.PBP';shutil.copy2(badexe if case=='legacy_vram' else exe,target)
        for n in ('io.bin','small','view115.bin','view250.bin','spawn250.bin'):
            p=a.data/n
            if p.is_dir():shutil.copytree(p,root/n)
            else:shutil.copy2(p,root/n)
        env=dict(os.environ,OB_FAULT=case,ASAN_OPTIONS='detect_leaks=0')
        runs=2 if case=='normal' else 1
        for ri in range(1,runs+1):
            prior={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.glob('run*/*') if p.is_file()}
            r=subprocess.run([str(target)],env=env,capture_output=True,text=True,timeout=60)
            (root/f'process-{ri}.log').write_text(r.stdout+r.stderr)
            run=root/f'run{ri:04d}';complete=(run/'COMPLETE.txt').exists();stopped=(run/'STOPPED.txt').exists()
            assert 'AddressSanitizer' not in r.stderr and 'runtime error:' not in r.stderr,r.stderr
            for p,h in prior.items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h,'previous run overwritten'
            if case=='normal':
                assert r.returncode==0 and complete and not stopped,(case,r.returncode,r.stderr)
                result=collector.analyze(run,dataset);assert result['complete'] and not result['integrity_issues'] and not result['io_errors'],result
                assert len(list(run.glob('*.rgb565')))==12
                log=[json.loads(x) for x in (run/'results.jsonl').read_text().splitlines()]
                assert sum(x.get('phase')=='capture_saved_verified' for x in log)==12
                assert sum(x.get('phase')=='scene_complete' for x in log)==3
            elif case=='legacy_vram':
                assert r.returncode==91 and not complete and 'REJECTED: video memory' in r.stderr
            else:
                assert r.returncode==20 and not complete and stopped,(case,r.returncode,r.stdout,r.stderr)
            results[f'{case}/{ri}']=dict(exit_code=r.returncode,complete=complete,stopped=stopped,old_runs_unchanged=True)
    report=dict(scope='HOST ONLY: actual program flow, synthetic GPU/memory/clocks; not a hardware benchmark',source_sha256=hashlib.sha256(read_main(src/'main.c').encode()).hexdigest(),tests=results)
    (a.out/'regression.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
