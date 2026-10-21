"""Gate existing native captures, including the real renderer's negative control."""
from pathlib import Path
import re
import subprocess
import sys
here = Path(__file__).resolve().parent
root = Path(sys.argv[1]).resolve()
for name in ('full', 'full-old', 'full-background', 'control', 'control-old', 'control5', 'control5-old'):
    log = (root/f'{name}-stage/smoke.txt').read_text()
    assert re.search(r'^END$', log, re.M), (name, 'END')
    stat = re.findall(r'^STAT .*$', log, re.M)[-1]
    for key in ('readerr', 'allocfail', 'gebad', 'memfail'):
        assert re.search(r'\b'+key+r' 0\b', stat), (name, key)
assert 'flag glowblendold 1' in (root/'full-old-stage/scenario.txt').read_text()
assert 'flag glowblendold 1' not in (root/'full-stage/scenario.txt').read_text()
subprocess.run([sys.executable, str(here/'materials.py')], check=True)
subprocess.run([sys.executable, str(here/'pixels.py'), str(root/'full-shots'), str(root/'full-background-shots')], check=True)
old = subprocess.run([sys.executable, str(here/'pixels.py'), str(root/'full-old-shots'), str(root/'full-background-shots')], capture_output=True, text=True)
assert old.returncode == 1 and 'opaque black glow corner' in old.stderr, old.stdout+old.stderr
print('EXPECTED RED:', old.stdout.strip())
subprocess.run([sys.executable, str(here/'controls.py'), str(root)], check=True)
print('PASS: full native package, actual OLD red, neighboring glows, END/errors0')
