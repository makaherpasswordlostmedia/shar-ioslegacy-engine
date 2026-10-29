#!/usr/bin/env python3
"""Правка Роба 349 (05.10, голосом): «Сектор L1 K2-8 — там, где горящие покрышки за забором — вся зона недопустима; в оригинале,
если туда попадаешь, всё темнеет и переносит». Гейт без эмулятора: данные диска + мир ботов (game_headless — тот же код машины,
Гомера, коллизии и viewer/game.c gameDeath, что EBOOT). Показ (затемнение) — в эмуляторе: tests/death/emu_check.py.

[диск] Локатор DEATH (Event 4) R6D01 (art/l1r6.p3d) — ДВА объёма TriggerVolume: ящик x 284…312 и ящик x 262…287 (z −543…−488,
наклонены по склону ямы) — весь двор покрышек за забором; точка возврата (285,4; 5,3; −551,4), LocatorMatrix — единичная.
До правки экспорт брал только первый объём: двор у K2-8 (x 262…284) был проезжим тупиком.
[PS2] 05.10, pcsx2-twins без окна и звука (agent349/ps2: s1 — машина в обоих ящиках, с трамплина, сверху; s2 — Z6D1; s4 — Гомер
пешком): в любом объёме — мир стоит, экран гаснет 0,92 с, перенос в точку локатора (машина курсом локатора: R6D01 2,672 → 0,000,
Z6D1 0,852 → 0,785), чёрный 0,26 с, картинка сразу.

Проверки:
  D1 данные: tools/jumps_export.deaths(1, every=True) — у R6D01 два объёма, точки двора K2-8 внутри; every=False (как до правки) —
     точки ящика 1 вне зоны (красный данных)
  D2 все уровни: точки возврата не внутри ни одного объёма (иначе перенос в зону — двойное срабатывание)
  D3 курс возврата из LocatorMatrix: R6D01 π, Z6D1 π − π/4, R3D11 0
  D4 build/level.shr несёт новый блок JMP1 (зон DEATH столько же, сколько объёмов в данных уровня 1)
  B1–B4 мир ботов (BIN): машина в ящике 1 / ящике 0, въезд через трамплин с газом, Гомер пешком — перенос к точке R6D01, машина
     дальше едет по −z (курс π); с BW_DEATH_OLD=1 (как до правки) ящик 1 и Гомер в нём НЕ переносятся, у ящика 0 курс прежний
  B5 повторы tests/bots/regress/*.in: новое против BW_DEATH_OLD=1 — переносы различаются только там, где игрок в новом объёме
     (нигде больше поведение не изменилось)
  B6 (правка 368) яма трамплина jumpzone1 L3/L6: упала — R5D03 один раз (курс локатора, без повтора); дно ямы — R5D03#1
  python3 tests/death/check.py BIN [LEVEL]    BIN — game_headless (tools/bots/build.sh), LEVEL — build/level.shr -> PASS / FAIL"""
import math, os, re, struct, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools')); sys.path.insert(0, str(ROOT / 'tools/missions'))
import jumps_export as J   # noqa: E402

RET = (285.43, -551.42)
YARD = [(266.0, 6.5, -515.0), (274.0, 8.7, -515.0), (265.0, 7.0, -530.0), (300.0, 7.7, -515.0), (305.0, 4.7, -500.0)]   # двор (x, y, z движка)
BOX1 = YARD[:3]   # только во втором объёме (x < 284)
TR = re.compile(r'кадр (\d+) (\S+) (\S+) (\S+) (\S+) на земле')
bad = []


def need(c, msg):
    print(('ok   ' if c else 'FAIL ') + msg)
    if not c: bad.append(msg)


def inside(d, p, grow=0.0):
    q = [p[i] - d['c'][i] for i in range(3)]
    if not d['shape']: return sum(v * v for v in q) <= (d['h'][0] + grow) ** 2
    return all(abs(sum(q[i] * d['axes'][k][i] for i in range(3))) <= d['h'][k] + grow for k in range(3))


def data_checks(level_path):
    new, old = J.deaths(1, every=True), J.deaths(1)
    r6 = [d for d in new if d['name'] == 'R6D01']
    need(len(r6) == 2, f'D1 R6D01: объёмов {len(r6)} (диск: 2)')
    need(all(any(inside(d, p, .5) for d in r6) for p in YARD), 'D1 точки двора покрышек (K2-8 … K2-9) внутри зоны R6D01')
    need(not any(inside(d, p, .5) for d in old for p in BOX1), 'D1 красный данных: первым объёмом (как до правки) ящик 1 (K2-8) вне зоны')
    tot = []
    for lv in range(1, 8):
        D = J.deaths(lv, every=True); tot.append(f'L{lv} {len({d["name"] for d in D})}/{len(D)}')
        clash = sorted({(d['name'], e['name']) for d in D for e in D for dy in (0, .5, 1, 1.5)
                        if inside(e, (d['apex'][0], d['apex'][1] + dy, d['apex'][2]), .5)})
        need(not clash, f'D2 L{lv}: точки возврата вне всех объёмов ({clash[:4]})')
    print('     локаторов/объёмов DEATH: ' + ', '.join(tot))
    h = {d['name']: d['ret_h'] for d in new}
    need(abs(J.death_heading((1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1)) - math.pi) < 1e-6 or
         abs(abs(J.death_heading((1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1))) - math.pi) < 1e-6, 'D3 единичная матрица -> курс π')
    need(abs(abs(h['R6D01']) - math.pi) < 1e-3, f'D3 R6D01 курс возврата {h["R6D01"]:.4f} (π)')
    need(abs(h['Z6D1'] - (math.pi - math.pi / 4)) < 2e-3, f'D3 Z6D1 курс возврата {h["Z6D1"]:.4f} (π − π/4; [PS2] курс оригинала 0,785)')
    need(abs(h['R3D11']) < 1e-3, f'D3 R3D11 курс возврата {h["R3D11"]:.4f} (0)')
    b = Path(level_path).read_bytes(); col = struct.unpack_from('<5I', b, 76)[4]
    flags = struct.unpack_from('<8I', b, col + 16)[7]; j = col + flags
    nd = struct.unpack_from('<7I', b, j + 4)[5] if flags and b[j:j + 4] == b'JMP1' else -1
    need(nd == len(new), f'D4 {Path(level_path).name}: зон DEATH в JMP1 {nd} (данные: {len(new)}; старый блок — {len(old)}: пересобрать уровень)')


def run(binp, level, start, frames, env=None):
    with tempfile.NamedTemporaryFile('w', suffix='.in', delete=False) as f:
        f.write('# правка 349\n' + ''.join(f'{n} {b:x} {ax} {ay}\n' for n, b, ax, ay in frames)); inp = f.name
    e = dict(os.environ, GH_TRACE='1', **(env or {}))
    hom = Path(level).parent / 'homer.shr'
    if not hom.exists(): hom = ROOT / 'build/homer.shr'   # уровни 2–7 (build/levels/lN/) — Гомер общий
    r = subprocess.run([binp, str(level), str(hom), '--input', inp, '--start', *map(str, start)],
                       capture_output=True, text=True, env=e, timeout=300)
    os.unlink(inp)
    return [(int(m[1]), m[2] == 'Гомер', float(m[3]), float(m[4]), float(m[5])) for m in map(TR.match, r.stderr.splitlines()) if m]


def jumps(rows, d=15.0, start=None):
    """переносы (> d м за кадр); start — точка старта (перенос на самом первом шаге: игрок поставлен прямо в зону)"""
    R = ([(-1, False, float(start[0]), float(start[1]), float(start[2]))] if start else []) + rows
    return [(R[i][0], R[i]) for i in range(1, len(R)) if math.hypot(R[i][2] - R[i - 1][2], R[i][4] - R[i - 1][4]) > d]


GAS, TRI = 0x200, 0x1000


def world_checks(binp, level):
    old = {'BW_DEATH_OLD': '1'}
    cases = [('B1 машина в ящике 1 (K2-8)', (274, 9, -515, 1.5708), [(30, 0, 0, 0), (40, GAS, 0, 0)], True, False),
             ('B2 машина в ящике 0', (298, 8.5, -515, 1.5708), [(30, 0, 0, 0), (40, GAS, 0, 0)], True, True)]
    for name, st, fr, want_new, want_old in cases:
        for tag, env in (('новое', None), ('BW_DEATH_OLD=1', old)):
            rows = run(binp, level, st, fr, env); J1 = jumps(rows, start=(st[0], st[1], st[2]))
            first = J1[0][1] if J1 else None
            at_ret = first is not None and math.hypot(first[2] - RET[0], first[4] - RET[1]) < 3.0
            after = [r for r in rows if first and r[0] > first[0] + 30]
            dx, dz = (after[-1][2] - after[0][2], after[-1][4] - after[0][4]) if len(after) > 5 else (0, 0)
            if tag == 'новое':
                need(at_ret and len(J1) == 1, f'{name}: перенос к точке R6D01 один раз ({len(J1)}; кадр {first[0] if first else "-"})')
                need(dz < -1.0 and abs(dx) < abs(dz) * .3, f'{name}: после переноса газ ведёт по −z — курс локатора π (dx {dx:.1f}, dz {dz:.1f})')
            elif not want_old:
                need(not J1, f'{name} [{tag}]: прежнее — переноса нет (красный пойман: {len(J1)})')
            else:
                need(at_ret and dx > 1.0 and abs(dz) < dx * .3, f'{name} [{tag}]: прежнее — перенос, курс прежний (+x: dx {dx:.1f}, dz {dz:.1f})')
    # B3 трамплин jumpzone9 у K2-8: с газом через забор во двор
    rn = run(binp, level, (236, 7, -508.5, 1.5708), [(60, 0, 0, 0), (300, GAS, 0, 0)]); jn = jumps(rn)
    ro = run(binp, level, (236, 7, -508.5, 1.5708), [(60, 0, 0, 0), (300, GAS, 0, 0)], old); jo = jumps(ro)
    fn = jn[0][0] if jn else None; fo = jo[0][0] if jo else None
    pre = next((r for r in rn if fn and r[0] == fn - 1), None)
    need(fn is not None and math.hypot(jn[0][1][2] - RET[0], jn[0][1][4] - RET[1]) < 3.0,
         f'B3 въезд с трамплина: перенос к точке R6D01 (кадр {fn}, перед ним x {pre[2] if pre else "-":.1f}; прежнее — кадр {fo})')
    # B4 Гомер пешком: машина у забора, △ — выйти, стик вперёд с бегом и прыжками (через забор во двор)
    walk = [(30, 0, 0, 0), (2, TRI, 0, 0), (90, 0, 0, 0)] + [(20, 0x2000, -1, 0), (2, 0x6000, -1, 0)] * 14   # стик влево = +x (камера за машиной, курс +x), ○ бег, ✕ прыжок
    for tag, env in (('новое', None), ('BW_DEATH_OLD=1', old)):
        rows = run(binp, level, (252, 7, -522, 1.5708), walk, env)
        foot = [r for r in rows if r[1]]; J1 = jumps(foot, 10.0)
        mx = max((r[2] for r in foot), default=0.0)
        inyard = any(r[2] > 262.5 and -543 < r[4] < -488 for r in foot)
        if tag == 'новое':
            need(bool(J1) and math.hypot(J1[0][1][2] - RET[0], J1[0][1][4] - RET[1]) < 3.0,
                 f'B4 Гомер пешком во двор: перенос к точке R6D01 (переносов {len(J1)}, кадр {J1[0][0] if J1 else "-"}, дальше всего x {mx:.1f})')
        else:
            need(not J1 and inyard, f'B4 Гомер [{tag}]: прежнее — во дворе и без переноса (красный пойман: переносов {len(J1)}, во дворе {inyard})')
    # B5 повторы ботов: новое против прежнего — разница только из-за новых объёмов
    reg = sorted((ROOT / 'tests/bots/regress').glob('*.in')); diff, same = [], 0
    allv = J.deaths(1, every=True)
    for p in reg:
        head = p.read_text().splitlines()[0]; m = re.search(r'--start (\S+) (\S+) (\S+) (\S+)', head)
        if not m: continue
        fr = []
        for ln in p.read_text().splitlines()[1:]:
            if ln.startswith('#') or not ln.strip(): continue
            n, b, ax, ay = ln.split(); fr.append((int(n), int(b, 16), float(ax), float(ay)))
        a = run(binp, level, m.groups(), fr); b_ = run(binp, level, m.groups(), fr, old)
        if a == b_: same += 1; continue
        k = next((i for i in range(min(len(a), len(b_))) if a[i] != b_[i]), min(len(a), len(b_)))
        pa, pb = a[min(k, len(a) - 1)], b_[min(k, len(b_) - 1)]
        at = [d for d in allv if math.hypot(pa[2] - d['apex'][0], pa[4] - d['apex'][2]) < 2.0]   # новое в этом кадре — у точки возврата
        if at and math.hypot(pb[2] - pa[2], pb[4] - pa[4]) < 2.0 and not pb[1]:
            why = [f'тот же перенос {at[0]["name"]}, курс машины — курс локатора']   # и прежнее перенесло туда же: разница — курс
        else:
            why = [d['name'] + f'#{d["vol"]}' for d in allv if d['vol'] > 0 and inside(d, (pb[2], pb[3] + .5, pb[4]), .5)]   # прежнее в этом кадре — в новом объёме
        diff.append((p.name, pb, why))
    for nm, pt, why in diff: print(f'     повтор {nm}: расходится с кадра {pt[0]} у ({pt[2]:.1f}, {pt[3]:.1f}, {pt[4]:.1f}) — {why or "НЕ новый объём"}')
    need(all(w for _, _, w in diff), f'B5 повторы ботов ({len(reg)}): совпали {same}, разошлись {len(diff)} — только в новых объёмах DEATH')


def ramp_checks(binp):
    """B6 (правка 368, 05.10: «L6, прыгнул с трамплина — возвращает обратно на трамплин, как ресет»). Яма под трамплином jumpzone1
    (дорога x 107…130, разрыв z −245…−270) — настоящие зоны оригинала R5D02/R5D03 (первые объёмы, с правки 86): упала в яму —
    перенос к точке R5D03 (край по ту сторону, курс локатора π) ровно один раз; машина на дне ямы (y −80) — R5D03#1 (второй объём,
    правка 349) переносит. Красный (BW_DEATH_OLD=1, как до 349): дно ямы не переносит — машина остаётся внизу навсегда; въезд с юга
    в яму повторяется (курс прежний — снова в яму)"""
    old = {'BW_DEATH_OLD': '1'}
    for lv in (3, 6):
        level = ROOT / f'build/levels/l{lv}/level.shr'
        if not level.exists(): need(False, f'B6 L{lv}: нет {level}'); continue
        allv = J.deaths(lv, every=True)
        r5 = next(d for d in allv if d['name'] == 'R5D03')
        gap = (120.0, -5.3, -277.3, 0.0)   # с юга, курсом +z в разрыв jumpzone1 (без разгона — падает)
        a = jumps(run(binp, level, gap, [(10, 0, 0, 0), (420, GAS, 0, 0)]), 10.0, start=gap[:3])
        b = jumps(run(binp, level, gap, [(10, 0, 0, 0), (420, GAS, 0, 0)], old), 10.0, start=gap[:3])
        at5 = lambda t: all(math.hypot(r[2] - r5['apex'][0], r[4] - r5['apex'][2]) < 2 for _, r in t)
        need(len(a) == 1 and at5(a), f'B6 L{lv}: упала в яму jumpzone1 — перенос к R5D03 один раз (переносов {len(a)})')
        need(len(b) > 1 and at5(b), f'B6 L{lv} [BW_DEATH_OLD=1]: прежнее — перенос курсом в яму повторяется (красный пойман: {len(b)})')
        floor = (119.0, -78.0, -262.0, 0.0)   # дно ямы
        a = jumps(run(binp, level, floor, [(60, 0, 0, 0)]), 10.0, start=floor[:3])
        b = jumps(run(binp, level, floor, [(60, 0, 0, 0)], old), 10.0, start=floor[:3])
        need(len(a) == 1 and at5(a), f'B6 L{lv}: дно ямы (y −80) — перенос к R5D03 вторым объёмом ({len(a)})')
        need(not b, f'B6 L{lv} [BW_DEATH_OLD=1]: прежнее — дно ямы без переноса (красный пойман: {len(b)})')


def main():
    binp = sys.argv[1]; level = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / 'build/level.shr'
    data_checks(level); world_checks(binp, level); ramp_checks(binp)
    print('death gate: PASS' if not bad else f'death gate: FAIL ({len(bad)})')
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(main())
