#!/usr/bin/env python3
"""SPR1 уровня (без конвертера: меши подменены треугольником, текстуры -1) — прежним prp2_export (файл OLD) и нынешним;
печатает, совпали ли байты подсекции по уровням. Уровни без барьеров 0x3F0000F обязаны совпасть (уровень 1 — прежний).

  python3 tests/levelmech/spr1_same.py OLD_prp2_export.py [уровни 1-7]
"""
import contextlib, importlib.util, io, sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools')); sys.path.insert(0, str(ROOT / 'tools'))


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def spr1(mod, lv):
    tri = [(0, 0, np.eye(3), np.zeros((3, 2)), np.full(3, 0xffffffff, np.uint32))]
    art = ROOT / 'hit-and-run-web/source/game/art'
    with contextlib.redirect_stdout(io.StringIO()):
        sp = mod.StateProps(lv, art, lambda f, m: tri, lambda f, s: -1, verbose=False)
        body = sp.section({-1: -1, 0: 0}, [])
    return body, sorted(sp.city_skip)


def main():
    old = load(sys.argv[1], 'prp2_old'); new = load(str(ROOT / 'tools/prp2_export.py'), 'prp2_new')
    lo, _, hi = (sys.argv[2] if len(sys.argv) > 2 else '1-7').partition('-')
    for lv in range(int(lo), int(hi or lo) + 1):
        a, ca = spr1(old, lv); b, cb = spr1(new, lv)
        print(f'L{lv}: SPR1 {"совпадает" if a == b else "другой"} ({len(a)} -> {len(b)} Б), город без мешей: '
              f'{"тот же" if ca == cb else "+" + ",".join(sorted(set(cb) - set(ca)))}')


if __name__ == '__main__':
    main()
