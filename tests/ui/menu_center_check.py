#!/usr/bin/env python3
"""Аудит интерфейса 151 и отзыв Роба 26.09 («пункты жмутся к верху рамки-телевизора, низ пустой»): OPTIONS главного меню —
у PSP скрыты строки оригинала Display, Controller, SurroundSound (tools/menu_export.py HIDE_ROWS), видимые SOUND / VIEW MOVIES /
VIEW CREDITS стояли на местах верхних строк, внизу дыра. Правило порта: столбец видимых строк — посередине места всех строк
оригинала. Проверка по раскладке экспортёра (tools/menu_export.py items, хост, без эмулятора): середина столбца видимых строк
не дальше 2 px от середины места строк оригинала; шаг строк тот же.
  python3 tests/ui/menu_center_check.py               зелёный
  python3 tests/ui/menu_center_check.py --negative    красный: MENU_TOP=1 (прежнее — к верху) обязан упасть"""
import argparse, importlib, os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--negative', action='store_true'); a = ap.parse_args()
    if a.negative: os.environ['MENU_TOP'] = '1'
    M = importlib.import_module('menu_export'); U = M.U
    U.SCREEN_PAGES['options'] = M.PAGES['options']   # как export(): экраны пакета menu
    its, _ = U.build_items('options')
    tops_all = {}
    for it in its:
        k = M.row_key(it)
        if k is not None: tops_all[k] = min(tops_all.get(k, 1e9), it['rect'][1])
    rk = M.rows(its); M.compact(its, rk, center=True)
    tops = {}
    for it in its:
        k = M.row_key(it)
        if k in rk: tops[k] = min(tops.get(k, 1e9), it['rect'][1])
    vis = sorted(tops.values()); allv = sorted(tops_all.values())
    first = min(tops_all[k] for k in rk)
    span_c = (first + allv[-1]) / 2; vis_c = (vis[0] + vis[-1]) / 2
    steps = [round(b - a, 1) for a, b in zip(vis, vis[1:])]
    print(f'строк оригинала {len(allv)} ({sorted(tops_all, key=tops_all.get)}), видимых {len(vis)}: верх {vis[0]:.1f}, шаг {steps}; '
          f'середина видимых {vis_c:.1f}, середина места строк {span_c:.1f}')
    bad = abs(vis_c - span_c) > 2 or len(set(steps)) > 1
    if bad:
        print(('КРАСНЫЙ (ожидаемо): ' if a.negative else 'ПРОВАЛ: ') + f'столбец не посередине (сдвиг {vis_c - span_c:+.1f} px)'); return 0 if a.negative else 1
    if a.negative: print('ПРОВАЛ ГЕЙТА: красный прошёл'); return 1
    print('OK: пункты OPTIONS посередине места строк оригинала'); return 0


if __name__ == '__main__':
    sys.exit(main())
