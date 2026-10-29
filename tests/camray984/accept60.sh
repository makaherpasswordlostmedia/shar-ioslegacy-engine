#!/bin/bash
# №984 «Небо»: камера — лучи ближней плоскости.   tests/camray984/accept60.sh      (последняя строка: PASS или FAIL)
#   QUICK=1 — без пересборки (viewer/build_cr_new, build_cr_red), RERUN=0 — без эмулятора (прогоны в build/c984/acc)
#   Приёмы (оба побитно тот же ответ): а) тела за шаром лучей (кузова, стейтпропы, люди) на лучи не ходят — CAM_RAYBOX_OLD=1 / flag camrayboxold 1;
#   б) камера стоит (глаз, взгляд, угол те же) и в шаре лучей нет тел — прошлый ответ csNearFree, не дольше 3 кадров подряд — CAM_NFSTILL_OLD=1 / flag camnfstillold 1.
#   Маршруты: tests/camray984/route_l3…l7.txt (автопилот flag drive 24 с, кадр в кадр flag camdet, строки CAMF/CAMSUB), «как было» — оба флага на той же сборке.
#   Зелёное: траектория глаза, взгляда и ближней плоскости (CAMF) та же в допуске 0,5 мм на всех пяти уровнях; цена камеры (CAMSUB) не больше --max от прежней; красное (обязано упасть): прежнее против прежнего (цена),
#   красная сборка (-DCS_NFSTILL_K=0.5f: повторный ответ испорчен) против прежнего (near в CAMF).
set -u
export PATH=$HOME/Downloads/shar-psp/build/xcshim/bin:$PATH
W=$(cd "$(dirname "$0")/../.." && pwd); cd "$W"; T=tests/camray984; A=${A:-$W/build/c984/acc}; mkdir -p "$A" build/c984; BAD=0; MAXC=${MAXC:-0.97}
ok() { echo "  [ok]  $1"; }; bad() { echo "  [BAD] $1"; BAD=$((BAD + 1)); }
[ "${QUICK:-0}" != 1 ] && { echo "== 1. сборки"; $T/mk.sh new "" > /dev/null; $T/mk.sh red "-DCS_NFSTILL_K=0.5f" > /dev/null; }
for v in new red; do [ -f viewer/build_cr_$v/EBOOT.PBP ] || bad "нет сборки $v"; done
if [ "${RERUN:-1}" != 0 ]; then echo "== 2. эмулятор: маршруты L3–L7 (по два)"; rm -f "$A/runall.done"; A=$A $T/runall.sh 3:new 3:old 4:new 4:old 5:new 5:old 6:new 6:old 7:new 7:old 4:red 5:red; fi
P=tests/camera/camperf.py; S() { echo "$A/out_r$1_$2/smoke.txt"; }
echo "== 3. траектория камеры (CAMF): новое против прежнего"
for L in 3 4 5 6 7; do python3 $P equal "$(S $L old)" "$(S $L new)" --tol 0.0005 | tail -1; python3 $P equal "$(S $L old)" "$(S $L new)" --tol 0.0005 > /dev/null && ok "L$L траектория та же" || bad "L$L траектория разошлась"; done
echo "== 4. цена камеры (CAMSUB)"
for L in 3 4 5 6 7; do python3 $P cost "$(S $L old)" "$(S $L new)" --max $MAXC | tail -1; python3 $P cost "$(S $L old)" "$(S $L new)" --max $MAXC > /dev/null && ok "L$L цена ≤ $MAXC от прежней" || bad "L$L цена не снижена до $MAXC"; done
echo "== 5. красные"
python3 $P cost "$(S 5 old)" "$(S 5 old)" --max $MAXC > /dev/null && bad "красный: прежнее против прежнего прошло по цене" || ok "красный: прежнее против прежнего (цена) упало, как должно"
r=0; for L in 4 5; do python3 $P equal "$(S $L old)" "$(S $L red)" --tol 0.0005 > /dev/null || r=1; done; [ $r = 1 ] && ok "красный: красная сборка (испорченный повторный ответ) даёт другую ближнюю плоскость" || bad "красная сборка не отличилась от прежнего"
[ $BAD = 0 ] && echo PASS || echo FAIL
