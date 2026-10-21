#!/usr/bin/env python3
"""Сверка гейта «переход между уровнями» (tests/levels/switch.sh) по smoke.txt прогона tests/levels/switch_scenario.txt.

  switch_check.py RUN_DIR [--short]      -> первая строка PASS / FAIL, код 0 / 1 (--short: только круг 1 -> 2 -> 1)

Строки движка (viewer/main.c levelLog): LEVEL ev=load|free|now n=N ... heap=Б spawn=x,y,z,курс msn=N clt=N; LEVELUP from to.
Проверки:
  * порядок: уровень 1 -> (конец уровня: LEVELDONE code=1, LEVELUP from=1 to=2) -> уровень 2 -> уровень 1 [-> 3 .. 7];
  * набор уровня — свой: старт (заголовок level.shr) в 1.5 м и 0.01 рад от старта уровня по данным диска
    (tools/psp_export.level_start: локатор InitLevelPlayerVehicle; уровень 1 — правило порта SPAWN), номер уровня в пакете миссий
    (MSN1) и карточек (CLT1) = N; есть коллизия, пропы, трафик, частицы, интерфейс и звук своего уровня;
  * куча: уровень 1 после круга 1 -> 2 -> 1 — та же ±64 КБ (после чтения набора и на старте), куча после выгрузки любого уровня
    одна и та же ±64 КБ (всё, что читает уровень, возвращено);
  * на старте уровней 2–7 свободно не меньше 20 МБ (МиБ, как столбец «куча» смоука); уровень 1 — справочно (как до правки)."""
import sys, math
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools')); sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))
TOL = 64 * 1024
MIN_FREE = 20 * 1048576


def kv(line):
    return dict(p.split('=', 1) for p in line.split()[1:] if '=' in p)


def main():
    run = Path(sys.argv[1]); short = '--short' in sys.argv
    log = (run / 'smoke.txt').read_text(errors='replace').splitlines() if (run / 'smoke.txt').exists() else []
    lv = [(l.split()[0], kv(l)) for l in log if l.startswith(('LEVEL ', 'LEVELUP ', 'LEVELDONE '))]
    bad, notes = [], []
    if not any(l.startswith('END') for l in log): bad.append('нет END (упал / завис)')
    loads = [d for t, d in lv if t == 'LEVEL' and d.get('ev') == 'load']
    nows = [d for t, d in lv if t == 'LEVEL' and d.get('ev') == 'now']
    frees = [d for t, d in lv if t == 'LEVEL' and d.get('ev') == 'free']
    seq = [int(d['n']) for d in loads]
    want = [1, 2, 1] + ([] if short else [3, 4, 5, 6, 7])
    if seq != want: bad.append(f'порядок уровней {seq}, нужен {want}')
    if not any(t == 'LEVELDONE' and d.get('n') == '1' and d.get('code') == '1' for t, d in lv): bad.append('нет конца уровня 1 (LEVELDONE code=1)')
    if not any(t == 'LEVELUP' and d.get('from') == '1' and d.get('to') == '2' for t, d in lv): bad.append('нет перехода 1 -> 2 (LEVELUP)')
    import psp_export as PE
    starts = {}
    for d in loads:
        n = int(d['n'])
        if n not in starts: starts[n] = PE.level_start(n)
        (pos, h), car, src = starts[n]
        x, y, z, hh = map(float, d['spawn'].split(','))
        dist = math.hypot(x - pos[0], z - pos[2]); dh = abs((hh - h + math.pi) % (2 * math.pi) - math.pi)
        line = f'уровень {n}: старт ({x:.2f}, {y:.2f}, {z:.2f}) курс {hh:.3f}; данные: {src} — {dist:.2f} м, курс {dh:.3f}'
        if dist > 1.5 or abs(y - pos[1]) > 1.5 or dh > .01: bad.append('чужой набор? ' + line)
        else: notes.append(line)
        for k in ('msn', 'clt'):
            if d.get(k) != str(n): bad.append(f'уровень {n}: {k}={d.get(k)} (пакет чужого уровня или нет пакета)')
        for k in ('col', 'props', 'traffic', 'fx'):
            if d.get(k) != '1': bad.append(f'уровень {n}: {k}={d.get(k)}')
        if d.get('ui') != f'1/{n}' and not (n == 1 and d.get('ui') == '1/1'): bad.append(f'уровень {n}: интерфейс {d.get("ui")}')
        if d.get('snd') != f'1/{n}': bad.append(f'уровень {n}: звук {d.get("snd")}')
    # куча
    l1 = [int(d['heap']) for d in loads if d['n'] == '1']
    if len(l1) >= 2:
        dd = l1[1] - l1[0]
        (bad.append if abs(dd) > TOL else notes.append)(f'куча после чтения уровня 1: {l1[0]} -> {l1[1]} Б ({dd:+d} Б, допуск ±{TOL})')
    n1 = [int(d['heap']) for d in nows if d['n'] == '1']
    if len(n1) >= 2:
        dd = n1[1] - n1[0]
        (bad.append if abs(dd) > TOL else notes.append)(f'куча на старте уровня 1: {n1[0]} -> {n1[1]} Б ({dd:+d} Б)')
    fr = [int(d['heap']) for d in frees]
    if fr:
        span = max(fr) - min(fr)
        (bad.append if span > TOL else notes.append)(f'куча после выгрузки уровня ({len(fr)} раз): {min(fr)}..{max(fr)} Б, разброс {span} Б')
    else: bad.append('ни одной выгрузки уровня (LEVEL ev=free)')
    for d in nows:
        n = int(d['n']); f = int(d['heap'])
        s = f'уровень {n}: на старте свободно {f / 1048576:.2f} МиБ ({f / 1e6:.2f} МБ)'
        if n > 1 and f < MIN_FREE: bad.append(s + ' < 20 МиБ')
        else: notes.append(s + (' (справочно, как до правки)' if n == 1 else ''))
    for s in notes: print('  ' + s)
    for s in bad: print('  ПРОВАЛ: ' + s)
    print(('PASS' if not bad else f'FAIL ({len(bad)})') + f' — уровни {seq}')
    return 0 if not bad else 1


if __name__ == '__main__':
    r = main()
    sys.exit(r)
