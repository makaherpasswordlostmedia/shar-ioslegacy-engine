#!/usr/bin/env python3
"""Разбор прогона tests/cars/emu.sh (smoke.txt движка): машина уровня N в эмуляторе.

  emu_check.py SMOKE.txt --level N     PASS / FAIL (код 0 / 1)
Проверки: строка CAR — уровень N, машина = InitLevelPlayerVehicle уровня N с диска, прочитана из CAR1 v2 («машина уровня
из CAR1»); езда прямо — скорость (CARV) выросла до ≥ 5 м/с; △ — Гомер вышел (onfoot=1), △ — снова за рулём (onfoot=0);
свободная куча на старте уровня ≥ 20 МБ (последний столбец строк кадра сцены spawn); сцена drive — 30 FPS (медиана ≥ 29.4,
без строк «settling»); прогон дошёл до END."""
import re, sys, argparse, statistics
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
GAME = (ROOT / 'hit-and-run-web/source/game').resolve()   # как convert.GAME (папка — ссылка на общую копию)


def level_car(level):
    txt = re.sub(r'//[^\n]*', '', (GAME / f'scripts/missions/level0{level}/leveli.mfk').read_text(errors='replace'))
    return re.search(r'InitLevelPlayerVehicle\s*\(\s*"([^"]+)"', txt).group(1)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('smoke'); ap.add_argument('--level', type=int, required=True); a = ap.parse_args()
    p = Path(a.smoke)
    if not p.exists(): print(f'FAIL: нет {p}'); return 1
    lines = p.read_text(errors='replace').splitlines(); bad = []
    car = level_car(a.level)
    cl = next((l for l in lines if l.startswith('CAR ')), None)
    if not cl: bad.append('нет строки CAR (машина не прочитана)')
    else:
        kv = dict(re.findall(r'(\w+)=(\S+)', cl)); src = re.search(r'src=(.*?) mass=', cl).group(1)
        print(f'CAR: уровень {kv.get("level")}, машина {kv.get("car")} ({src}), масса {kv.get("mass")}, TopSpeed {kv.get("top")} км/ч, '
              f'кузов {kv.get("body")}, дверь {kv.get("door")}, камера {kv.get("cam")}')
        if kv.get('level') != str(a.level) or kv.get('car') != car or src != 'машина уровня из CAR1':
            bad.append(f'машина {kv.get("car")} ({src}) на уровне {kv.get("level")}; ждали {car} из CAR1 уровня {a.level}')
    scene, carv, fps, heap = None, [], {}, {}
    for l in lines:
        if l.startswith('SCENE '): scene = l.split()[1]
        m = re.match(r'CARV t=([\d.]+) v=([-\d.]+) onfoot=(\d)', l)
        if m: carv.append((scene, float(m.group(2)), int(m.group(3))))
        f = l.split()
        if len(f) >= 15 and re.match(r'^[\d.]+$', f[0]) and f[1] == scene:
            fps.setdefault(scene, []).append((float(f[2]), 'settling' in l)); heap.setdefault(scene, float(f[14]))
    drive = [v for s, v, _ in carv if s == 'drive']
    print(f'езда: CARV {[round(v, 1) for v in drive]} м/с')
    if not drive or max(drive) < 5.0: bad.append('езда прямо: скорость не выросла до 5 м/с')
    ex = [o for s, _, o in carv if s == 'exit']; en = [o for s, _, o in carv if s == 'enter']
    print(f'выход △: onfoot={ex}; посадка △: onfoot={en}')
    if ex != [1]: bad.append('△ — Гомер не вышел')
    if en != [0]: bad.append('△ — Гомер не сел обратно')
    h = heap.get('spawn')
    print(f'куча на старте: {h} МБ')
    if h is None or h < 20.0: bad.append(f'свободная куча на старте {h} МБ < 20')
    df = [v for v, st in fps.get('drive', []) if not st]
    med = statistics.median(df) if df else 0.0
    print(f'FPS езды: {[round(v, 1) for v in df]} (медиана {med:.1f})')
    if med < 29.4: bad.append(f'FPS езды {med:.1f} < 30')
    if not any(l.startswith('END') for l in lines): bad.append('прогон не дошёл до END')
    for b in bad: print('  ПРОВАЛ:', b)
    print(f'уровень {a.level} ({car}): ' + ('PASS' if not bad else f'FAIL ({len(bad)})'))
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(main())
