#!/usr/bin/env python3
"""Точки замер-тура — только там, где машина ездит (Роб 04.10: «зачем тест ставит машину в места, где ездить нельзя, в текстуры,
в дома?»). Карта проезжих клеток — build/playable-l1.tsv (tools/bots/anatomy.py map: рой исследователей на процессоре Мака,
клетка 6 м, машина ездит здесь по земле в связной сети от спавна; goto_ok = 1 — goto смоука кладёт машину именно на эту
поверхность, а не на крышу над ней; курс_ось — типичный курс движения ботов).

  fix_tour(S, path)         -> (S2, отчёт): каждая строка «goto X Z H» сценария тура проверяется; точка не на проезжей клетке —
                               сдвиг на ближайшую проезжую (до 60 м) с курсом вдоль движения ботов, печать «сдвинута на N м»;
                               ближе нет — сцена выбрасывается целиком (её goto, ожидания и снимки), печать «выброшена»
  playable_views(B, path)   -> виды части B (сетка стенда по всему уровню) только с проезжих клеток (без сдвига)
  on_green(x, z, P)         -> точка на проезжей клетке, куда goto ставит машину на поверхность езды
  python3 tools/tour_playable.py СЦЕНАРИЙ [--playable build/playable-l1.tsv]   проверка готового scenario.txt: точки вне зелёного"""
import math, sys
from pathlib import Path

G = 6.0
MAX_SHIFT = 60.0   # дальше — точка не про это место, выбросить


def load(path):
    """playable-l1.tsv -> {(x, z): dict(x, z, y, top, ax, st, n, ok, mx, mz)}; нет файла — None"""
    p = Path(path)
    if not p.exists(): return None
    P = {}
    for ln in p.read_text().splitlines():
        if ln.startswith('#') or not ln.strip(): continue
        f = ln.split('\t')
        x, z = int(f[0]), int(f[1]); ax = float(f[4]) if f[4] != '-' else float('nan')
        P[(x, z)] = dict(x=x, z=z, y=float(f[2]), top=float(f[3]), ax=ax, st=float(f[5]), n=int(f[6]), ok=int(f[7]),
                         mx=float(f[9]) if len(f) > 9 else x + G / 2, mz=float(f[10]) if len(f) > 10 else z + G / 2,
                         mask=f[11] if len(f) > 11 else '111111111', road=int(f[12]) if len(f) > 12 else 0)
    return P


def cell(x, z): return (int(math.floor(x / G) * G), int(math.floor(z / G) * G))


def on_green(x, z, P):
    """клетка проезжая и в этой её части (маска 2 м) goto кладёт машину на высоту езды ботов, а не на крышу или навес над ней"""
    c = P.get(cell(x, z))
    if not (c and c['ok']): return False
    i = min(2, int((x - c['x']) // 2)); j = min(2, int((z - c['z']) // 2))
    return c['mask'][3 * j + i] == '1'


def interior(c, P):   # соседей-проезжих из 8: внутри сети, не на краю у стены
    return sum(1 for dx in (-G, 0, G) for dz in (-G, 0, G) if (dx or dz) and (P.get((int(c['x'] + dx), int(c['z'] + dz))) or {}).get('ok'))


def heading_along(c, h):
    """курс вдоль движения ботов в клетке, ближайший к прежнему (ось по модулю π); движение не вдоль одной оси (перекрёсток,
    площадь, сила < 0.5) — прежний курс"""
    ax = c['ax']
    if ax != ax or c['st'] < .5: return h, False
    best = min((ax, ax + math.pi), key=lambda a: abs((a - h + math.pi) % (2 * math.pi) - math.pi))
    best = (best + math.pi) % (2 * math.pi) - math.pi
    return best, abs((best - h + math.pi) % (2 * math.pi) - math.pi) > math.radians(30)


def nearest(x, z, P):
    """ближайшая проезжая клетка; в приоритете — на дороге из данных уровня (асфальт, а не газон рядом), внутри сети (≥ 6 соседей из 8),
    с частыми проездами (≥ 20 выборок)"""
    best, bd = None, 1e18
    for c in P.values():
        if not c['ok']: continue
        d = math.hypot(c['mx'] - x, c['mz'] - z)
        pen = (0 if c['road'] else 20.) + (0 if interior(c, P) >= 6 else 12.) + (0 if c['n'] >= 20 else 8.)   # штраф в метрах: не дорога, край сети, редкий проезд
        if d + pen < bd: bd, best = d + pen, c
    return best


def fix_goto(x, z, h, P):
    """-> (x, z, h, сдвиг м, курс_поправлен) или None (выброшена)"""
    if on_green(x, z, P): return x, z, h, 0.0, False   # на проезжей клетке — точка и курс как были
    c = nearest(x, z, P)
    if not c: return None
    d = math.hypot(c['mx'] - x, c['mz'] - z)
    if d > MAX_SHIFT: return None
    h2, turned = heading_along(c, h)
    return c['mx'], c['mz'], h2, d, turned


KEEP = ('E_freeze', 'f10_')   # повтор пути Роба (место зависания 252, tests/crash_f10): точки — его, не двигать


def fix_tour(S, path, log=print, keep=KEEP):
    """сценарий тура (строки) -> (новые строки, сводка). Сцена = от строки «scene» до следующей «scene»/«end»; сцены keep — как есть"""
    P = load(path)
    if P is None:
        log(f'  (нет {path}: точки goto не проверены по карте проезжих клеток)'); return S, dict(checked=0)
    blocks, cur = [], []
    for l in S:
        if l.startswith('scene ') or l == 'end':
            if cur: blocks.append(cur)
            cur = [l]
        else: cur.append(l)
    if cur: blocks.append(cur)
    out, st = [], dict(checked=0, kept=0, turned=0, shifted=0, dropped=0)
    for b in blocks:
        name = b[0].split()[1] if b[0].startswith('scene ') else b[0]
        if name.startswith(keep):
            out += b; log(f'  {name}: точки как есть (повтор пути Роба)') if any(l.startswith('goto ') for l in b) else None; continue
        nb, drop = [], False
        for l in b:
            p = l.split()
            if p and p[0] == 'goto' and len(p) >= 4:
                x, z, h = float(p[1]), float(p[2]), float(p[3]); st['checked'] += 1
                r = fix_goto(x, z, h, P)
                if r is None:
                    log(f'  {name}: goto {x:.0f} {z:.0f} — выброшена (проезжих клеток ближе {MAX_SHIFT:.0f} м нет)'); st['dropped'] += 1; drop = True; break
                nx, nz, nh, d, turned = r
                if d > 0:
                    log(f'  {name}: goto {x:.0f} {z:.0f} — сдвинута на {d:.0f} м -> {nx:.1f} {nz:.1f}, курс {nh:.3f}' + (' (вдоль движения ботов)' if turned else ''))
                    st['shifted'] += 1
                else: st['kept'] += 1
                nb.append(f'goto {nx:.1f} {nz:.1f} {nh:.4f}' if d > 0 else l)
            else: nb.append(l)
        if not drop: out += nb
    log(f'  точки goto по карте проезжих клеток: проверено {st["checked"]}, на проезжей клетке {st["kept"]}, сдвинуто {st["shifted"]}, '
        f'выброшено сцен {st["dropped"]}')
    return out, st


def playable_views(B, path, log=print):
    """часть B: виды (имя, «goto X Z H») только с проезжих клеток; остальные — в отчёт"""
    P = load(path)
    if P is None: return []
    keep = []
    for name, go in B:
        p = go.split(); x, z = float(p[1]), float(p[2])
        if on_green(x, z, P): keep.append((name, go))
    log(f'  виды B: {len(B)} точек стенда, с проезжих клеток {len(keep)}, остальные (дома, текстуры, крыши) не взяты')
    return keep


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument('scenario'); ap.add_argument('--playable', default=str(Path(__file__).resolve().parents[1] / 'build/playable-l1.tsv'))
    a = ap.parse_args(); P = load(a.playable); bad = 0; n = 0; scene = '-'
    for l in Path(a.scenario).read_text().splitlines():
        p = l.split()
        if p and p[0] == 'scene': scene = p[1]
        if p and p[0] == 'goto':
            n += 1; x, z = float(p[1]), float(p[2])
            if not on_green(x, z, P): bad += 1; print(f'  вне зелёного: {scene}: {l}')
    print(f'{a.scenario}: точек goto {n}, вне зелёного {bad}')
    sys.exit(1 if bad else 0)
