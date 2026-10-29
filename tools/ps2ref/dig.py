#!/usr/bin/env python3
"""О2 · раскопка памяти оригинала по атомарным снимкам (ОРАКУЛ_PS2 §3). Только меняющиеся данные: снимки, разности.
Кода игры не касаемся: области исполняемого файла не ищем, дизассемблера нет. Снимок — eeMemory.bin из .p2s (PINE save
или готовое состояние; zip, zstd метод 93, Python ≥ 3.14). dump.py (32 МБ по PINE ≈ 5 с на ходу) для разностей не годится.

  dig.py find  STATE.p2s --pos X Y Z [--tol 0.05]   тройки float рядом с позицией; какие из них — перенос матрицы 4×4
  dig.py copies STATE.p2s [STATE2.p2s ...] --addr HEX   все копии позиции из матрицы по адресу — в каждом снимке и общие
  dig.py diff  A.p2s B.p2s [C.p2s ...] --type f32|u32 --rule R [--quiet N1.p2s N2.p2s] [--lo L --hi H]
               R — цепочка знаков между соседними снимками: '+' выросло, '-' упало, '=' то же, '*' изменилось
               (пример: '+=' — выросло A→B и не менялось B→C); --quiet: пара снимков без события, изменившееся там — шум
  dig.py gate  гейт О2: без подсказки адреса находит матрицу машины 0xa21870 в state_l1_incar.p2s по позиции старта
               (215,05; 4,05; −170,25); с неверной подсказкой позиции не находит ничего (красный)"""
import argparse, json, sys, zipfile
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
EE_SIZE = 32 << 20
INCAR = ROOT / 'build/ps2ref/state_l1_incar.p2s'
START_POS = (215.05, 4.05, -170.25)
MAT_ADDR = 0xa21870


def load_ee(p2s):
    with zipfile.ZipFile(p2s) as z:
        ee = z.read('eeMemory.bin')
    if len(ee) != EE_SIZE: raise ValueError(f'{p2s}: eeMemory.bin {len(ee)} байт, ждём {EE_SIZE}')
    return np.frombuffer(ee, dtype=np.uint8)


def f32(ee): return ee.view('<f4')
def u32(ee): return ee.view('<u4')


def triples(ee, pos, tol):
    """Индексы float i, где f[i], f[i+1], f[i+2] ≈ pos (выровнено по 4 байта)."""
    f = f32(ee); n = len(f) - 2
    with np.errstate(invalid='ignore'):
        m = np.abs(f[:n] - pos[0]) < tol
        m &= np.abs(f[1:n + 1] - pos[1]) < tol
        m &= np.abs(f[2:n + 2] - pos[2]) < tol
    return np.nonzero(m)[0]


def matrix_at(ee, i):
    """Перенос в f[i..i+2] — строка 3 матрицы 4×4 по строкам (как 0xa21870)? Поворот ортонормирован, 4-й столбец 0 0 0 1."""
    f = f32(ee)
    if i < 12 or i + 3 >= len(f): return False
    m = f[i - 12:i + 4].astype(np.float64).reshape(4, 4)
    if not np.all(np.isfinite(m)): return False
    r = m[:3, :3]
    if np.max(np.abs(r @ r.T - np.eye(3))) > 1e-3: return False
    return bool(np.all(np.abs(m[:3, 3]) < 1e-4) and abs(m[3, 3] - 1.0) < 1e-4)


def find(p2s, pos, tol, quiet=False):
    ee = load_ee(p2s); hits = []
    for i in triples(ee, pos, tol):
        a = int(i) * 4; kind = 'mat4' if matrix_at(ee, int(i)) else 'vec3'
        hits.append(dict(addr=a - 48 if kind == 'mat4' else a, pos_addr=a, kind=kind,
                         value=[round(float(x), 4) for x in f32(ee)[i:i + 3]]))
    if not quiet:
        for h in hits: print(f"{h['kind']}  0x{h['addr']:07x}  (позиция в 0x{h['pos_addr']:07x})  {h['value']}")
        print(f'{len(hits)} совпадений ({sum(h["kind"] == "mat4" for h in hits)} матриц) в {p2s}')
    return hits


def copies(states, addr, tol=1e-3):
    common = None
    for s in states:
        ee = load_ee(s); pos = tuple(float(x) for x in f32(ee)[addr // 4 + 12:addr // 4 + 15])
        hits = {h['pos_addr']: h['kind'] for h in find(s, pos, tol, quiet=True)}
        print(f'{Path(s).name}: позиция {tuple(round(x, 3) for x in pos)}; копий {len(hits)}: ' +
              ', '.join(f'0x{a:07x}{"(m)" if k == "mat4" else ""}' for a, k in sorted(hits.items())))
        common = set(hits) if common is None else common & set(hits)
    print('общие для всех снимков:', ', '.join(f'0x{a:07x}' for a in sorted(common or [])) or 'нет')
    return sorted(common or [])


def diff(states, typ, rule, quiet=None, lo=None, hi=None):
    if len(rule) != len(states) - 1: raise ValueError('rule: по знаку на каждую пару соседних снимков')
    view = f32 if typ == 'f32' else u32
    vals = [view(load_ee(s)) for s in states]
    keep = np.ones(len(vals[0]), dtype=bool)
    with np.errstate(invalid='ignore'):
        for k, c in enumerate(rule):
            a, b = vals[k], vals[k + 1]
            keep &= {'+': b > a, '-': b < a, '=': b == a, '*': b != a}[c]
        if typ == 'f32': keep &= np.all([np.isfinite(v) for v in vals], axis=0)
        if lo is not None: keep &= np.all([v >= lo for v in vals], axis=0)
        if hi is not None: keep &= np.all([v <= hi for v in vals], axis=0)
        if quiet:
            q1, q2 = (view(load_ee(s)) for s in quiet); keep &= q1 == q2
    idx = np.nonzero(keep)[0]
    print(f'{len(idx)} адресов по правилу {rule!r} ({typ})' + (', шум отсеян парой без события' if quiet else ''))
    for i in idx[:60]:
        print(f'0x{int(i) * 4:07x}  ' + '  '.join(f'{v[i]:.4g}' if typ == 'f32' else str(int(v[i])) for v in vals))
    return idx


def gate():
    if not INCAR.exists(): print('FAIL: нет', INCAR); return 1
    out = {}
    hits = find(INCAR, START_POS, 0.05, quiet=True)
    mats = [h['addr'] for h in hits if h['kind'] == 'mat4']
    out['green'] = dict(hint=START_POS, hits=len(hits), matrices=[hex(a) for a in mats], found=MAT_ADDR in mats)
    wrong = (START_POS[0], START_POS[1], START_POS[2] + 50.0)
    whits = find(INCAR, wrong, 0.05, quiet=True)
    out['red'] = dict(hint=wrong, hits=len(whits), matrices=[hex(h['addr']) for h in whits if h['kind'] == 'mat4'])
    ok = out['green']['found'] and out['red']['hits'] == 0
    print(f"зелёный: подсказка {START_POS} → совпадений {len(hits)}, матрицы {out['green']['matrices']}; "
          f"0xa21870 {'найдена' if out['green']['found'] else 'НЕ найдена'}")
    print(f"красный: неверная подсказка {wrong} → совпадений {out['red']['hits']} "
          f"({'пусто, как должно' if out['red']['hits'] == 0 else 'НЕ пусто'})")
    dst = ROOT / 'build/ps2ref/gates/dig_gate.json'; dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(dict(ok=ok, state=str(INCAR), **out), ensure_ascii=False, indent=1) + '\n')
    print('PASS' if ok else 'FAIL', '→', dst.relative_to(ROOT))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    a = sp.add_parser('find'); a.add_argument('state'); a.add_argument('--pos', type=float, nargs=3, required=True)
    a.add_argument('--tol', type=float, default=0.05)
    a = sp.add_parser('copies'); a.add_argument('states', nargs='+'); a.add_argument('--addr', default='a21870')
    a = sp.add_parser('diff'); a.add_argument('states', nargs='+'); a.add_argument('--type', default='f32', choices=['f32', 'u32'])
    a.add_argument('--rule', required=True); a.add_argument('--quiet', nargs=2)
    a.add_argument('--lo', type=float); a.add_argument('--hi', type=float)
    sp.add_parser('gate')
    a = ap.parse_args()
    if a.cmd == 'find': find(a.state, a.pos, a.tol)
    elif a.cmd == 'copies': copies(a.states, int(a.addr, 16))
    elif a.cmd == 'diff': diff(a.states, a.type, a.rule, a.quiet, a.lo, a.hi)
    elif a.cmd == 'gate': return gate()
    return 0


if __name__ == '__main__':
    sys.exit(main())
