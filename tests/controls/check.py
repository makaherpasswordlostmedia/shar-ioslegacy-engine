#!/usr/bin/env python3
"""Разбор прогона tests/controls/scenario.txt (tools/smoke.sh): раскладка пешком как в оригинале.

    python tests/controls/check.py build/smoke/<время>

Источник: frontend.p3d ControllerPS2.pag (подписи «пешком»: X JUMP, □ ATTACK, ○ DASH / SPRINT, △ GET IN CAR / TALK TO
CHARACTER) и подсказка обучения srr2 «USE LEFT ANALOG STICK TO MOVE AROUND / USE X TO JUMP / PRESS AND HOLD ○ TO RUN».
Зелёный, если в режиме игрока (строка «SVC mode svc=0») шесть строк HOMERV (Гомер пешком) и:
  [walk]   ↑ без ○ — ходьба: наибольшая скорость на земле WALK_LO..WALK_HI (4 м/с)
  [sprint] ↑ + ○ — бег: не меньше SPRINT_MIN (8 м/с) и быстрее ходьбы на SPRINT_GAIN
  [kick]   □ на земле — удар (событие HIT), без стомпа
  [jkick]  X, потом □ — один прыжок и удар в прыжке (HIT), без стомпа
  [stomp]  X X □ — два прыжка и один стомп (событие STOMP)
Причина провала — первой строкой (с ключом), код 1."""
import sys
from pathlib import Path

WALK_LO, WALK_HI = 3.5, 4.4
SPRINT_MIN, SPRINT_GAIN = 7.5, 2.5


def kv(line):
    return dict(p.split('=', 1) for p in line.split()[1:] if '=' in p)


def main():
    out = Path(sys.argv[1]); log = (out / 'smoke.txt').read_text().splitlines()
    fails, notes = [], []
    mode = [kv(l) for l in log if l.startswith('SVC mode')]
    if not mode: fails.append('[mode] нет строки «SVC mode» (движок не знает flag player — старая сборка?)')
    elif mode[0].get('svc') != '0': fails.append(f"[mode] режим не игрока: svc={mode[0].get('svc')}")
    hv = [kv(l) for l in log if l.startswith('HOMERV')]
    notes.append('HOMERV: ' + '; '.join(f"vmax={h.get('vmax')} прыжков={h.get('jumps')} ударов={h.get('hits')} стомпов={h.get('stomps')}"
                                         f"{' (прежняя раскладка)' if h.get('oldpad') == '1' else ''}" for h in hv))
    if len(hv) < 6: fails.append(f'[run] строк HOMERV {len(hv)} из 6 (сценарий не дошёл; движок не знает flag homerv?)')
    else:
        if any(h.get('onfoot') != '1' for h in hv): fails.append('[run] Гомер не пешком в строке HOMERV')
        f = lambda i, k: float(hv[i][k])
        walk, run = f(1, 'vmax'), f(2, 'vmax')
        if not WALK_LO <= walk <= WALK_HI: fails.append(f'[walk] ↑ без ○: {walk:.2f} м/с, ждём ходьбу {WALK_LO}..{WALK_HI} (○ не зажат — не бег)')
        if run < SPRINT_MIN or run < walk + SPRINT_GAIN:
            fails.append(f'[sprint] ↑ + ○: {run:.2f} м/с при ходьбе {walk:.2f} — ○ не бег (ждём ≥ {SPRINT_MIN} и на {SPRINT_GAIN} быстрее)')
        d = lambda i, k: int(hv[i][k]) - int(hv[i - 1][k])
        if d(3, 'hits') < 1 or d(3, 'stomps'): fails.append(f"[kick] □ на земле: ударов +{d(3, 'hits')}, стомпов +{d(3, 'stomps')} (ждём удар без стомпа)")
        if d(4, 'jumps') != 1 or d(4, 'hits') < 1 or d(4, 'stomps'):
            fails.append(f"[jkick] X, □: прыжков +{d(4, 'jumps')}, ударов +{d(4, 'hits')}, стомпов +{d(4, 'stomps')} (ждём 1 прыжок и удар в прыжке)")
        if d(5, 'jumps') != 2 or d(5, 'stomps') != 1:
            fails.append(f"[stomp] X X □: прыжков +{d(5, 'jumps')}, стомпов +{d(5, 'stomps')} (ждём 2 прыжка и 1 стомп)")
    print('FAIL: ' + fails[0] if fails else 'PASS: пешком ↑ — шаг, ↑+○ — бег, □ — пинок, X □ — удар в прыжке, X X □ — стомп')
    for x in fails[1:]: print('  ещё: ' + x)
    for n in notes: print('  ' + n)
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
