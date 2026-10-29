"""Exercise detached launch, duplicate guard, process-tree stop and PID safety."""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time

SOURCE = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / 'tools/polygon/control.py'

def wait_for(predicate):
    end = time.monotonic() + 10
    while time.monotonic() < end:
        if predicate(): return
        time.sleep(.1)
    raise AssertionError('timed out')

with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    (root / 'tools/polygon').mkdir(parents=True)
    (root / 'build/polygon').mkdir(parents=True)
    controller = root / 'tools/polygon/control.py'
    shutil.copyfile(SOURCE, controller)
    (root / 'tools/polygon/run_24x7.sh').write_text("exec python3 tools/polygon/worker.py\n")
    (root / 'tools/polygon/worker.py').write_text("""import os, signal, subprocess, sys, time
from pathlib import Path
child = subprocess.Popen([sys.executable, '-c', 'import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(120)'])
Path('build/polygon/child.pid').write_text(str(child.pid))
Path('build/polygon/partial.txt').write_text('keep results')
time.sleep(120)
""")
    state = root / 'build/polygon/background.json'
    stop = root / 'build/polygon/STOP'
    stop.write_text('previous stop')
    def call(action, check=True):
        return subprocess.run([sys.executable, str(controller), action], cwd=root,
                              capture_output=True, text=True, timeout=15, check=check)
    unrelated = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])
    try:
        # A stale/reused PID must never be signalled
        state.write_text(json.dumps(dict(state='running', pid=unrelated.pid, identity='wrong identity')))
        call('stop')
        assert unrelated.poll() is None
        call('start')
        first = json.loads(state.read_text())
        call('start')
        assert json.loads(state.read_text())['pid'] == first['pid'], 'duplicate supervisor'
        assert list(stop.parent.glob('STOP.*')), 'old STOP discarded'
        wait_for(lambda: (stop.parent / 'child.pid').exists())
        child_pid = (stop.parent / 'child.pid').read_text()
        began = time.monotonic()
        call('stop')
        assert time.monotonic() - began < 8, 'stop waits for long stage'
        wait_for(lambda: subprocess.run(['ps', '-p', child_pid], capture_output=True).returncode != 0)
        assert json.loads(state.read_text())['state'] == 'stopped'
        assert (stop.parent / 'partial.txt').read_text() == 'keep results'
        assert unrelated.poll() is None, 'unrelated process killed'
        # STOP-file path must stop the entire group too
        call('start')
        stop.touch()
        wait_for(lambda: json.loads(state.read_text())['state'] == 'stopped')
    finally:
        call('stop', check=False)
        pidfile = stop.parent / 'child.pid'
        if pidfile.exists():
            try: os.kill(int(pidfile.read_text()), signal.SIGKILL)
            except ProcessLookupError: pass
        unrelated.terminate()
        unrelated.wait()
print('PASS: detached start, one instance, fast tree stop, stale PID safe, results kept')
