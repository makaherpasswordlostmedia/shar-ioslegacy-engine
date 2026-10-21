#!/usr/bin/env python3
"""Правка 180: модели персонажей без родных полос PS2 — обычные списки Pure3D (louie_m — Луи у школы; прохожий busm2 трафика;
a_army_m, kearne_m). Номера костей вершины (0x1000b) лежат от старшего байта; прочитанные от младшего — рука торчит вбок
(эмулятор 03.10: busm2 со старым traffic.shr идёт с вытянутой рукой). Проверка по модели: экспорт tools/char_export.py → .chr →
поза стойки loco_idle_rest (art/chars/npd_a.p3d) той же математикой, что skin.c (char_export.skin): руки опущены — полуширина
модели по x не больше 0,65 м (у моделей с родными полосами в той же стойке 0,40–0,56 м: barney, lenny, carl, moe, burns, gil;
с торчащей рукой — 0,91–0,97 м); в позе T (bind) те же модели шире 0,6 м — мера различает.
Список моделей — с диска (группы кожи без 0x10012), руками не вписан.

  python3 tests/chars/generic_skin_check.py              зелёный
  python3 tests/chars/generic_skin_check.py --negative   красный: номера костей от младшего байта (прежнее чтение) — обязан упасть"""
import argparse, sys, tempfile
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools')); sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))
import char_export as ce   # noqa: E402
from p3d import read, walk   # noqa: E402

IDLE_MAX, BIND_MIN = .65, .6


def generic_models():
    out = []
    for f in sorted((ce.GAME / 'art/chars').glob('*_m.p3d')):
        pgs = [pg for s in walk(read(f)) if s.id == 0x10001 for pg in s.children if pg.id == 0x10002]
        if pgs and not all(any(k.id == 0x10012 for k in pg.children) for pg in pgs): out.append(f.name[:-6])
    return out


def half_width(m, clip):
    local = [(j['q'], j['t']) for j in m['joints']] if clip is None else ce.sample_local(m, clip, 0.)
    pal, _ = ce.palette(m, local)
    return max(float(np.abs(P[:, 0]).max()) for P, *_ in ce.skin(m, pal))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--negative', action='store_true'); a = ap.parse_args()
    ce.GENERIC_BONES_LSB = a.negative
    names = generic_models(); bad = []
    print(f'модели без родных полос: {names}')
    with tempfile.TemporaryDirectory() as td:
        for nm in names:
            out = Path(td) / f'{nm}.chr'
            import contextlib, io
            with contextlib.redirect_stdout(io.StringIO()):
                ce.export(nm, f'art/chars/{nm}_m.p3d', 'art/chars/npd_a.p3d', out, keep=['loco_idle_rest'])
            m = ce.read_chr(out); idle = next(i for i, c in enumerate(m['clips']) if c['name'].endswith('loco_idle_rest'))
            wb, wi = half_width(m, None), half_width(m, idle)
            ok = wi <= IDLE_MAX and wb >= BIND_MIN
            print(f'{nm:8s} поза T {wb:.2f} м, стойка {wi:.2f} м — {"руки опущены" if ok else "РУКА ТОРЧИТ" if wi > IDLE_MAX else "мера не различает"}')
            if not ok: bad.append(nm)
    if len(names) < 2: bad.append('моделей без родных полос меньше 2 — данные?')
    if bad:
        print(('КРАСНЫЙ (ожидаемо): ' if a.negative else 'ПРОВАЛ: ') + ', '.join(bad)); return 0 if a.negative else 1
    if a.negative: print('ПРОВАЛ ГЕЙТА: красный прогон прошёл'); return 1
    print('OK: у моделей без родных полос в стойке руки опущены'); return 0


if __name__ == '__main__':
    sys.exit(main())
