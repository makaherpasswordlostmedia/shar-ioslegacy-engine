#!/bin/bash
# №970 «Небо»: блики ключа, будки, монеты и огней машины.   tests/glint970/accept60.sh      (последняя строка: PASS или FAIL)
#   QUICK=1 — без пересборки (EBOOT уже в viewer/build_g_*), RERUN=0 — без эмулятора (снимки уже в build/g970/acc)
#   Сборки тура (с -DZF932_OLD=1): new; none (все блики №970 погашены: опора кадра); oldc (-DGLINT970_OLD=1, как TEST66); red (по одному недоделанному правилу на предмет:
#   ключ без прозрачности, будка без снижения и с сердцевиной, монета с одним бликом, огни без увеличения). «Как было» на сборке new — файл flag glint970old 1.
#   Зелёное: ход слоёв ключа (host.c: ближе к центру, без шва и рывков, пульс не повторяется); ключ — площадь ≤ 0,75, масса ≤ 0,45 от прежнего; будка — масса 0,3..0,62, размер тот;
#   монета — ≥ 3 пятен, каждое мельче (ширина ≤ 0,6), центр масс в центре монеты (№965); огни — размер блика ×1,15..1,5; соседние блики (лист форм, звезда входа, стекло, «!») пиксель в пиксель;
#   сборка oldc = new с flag glint970old 1 (по числам блика).
#   Красное (обязано упасть): прежнее против прежнего (все 5 гейтов), red по своему предмету, прежняя формула хода в host.
set -u
export PATH=$HOME/Downloads/shar-psp/build/xcshim/bin:$PATH
W=$(cd "$(dirname "$0")/../.." && pwd); cd "$W"; T=tests/glint970; A=${A:-$W/build/g970/acc}; mkdir -p "$A" build/g970; BAD=0
export SDKROOT=${SDKROOT:-/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk}
ok() { echo "  [ok]  $1"; }; bad() { echo "  [BAD] $1"; BAD=$((BAD + 1)); }
C="python3 $T/check.py"; O=$A/out_
echo "== 1. ход слоёв ключа (host.c)"
cc -O1 -o build/g970/host $T/host.c -lm && build/g970/host new > build/g970/host_new.txt && build/g970/host old > build/g970/host_old.txt || bad "host.c"
$C host build/g970/host_new.txt build/g970/host_old.txt && ok "ход слоёв ключа" || bad "ход слоёв ключа"
$C host build/g970/host_old.txt build/g970/host_old.txt > build/g970/red_host.txt 2>&1 && bad "красный: прежняя формула прошла" || ok "красный: прежняя формула хода упала, как должна"
if [ "${QUICK:-0}" != 1 ]; then
  echo "== 2. сборки"
  $T/mkall.sh
fi
for v in new none oldc red; do [ -f viewer/build_g_$v/EBOOT.PBP ] || bad "нет сборки $v"; done
if [ "${RERUN:-1}" != 0 ]; then
  echo "== 3. эмулятор (по два): ключ, будка, огни, монета, соседи"
  rm -f "$A/runall.done"
  $T/runall.sh wrench:new wrench:old phone:new phone:old lights:new lights:old coin:new coin:old wrench:none phone:none lights:none coin:none \
    wrench:oldc phone:oldc lights:oldc coin:oldc wrench:red phone:red lights:red coin:red lab1:new lab1:oldc lab2:new lab2:oldc glass:new glass:oldc excl:new excl:oldc
fi
echo "== 4. гейты по снимкам"
for o in "wrench w" "phone p" "lights l" "coin c"; do set -- $o
  $C $1 ${O}${2}_none ${O}${2}_old ${O}${2}_new > "$A/gate_$1.txt" 2>&1; tail -8 "$A/gate_$1.txt" | grep -v "^PASS\|^FAIL" | tail -3; [ "$(tail -1 "$A/gate_$1.txt")" = PASS ] && ok "$1: новое" || bad "$1: новое не прошло"
  $C $1 ${O}${2}_none ${O}${2}_old ${O}${2}_old > "$A/red_old_$1.txt" 2>&1 && bad "красный (прежнее против прежнего) прошёл: $1" || ok "красный $1: прежнее против прежнего упало, как должно"
  $C $1 ${O}${2}_none ${O}${2}_old ${O}${2}_red > "$A/red_$1.txt" 2>&1 && bad "красный red прошёл: $1" || { ok "красный $1: недоделанное правило упало, как должно"; tail -3 "$A/red_$1.txt" | head -2; }
  $C $1 ${O}${2}_none ${O}${2}_old ${O}${2}_oldc > "$A/oldc_$1.txt" 2>&1 && bad "oldc ($1) прошёл гейт нового: -DGLINT970_OLD не вернул прежнее" || ok "сборка -DGLINT970_OLD=1 ($1) возвращает прежнее (гейт нового падает)"
done
echo "== 5. соседние блики: new = oldc пиксель в пиксель"
$C same ${O}lab1_new ${O}lab1_oldc lab lab2 && ok "лист форм и звезда стекла те же" || bad "лист форм изменился"
$C same ${O}lab2_new ${O}lab2_oldc lab lab_b && ok "звезда входа та же" || bad "звезда входа изменилась"
$C same ${O}glass_new ${O}glass_oldc g_pre g_a g_b g_c g_d g_e g_f --coins && ok "стекло L1 то же (кроме монет)" || bad "стекло L1 изменилось"
$C same ${O}excl_new ${O}excl_oldc ex0 ex1 ex2 ex3 --coins && ok "«!» над персонажем тот же (кроме монет рядом)" || bad "«!» изменился"
echo "== 6. семейство блика: кто зовёт общий путь (census)"
n=$(grep -c "gvMode970 = 1" viewer/spritelight.h); [ "$n" = 1 ] && ok "ход слоёв включается в одном месте (ключ)" || bad "gvMode970 = 1 встречается $n раз"
[ $BAD = 0 ] && echo PASS || echo FAIL
