#!/usr/bin/env python3
"""Старт, машина и небо уровня N — из данных (блокер уровней 2–7, docs/РЕЦЕПТ_УРОВНЯ.md §3.1, 29.09): level.shr против диска.

  start_check.py --level N SHR            PASS / FAIL (код 0 / 1)
  start_check.py --plant-center SHR КОПИЯ старт в заголовке — центр габарита на максимальной высоте курсом 0 (как было у 2–7
                                          до 29.09) — обязан дать FAIL
  start_check.py --plant-nosky SHR КОПИЯ  куски неба отданы городу (как l2..l7 до 29.09: неба нет) — обязан дать FAIL
  (машина чужого уровня: level.shr уровня 1 с famil_v проверить как уровень 4 — обязан дать FAIL)
Проверки (свой разбор файла; данные — скрипты и локаторы диска):
  * старт: заголовок SHR7 @36 (x y z курс) в 1.5 м от локатора InitLevelPlayerVehicle уровня (tools/level_sweep.find_spawn),
    курс — в 0.01 рад; уровень 1 — ПРАВИЛО ПОРТА tools/psp_export.py SPAWN (точка телепорта Simpsons' House, pi/2);
  * машина: суставы CAR1 = скелет составного рисунка модели машины уровня (LoadDisposableCar / art/cars/<машина>.p3d) — имена
    по порядку; famil_v на уровне с honor_v — провал;
  * небо: куски владельца 2 (небо) есть и в них есть треугольники — у l2..l7_terra небо только в мировой сфере 0x3f0000b."""
import sys, struct, math, argparse
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools')); sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))


def car_joints(level):
    import psp_export as PE, car_dump as cd
    from p3d import read, string
    (pos, h), car, src = PE.level_start(level)
    root = read(PE.car_model(level, car))
    comp = next(c for c in root.children if c.id == 0x4512)
    _, p = string(comp.data); sk, _ = string(comp.data, p)
    J = cd.skeleton(next(c for c in root.children if c.id == 0x4500 and string(c.data)[0] == sk))
    return car, [j[0][:11] for j in J], (pos, h), src


def check(level, shr):
    d = Path(shr).read_bytes(); bad = []
    if d[:4] != b'SHR7': print('FAIL: не SHR7'); return 1
    sx, sy, sz, sh = struct.unpack_from('<4f', d, 36)
    car, joints, (pos, h), src = car_joints(level)
    dist = math.hypot(sx - pos[0], sz - pos[2])
    dh = abs((sh - h + math.pi) % (2 * math.pi) - math.pi)
    (bad.append if dist > 1.5 or abs(sy - pos[1]) > 1.5 or dh > .01 else print)(
        f'старт ({sx:.2f}, {sy:.2f}, {sz:.2f}) курс {sh:.3f}; данные: {src} ({pos[0]:.2f}, {pos[1]:.2f}, {pos[2]:.2f}) курс {h:.3f} — {dist:.2f} м')
    c1, = struct.unpack_from('<I', d, 100)
    if not c1 or d[c1:c1 + 4] != b'CAR1': bad.append('нет CAR1')
    else:
        nj, = struct.unpack_from('<I', d, c1 + 8)
        got = [d[c1 + 80 + 28 * i:c1 + 80 + 28 * i + 12].split(b'\0')[0].decode('latin1') for i in range(nj)]
        (bad.append if got != joints else print)(f'машина {car}: суставов CAR1 {nj}, скелет модели {len(joints)}' +
                                                  ('' if got == joints else f'; CAR1 {got[:5]}…, модель {joints[:5]}…'))
    npc, = struct.unpack_from('<I', d, 8); po, = struct.unpack_from('<I', d, 76)
    sky = [struct.unpack_from('<I', d, po + 80 * i + 36)[0] for i in range(npc) if struct.unpack_from('<I', d, po + 80 * i + 40)[0] == 2]
    (bad.append if not sky or sum(sky) == 0 else print)(f'небо: кусков {len(sky)}, треугольников {sum(sky) // 3}')
    for b in bad: print('  ПРОВАЛ:', b)
    print(f'уровень {level}: ' + ('PASS' if not bad else f'FAIL ({len(bad)})'))
    return 0 if not bad else 1


def plant_center(src, dst):
    d = bytearray(Path(src).read_bytes()); bb = struct.unpack_from('<6f', d, 12)
    struct.pack_into('<4f', d, 36, (bb[0] + bb[3]) / 2, bb[4], (bb[2] + bb[5]) / 2, 0.0)
    Path(dst).write_bytes(bytes(d)); return 0


def plant_nosky(src, dst):
    d = bytearray(Path(src).read_bytes()); npc, = struct.unpack_from('<I', d, 8); po, = struct.unpack_from('<I', d, 76)
    for i in range(npc):
        if struct.unpack_from('<I', d, po + 80 * i + 40)[0] == 2: struct.pack_into('<I', d, po + 80 * i + 40, 0)
    Path(dst).write_bytes(bytes(d)); return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('shr', nargs='?'); ap.add_argument('--level', type=int, default=1)
    ap.add_argument('--plant-center', nargs=2, metavar=('SHR', 'КОПИЯ')); ap.add_argument('--plant-nosky', nargs=2, metavar=('SHR', 'КОПИЯ'))
    a = ap.parse_args()
    if a.plant_center: return plant_center(*a.plant_center)
    if a.plant_nosky: return plant_nosky(*a.plant_nosky)
    return check(a.level, a.shr)


if __name__ == '__main__':
    sys.exit(main())
