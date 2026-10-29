#!/usr/bin/env python3
"""Local CPU polygon: one detached supervisor, owned worker group, no network."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
P = ROOT / 'build/polygon'
STATE = P / 'background.json'


def identity(pid):
    r = subprocess.run(['ps', '-p', str(pid), '-o', 'lstart=', '-o', 'command='], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ''


def current():
    try:
        data = json.loads(STATE.read_text())
        observed = identity(data['pid'])
        if data.get('state') == 'running' and observed and observed == data['identity']:
            return data
    except (OSError, ValueError, KeyError):
        pass
    return None


def legacy_running():
    rows = subprocess.check_output(['ps', '-axo', 'pid=,command='], text=True).splitlines()
    for row in rows:
        pid, command = row.strip().split(None, 1)
        if not command.startswith('bash tools/polygon/run_24x7.sh'):
            continue
        if sys.platform == 'darwin':
            cwd = subprocess.run(['lsof', '-a', '-p', pid, '-d', 'cwd', '-Fn'], capture_output=True, text=True).stdout
            if 'n' + str(ROOT) in cwd.splitlines():
                return True
        else:
            try:
                if Path('/proc/' + pid + '/cwd').resolve() == ROOT:
                    return True
            except OSError:
                pass
    return False


def save(data):
    tmp = STATE.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(STATE)


def run():
    P.mkdir(parents=True, exist_ok=True)
    with (P / 'background.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 2
        stop = P / 'STOP'
        if stop.exists():
            stop.rename(P / ('STOP.' + str(time.time_ns())))
        stopping = False

        def requested(*_):
            nonlocal stopping
            stopping = True
            stop.touch()

        signal.signal(signal.SIGTERM, requested)
        signal.signal(signal.SIGINT, requested)
        worker = subprocess.Popen(['bash', 'tools/polygon/run_24x7.sh'], cwd=ROOT,
                                  env=dict(os.environ, POLY_CAFF='1', POLY_MANAGED='1'), start_new_session=True)
        coffee = None
        if sys.platform == 'darwin':
            coffee = subprocess.Popen(['caffeinate', '-i', '-w', str(os.getpid())])
        data = dict(state='running', pid=os.getpid(), identity=identity(os.getpid()),
                    worker_pid=worker.pid, started=time.strftime('%Y-%m-%d %H:%M:%S'), root=str(ROOT))
        save(data)
        try:
            while worker.poll() is None and not stopping and not stop.exists():
                time.sleep(0.25)
        finally:
            # Every bot inherits this private worker group, never the user's terminal group
            try:
                os.killpg(worker.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            time.sleep(1)
            try:
                os.killpg(worker.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            worker.wait()
            if coffee:
                coffee.terminate()
                coffee.wait()
            data.update(state='stopped' if stopping or stop.exists() else 'failed',
                        returncode=worker.returncode, ended=time.strftime('%Y-%m-%d %H:%M:%S'))
            save(data)
        return 0 if data['state'] == 'stopped' else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('start', 'stop', 'status', 'run'))
    action = parser.parse_args().action
    if action == 'run':
        return run()
    data = current()
    if action == 'status':
        print('Работает в фоне, PID ' + str(data['pid']) if data else 'Полигон остановлен')
        print('Итог: ' + str(P / 'ИТОГ.md'))
        return 0
    if action == 'stop':
        if not data:
            print('Полигон уже остановлен')
            return 0
        try:
            os.kill(data['pid'], signal.SIGTERM)
        except ProcessLookupError:
            print('Полигон уже остановлен')
            return 0
        for _ in range(80):
            if not current():
                print('Полигон остановлен; результаты сохранены')
                return 0
            time.sleep(0.1)
        print('Остановка ещё идёт; см. background.log', file=sys.stderr)
        return 1
    if data:
        print('Уже работает в фоне, PID ' + str(data['pid']))
        return 0
    # Also refuse an older foreground runner, which does not hold our lock
    if legacy_running():
        print('Сначала остановите прежний запуск полигона', file=sys.stderr)
        return 1
    P.mkdir(parents=True, exist_ok=True)
    with (P / 'background.log').open('ab') as log:
        child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'run'], cwd=ROOT,
                                 stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
    for _ in range(100):
        data = current()
        if data:
            print('Запущен в фоне на CPU Мака, PID ' + str(data['pid']))
            return 0
        if child.poll() is not None:
            # Concurrent start may have won the lock, recheck its state
            if current():
                return 0
            print('Запуск не удался; см. ' + str(P / 'background.log'), file=sys.stderr)
            return 1
        time.sleep(0.1)
    print('Запуск ещё идёт; см. background.log', file=sys.stderr)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
