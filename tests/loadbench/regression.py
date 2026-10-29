"""Run real main.c + LZ4 under ASan/UBSan; these are NOT PSP measurements."""
import argparse
import hashlib
import json
import os
import shutil
import struct
import subprocess
from pathlib import Path
from collect import analyze
from verify import hash32, verify

HERE=Path(__file__).resolve().parent


def build(exe,extra=()):
    subprocess.run(['clang','-std=c11','-D_POSIX_C_SOURCE=200809L','-DLB_HOST_TEST',
                    '-fsanitize=address,undefined','-fno-omit-frame-pointer','-O1','-g',
                    '-I/opt/homebrew/include','-L/opt/homebrew/lib','-llz4',*extra,
                    str(HERE/'main.c'),'-o',str(exe)],check=True)


def run_tests(data,out):
    out.mkdir(parents=True,exist_ok=False)
    dataset=json.loads((data/'lb_dataset.json').read_text())
    exe=out/'hostbench';build(exe)
    verification=verify(data,HERE.parents[1]/'build/level_ni.shr')
    results={}
    names=['lb_index.bin','lb_raw.bin','lb_fast.bin','lb_hc.bin']
    for case in ('normal','short_read','payload_corrupt','short_write','report_corrupt',
                 'index_corrupt','index_bounds','truncated_container'):
        root=out/case;root.mkdir();target=root/'EBOOT.PBP';shutil.copy2(exe,target)
        for name in names:shutil.copy2(data/name,root/name)
        if case=='index_corrupt':
            b=bytearray((root/'lb_index.bin').read_bytes());b[-1]^=1;(root/'lb_index.bin').write_bytes(b)
        if case=='index_bounds':
            b=bytearray((root/'lb_index.bin').read_bytes());struct.pack_into('<I',b,32+4,65537)
            (root/'lb_index.bin').write_bytes(b)
            # A checksummed malformed index proves bounds validation itself rejects it.
            build(target,[f'-DDATA_INDEX_FNV=0x{hash32(b):08x}u'])
        if case=='truncated_container':
            p=root/'lb_hc.bin';p.write_bytes(p.read_bytes()[:-1])
        for i in range(1,3 if case=='normal' else 2):
            prior={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.glob('load*/*') if p.is_file()}
            env=dict(os.environ,LB_FAULT=case,ASAN_OPTIONS='detect_leaks=0')
            result=subprocess.run([str(target)],env=env,capture_output=True,text=True,timeout=60)
            (root/f'process-{i}.log').write_text(result.stdout+result.stderr)
            assert 'AddressSanitizer' not in result.stderr and 'runtime error:' not in result.stderr,result.stderr
            assert all(hashlib.sha256(p.read_bytes()).hexdigest()==h for p,h in prior.items())
            run=root/f'load{i:04d}';analysis=analyze(run,dataset,expected_platform='host-test')
            (root/f'analysis-{i}.json').write_text(json.dumps(analysis,indent=2)+'\n')
            if case=='normal':
                assert result.returncode==0 and analysis['complete'],analysis['issues']
                assert analysis['samples']==4446
            else:
                assert result.returncode==20 and not analysis['complete'] and (run/'STOPPED.txt').exists(),(case,result.returncode,result.stderr)
                assert not (run/'COMPLETE.txt').exists(),case
            results[f'{case}/{i}']=dict(exit_code=result.returncode,complete=analysis['complete'],
                                      samples=analysis['samples'],prior_results_unchanged=True,
                                      reason=(run/'STOPPED.txt').read_text() if (run/'STOPPED.txt').exists() else None)
    # Collector must reject plausible-looking, COMPLETE-marked reports with a bad row.
    original=out/'normal/load0001';mutant=out/'collector-mutant';shutil.copytree(original,mutant)
    p=mutant/'case001.csv';lines=p.read_text().splitlines();row=lines[1].split(',');row[13]=str(int(row[13])+1);lines[1]=','.join(row);p.write_text('\n'.join(lines)+'\n')
    assert not analyze(mutant,dataset,expected_platform='host-test')['complete']
    results['collector_timing_mutant']=dict(rejected=True)
    assert not analyze(original,dataset)['complete']
    results['host_as_hardware_rejected']=dict(rejected=True)
    # Binary package verifier must reject changed asset bytes independently of logs.
    bad=out/'package-mutant';bad.mkdir()
    for name in names+['lb_dataset.json']:shutil.copy2(data/name,bad/name)
    p=bad/'lb_raw.bin';b=bytearray(p.read_bytes());b[55]^=1;p.write_bytes(b)
    try:verify(bad)
    except AssertionError:results['package_data_mutant']=dict(rejected=True)
    else:raise AssertionError('Package verifier accepted corrupted data')
    report=dict(scope='HOST ONLY: real C control flow, files and LZ4, POSIX PSP API adapter; not PSP performance or stability',
                source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.iterdir() if p.is_file()},
                verification=verification,tests=results)
    (out/'regression.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='source_sha256'},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();run_tests(a.data,a.out)
