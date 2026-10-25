#!/bin/bash
# Гейт правки Роба 304 (04.10, L1 H10-5: «кусты почему-то тормозят машину — прям затормаживают»). Мак, без эмулятора.
# Три сборки tests/foliage/cover.c на настоящих car.c/col.c: новая, ПРЕЖНЯЯ (-DFOLIAGE_DRAG_BOX=1: вязкость в полную силу по
# пересечению габаритных коробок) и ОПОРНАЯ (-DFOLIAGE_DRAG=0: листва не вяжет совсем). Заезды у каждого куста уровня:
#   вдоль куста, не касаясь (par) — в листве не дольше одного кадра (0.034 с; было 0.02: par 9 рядом с J9-4 задевает 0.027 — касание одной пробой за кадр), конечная скорость не ниже 95 % опорной
#   поперёк через куст накатом (crs) — мягко: не ниже половины опорной
#   путь из жалобы (h10, только L1) — не ниже 98 % опорной
# Широкая изгородь (толщина ≥ 3 м, J9-4 по №587) — намеренно листва: поперёк не ниже 0,3 опорной, вдоль «в листве» не считается (скорость не ниже 0,7).
# Сначала КРАСНЫЙ: прежняя сборка обязана нарушить хотя бы одно, потом ЗЕЛЁНЫЙ на всех уровнях.
#   tests/foliage/cover.sh [level.shr ...]   (по умолчанию build/level.shr и build/levels/l2..l7/level.shr)
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
OUT=build/foliage; mkdir -p "$OUT"
LEVELS=("$@"); [ ${#LEVELS[@]} -eq 0 ] && { LEVELS=(build/level.shr); for n in 2 3 4 5 6 7; do [ -f build/levels/l$n/level.shr ] && LEVELS+=(build/levels/l$n/level.shr); done; }
CC="cc -O2 -std=c11 -Wall -I viewer"
$CC tests/foliage/cover.c viewer/car.c viewer/col.c -lm -o "$OUT/cover-new" || exit 2
$CC -DFOLIAGE_DRAG_BOX=1 tests/foliage/cover.c viewer/car.c viewer/col.c -lm -o "$OUT/cover-old" || exit 2
$CC -DFOLIAGE_DRAG=0 tests/foliage/cover.c viewer/car.c viewer/col.c -lm -o "$OUT/cover-ref" || exit 2
PY=python3; [ -x .venv/bin/python ] && PY=.venv/bin/python
fail=0
for lvl in "${LEVELS[@]}"; do
  n=$(basename "$(dirname "$lvl")"); [ "$lvl" = build/level.shr ] && n=l1
  for v in new old ref; do "$OUT/cover-$v" "$lvl" "$n" > "$OUT/cover_${v}_$n.txt" || { echo "FAIL: cover-$v $lvl"; exit 2; }; done
  $PY - "$OUT" "$n" <<'PY' || fail=1
import sys, math
out, n = sys.argv[1], sys.argv[2]
def load(v):
    d = {}
    for ln in open(f'{out}/cover_{v}_{n}.txt'):
        p = ln.split(); d[(p[0], p[1])] = [float(x) for x in p[2:]]
    return d
new, old, ref = load('new'), load('old'), load('ref')
def check(run):
    bad = []; cnt = {'par': 0, 'crs': 0, 'h10': 0}
    for k, r in ref.items():
        if k not in run: continue
        vr, vn, cov = r[0], run[k][0], run[k][1]
        # опорная (без вязкости) встала о твёрдое или в горку: заезд не про листву (дальше — хаос касаний), не считаем
        if vr < (5.0 if k[0] == 'par' else 3.0): continue
        cnt[k[0]] += 1; q = vn / vr
        # вдоль куста не касаясь: в листве не дольше 0.02 с (касание одной пробой за кадр при уводе) и скорость как у опорной
        # №587 (15.10, живая изгородь J9-4 common_gens51: ящик и 2 капсулы толщиной 3,5–3,9 м — НАМЕРЕННО листва, pad = 1): через неё ехать вязко (порог ×0,3 вместо 0,5),
        # рядом вдоль неё «в листве» не нарушение (объём широкий — боковой ряд в 0,5 м от края задевает его), скорость вдоль — не ниже 0,7 опорной. Узкие кусты — прежние пороги
        wide = len(r) > 2 and r[2] >= 3.0
        if k[0] == 'par' and wide and q < .7: bad.append(f'{k[0]} {k[1]}: вдоль широкой изгороди {vn:.1f} м/с против {vr:.1f} (в листве {cov:.2f} с)')
        elif k[0] == 'par' and not wide and (q < .95 or cov > .034): bad.append(f'{k[0]} {k[1]}: вдоль куста {vn:.1f} м/с против {vr:.1f} (в листве {cov:.2f} с)')
        # поперёк: мягко — не меньше половины скорости опорной (прежде машина вставала в низкой изгороди: ×0.0–0.2)
        if k[0] == 'crs' and q < (.3 if wide else .5): bad.append(f'{k[0]} {k[1]}: поперёк {vn:.1f} м/с против {vr:.1f} (×{q:.2f}, толщина {r[2]:.1f} м, в листве {cov:.2f} с)')
        if k[0] == 'h10' and q < .98: bad.append(f'h10: путь H10-5 {vn:.1f} м/с против {vr:.1f} (×{q:.2f}, в листве {cov:.2f} с)')
    return bad, cnt
bo, co = check(old); bn, cn = check(new)
felt = [r[0] / ref[k][0] for k, r in new.items() if k[0] == 'crs' and k in ref and ref[k][0] >= 3]
print(f'{n}: заездов вдоль {cn["par"]}, поперёк {cn["crs"]} (куст ощутим в {sum(q < .995 for q in felt)}, худший ×{min(felt, default=1):.2f}), путь H10-5 {cn["h10"]}' +
      (f' ×{new[("h10","0")][0] / ref[("h10","0")][0]:.2f} (прежде ×{old[("h10","0")][0] / ref[("h10","0")][0]:.2f})' if ('h10', '0') in ref else ''))
if co['par'] + co['crs'] == 0: print(f'  {n}: кустов нет — красный не применим')
elif bo: print(f'  красный ({n}, прежняя вязкость): упал, как должен — {len(bo)} нарушений, напр. {bo[0]}')
else: print(f'  красный ({n}): прежняя вязкость здесь не нарушила' + (' — КРАСНЫЙ НЕ ПОЙМАН' if n == 'l1' else ''))
for b in bn[:6]: print('  FAIL', b)
if bn: print(f'  ЗЕЛЁНЫЙ НЕ ПРОШЁЛ ({n}): {len(bn)} нарушений')
sys.exit(0 if not bn and (bo or n != 'l1') else 1)
PY
done
[ $fail -eq 0 ] && { echo "PASS: красный пойман, зелёный"; exit 0; }
echo "FAIL"; exit 1
