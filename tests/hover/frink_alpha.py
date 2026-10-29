#!/usr/bin/env python3
"""Гейт правки 413б по прогону tests/hover/frink_alpha.txt (tools/smoke.sh, безголовый эмулятор).
  python tests/hover/frink_alpha.py build/smoke/<время> [msncars-l7.shr]
Мерим (строки CARGLASS движка — треугольники СВОЕЙ машины за окно, делённые на кадры окна; снимки кадра):
  ship  (призрак L7, альфа текстуры 0..185 из 255 — полупрозрачен в данных): полупрозрачных треугольников за кадр = все 992 и при
        правиле, и прежним путём; снимки ship_new / ship_old по области машины совпадают (правило его не трогает; город вокруг живёт — прохожие)
  frink (frink_v, летающая машина Фринка): полупрозрачных за кадр = только прозрачное в данных (купол и катушка, считает
        tests/hover/mcr_dump.py по пакету, 60), прежний путь — весь кузов (красный: падает тем же критерием);
        снимок машины меняется (средняя разница по области машины, 0..255)
Выход 0 — всё сошлось; иначе первая строка — причина."""
import re, sys
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mcr_dump

CAR_BOX = (170, 110, 310, 225)   # область своей машины на снимке (камера за машиной, 480×272)


def windows(txt):
    """-> [(old, blend/кадр, opaque/кадр)] — второе окно каждой пары (первое — с начала сцены, с загрузкой модели)"""
    rows = [(int(m[1]), int(m[2]), int(m[3]), int(m[4])) for m in re.finditer(r'CARGLASS t=\S+ old=(\d) frames=(\d+) blend=(\d+) opaque=(\d+)', txt)]
    return [(o, b / max(f, 1), q / max(f, 1)) for o, f, b, q in rows[1::2]]


def main():
    run = Path(sys.argv[1]); pack = sys.argv[2] if len(sys.argv) > 2 else 'build/levels/l7/msncars-l7.shr'
    w = windows((run / 'smoke.txt').read_text(errors='replace'))
    if len(w) != 4: print(f'FAIL окон CARGLASS {len(w)} из 4 (прогон не дошёл)'); return 1
    exp = {}
    for name in ('ship', 'frink_v'):
        pcs, _ = mcr_dump.model(pack, name); near = [p for p in pcs if p['near']]
        exp[name] = (sum(p['tris'] for p in near), sum(p['tris'] for p in near if p['flags'] & 2 and not p['opaque_tex']))
    img = {k: np.asarray(Image.open(run / f'{k}.png').convert('RGB'), np.float32) for k in ('ship_new', 'ship_old', 'frink_new', 'frink_old')}
    box = lambda a: a[CAR_BOX[1]:CAR_BOX[3], CAR_BOX[0]:CAR_BOX[2]]
    d_ship = float(np.abs(box(img['ship_new']) - box(img['ship_old'])).mean())
    d_frink = float(np.abs(box(img['frink_new']) - box(img['frink_old'])).mean())
    ok = lambda name, blend: abs(blend - exp[name][1]) <= 0.5   # критерий: полупрозрачно ровно то, что прозрачно в данных
    res = [
        ('ship правило: полупрозрачных за кадр', w[0][1], exp['ship'][1], ok('ship', w[0][1])),
        ('ship прежнее: полупрозрачных за кадр', w[1][1], exp['ship'][1], ok('ship', w[1][1])),
        ('frink_v правило: полупрозрачных за кадр', w[2][1], exp['frink_v'][1], ok('frink_v', w[2][1])),
        ('frink_v правило: непрозрачных за кадр', w[2][2], exp['frink_v'][0] - exp['frink_v'][1], abs(w[2][2] - (exp['frink_v'][0] - exp['frink_v'][1])) <= 0.5),
    ]
    red = ('frink_v ПРЕЖНЕЕ (красный, обязан упасть): полупрозрачных за кадр', w[3][1], exp['frink_v'][1], ok('frink_v', w[3][1]))
    pix = [('ship: снимок правило/прежнее, разница по машине', d_ship, '< 1', d_ship < 1.),
           ('frink_v: снимок правило/прежнее, разница по машине', d_frink, '> 8', d_frink > 8.)]
    bad = [r for r in res if not r[3]] + [r for r in pix if not r[3]] + ([red] if red[3] else [])
    for r in res + [red]: print(f'{"ok  " if r[3] else "FAIL"} {r[0]}: {r[1]:.1f} (данные {r[2]})')
    for r in pix: print(f'{"ok  " if r[3] else "FAIL"} {r[0]}: {r[1]:.2f} ({r[2]})')
    if bad:
        print('FAIL', bad[0][0] if bad[0] is not red else 'красный контроль прошёл — гейт ничего не доказывает'); return 1
    print('PASS 413б: полупрозрачно только прозрачное в данных; прежний путь пойман'); return 0


if __name__ == '__main__':
    raise SystemExit(main())
