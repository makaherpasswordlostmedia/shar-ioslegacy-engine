#!/usr/bin/env python3
"""Проверка прогона tests/aicar/racepos.sh (правка Роба 326, правило Роба «кто ближе к точке — тот и первый»): место игрока в
гонке S-M-R-T (m1) против расстояний по прямой до финиша m1_AI_path4 (10,5; 623,8) — у игрока одна точка гонки, у Скиннера
счёт точек игрока 0 до конца его пути.
Источники в smoke.txt: RACEPOS (строка в кадр смены места: pos, px pz, dp, у соперника x z rk d a), MCAR skinn_v (раз в секунду,
pos=P/1), SHOT (где игрок), SCENE (фазы: start, hook, side, chase, cut, back).
Зелёный:
  * каждая смена места (RACEPOS) — у равного расстояния: |dp − d| ≤ 1,5 м, или первая строка после переноса (SCENE), или соперник
    доехал (rk);
  * снимки (SHOT игрока + ближайшая следующая MCAR Скиннера в фазах, где игрок стоит): при разнице расстояний больше 2 м место
    на экране совпадает с тем, кто ближе (в chase игрок едет — допуск 12 м);
  * start: ≥ 2 снимков «2-й» (Скиннер ближе к школе); в hook или side есть смена места рядом (|dp − d| ≤ 1,5 м);
  * cut: после переноса к школе «1-й», back: после переноса к старту «2-й».
   racepos_check.py smoke.txt"""
import math, re, sys

FIN = (10.5, 623.8)
TOL_SW, TOL_SNAP, TOL_MOVE = 1.5, 2.0, 12.0


def d(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def kv(ln):
    return dict(x.split('=', 1) for x in ln.split()[1:] if '=' in x)


def main(path):
    phase, me, last_pos, after_scene = '-', None, None, False
    sw_ok, sw_bad, snaps, bad_snaps = [], [], [], []
    start2, cut1, back2, near_sw = 0, None, None, 0
    lines = open(path, errors='replace').read().splitlines()
    for ln in lines:
        if ln.startswith('SCENE '):
            phase = ln.split()[1]; after_scene = True; me = None
            continue
        m = re.match(r'SHOT \S+ [-\d.]+ pos ([-\d.]+) [-\d.]+ ([-\d.]+)', ln) or re.match(r'WP \d+ t=\S+ v=\S+ at ([-\d.]+) [-\d.]+ ([-\d.]+)', ln)
        if m:
            me = (float(m.group(1)), float(m.group(2)))
            continue
        if ln.startswith('RACEPOS '):
            f = kv(ln); pos = int(f['pos'].split('/')[0])
            # первая строка соперника: " skinn_v x=… z=… rk=… d=… a=…" — поля после имени
            rm = re.search(r' skinn_v x=([-\d.]+) z=([-\d.]+) rk=(\d+) d=([-\d.]+) a=(-?\d)', ln)
            if pos <= 0 or not rm:
                after_scene = False; last_pos = pos; continue
            dp, dr, rk = float(f['dp']), float(rm.group(4)), int(rm.group(3))
            gap = dp - dr
            rec = (phase, f['t'], pos, dp, dr, rk)
            if last_pos and last_pos > 0 and pos != last_pos:
                if abs(gap) <= TOL_SW:
                    sw_ok.append(rec)
                    if phase in ('hook', 'side'):
                        near_sw += 1
                elif after_scene or rk >= 1:
                    sw_ok.append(rec + ('перенос/финиш',))
                else:
                    sw_bad.append(rec)
            last_pos = pos; after_scene = False
            continue
        if ln.startswith('MCAR ') and 'name=skinn_v' in ln and me:
            f = kv(ln); pos = int(f['pos'].split('/')[0])
            if pos <= 0:
                continue
            S = (float(f['x']), float(f['z'])); dp, ds = d(me, FIN), d(S, FIN)
            tol = TOL_MOVE if phase == 'chase' else TOL_SNAP
            want = 1 if dp < ds - tol else 2 if dp > ds + tol else 0
            snaps.append((phase, f['t'], me, S, dp, ds, pos, want))
            if want and pos != want:
                bad_snaps.append(snaps[-1])
            if phase == 'start' and want == 2 and pos == 2:
                start2 += 1
            if phase == 'cut' and cut1 is None:
                cut1 = pos
            if phase == 'back' and back2 is None:
                back2 = pos
            me = None   # снимок использован: следующая MCAR — с новым SHOT
    print(f"{'фаза':6s} {'t':>6s}  {'игрок':>12s} {'Скиннер':>12s}  {'до шк.игр':>9s} {'до шк.Ск':>8s}  экран  нужно")
    for ph, t, me_, s, dp, ds, pos, want in snaps:
        print(f"{ph:6s} {t:>6s}  ({me_[0]:5.0f},{me_[1]:4.0f}) ({s[0]:5.0f},{s[1]:4.0f})  {dp:9.0f} {ds:8.0f}  {pos:^5d}  {want or '~'}")
    print('смены места (RACEPOS):')
    for r in sw_ok + sw_bad:
        print(f"  {r[0]:6s} t={r[1]:>7s} -> {r[2]}  игроку {r[3]:.1f} м, Скиннеру {r[4]:.1f} м (разница {r[3] - r[4]:+.1f})"
              f"{'  ' + r[6] if len(r) > 6 else ''}{'  НЕ У РАВЕНСТВА' if r in sw_bad else ''}")
    fail = []
    if sw_bad:
        fail.append(f"смена места не у равного расстояния: {len(sw_bad)} (первая t={sw_bad[0][1]} фаза {sw_bad[0][0]}, разница {sw_bad[0][3] - sw_bad[0][4]:+.1f} м)")
    if bad_snaps:
        b = bad_snaps[0]
        fail.append(f"место на экране против расстояний: {len(bad_snaps)} снимков, первый t={b[1]} фаза {b[0]}: игроку {b[4]:.0f} м, Скиннеру {b[5]:.0f} м, на экране {b[6]}")
    if start2 < 2:
        fail.append(f"старт: Скиннер ближе к школе, на экране 2-й — {start2} снимков (нужно ≥ 2)")
    if near_sw < 1:
        fail.append("hook/side: ни одной смены места рядом со Скиннером (|разница| ≤ 1,5 м)")
    if cut1 != 1:
        fail.append(f"срезка к школе: на экране {cut1} (нужно 1)")
    if back2 != 2:
        fail.append(f"назад к старту: на экране {back2} (нужно 2)")
    for s in fail:
        print('  FAIL:', s)
    print('RESULT', 'FAIL' if fail else 'PASS', f"(смен у равенства {len(sw_ok)}, не у равенства {len(sw_bad)}, рядом {near_sw}, "
          f"снимков {len(snaps)}, противоречий {len(bad_snaps)})")
    return 1 if fail else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
