#!/usr/bin/env python3
"""№236: машина не уходит с места при входе в дом и выходе. Вход: smoke.txt прогона tests/rooms/car_stays_236.txt.
Допустимые CARJUMP — только сразу (до 0,5 с) после начала сцены *_car (это сам сценарий ставит машину командой goto).
Остальные CARJUMP (в комнате, после выхода, на улице) — провал. Нужны входы и выходы всех трёх комнат (ROOM ev=enter/exit по 3).
  car_stays_236.py smoke.txt          — проверка;   car_stays_236.py --selftest — красный контроль на подброшенной строке CARJUMP"""
import re, sys

def check(lines):
    scene_t = {}; cur = None; bad = []; enters = exits = 0
    for ln in lines:
        m = re.match(r'SCENE (\S+) ([\d.]+)', ln)
        if m: cur = m.group(1); scene_t[cur] = float(m.group(2)); continue
        if ln.startswith('ROOM ev=enter'): enters += 1
        if ln.startswith('ROOM ev=exit'): exits += 1
        m = re.match(r'CARJUMP .* t=([\d.]+)', ln)
        if m:
            t = float(m.group(1))
            if not (cur and cur.endswith('_car') and t - scene_t[cur] <= 0.5): bad.append(ln.strip())
    return bad, enters, exits

def main():
    if sys.argv[1] == '--selftest':
        base = ['SCENE K_car 3.1', 'CARJUMP from=1,1 to=2,2 d=382 op=x t=3.2', 'ROOM ev=enter room=K', 'ROOM ev=exit room=K', 'SCENE K_out 9.0']
        bad, e, x = check(base); assert not bad and e == 1 and x == 1, (bad, e, x)
        bad, e, x = check(base + ['CARJUMP from=1,1 to=9,9 d=11 op=room t=10.0']); assert len(bad) == 1, bad
        print('selftest: подброшенный перенос после выхода пойман, перенос сценария пропущен'); return 0
    bad, e, x = check(open(sys.argv[1], errors='replace'))
    if bad or e < 3 or x < 3:
        print('FAIL car_stays_236: переносов %d, входов %d, выходов %d' % (len(bad), e, x)); [print('  ', b) for b in bad]; return 1
    print('PASS car_stays_236: входов %d, выходов %d, машину не переносило' % (e, x)); return 0
sys.exit(main())
