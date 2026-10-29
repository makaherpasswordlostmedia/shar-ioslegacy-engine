#!/usr/bin/env python3
"""Сверка гейта «сохранение несёт уровень» (tests/levels/save_level.sh) по smoke.txt двух прогонов:
  прогон 1 (save_level_save.txt): уровень 2 прочитан (LEVEL ev=load n=2, пакеты уровня 2), прогресс SVPROG src=now level=2,
            запись подтверждена чтением (SVIO op=save res=00000000 verify=O), «Save Successful», игра не упала;
  прогон 2 (save_level_load.txt): LOAD GAME слота 1 -> прочитан набор уровня записи (LEVEL ev=load n=2: старт уровня 2 из
            данных диска, пакеты миссий и карточек уровня 2), SVPROG src=load level=2 и тот же прогресс, что при записи;
  прогон 3 (save_level_resume.txt, необязательный): RESUME GAME — то же, что прогон 2.
    save_level_check.py RUN1 RUN2 [RUN3]   -> последняя строка PASS / FAIL, код 0 / 1"""
import sys, math
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools')); sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))
KEYS = ('level', 'msn', 'story', 'cards', 'wasps', 'gags', 'coins', 'vol', 'radar')
LEVEL = 2


def lines(d):
    p = Path(d) / 'smoke.txt'
    return p.read_text(errors='replace').splitlines() if p.exists() else []


def kv(line):
    return dict(p.split('=', 1) for p in line.split()[1:] if '=' in p)


def first(log, head, **want):
    return next((l for l in log if l.startswith(head + ' ') and all(kv(l).get(k) == v for k, v in want.items())), None)


def level_ok(log, tag, bad):
    ld = [kv(l) for l in log if l.startswith('LEVEL ') and kv(l).get('ev') == 'load']
    if not ld: bad.append(f'{tag}: уровень не читался (нет LEVEL ev=load)'); return
    d = ld[-1]
    if d.get('n') != str(LEVEL): bad.append(f'{tag}: прочитан уровень {d.get("n")}, а не {LEVEL}'); return
    import psp_export as PE
    (pos, h), car, src = PE.level_start(LEVEL)
    x, y, z, hh = map(float, d['spawn'].split(','))
    if math.hypot(x - pos[0], z - pos[2]) > 1.5: bad.append(f'{tag}: старт ({x:.1f}, {z:.1f}) не уровня {LEVEL} ({src})')
    for k in ('msn', 'clt'):
        if d.get(k) != str(LEVEL): bad.append(f'{tag}: {k}={d.get(k)} — пакет не уровня {LEVEL}')
    print(f'  {tag}: уровень {d["n"]}, старт ({x:.2f}, {y:.2f}, {z:.2f}) — {src}; msn={d.get("msn")} clt={d.get("clt")}')


def main():
    r1, r2 = lines(sys.argv[1]), lines(sys.argv[2])
    runs = [('прогон 2 (LOAD GAME)', r2)] + ([('прогон 3 (RESUME GAME)', lines(sys.argv[3]))] if len(sys.argv) > 3 else [])
    bad = []
    for tag, lg in [('прогон 1', r1)] + runs:
        if not any(l.startswith('END') for l in lg): bad.append(f'{tag}: нет END (упал / завис)')
    level_ok(r1, 'прогон 1 (новая игра, уровень 2)', bad)
    now = first(r1, 'SVPROG', src='now')
    if not now: bad.append('прогон 1: нет строки прогресса (SVPROG src=now)')
    elif kv(now).get('level') != str(LEVEL): bad.append(f'прогон 1: прогресс уровня {kv(now).get("level")}')
    io = first(r1, 'SVIO', op='save')
    if not io or kv(io).get('res') != '00000000' or kv(io).get('verify') != 'O': bad.append('прогон 1: запись не подтверждена (%s)' % (io or 'нет SVIO op=save'))
    if not first(r1, 'SVMSG', key='MSG_SAVE_SUCCESSFUL'): bad.append('прогон 1: нет «Save Successful»')
    for tag, lg in runs:
        level_ok(lg, tag, bad)
        got = first(lg, 'SVPROG', src='load')
        if not got: bad.append(f'{tag}: загрузки не было (нет SVPROG src=load)')
        elif now:
            a, b = kv(now), kv(got)
            diff = [f'{k} {a.get(k)}->{b.get(k)}' for k in KEYS if a.get(k) != b.get(k)]
            if diff: bad.append(f'{tag}: прогресс после загрузки другой: ' + ', '.join(diff))
            else: print(f'  {tag}: прогресс = прогресс записи: level={b.get("level")} msn={b.get("msn")} story={b.get("story")}')
    for s in bad: print('  ПРОВАЛ: ' + s)
    print('PASS' if not bad else f'FAIL ({len(bad)})')
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(main())
