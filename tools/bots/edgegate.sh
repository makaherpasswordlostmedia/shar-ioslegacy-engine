#!/bin/bash
# Гейт «край над зоной DEATH» (EDGE_DEATH_OLD, car.c): (1) глухие ямы ночи 11.10 на L3 и L6 открыты (trapcheck: было >=3 курсов без выхода, стало 0);
# (2) ни одно из 70 мест разбора (по 10 на уровень) не стало хуже; (3) обычная езда: отпечаток движения 90 миссий ночи с правилом и без него одинаков,
# кроме миссий, где правило сработало (их список печатается). DATA — пакет уровней, RUN — папка миссий ночи, POINTS — папка с trap_L<N>.txt
cd "$(dirname "$0")/../.." || exit 2
D=${DATA:-../shar-psp-night-w/build}; R=${RUN:-$D/night-final/2026-10-11/missions}; P=${POINTS:-/tmp/npt}
BINS="trapcheck mcrprof" bash tools/bots/build.sh >/dev/null || exit 2
BINS=trapcheck SUF=_old OUT_DIR=/tmp/edgegate_bp bash tools/bots/build.sh -DEDGE_DEATH_OLD=1 >/dev/null || exit 2
python3 - "$D" "$R" "$P" <<'PY'
import subprocess, os, re, glob, sys
D, R, P = sys.argv[1:4]; ok = True
def files(L):
    return [f'{D}/levels/l{L}/level.shr', f'{D}/levels/l{L}/player.shr', f'{D}/levels/l{L}/level0{L}.msn'] if L > 1 else [f'{D}/level.shr', f'{D}/homer.shr', f'{D}/level01.msn']
def tc(binary, L):
    pts = f'{P}/trap_L{L}.txt'
    if not os.path.exists(pts): return {}
    o = subprocess.run([binary, *files(L)[:2], pts], capture_output=True, text=True, env=dict(os.environ, BW_LEVEL=str(L))).stdout
    return {l.split('\t')[2]: int(l.split('\t')[3]) for l in o.splitlines() if l.startswith('P\t')}
worse = fixed = 0; pits = []
for L in range(1, 8):
    old, new = tc('/tmp/edgegate_bp/trapcheck_old', L), tc('build/bots/trapcheck', L)
    for k in old:
        if k in new:
            if new[k] > old[k]: worse += 1; print(f'ХУЖЕ L{L} {k}: {old[k]} -> {new[k]}'); ok = False
            if old[k] >= 3 and new[k] == 0: fixed += 1; pits.append((L, k, old[k]))
print(f'(1,2) мест, где было >=3 курсов без выхода и стало 0: {fixed}; стало хуже: {worse}'); [print('   открыта: L%d %s было %d из 16' % p) for p in pits]
if fixed < 6: print('ЯМЫ НЕ ОТКРЫТЫ'); ok = False
diff = []; edgeN = 0; tot = 0
for L in range(1, 8):
    for d in sorted(glob.glob(f'{R}/L{L}_m*_s1')):
        mi = int(re.search(r'_m(\d+)_', d).group(1)); inp = f'{d}/m{mi}.in'
        if not os.path.exists(inp): continue
        res = []
        for old in (0, 1):
            env = dict(os.environ, BW_LEVEL=str(L), MCRPROF_FP='1'); 
            if old: env['MCRPROF_EDGE_OLD'] = '1'
            o = subprocess.run(['build/bots/mcrprof', *files(L), inp, str(mi), '1'], capture_output=True, text=True, env=env).stdout
            m = re.search(r'движения (\w+).*край принят из-за DEATH (\d+)', o); res.append((m.group(1), int(m.group(2))) if m else None)
        tot += 1
        if res[0] and res[1] and res[0][0] != res[1][0]: diff.append((L, mi, res[0][1]))
        if res[0]: edgeN += res[0][1]
print(f'(3) миссий {tot}: отпечаток движения с правилом и без одинаков в {tot - len(diff)}; различается в {len(diff)}: ' + ', '.join(f'L{a} m{b} (срабатываний {c})' for a, b, c in diff))
bad = [x for x in diff if x[2] == 0]
if bad: print('ЛОЖНОЕ РАЗЛИЧИЕ без срабатывания правила:', bad); ok = False
print('ГЕЙТ edgegate:', 'PASS' if ok else 'FAIL'); sys.exit(0 if ok else 1)
PY
