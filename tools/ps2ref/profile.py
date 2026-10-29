#!/usr/bin/env python3
"""Private portable PCSX2. Copies only the installed app and owner's BIOS/cards.
No game boot in --check: N2.3 data investigation precedes emulator confirmation.
"""
import argparse
import configparser
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
PERSONAL = Path.home() / 'Library/Application Support/PCSX2'
BASE = ROOT / 'build/ps2ref/profiles'
FOLDERS = dict(Bios='bios', Snapshots='snaps', Savestates='sstates', MemoryCards='memcards',
               Logs='logs', Cheats='cheats', Patches='patches', UserResources='resources', Cache='cache',
               Textures='textures', InputProfiles='inputprofiles', Videos='videos',
               DebuggerLayouts='debuggerlayouts', DebuggerSettings='debuggersettings')


def read_ini(path):
    c = configparser.ConfigParser(interpolation=None, strict=False); c.optionxform = str
    c.read(path); return c


def protected_hashes():
    # Logs/cache can be updated by Rob's running process; persistent user data must stay unchanged.
    files = list(PERSONAL.glob('*.ini'))
    for name in ('inis', 'bios', 'memcards', 'sstates'):
        files.extend(p for p in (PERSONAL / name).rglob('*') if p.is_file())
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}


def prepare(index=1):
    if not 1 <= index <= 3: raise ValueError('only profiles 1..3')
    base = BASE / f'observer{index}'; base.mkdir(parents=True, exist_ok=True)
    app = base / 'PCSX2.app'; data = base / 'data'; ini = data / 'inis/PCSX2.ini'
    if not app.exists():
        source = next(Path('/Applications').glob('PCSX2*.app'))
        shutil.copytree(source, app, symlinks=True)
    (base / 'portable.txt').write_text('data\n')
    if not ini.exists():
        (data / 'inis').mkdir(parents=True, exist_ok=True)
        c = read_ini(PERSONAL / 'inis/PCSX2.ini')
        for name in FOLDERS.values(): (data / name).mkdir(exist_ok=True)
        for section in ('Folders', 'EmuCore', 'UI', 'AutoUpdater', 'Achievements', 'GameList'):
            if not c.has_section(section): c.add_section(section)
        for k, v in FOLDERS.items(): c.set('Folders', k, str(data / v))
        for k, v in {'EnablePINE': 'true', 'PINESlot': str(28120 + index), 'EnableRecordingTools': 'true'}.items(): c.set('EmuCore', k, v)
        for k, v in {'ConfirmShutdown': 'false', 'SetupWizardIncomplete': 'false', 'StartFullscreen': 'false', 'PauseOnFocusLoss': 'false'}.items(): c.set('UI', k, v)
        c.set('AutoUpdater', 'CheckAtStartup', 'false'); c.set('Achievements', 'Enabled', 'false')
        c.remove_section('GameList'); c.add_section('GameList')
        # No inherited keyboard shortcuts or physical controller input to the observer.
        for section in ('Hotkeys', 'InputSources') + tuple(f'Pad{i}' for i in range(1, 9)):
            c.remove_section(section); c.add_section(section)
        c.set('Pad1', 'Type', 'DualShock2'); c.set('InputSources', 'SDL', 'false')
        bios = c.get('Filenames', 'BIOS')
        for src in (PERSONAL / 'bios').glob(Path(bios).stem + '.*'):
            if src.is_file(): shutil.copy2(src, data / 'bios' / src.name)
        for src in (PERSONAL / 'memcards').glob('*.ps2'): shutil.copy2(src, data / 'memcards' / src.name)
        with ini.open('w') as f: c.write(f)
    validate(index)
    return base, app, data


def validate(index):
    base = (BASE / f'observer{index}').resolve(); data = base / 'data'; c = read_ini(data / 'inis/PCSX2.ini')
    if base.is_relative_to(PERSONAL.resolve()): raise ValueError('personal profile forbidden')
    if c.getint('EmuCore', 'PINESlot') != 28120 + index: raise ValueError('wrong/private PINE slot required')
    if (base / 'portable.txt').read_text().strip() != 'data': raise ValueError('wrong portable root')
    for key in FOLDERS:
        p = Path(c.get('Folders', key)).resolve()
        if not p.is_relative_to(data): raise ValueError(f'folder escapes isolated profile: {key}')
    if c.getboolean('UI', 'SetupWizardIncomplete'): raise ValueError('wizard still enabled')


def check(index):
    base, app, data = prepare(index)
    ini = data / 'inis/PCSX2.ini'; original = ini.read_text(); c = read_ini(ini)
    # Negative control only edits our own copy; personal input is never modified.
    c.set('Folders', 'MemoryCards', str(PERSONAL / 'memcards'))
    with ini.open('w') as f: c.write(f)
    try:
        try: validate(index)
        except ValueError as e: print('RED rejected:', e)
        else: raise RuntimeError('isolation gate missed personal memory card path')
    finally: ini.write_text(original)
    before = protected_hashes()
    r = subprocess.run([str(app / 'Contents/MacOS/PCSX2'), '-portable', '-earlyconsolelog', '-testconfig'], cwd=base,
                       capture_output=True, text=True, timeout=30)
    after = protected_hashes()
    log = r.stdout + r.stderr; (base / 'config-check.log').write_text(log)
    changed = [p for p in before.keys() | after.keys() if before.get(p) != after.get(p)]
    result = dict(ok=r.returncode == 0 and not changed and str(data) in log, returncode=r.returncode,
                  changed=changed, before=before, after=after, scope='config startup; no game boot', slot=28120 + index)
    (base / 'isolation.json').write_text(json.dumps(result, indent=2) + '\n')
    if not result['ok']: raise RuntimeError(f'isolation check FAIL: {base}/isolation.json')
    print('GREEN:', len(before), 'personal persistent files unchanged;', data)


def launch(index, state=None):
    # 30.09: прямой запуск показывает окно и забирает фокус (raise() главного окна на старте) — только ask.py:
    # скрыто (open -j -g, -nogui, QT_MAC_SET_RAISE_PROCESS=0) и со сторожем фокуса. Код ниже — история.
    raise RuntimeError('запуск наблюдателя только через tools/ps2ref/ask.py (скрыто, со сторожем фокуса)')
    base, app, data = prepare(index); validate(index)
    pidfile = base / 'process.json'
    if pidfile.exists():
        old = json.loads(pidfile.read_text())
        cmd = subprocess.run(['ps', '-p', str(old['pid']), '-o', 'command='], capture_output=True, text=True).stdout
        if str(app) in cmd: raise RuntimeError('own observer already running')
    args = [str(app / 'Contents/MacOS/PCSX2'), '-portable', '-batch', '-nofullscreen']
    if state:
        src = Path(state).resolve()
        if not src.is_relative_to(ROOT / 'build/ps2ref'): raise ValueError('state must be in build/ps2ref')
        dst = data / 'sstates/start.p2s'; shutil.copy2(src, dst); args += ['-statefile', str(dst)]
    else: args += ['-fastboot']
    args += ['--', str(ROOT / 'game/Hit and Run.iso')]
    with (base / 'stdout.log').open('w') as out:
        p = subprocess.Popen(args, cwd=base, stdout=out, stderr=subprocess.STDOUT, start_new_session=True)
    pidfile.write_text(json.dumps(dict(pid=p.pid, slot=28120 + index, executable=args[0], started=time.time())) + '\n')
    print('observer', index, 'pid', p.pid, 'PINE', 28120 + index)
    return p


def owned_pid(index=1):
    base = BASE / f'observer{index}'
    meta = json.loads((base / 'process.json').read_text())
    expected = str(base / 'PCSX2.app/Contents/MacOS/PCSX2')
    cmd = subprocess.run(['ps', '-p', str(meta['pid']), '-o', 'command='], capture_output=True, text=True).stdout
    if meta['executable'] != expected or not cmd.startswith(expected + ' '):
        raise RuntimeError('refusing to signal anything except our recorded portable instance')
    return meta['pid']


def stop(index):
    import signal
    pid = owned_pid(index)
    os.kill(pid, signal.SIGTERM)
    print('stopped own observer', index, pid)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--index', type=int, default=1)
    p.add_argument('action', choices=['prepare', 'check', 'launch', 'stop', 'pid']); p.add_argument('--state')
    a = p.parse_args()
    if a.action == 'check': check(a.index)
    elif a.action == 'launch': launch(a.index, a.state)
    elif a.action == 'stop': stop(a.index)
    elif a.action == 'pid': print(owned_pid(a.index))
    else: print(prepare(a.index)[0])
