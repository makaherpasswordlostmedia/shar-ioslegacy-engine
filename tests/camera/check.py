#!/usr/bin/env python3
"""Разбор прогона tests/camera/scenario.txt (tools/smoke.sh): камера не заходит в стены (правки Роба 40, 27).

    python tests/camera/check.py build/smoke/<время> [--expect-red]

По каждой сцене — последняя строка CAMW (окно после «flag camstat 1»): кадров и кадров с глазом за препятствием (луч от точки
взгляда к глазу упирается в коллизию мира или комнаты). Зелёный: в каждой сцене кадров ≥ 15 и за препятствием 0.
--expect-red: проверка прогона с «flag nocamwall» — глаз за стеной хотя бы в MIN_RED сценах (иначе сценарий ничего не ловит)."""
import sys
from pathlib import Path

MIN_RED = 3


def kv(line):
    return dict(p.split('=', 1) for p in line.split()[1:] if '=' in p)


def main():
    out = Path(sys.argv[1]); red = '--expect-red' in sys.argv
    scene, last = None, {}
    for l in (out / 'smoke.txt').read_text().splitlines():
        if l.startswith('SCENE '): scene = l.split()[1]
        elif l.startswith('CAMW t=') and scene: last[scene] = kv(l)
    rows = {s: v for s, v in last.items() if s not in ('start', 'house_door')}
    fails, notes = [], []
    blocked_scenes = 0
    for s, v in rows.items():
        f, b = int(v['frames']), int(v['blocked'])
        notes.append(f"{s}: кадров {f}, глаз за препятствием {b} (пешком={v['onfoot']}, комната={v['room']})")
        if b: blocked_scenes += 1
        if not red and f < 15: fails.append(f'{s}: мало кадров ({f}) — сцена не дошла')
        if not red and b: fails.append(f'{s}: глаз камеры за стеной в {b} кадрах из {f}')
    if len(rows) < 6: fails.append(f'сцен с CAMW {len(rows)} из 6 (сценарий не дошёл)')
    if red and blocked_scenes < MIN_RED: fails.append(f'красный контроль: глаз за стеной только в {blocked_scenes} сценах (нужно ≥ {MIN_RED})')
    ok_msg = ('PASS (красный контроль: без обхода стен глаз за стеной в %d сценах)' % blocked_scenes) if red else \
        'PASS: камера пешком и за машиной у стен ни разу не за препятствием'
    print('FAIL: ' + fails[0] if fails else ok_msg)
    for f in fails[1:]: print('  ещё: ' + f)
    for n in notes: print('  ' + n)
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
