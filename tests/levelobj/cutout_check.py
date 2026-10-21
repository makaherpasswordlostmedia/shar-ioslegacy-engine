#!/usr/bin/env python3
"""Гейт семейства «вырезка со смешиванием» (правка Роба 28.09: лестница пожарной машины местами пропадает).

  python3 tests/levelobj/cutout_check.py LEVEL.shr [--expect-family N]
Правило (tools/psp_export.py binary_alpha): куски города, пропов, стейтпропов и машины, чья текстура — «вырезка»
(альфа уровня 0 почти только 0/255: то же условие, что texq/blendmip_check is_cutout), рисуются альфа-тестом с записью
глубины, НЕ смешиванием (флаг 2): иначе на мелких мипах PSP предмет — полупрозрачный призрак (у лестницы альфа 62%),
а без записи глубины его перекрывает соседнее прозрачное. Билборды (свечения, тени) — всегда смешивание, не считаются.
Проверки: [1] ни одной вырезки со смешиванием у кусков; [2] вырезок с одним альфа-тестом не меньше, чем было
(семейство не пропало из уровня); мипы вырезок с альфа-тестом держат покрытие — отдельный гейт tools/blendmip_check.py.
Отрицательный контроль: уровень до правила (SHR_CUT_BLEND=0 или сборка до пакета) обязан упасть на [1]."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import blendmip_check as BC   # noqa: E402

def main():
    path = Path(sys.argv[1]); b = path.read_bytes(); assert b[:4] == b'SHR7'
    T = BC.textures(b); U = BC.users(b)
    bad, cut_alpha = [], 0
    for ti, (w, h, pal, lv) in enumerate(T):
        if ti not in U or not BC.is_cutout(lv[0][..., 3].astype(float)): continue
        who = U[ti]['blend'] - {'билборд'}
        if who: bad.append(f'  tex {ti} {w}x{h}: вырезка со смешиванием у {", ".join(sorted(who))}')
        if U[ti]['alpha']: cut_alpha += 1
    for s in bad: print(s)
    need = int(sys.argv[sys.argv.index('--expect-family') + 1]) if '--expect-family' in sys.argv else 0
    ok1, ok2 = not bad, cut_alpha >= need
    print(f'CHECK cutout.no_blend  {"ok  " if ok1 else "FAIL"} вырезок со смешиванием у кусков: {len(bad)}')
    print(f'CHECK cutout.family    {"ok  " if ok2 else "FAIL"} вырезок с альфа-тестом: {cut_alpha} (нужно >= {need})')
    print(f'RESULT {"PASS" if ok1 and ok2 else "FAIL"}')
    return 0 if ok1 and ok2 else 1

if __name__ == '__main__':
    sys.exit(main())
