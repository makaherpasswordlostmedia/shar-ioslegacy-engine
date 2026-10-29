#!/usr/bin/env python3
"""Близнецы · дирижёр (docs/handoff/БЛИЗНЕЦЫ_2026-10-01.md §1, Б1): маршрут точек -> синхронизация сторон -> N кадров -> пакеты -> судья.
Без AI: считает Мак, агент читает только report.md.

  python3 tools/twins/conductor.py run [--points l1_start] [--sides orig,port_light,port_full] [--frames N] [--fake-shift M] [--no-sync]
  python3 tools/twins/conductor.py gate     гейт Б1: без подлога — чисто; подлог 5 м (порт сдвинут вдоль носа) — судья видит
  python3 tools/twins/conductor.py calib    балласт памяти П-полного: куча на старте эмулятора против последнего замера PSP
  python3 tools/twins/conductor.py queue    очередь вопросов knowledge/questions.tsv (tools/twins/inbox.py)
Точки — tools/twins/points.tsv (имя · состояние оригинала · телепорт · кадров оригинала · что это). Синхронизация Б1: порт ставится в позу
машины из самого состояния оригинала (начало модели, курс; оси порта: z зеркально, курс h = pi - курс оригинала); у оригинала точка = его
состояние (телепорт хирургией тела — только если задан в точке). Кадры: оригинал N (1/50 с), порт N*60/50 (1/60 с) — одно игровое время.
Отрицательные контроли гейта (руками, до «зелёного»): TWINS_BREAK=judge_pose (судья без правила позиции) и TWINS_BREAK=no_sync
(порт не синхронизирован — стоит на своём спавне): каждый обязан сделать гейт красным.
Результат: build/twins/<время date>/ — packets.jsonl (строка на сторону и точку), manifest.json, report.md, findings.json, pairs.png."""
import argparse, json, math, os, sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
import judge as J
import orig as O
import port as P

POINTS = C.WT / 'tools/twins/points.tsv'
BALLAST = C.OUT / 'ballast.json'
FAKE_DEFAULT = 5.0


def points():
    out = []
    for l in POINTS.read_text().splitlines():
        if not l.strip() or l.startswith('#'): continue
        f = l.split('\t')
        tp = None if f[2].strip() in ('-', '') else [float(v) for v in f[2].split()]
        out.append(dict(name=f[0], state=f[1], teleport=tp, frames=int(f[3]), note=f[4] if len(f) > 4 else ''))
    return out


def ballast_mb():
    if BALLAST.exists(): return json.loads(BALLAST.read_text())['ballast_mb']
    return 9   # ТЗ §2: эмулятор завышает свободную память примерно на 9 МБ (замер 30.09) — пока нет своей калибровки (calib)


def sync_pose(pt):
    """поза для порта (оси порта) из состояния оригинала: (x, y, z, h)"""
    O.bind()
    sp = O.state_pose(C.DATA / pt['state'])
    x, y, z = pt['teleport'] if pt['teleport'] else sp['pos']
    return (x, y, -z, C.port_h_of_yaw(sp['heading'])), sp


def run(names=None, sides=('orig', 'port_light', 'port_full'), frames=None, fake_shift=0.0, no_sync=None, out=None, fresh=False):
    no_sync = bool(no_sync) or 'no_sync' in os.environ.get('TWINS_BREAK', '')
    run_dir = Path(out) if out else C.OUT / C.stamp()
    if run_dir.exists() and (run_dir / 'packets.jsonl').exists(): raise SystemExit(f'{run_dir} уже есть — завершённые серии не перезаписываются')
    run_dir.mkdir(parents=True, exist_ok=True)
    man = dict(started=C.clock(), code=C.git_head(), sides=list(sides), fake_shift=fake_shift, no_sync=no_sync, points={}, notes=[],
               ballast_mb=ballast_mb() if 'port_full' in sides else None)
    pk = []
    for pt in points():
        if names and pt['name'] not in names: continue
        n = frames or pt['frames']; info = man['points'][pt['name']] = dict(frames_orig=n, note=pt['note'])
        place, sp = sync_pose(pt)
        info['sync'] = dict(orig_pos=sp['pos'], orig_heading=sp['heading'], orig_frame=sp['frame'], port_place=place)
        fake = None
        if fake_shift:
            fake = (fake_shift * math.sin(place[3]), fake_shift * math.cos(place[3]))   # вдоль носа машины порта
            info['fake'] = dict(meters=fake_shift, dx=fake[0], dz=fake[1])
        if no_sync:
            spawn = C.level_spawn(C.DATA / 'build/level.shr')
            info['natural_spawn_port'] = spawn
            d = math.hypot(spawn[0] - place[0], spawn[2] - place[2])
            man['notes'].append(f"{pt['name']}: порт без синхронизации — свой спавн ({spawn[0]:.2f}, {spawn[1]:.2f}, {spawn[2]:.2f}) курс {spawn[3]:.3f}, "
                                f"до позы оригинала {d:.2f} м (правило порта SPAWN, tools/psp_export.py: точка телепорта «Simpsons' House»)")
        pl = None if no_sync else place
        if 'orig' in sides:
            p, i = O.run_point(pt, run_dir, n, fresh=fresh); pk.append(p); info['orig'] = i
        if 'port_light' in sides:
            p, i = P.run_light(pt['name'], run_dir, round(n * 60 / 50), place=pl, fake=fake); pk.append(p); info['port_light'] = dict(i, start=i['start'])
        if 'port_full' in sides:
            p, i = P.run_full(pt['name'], run_dir, n / 50.0, place=pl, fake=fake, ballast_mb=man['ballast_mb']); pk.append(p); info['port_full'] = i
    (run_dir / 'packets.jsonl').write_text(''.join(C.line(p) + '\n' for p in pk))
    man['finished'] = C.clock()
    (run_dir / 'manifest.json').write_text(json.dumps(man, ensure_ascii=False, indent=1) + '\n')
    res = J.judge(pk); J.report(run_dir, res, man)
    return run_dir, res


def gate(fresh=False):
    """Гейт Б1. PASS: (А) без подлога — ни одной находки правил позы; (Б) подлог 5 м — pose_xz >= 4 м у каждой стороны порта."""
    sides = ('orig', 'port_light', 'port_full') if P.HEADLESS.exists() else ('orig', 'port_light')
    ra, a = run(['l1_start'], sides, fresh=fresh)
    rb, b = run(['l1_start'], sides, fake_shift=FAKE_DEFAULT)
    ports = [s for s in sides if s != 'orig']
    clean = not [x for x in a['findings'] if x['rule'] in ('pose_xz', 'pose_y', 'heading', 'speed')]
    seen = {s: max([x['value'] for x in b['findings'] if x['rule'] == 'pose_xz' and x['sides'].endswith(s)], default=0.0) for s in ports}
    ok = clean and all(v >= FAKE_DEFAULT * 0.8 for v in seen.values())
    res = dict(ok=ok, time=C.clock(), code=C.git_head(), broken=os.environ.get('TWINS_BREAK', ''), sides=list(sides),
               A=dict(run=str(ra.relative_to(C.DATA)), clean=clean, findings=[(x['rule'], x['sides'], x['value']) for x in a['findings']]),
               B=dict(run=str(rb.relative_to(C.DATA)), seen_pose_xz=seen))
    g = C.OUT / 'gates'; g.mkdir(parents=True, exist_ok=True)
    (g / f"b1_{C.stamp()}{'_break-' + res['broken'] if res['broken'] else ''}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1) + '\n')
    print(('PASS' if ok else 'FAIL'), 'гейт Б1', f"(сломано нарочно: {res['broken']})" if res['broken'] else '',
          f"| А без подлога: {'чисто' if clean else 'НЕ чисто ' + str(res['A']['findings'])} ({res['A']['run']})",
          f"| Б подлог {FAKE_DEFAULT} м: судья видит {', '.join(f'{k} {v:.2f} м' for k, v in seen.items())} ({res['B']['run']})")
    return 0 if ok else 1


def calib():
    """балласт = куча на старте эмулятора (свой PPSSPPHeadless, без балласта) − куча на старте последнего замера PSP (без балласта)"""
    hw = P.hw_heap_at_start()
    if not hw: raise SystemExit('нет замера PSP с «heap free at start» без балласта (build/psp-logs/*/smoke.txt)')
    rd = C.OUT / f'calib-{C.stamp()}'; rd.mkdir(parents=True)
    pt = [p for p in points() if p['name'] == 'l1_start'][0]
    place, _ = sync_pose(pt)
    _, i = P.run_full('l1_start', rd, 1.0, place=place, ballast_mb=0)
    emu = i['heap_start'][0]; mb = max(0, round(emu - hw[0]))
    BALLAST.write_text(json.dumps(dict(ballast_mb=mb, emu_heap_start=emu, hw_heap_start=hw[0], hw_log=hw[1], eboot=i['inputs']['EBOOT.PBP'],
                                       time=C.clock(), how='куча на старте: эмулятор без балласта − PSP без балласта'), ensure_ascii=False, indent=1) + '\n')
    print(f'балласт {mb} МБ: эмулятор {emu:.2f} МБ на старте, PSP {hw[0]:.2f} МБ ({hw[1]}) → {BALLAST.relative_to(C.DATA)}')
    return 0


def queue():
    """очередь вопросов — tools/twins/inbox.py (вход для других сессий и ботов)"""
    import inbox
    sys.argv = ['inbox.py', 'list']
    return inbox.main()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['run', 'gate', 'calib', 'queue'])
    ap.add_argument('--points'); ap.add_argument('--sides', default='orig,port_light,port_full'); ap.add_argument('--frames', type=int)
    ap.add_argument('--fake-shift', type=float, default=0.0); ap.add_argument('--no-sync', action='store_true'); ap.add_argument('--fresh', action='store_true')
    a = ap.parse_args()
    try:
        if a.cmd == 'gate': return gate(a.fresh)
        if a.cmd == 'calib': return calib()
        if a.cmd == 'queue': return queue()
        rd, res = run(a.points.split(',') if a.points else None, tuple(a.sides.split(',')), a.frames, a.fake_shift, a.no_sync, fresh=a.fresh)
        print(f"расхождений {len(res['findings'])}, не сверено {len(res['unknown'])}, пар кадров {len(res['pairs'])} → {(rd / 'report.md').relative_to(C.DATA)}")
        for x in res['findings'][:5]: print(f"  {x['point']} {x['sides']} {x['rule']} {x['value']} > {x['limit']}")
        return 0
    except (O.OrigFail, P.PortFail) as e:
        print('FAIL:', e); return 1


if __name__ == '__main__':
    sys.exit(main())
