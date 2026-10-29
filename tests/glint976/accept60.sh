#!/bin/bash
# №976 «Небо»: точка цели — кольцо на полу и звёзды столба.   tests/glint976/accept60.sh      (последняя строка: PASS или FAIL)
#   QUICK=1 — без пересборки (EBOOT в viewer/build_g_*), RERUN=0 — без эмулятора (снимки в build/g970/acc976). Сборки и сценарий sphere.txt общие с №970 (tests/glint970).
#   Кружок: уже векторный (lightsprite.h vecGlowHook, пятно carsphere_shadow); граненость: 18 сторон -> SPHERE976_N (48) ближе VG_LOD_D. Звёзды столба (collectfx.c): прозрачность COL976_A, ход по канону кинематики
#   (viewer/glintmotion976.h). «Как было» — flag glint976old 1 или сборка oldc.
#   Зелёное: host.c (яркость ×0,5, ускорение фронта ≤ 100 против 1200, звезда без рывка, кольцо ровнее); кадры входа: масса звёзд 0,15..0,6 от прежней; сторон кольца ≥ 40.
#   Красное (обязано упасть): прежнее против прежнего, сборка red (COL976_A=1, SPHERE976_N=18), прежняя формула в host, oldc.
set -u
export PATH=$HOME/Downloads/shar-psp/build/xcshim/bin:$PATH
W=$(cd "$(dirname "$0")/../.." && pwd); cd "$W"; T=tests/glint970; A=${A:-$W/build/g970/acc976}; mkdir -p "$A" build/g976; BAD=0
export SDKROOT=${SDKROOT:-/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk}
ok() { echo "  [ok]  $1"; }; bad() { echo "  [BAD] $1"; BAD=$((BAD + 1)); }
C="python3 $T/check976.py"; O=$A/out_
echo "== 1. ход столба и кольцо (host.c)"
cc -O1 -o build/g976/host tests/glint976/host.c -lm && build/g976/host new > build/g976/host_new.txt && build/g976/host old > build/g976/host_old.txt || bad "host.c"
$C host build/g976/host_new.txt build/g976/host_old.txt && ok "ход столба и ровность кольца" || bad "ход столба"
$C host build/g976/host_old.txt build/g976/host_old.txt > build/g976/red_host.txt 2>&1 && bad "красный: прежняя формула прошла" || ok "красный: прежняя формула упала, как должна"
[ "${QUICK:-0}" != 1 ] && { echo "== 2. сборки"; $T/mkall.sh; }
for v in new none oldc red; do [ -f viewer/build_g_$v/EBOOT.PBP ] || bad "нет сборки $v"; done
if [ "${RERUN:-1}" != 0 ]; then echo "== 3. эмулятор: сфера цели L1, камера на кружок"; rm -f "$A/runall.done"; A=$A $T/runall.sh sphere:new sphere:old sphere:none sphere:oldc sphere:red; fi
echo "== 4. кадры"
$C frames ${O}sphere_none ${O}sphere_old ${O}sphere_new && ok "звёзды цели прозрачнее вдвое" || bad "звёзды цели"
$C frames ${O}sphere_none ${O}sphere_old ${O}sphere_old > "$A/red_old.txt" 2>&1 && bad "красный: прежнее против прежнего прошло" || ok "красный: прежнее против прежнего упало, как должно"
$C frames ${O}sphere_none ${O}sphere_old ${O}sphere_red > "$A/red_red.txt" 2>&1 && bad "красный red прошёл" || ok "красный red (COL976_A=1) упал, как должен"
$C frames ${O}sphere_none ${O}sphere_old ${O}sphere_oldc > "$A/red_oldc.txt" 2>&1 && bad "oldc прошёл гейт нового" || ok "сборка -DGLINT976_OLD=1 возвращает прежнее"
echo "== 5. кольцо: число сторон по журналу"
$C ring ${O}sphere_new/smoke.txt ${O}sphere_old/smoke.txt && ok "кольцо цели ≥ 40 сторон (прежнее 18)" || bad "кольцо цели"
$C ring ${O}sphere_red/smoke.txt ${O}sphere_old/smoke.txt > "$A/red_ring.txt" 2>&1 && bad "красный: кольцо red прошло" || ok "красный: кольцо red (18 сторон) упало, как должно"
n=$(grep -c 'strstr(name, "sphere")' viewer/lightsprite.h); [ "$n" -ge 1 ] && ok "кольцо: только сферы цели (по имени)" || bad "правило по имени сферы не найдено"
[ $BAD = 0 ] && echo PASS || echo FAIL
