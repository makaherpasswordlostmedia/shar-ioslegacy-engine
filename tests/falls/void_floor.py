#!/usr/bin/env python3
"""Гейт правки 142, семейство «над пустотой без шага» (ДОБИВКА 13): ночи ботов 02.10–07.10, L1 J14-3 / J14-6 / K14-1 (дорога l1r2
под нависающим склоном холма) — Гомер попадал в столб без опоры не шагом (шаг туда — стена voidEdge), а выходом через верх
на крышу машины у края дороги под склоном: машина отъезжала/скатывалась, он сходил с крыши — и падал до «выпал из мира» (60 м),
застряв по плоскости (каждый подшаг в пустоту отменён). Правило (viewer/homer.c voidFloor, за HOMER_VOID_FLOOR_OLD): такой
столб — пол на высоте ближайшей опоры рядом; оттуда к опоре можно идти. Оракул PS2 f03/f08: машина оригинала там не падает.
Повторы tests/bots/regress/vf_*.in (ввод каскадёра, не ресурс игры) проигрываются game_headless двумя сборками мира:
  зелёная — как есть; красная — -DHOMER_VOID_FLOOR_OLD=1 (как до правки).
Провал = игрок ниже FALL_Y хоть на одном кадре. Требования:
  1) каждый повтор: красная проваливается, зелёная нет;
  2) соседние варианты ввода (стик ±10°/±20°, ×0.7, бег↔шаг): в зелёной провалов 0, в красной есть;
  3) правило сработало и не заперло: в каждом зелёном повторе Гомер садится на пол над пустотой, и с этого кадра за 3 с
     бега хоть в одну из 8 сторон стика уходит на опору коллизии
     (probe --under: под ним земля коллизии) — правило не делает из пустоты ловушку;
  4) законные падения целы: прыжок с моста l1r7 в канал (g4_001) возвращает зона DEATH, падения ≥ 2 м с посадкой есть.
  5) L1 F10-8 (повторы vt_*.in, ящик b188): красная -DHOMER_VOID_SQUEEZE_OLD=1 заперта (8 сторон × бег/двойной прыжок — никуда
     на 1.5 м), зелёная нет; соседние варианты в зелёной не заперты ни разу.
  python3 tests/falls/void_floor.py BIN_GREEN BIN_RED PROBE BIN_RED_SQUEEZE   -> PASS / FAIL"""
import math, os, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from check import variant, frames, TR, LVL, HOM, FALL_Y   # тот же разбор трассы и те же варианты, что у гейта Г4
ROOT = Path(__file__).resolve().parents[2]
REG = ROOT / 'tests/bots/regress'


def trace(binp, path, env=None):
    s = re.search(r'--start (\S+) (\S+) (\S+) (\S+)', Path(path).read_text().split('\n', 1)[0]).groups()
    r = subprocess.run([str(binp), str(LVL), str(HOM), '--input', str(path), '--start', *s], capture_output=True, text=True,
                       env=dict(os.environ, GH_TRACE='1', **(env or {})))
    return [(int(m[1]), m[2], float(m[3]), float(m[4]), float(m[5]), int(m[6])) for m in TR.finditer(r.stderr)], r.stderr


def judge(rows):
    if not rows: return None
    ymin = min(q[3] for q in rows); drops = 0; top = None
    for a, b in zip(rows, rows[1:]):
        if a[5] and not b[5]: top = a[3]
        if b[5] and top is not None:
            if top - b[3] >= 2.0 and b[3] > FALL_Y: drops += 1
            top = None
    tele = any(a[1] == b[1] == 'Гомер' and math.dist(a[2:5], b[2:5]) > 5 for a, b in zip(rows, rows[1:]))
    return dict(fell=ymin < FALL_Y, ymin=ymin, drops=drops, tele=tele, end=rows[-1])


def under(probe, x, y, z):
    w = subprocess.run([str(probe), str(LVL), str(HOM), '--under', f'{x}', f'{y}', f'{z}'], capture_output=True, text=True).stdout
    return 'U\t1' in w


def cut(path, n):
    """первые n кадров ввода повтора (строки "N кнопки ax ay" — N кадров подряд)"""
    lines = Path(path).read_text().splitlines(); out = [lines[0]]; left = n
    for ln in lines[1:]:
        if ln.startswith('#') or not ln.strip(): continue
        k, rest = ln.split(None, 1); k = int(k)
        if left <= 0: break
        out.append(f'{min(k, left)} {rest}'); left -= k
    return '\n'.join(out)


def escape(binp, probe, path, tmp):
    """первый кадр на полу над пустотой (GH_VOID=1: счётчик homer.c voidFloors) -> ввод до этого кадра + 3 с бега (○)
    стиком в одну из 8 сторон: стоит ли он потом на земле коллизии (probe --under). -> (кадр посадки, стороны с выходом)"""
    _, err = trace(binp, path, {'GH_VOID': '1'}); m = re.search(r'пол над пустотой кадр (\d+)', err)   # homer.c voidFloors
    if not m: return None, []
    land = int(m.group(1)); txt = cut(path, land + 1); ok = []
    for k in range(8):
        a = k * math.pi / 4; q = tmp / f'{Path(path).stem}_esc{k}.in'
        q.write_text(txt + f'\n180 2000 {math.sin(a):.4f} {math.cos(a):.4f}\n30 0 0 0\n')
        r2, _ = trace(binp, q); e = r2[-1] if r2 else None
        if e and e[1] == 'Гомер' and e[5] and under(probe, e[2], e[3], e[4]): ok.append(k)
    return land, ok


def trapped(binp, path, tmp):
    """заперт ли Гомер в конце повтора (как foot_trapped исследователя): 8 сторон × (бег 1.5 с | бег с двойным прыжком) —
    ни разу не ушёл на 1.5 м по плоскости. None — повтор кончился не пешком"""
    txt = Path(path).read_text().rstrip('\n'); end = None; moved = 0
    rows, _ = trace(binp, path)
    if not rows or rows[-1][1] != 'Гомер': return None
    end = rows[-1]
    for k in range(8):
        a = k * math.pi / 4; sx, sy = math.sin(a), math.cos(a)
        for j, ex in enumerate((f'90 2000 {sx:.3f} {sy:.3f}\n',
                                f'5 2000 {sx:.3f} {sy:.3f}\n1 6000 {sx:.3f} {sy:.3f}\n15 2000 {sx:.3f} {sy:.3f}\n1 6000 {sx:.3f} {sy:.3f}\n68 2000 {sx:.3f} {sy:.3f}\n')):
            q = tmp / f'{Path(path).stem}_t{k}{j}.in'; q.write_text(txt + '\n' + ex)
            r2, _ = trace(binp, q)
            if r2 and math.hypot(r2[-1][2] - end[2], r2[-1][4] - end[4]) > 1.5: moved += 1
    return moved == 0


def main():
    green, red, probe = map(Path, sys.argv[1:4])   # argv[4] — красная HOMER_VOID_SQUEEZE_OLD (раздел F10-8)
    reps = sorted(REG.glob('vf_*.in'))
    if len(reps) < 5: print(f'нет повторов: {len(reps)} < 5'); return 1
    tmp = ROOT / 'build/tmp/void_floor'; tmp.mkdir(parents=True, exist_ok=True)
    vars_ = []
    for p in reps:
        for j, (rot, k, fr) in enumerate([(10, 1, 0), (-10, 1, 0), (20, 1, 0), (-20, 1, 0), (0, .7, 0), (0, 1, 1)]):
            q = tmp / f'{p.stem}_v{j}.in'; q.write_text(variant(p, rot, k, fr)); vars_.append(q)
    death = REG / 'g4_001_ev_fall_328_-176_L0_-.in'
    jobs = [('green', green, p) for p in reps + vars_ + [death]] + [('red', red, p) for p in reps + vars_]
    with ThreadPoolExecutor(os.cpu_count() or 4) as ex: res = list(ex.map(lambda j: (j[0], j[2], judge(trace(j[1], j[2])[0])), jobs))
    R = {}
    for kind, p, r in res: R.setdefault(kind, {})[p.name] = r
    bad = [(k, n) for k in R for n, r in R[k].items() if r is None]
    if bad: print('нет трассы:', bad[:3]); return 1
    ok = True
    with ThreadPoolExecutor(os.cpu_count() or 4) as ex: esc = dict(zip([p.name for p in reps], ex.map(lambda p: escape(green, probe, p, tmp), reps)))
    for p in reps:
        n = p.name; g, r = R['green'][n], R['red'][n]
        fl, ways = esc[n]
        line = (f"{n[:44]:44s} старый: {'ПРОВАЛ' if r['fell'] else 'нет'} ({r['ymin']:.0f} м) · новый: {'ПРОВАЛ' if g['fell'] else 'нет'} "
                f"({g['ymin']:.1f} м) · пол над пустотой с кадра {fl if fl is not None else '—'}, уходит на опору: {len(ways)}/8")
        if g['fell'] or not r['fell'] or fl is None or not ways: ok = False; line += '  <-- FAIL'
        print(line)
    vn = [q.name for q in vars_]
    gv = sum(R['green'][n]['fell'] for n in vn); rv = sum(R['red'][n]['fell'] for n in vn)
    print(f'соседние варианты (±10°, ±20°, ×0.7, бег↔шаг): {len(vn)} шт.; провалов: старый код {rv}, новый {gv}')
    if gv or not rv: ok = False; print('  <-- FAIL')
    drops = sum(R['green'][n]['drops'] for n in [p.name for p in reps] + vn)
    print(f'законные падения ≥ 2 м с посадкой в новом коде: {drops}')
    if not drops: ok = False; print('  <-- FAIL')
    t = R['green'][death.name]['tele']
    print(f'прыжок с моста l1r7 в канал: зона DEATH возвращает Гомера — {"да" if t else "НЕТ"}')
    if not t: ok = False; print('  <-- FAIL')
    # L1 F10-8 (ящик b188): стена выдавливала за край без дна, край возвращал — заперт (правило «стена главнее края», за HOMER_VOID_SQUEEZE_OLD)
    traps = sorted(REG.glob('vt_*.in')); red_sq = Path(sys.argv[4]) if len(sys.argv) > 4 else None
    if not traps or red_sq is None: print('нет повторов vt_*.in или красной сборки HOMER_VOID_SQUEEZE_OLD'); return 1
    tv = []
    for p in traps:
        for j, (rot, k, fr) in enumerate([(10, 1, 0), (-10, 1, 0), (20, 1, 0), (-20, 1, 0), (0, .7, 0), (0, 1, 1)]):
            q = tmp / f'{p.stem}_v{j}.in'; q.write_text(variant(p, rot, k, fr)); tv.append(q)
    jobs = [('green', green, p) for p in traps + tv] + [('red', red_sq, p) for p in traps + tv]
    with ThreadPoolExecutor(os.cpu_count() or 4) as ex: tr = list(ex.map(lambda j: (j[0], j[2].name, trapped(j[1], j[2], tmp)), jobs))
    T = {}
    for kind, n, r in tr: T.setdefault(kind, {})[n] = r
    for p in traps:
        g, r = T['green'][p.name], T['red'][p.name]
        line = f"{p.name[:44]:44s} старый: {'ЗАПЕРТ' if r else 'не заперт'} · новый: {'ЗАПЕРТ' if g else 'не заперт'}"
        if g or not r: ok = False; line += '  <-- FAIL'
        print(line)
    gt = sum(bool(T['green'][q.name]) for q in tv); rt = sum(bool(T['red'][q.name]) for q in tv)
    print(f'соседние варианты F10-8: {len(tv)} шт.; заперт: старый код {rt}, новый {gt}')
    if gt: ok = False; print('  <-- FAIL')
    print('PASS' if ok else 'FAIL'); return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
