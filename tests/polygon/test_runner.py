"""The real shell runner must retain failed runs and retry missing road data."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

SOURCE = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / 'tools/polygon/run_24x7.sh'


def run_case(prepare):
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        for name in ('tools/polygon', 'tools/bots', 'tools/cartest', 'build/bots', 'build/polygon/L2', 'build/levels/l2'):
            (root / name).mkdir(parents=True)
        runner = root / 'tools/polygon/run_24x7.sh'
        runner.write_bytes(SOURCE.read_bytes())
        (root / 'build/bots/inspector').write_text('')
        (root / 'build/bots/inspector').chmod(0o755)
        (root / 'tools/bots/build.sh').write_text('exit 0\n')
        (root / 'tools/bots/anatomy.py').write_text("from pathlib import Path\nPath('build/polygon/STOP').touch()\nraise SystemExit(2)\n")
        (root / 'tools/cartest/roads.py').write_text("from pathlib import Path\nimport sys\np=Path(sys.argv[sys.argv.index('--out')+1]); p.write_bytes(b'roads')\n")
        if prepare:
            (root / 'build/levels/l2/level.shr').write_bytes(b'level')
            (root / 'build/polygon/L2/quiet').write_text('3\n')
        env = dict(os.environ, POLY_MANAGED='1', POLY_CAFF='1', POLY_LEVELS='2')
        subprocess.run(['bash', str(runner)], cwd=root, env=env, capture_output=True, timeout=5, check=True)
        assert (root / 'build/polygon/L2/quiet').read_text().strip() == '0', 'failed level marked saturated'
        assert (root / 'build/polygon/L2/error').exists(), 'error not recorded'
        assert any(p.is_dir() for p in (root / 'build/polygon/L2').iterdir()), 'failed run discarded'
        if prepare:
            assert (root / 'build/sandbox/roads-l2.bin').read_bytes() == b'roads', 'missing roads not prepared'


run_case(False)
run_case(True)
print('PASS: errors preserved, quiet=0, missing roads prepared before saturation check')
