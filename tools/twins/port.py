"""Близнецы · сторона «Порт» (docs/handoff/БЛИЗНЕЦЫ_2026-10-01.md §1–2): два вида, пакет §1 в осях оригинала.

П-лёгкий (port_light): tools/twins/port_light.c поверх мира ботов (та же логика, что EBOOT), без экрана, детерминирован.
П-полный (port_full): наш EBOOT в СВОЁМ PPSSPPHeadless (tools/twins/ppsspp_build.sh) без окна: программный рендер 480×272,
  сценарий движка (goto → wait → shot → end), кадр по строке SHOT (заплатка), балласт памяти под настоящую PSP (файл ballast).
  Общий PPSSPPSDL, ~/.config/ppsspp и tools/ppsspp_run.sh не трогает: HOME нашей копии — build/twins/ppsspp_home.
Входы замораживаются в папку прогона (in/, копии APFS) с sha256 — повтор берёт те же байты."""
import json, math, os, re, shutil, struct, subprocess, sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

LIGHT_IN = ('level.shr', 'homer.shr', 'interiors-l1.bin', 'collect-l1.shr', 'traffic.shr', 'missions/level01.msn', 'msncars-l1.shr')
HEADLESS = C.BIN / 'PPSSPPHeadless'


class PortFail(Exception):
    pass


def _clone(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if subprocess.run(['cp', '-c', str(src), str(dst)], capture_output=True).returncode: shutil.copy2(src, dst)


def freeze_light(run):
    """Входы мира ботов из build/ основной папки -> run/in/ (как неизменяемая ночь tools/bots/night.py)."""
    man = {}
    for f in LIGHT_IN:
        s = C.DATA / 'build' / f
        if not s.exists():
            if f in ('msncars-l1.shr',): continue   # необязательные спутники
            raise PortFail(f'нет входа порта build/{f}')
        d = run / 'in' / Path(f).name; _clone(s, d); man[f] = C.sha256(d, 16)
    return man


def build_light():
    """port_light из кода рабочей копии (viewer/ + tools/bots/world.c): бинарник по хешу исходников — разные версии не путаются."""
    lib = subprocess.run(['bash', '-c', 'V=viewer; . tools/bots/lib.sh; echo "$BOTS_LIB"'], cwd=C.WT, capture_output=True, text=True, check=True).stdout.split()
    srcs = ['tools/twins/port_light.c'] + lib
    import hashlib
    h = hashlib.sha256()
    for s in sorted(set(srcs + [str(p.relative_to(C.WT)) for p in (C.WT / 'viewer').glob('*.h')] +
                        [str(p.relative_to(C.WT)) for p in (C.WT / 'tools/bots').glob('*.h')])):
        h.update(s.encode()); h.update((C.WT / s).read_bytes())
    out = C.BIN / f'port_light_{h.hexdigest()[:12]}'
    if not out.exists():
        C.BIN.mkdir(parents=True, exist_ok=True)
        cmd = ['cc', '-std=c11', '-O2', '-w', '-DSKIN_HOST', '-I', 'viewer', '-I', 'tools/bots'] + srcs + ['-lm', '-o', str(out)]
        r = subprocess.run(cmd, cwd=C.WT, capture_output=True, text=True)
        if r.returncode: raise PortFail('сборка port_light: ' + (r.stderr.strip().splitlines() or ['?'])[-1])
    return out


def light_packet(point, rows, frame):
    """строка мира ботов -> пакет §1 (оси оригинала)"""
    r = rows[-1]; p = C.packet(point, 'port_light')
    p['frame'] = frame
    lift = r['lift']
    if r['onfoot']: p['pos'] = C.z_flip(r['player'])
    else: p['pos'] = C.z_flip([r['car'][0], r['car'][1] + lift, r['car'][2]])
    p['heading'] = round(C.yaw_of_port(r['h']), 6)
    p['vel'] = [round(v, 5) for v in C.z_flip(r['vel'])]
    p['onfoot'] = bool(r['onfoot'])
    p['room'] = r['room']
    if r['cars'] >= 0: p['counters']['cars'] = r['cars']; p['counters']['peds'] = r['peds']
    return p


def run_light(point, run, frames, place=None, fake=None):
    """place = (x, y, z, h) в осях порта или None (свой спавн). fake = (dx, dz) — подлог гейта Б1 в осях порта."""
    exe = build_light(); man = freeze_light(run)
    args = [str(exe), str(run / 'in/level.shr'), str(run / 'in/homer.shr'), '--msn', str(run / 'in/level01.msn'), '--frames', str(frames), '--every', '30']
    if place:
        x, y, z, h = place
        if fake: x += fake[0]; z += fake[1]
        args += ['--place', f'{x:.5f}', f'{y:.5f}', f'{z:.5f}', f'{h:.6f}']
    r = subprocess.run(args, capture_output=True, text=True, timeout=600)
    if r.returncode: raise PortFail('port_light: ' + (r.stderr.strip().splitlines() or ['?'])[-1])
    rows = [json.loads(l) for l in r.stdout.splitlines() if l.startswith('{')]
    (run / f'light_{point}.jsonl').write_text(r.stdout)
    return light_packet(point, rows, rows[-1]['frame']), dict(bin=exe.name, inputs=man, start=rows[0], rows=len(rows))


# ---------- П-полный ----------

def ship_pairs():
    out = subprocess.run([str(C.DATA / 'tools/ship_files.sh'), '--pairs'], cwd=C.DATA, capture_output=True, text=True, check=True).stdout
    return [l.split('|', 1) for l in out.splitlines() if '|' in l]


def hw_heap_at_start():
    """свободная куча на старте по последнему замеру на PSP (build/psp-logs/*/smoke.txt) — для балласта"""
    best = None
    for d in sorted((C.DATA / 'build/psp-logs').glob('2*')):
        f = d / 'smoke.txt'
        if not f.exists(): continue
        m = re.search(r'# heap free at start ([\d.]+) MB \(ballast (\d+) MB\)', f.read_text(errors='replace'))
        if m and int(m.group(2)) == 0: best = (float(m.group(1)), d.name)
    return best


def stage_full(run, point, scenario, ballast_mb):
    d = run / 'full' / point
    if d.exists(): shutil.rmtree(d)
    d.mkdir(parents=True)
    src = C.DATA / 'build/EBOOT.PBP'
    if not src.exists(): raise PortFail('нет build/EBOOT.PBP')
    _clone(src, d / 'EBOOT.PBP'); man = {'EBOOT.PBP': C.sha256(d / 'EBOOT.PBP', 16)}
    for dst, s in ship_pairs():
        sp = C.DATA / s
        if not sp.exists():
            if dst.startswith(('l2/', 'l3/', 'l4/', 'l5/', 'l6/', 'l7/', 'movies/fmv')): continue
            raise PortFail(f'нет {s} для EBOOT')
        _clone(sp, d / dst)
    man['level.shr'] = C.sha256(d / 'level.shr', 16)
    (d / 'scenario.txt').write_text(scenario); (d / 'smokelog').write_text('')
    if ballast_mb: (d / 'ballast').write_text(f'{int(ballast_mb)}\n')
    return d, man


def run_full(point, run, secs, place=None, fake=None, ballast_mb=0, timeout=900):
    """EBOOT в своём PPSSPPHeadless: goto (оси порта) -> wait secs -> shot -> end. -> (пакет, сведения)"""
    if not HEADLESS.exists(): raise PortFail('нет своего PPSSPPHeadless: tools/twins/ppsspp_build.sh')
    lines = ['scene twins']
    if place:
        x, _, z, h = place
        if fake: x += fake[0]; z += fake[1]
        lines.append(f'goto {x:.4f} {z:.4f} {h:.5f}')
    lines += [f'wait {secs:.3f}', f'shot tw_{point}', 'end', '']
    d, man = stage_full(run, point, '\n'.join(lines), ballast_mb)
    home = C.OUT / 'ppsspp_home'; home.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, HOME=str(home), TWINS_SMOKE=str(d / 'smoke.txt'), TWINS_SHOTDIR=str(d), DYLD_FRAMEWORK_PATH=str(C.BIN))
    for k in ('XDG_CONFIG_HOME', 'XDG_DATA_HOME'): env.pop(k, None)
    t0 = C.clock()
    with (d / 'headless.log').open('w') as log:
        pr = subprocess.Popen(['nice', '-n', '10', str(HEADLESS), '--graphics=software', f'--timeout={timeout}', str(d / 'EBOOT.PBP')],
                              cwd=d, env=env, stdout=log, stderr=subprocess.STDOUT)
        bad = watch_no_window(pr, timeout + 60)
    if bad: raise PortFail(f'PPSSPPHeadless: {bad} — свой процесс остановлен')
    smk = (d / 'smoke.txt').read_text(errors='replace') if (d / 'smoke.txt').exists() else ''
    if 'END' not in smk.split(): raise PortFail(f'EBOOT в PPSSPPHeadless не дошёл до END (код {pr.returncode}); {d.relative_to(C.DATA)}/headless.log')
    return full_packet(point, run, d, smk), dict(inputs=man, dir=str(d.relative_to(C.DATA)), started=t0, rc=pr.returncode, ballast=ballast_mb,
                                                  heap_start=heap_at_start(smk))


def _front_pid():
    a = subprocess.run(['lsappinfo', 'front'], capture_output=True, text=True).stdout.strip()
    o = subprocess.run(['lsappinfo', 'info', '-only', 'pid', a], capture_output=True, text=True).stdout
    m = re.search(r'=(\d+)', o); return int(m.group(1)) if m else None


def watch_no_window(pr, limit):
    """Сторож «без окон и без фокуса» (БЛИЗНЕЦЫ §4): наш процесс впереди или его окно на экране -> остановить свой PID.
    Окна считает build/ps2ref/bin/wins (тот же, что у ask.py). -> '' или причина."""
    import time
    wins = C.DATA / 'build/ps2ref/bin/wins'; t_end = time.time() + limit; k = 0
    while pr.poll() is None:
        why = ''
        if _front_pid() == pr.pid: why = 'вышел вперёд'
        elif k % 5 == 0 and wins.exists():
            o = subprocess.run([str(wins), str(pr.pid)], capture_output=True, text=True).stdout
            if any(l.startswith('1 ') for l in o.splitlines()): why = 'окно на экране'
        if time.time() > t_end: why = 'не закончил за отведённое время'
        if why:
            pr.kill(); pr.wait(); return why
        k += 1; time.sleep(0.2)
    return ''


def bmp_to_png(bmp, png):
    """кадр заплатки: BMP 512×272 32 бит снизу вверх (BGRA) -> PNG 480×272"""
    from PIL import Image
    im = Image.open(bmp).convert('RGB').crop((0, 0, 480, 272)); im.save(png)


def full_packet(point, run, d, smk):
    p = C.packet(point, 'port_full')
    shot = re.search(r'^SHOT tw_' + re.escape(point) + r' ([\d.]+) pos (\S+) (\S+) (\S+) (\S+)', smk, re.M)
    if not shot: raise PortFail('в smoke.txt нет строки SHOT')
    t, x, y, z, h = map(float, shot.groups())
    lift = C.level_lift(d / 'level.shr')
    p['pos'] = [round(v, 5) for v in C.z_flip([x, y + lift, z])]
    p['heading'] = round(C.yaw_of_port(h), 6)
    sc = re.search(r'^SCENE twins ([\d.]+)', smk, re.M)   # синхронизация (goto) — первая команда сцены twins
    p['frame'] = round((t - (float(sc.group(1)) if sc else 0.0)) * 60)   # кадры 1/60 от синхронизации до снимка
    # секунда перед снимком: строка "t scene fps work workmax cpu tris draws ramMB mode missed missvis readerr allocfail heapMB"
    sec = [l.split() for l in smk.splitlines() if re.match(r'^[\d.]+ \S+ [\d.]+ ', l)]
    sec = [s for s in sec if float(s[0]) <= t + 1e-3] or sec
    if sec:
        s = sec[-1]
        p['counters']['tris'] = int(s[6]); p['counters']['draws'] = int(s[7]); p['mem']['free'] = float(s[14])
    st = re.search(r'^STAT twins .*?gepeak ([\d.]+)', smk, re.M)
    if st: p['mem']['ge'] = float(st.group(1)); p['counters']['ge_bytes'] = int(float(st.group(1)) * 1024)
    game = re.search(r'^GAME .*?cells=(\d+)', smk, re.M)
    if game: p['counters']['cells'] = int(game.group(1))
    bmp = d / f'tw_{point}.bmp'
    if bmp.exists():
        png = run / 'shots' / f'{point}_port_full.png'; png.parent.mkdir(exist_ok=True); bmp_to_png(bmp, png)
        p['shot'] = str(png.relative_to(run))
    return p


def heap_at_start(smk):
    m = re.search(r'# heap free at start ([\d.]+) MB \(ballast (\d+) MB\)', smk)
    return (float(m.group(1)), int(m.group(2))) if m else None
