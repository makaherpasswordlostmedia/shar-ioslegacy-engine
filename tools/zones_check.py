#!/usr/bin/env python3
"""Гейт (а) правки 139: прочтение строк загрузчиков зон (tools/traffic_export.py dyna_loaders) сверено с другим местом диска.
level.mfk AddTeleportDest(имя, x, y, z, "файлы;") называет файлы зон, загруженные в точке телепорта. Для каждой точки
набор ворот ближайшего уличного загрузчика обязан содержать все её файлы. Если перепутать «;» и «:» (--swap), наборы
становятся дополнением — проверка падает. Только данные, Мак.
  python3 tools/zones_check.py [--level 1] [--swap]
"""
import argparse, math, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools')); sys.path.insert(0, str(ROOT / 'tools/missions'))
import traffic_export as te   # noqa: E402
import mfk                    # noqa: E402


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--level', type=int, default=1); ap.add_argument('--swap', action='store_true')
    a = ap.parse_args()
    files = te.zone_files(a.level); loaders = te.dyna_loaders(a.level, swap=a.swap)
    print(f'уровень {a.level}: файлов зон {len(files)}, ворот уличных загрузчиков {len(loaders)}{" (ПОДБРОСКА swap)" if a.swap else ""}')
    calls, _ = mfk.parse_file(te.GAME / f'scripts/missions/level{a.level:02d}/level.mfk')
    bad = n = 0
    for c in calls:
        if c.op != 'AddTeleportDest' or len(c.args) < 5: continue
        x, z = float(c.args[1]), -float(c.args[3])            # координаты level.shr: z зеркалим
        want = {f[:-4].lower() for f in str(c.args[4]).split(';') if f.lower().endswith('.p3d')}
        wm = sum(1 << i for i, f in enumerate(files) if f in want)
        L = min(loaders, key=lambda L: math.hypot(L['c'][0] - x, L['c'][2] - z)) if loaders else None
        ok = L is not None and wm and (L['mask'] & wm) == wm; n += 1; bad += not ok
        print(f'  {"ok  " if ok else "FAIL"} {str(c.args[0])[:24]:24s} файлы {sorted(want)} ворота {L["name"] if L else "-"} '
              f'{math.hypot(L["c"][0] - x, L["c"][2] - z) if L else 0:5.0f} м')
    if not n: print('FAIL нет AddTeleportDest'); bad += 1
    print(f'RESULT {"PASS" if not bad else "FAIL"} точек {n}, ошибок {bad}'); return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
