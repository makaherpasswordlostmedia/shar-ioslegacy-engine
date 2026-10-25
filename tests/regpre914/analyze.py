#!/usr/bin/env python3
# Б TEST57: по smoke.txt прогона gen.py — на каждую сцену P<lv>_<i> число включений REGPRE и загрузок клеток (STREAMCOST loads) за окно замера (после строки HEAPLEFT want<99 до want=99)
# вывод: строка на сцену + итог; код 1, если где-то > MAXFLIP включений REGPRE или > MAXLD клеток за секунду окна
# с --gates gates.json: точка считается только если машина в окне стояла у ворот (BB-строка сцены в пределах 40 м от центра ворот), иначе «НЕ ТЕЛЕПОРТИРОВАЛО» — тоже красное
import re, sys, json, math
MAXFLIP = 2; MAXLD = 1.0; NEAR_M = 40.0
def run(path, gates=None):
    sc = None; win = None; res = {}; t0 = None; reg = 0; ld0 = None; ld = None; pos = {}
    for ln in open(path, encoding='utf-8', errors='replace'):
        m = re.match(r'SCENE (P\d+_\d+) ', ln)
        if m: sc = m[1]; continue
        m = re.match(r'BB\s+\d+ -\s+L\d \S+\s+(-?\d+)\s+-?\d+\s+(-?\d+)\s', ln)
        if m and sc: pos[sc] = (float(m[1]), float(m[2]))
        m = re.match(r'HEAPLEFT want=([\d.]+) got=([\d.]+) blocks=\d+ t=([\d.]+)', ln)
        if m and sc:
            if float(m[1]) < 90: win = sc; t0 = float(m[3]); reg = 0; ld0 = ld
            elif win:
                dt = float(m[3]) - t0; res[win] = (reg, (ld - ld0) / dt if ld0 is not None and dt > 0 else 0.0, float(m[2]), dt); win = None
            continue
        m = re.match(r'STREAMCOST .* loads=(\d+) .* t=([\d.]+)', ln)
        if m: ld = int(m[1])
        if ln.startswith('REGPRE ') and win: reg += 1
    if gates:
        for k in list(res):
            lv, i = map(int, k[1:].split('_')); g = next((x for x in gates if x['lv'] == lv and x['i'] == i), None)
            p = pos.get(k)
            if g and (not p or math.hypot(p[0] - g['c'][0], p[1] - g['c'][2]) > NEAR_M): res[k] = res[k][:3] + (-1.0,)
    return res
if __name__ == '__main__':
    bad = 0; tot = 0; a = sys.argv[1:]; gates = None
    if a and a[0] == '--gates': gates = json.load(open(a[1])); a = a[2:]
    for p in a:
        for k, (reg, lps, got, dt) in run(p, gates).items():
            tot += 1
            if dt < 0: bad += 1; print(f'{k} НЕ ТЕЛЕПОРТИРОВАЛО (машина не у ворот) КРАСНОЕ'); continue
            flag = reg > MAXFLIP or lps > MAXLD; bad += flag
            print(f'{k} REGPRE {reg} загрузок/с {lps:.1f} (свободно {got:.2f} МБ, окно {dt:.0f} с){" КРАСНОЕ" if flag else ""}')
    print(f'ИТОГ: точек {tot}, плохих {bad}'); sys.exit(1 if bad else 0)
