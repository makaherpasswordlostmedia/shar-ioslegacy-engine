#!/usr/bin/env python3
"""Exercise the real ship data loop and install block with two tiny exporters.

OLD timestamp selection must fail the same checkout/touch invariant. No EBOOT,
smoke, full dataset export, or deployment is started.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
ship = (ROOT / 'tools/ship.sh').read_text()
install = ship[ship.index('for nd in "${NEWDATA'):ship.index('\n{ echo "ship ', ship.index('for nd in "${NEWDATA'))]


def check(old=False):
    out = Path(tempfile.mkdtemp(prefix='cache-old-' if old else 'cache-new-', dir=ROOT / 'build'))
    (out / 'tools').mkdir(); (out / 'assets').mkdir(); (out / 'assets/x').write_text('asset')
    shutil.copy2(ROOT / 'tools/ship_cache.py', out / 'tools/ship_cache.py')
    for key in ('a', 'b'):
        (out / f'{key}.txt').write_text(key)
        (out / f'export_{key}.py').write_text('import os,sys\nfrom pathlib import Path\n'
            f'Path(sys.argv[1]).write_text(Path("{key}.txt").read_text()+os.getenv("SHR_TEST", ""))\n')
    rulefile = out / 'rules'
    rulefile.write_text('a|build/a|a.txt export_a.py|python export_a.py {out}\n'
                       'b|build/b|b.txt export_b.py assets optional.json|python export_b.py {out}\n')
    (out / 'tools/ship_files.sh').write_text('#!/bin/bash\ncat rules\n'); (out / 'tools/ship_files.sh').chmod(0o755)
    calls = 0
    def run(expect, *, options=None, do_install=True, force=0):
        nonlocal calls
        calls += 1
        stage = out / f'stage{calls}'; stage.mkdir(); (stage / 'log').mkdir()
        code = f'''ROOT="$PWD"; STAGE="{stage}"; LOG="$STAGE/log"; FORCE_LEVEL={force}; USE=()
fail() {{ echo "$*"; exit 1; }}
quality_check() {{ :; }}
step() {{ echo "$*"; }}
ok_name() {{ echo "$1.ok"; }}
. "{ROOT / 'tools/ship_data.sh'}"
'''
        if do_install:
            code += install
        p = subprocess.run(['bash', '-c', code], cwd=out, text=True, capture_output=True,
                           env=dict(os.environ, PATH=str(ROOT / ".venv/bin") + ":" + os.environ["PATH"],
                                    SHIP_HASH_OLD=str(int(old)), **(options or {})))
        assert p.returncode == 0, p.stdout + p.stderr
        built = {line.split(':')[0] for line in p.stdout.splitlines() if ': пересборка' in line}
        assert built == set(expect), f'{built} != {expect}\n{p.stdout}'
        return p
    run(['a', 'b']); run([])  # Required two consecutive runs, second does zero exports.
    for f in ('a.txt', 'b.txt', 'export_a.py', 'export_b.py'):
        p = out / f; stamp = (out / 'build/a').stat().st_mtime + 10; os.utime(p, (stamp, stamp))
    run([])  # git checkout/merge changes dates only: still zero.
    p = out / 'export_a.py'; p.write_text(p.read_text() + '# actual source change\n'); os.utime(p, (1, 1))
    run(['a']); run([])
    (out / 'build/b').write_text('foreign output'); run(['b'])
    rulefile.write_text(rulefile.read_text().replace('python export_a.py {out}', 'python export_a.py {out} # command changed'))
    run(['a']); run([])
    run(['a', 'b'], options={'SHR_TEST': 'option'}); run([], options={'SHR_TEST': 'option'})
    (out / 'assets/x').write_text('new asset'); run(['a', 'b'])  # a: options reset; b: directory input.
    (out / 'optional.json').write_text('{}'); run(['b'])
    (out / 'export_a.py').write_text((out / 'export_a.py').read_text() + '# next change\n')
    original = (out / 'build/a.inputs.sha256').read_bytes()
    run(['a'], do_install=False)
    assert (out / 'build/a.inputs.sha256').read_bytes() == original
    run(['a']); run([])
    print(f'PASS production data/install: {calls} runs; second/checkout zero; isolated exporter/command/output/options/dir/presence; no-install safe')


if __name__ == '__main__':
    check()
    try:
        check(old=True)
    except AssertionError as e:
        assert 'новее' in str(e), str(e)
        print('PASS negative: OLD timestamps rebuild unchanged inputs after checkout/touch')
    else:
        raise AssertionError('OLD escaped')
