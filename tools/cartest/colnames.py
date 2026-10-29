#!/usr/bin/env python3
"""Имена исходных объектов для коробок и цилиндров COL1 (перепись стен, tools/cartest/walls.py): тот же сбор, что
tools/psp_export.py col_collect, плюс запись имени сущности на каждый поставленный примитив. level.shr не меняется.
Сверка: число и координаты центров совпадают с COL1 в level.shr, иначе ошибка.
  python3 tools/cartest/colnames.py [--level-shr build/level.shr] [--level 1] -> build/sandbox/colnames-l1.json"""
import argparse, json, struct, sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools')); sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))
import psp_export as ex
from p3d import read


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--level-shr', type=Path, default=ROOT / 'build/level.shr')
    ap.add_argument('--level', type=int, default=1); ap.add_argument('--out', type=Path)
    a = ap.parse_args()
    art = ex.GAME / 'art'; lv = a.level
    names = [f'l{lv}_terra'] + sorted(p.stem for p in art.glob(f'l{lv}r*.p3d')) + sorted(p.stem for p in art.glob(f'l{lv}z*.p3d'))
    cur = dict(name=None, scene=None); placed = []
    leaves0, place0 = ex.col_leaves, ex.col_place
    def leaves(v, name):
        cur['name'] = name; return leaves0(v, name)
    def place(s, M):
        k, rec, err = place0(s, M); placed.append((k, cur['name'], cur['scene'])); return k, rec, err
    ex.col_leaves, ex.col_place = leaves, place
    roots = []
    for n in names:
        cur['scene'] = n; roots.append((n, read(art / (n + '.p3d'))))
    # сцена у примитива: col_collect обходит сцены по порядку; имя сцены берём из списка по мере обхода
    walk0 = ex.walk
    def walk(root):
        for sc, r in roots:
            if r is root: cur['scene'] = sc
        return walk0(root)
    ex.walk = walk
    TR, BX, CY, SG, rep = ex.col_collect(roots)
    box = [(nm, sc) for k, nm, sc in placed if k == 'box']; cyl = [(nm, sc) for k, nm, sc in placed if k != 'box']
    b = a.level_shr.read_bytes(); co = struct.unpack_from('<I', b, 92)[0]
    hdr = struct.unpack_from('<4s3f8I', b, co); ntri, nbox, ncyl, nseg = hdr[6:10]
    # COL1: заголовок 48 Б -> треугольники 48 Б -> ящики 64 Б -> цилиндры 48 Б (tools/psp_export.py col_section)
    o = co + 48 + 48 * ntri; boxc = np.frombuffer(b, '<f4', 16 * nbox, o).reshape(-1, 16)[:, :3]
    cylc = np.frombuffer(b, '<f4', 12 * ncyl, o + 64 * nbox).reshape(-1, 12)[:, :3]
    # хвост COL1 после сбора — объёмы AnimCollision (tools/animobj_export.py col_extend: статичные и живые, ANM1): сверяем
    # префикс, хвост подписываем «AnimCollision»
    ok = nbox >= len(BX) == len(box) and ncyl >= len(CY) == len(cyl) and np.allclose(boxc[:len(BX)], BX[:, :3], atol=1e-3) \
        and np.allclose(cylc[:len(CY)], CY[:, :3], atol=1e-3)
    print(f'COL1: ящиков {nbox} (сбор {len(BX)}, имён {len(box)}), цилиндров {ncyl} (сбор {len(CY)}, имён {len(cyl)}), заборов {nseg}; '
          f'хвост AnimCollision: ящиков {nbox - len(BX)}, цилиндров {ncyl - len(CY)}; совпадает: {ok}')
    if not ok: return 1
    box += [('AnimCollision', None)] * (nbox - len(BX)); cyl += [('AnimCollision', None)] * (ncyl - len(CY))
    out = a.out or ROOT / f'build/sandbox/colnames-l{lv}.json'
    out.write_text(json.dumps(dict(box=box, cyl=cyl, nseg=int(nseg), scenes=names), ensure_ascii=False))
    print('->', out); return 0


if __name__ == '__main__':
    sys.exit(main())
