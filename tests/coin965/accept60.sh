#!/bin/bash
# №965 «Мультик»: блик у монет вдвое меньше и в центре монеты.   tests/coin965/accept60.sh      (последняя строка: PASS или FAIL)
#   Сборки тура (с -DZF932_OLD=1): new; old (-DCOIN_GLINT965_OLD=1 — как test62); none (-DCOIN_GLINT_S=0.001f — блик погашен, опора кадра); red2 (-DCOIN_GLINT_LIFT=0.f — вдвое меньше, но без сдвига к глазу).
#   Сцена: L1, L2, L5, камера в 2,5 м от монеты мира (flag coincam), 4 снимка с шагом 0,37 с. Эмулятор повторяет числа: монета на снимках new/old/none одна и та же, блик = разница с none.
#   Зелёное: ширина блика new/old 0,25..0,62; центр блика в 0,2 размера монеты от центра; низ/верх по массе 0,6..1,7. Красное: old обязан упасть (размер), red2 — упасть (центр: верх блика за монетой).
#   Соседние блики не тронуты: лист форм (glintlab 1), звезда входа (glintlab 2) и стекло L1 в new и old — пиксель в пиксель (строка HUD не считается; в стекле L1 рядом две монеты — отличия в 32 пикс от них разрешены).
set -u
export PATH=$HOME/Downloads/shar-psp/build/xcshim/bin:$PATH
W=$(cd "$(dirname "$0")/../.." && pwd); cd "$W"; T=tests/coin965; mkdir -p build/c965
export SET=${SET:-$HOME/Downloads/shar-psp-integ/build/test63tour/PSP/GAME/SHARTEST15}; export EMU_OWNER=${EMU_OWNER:-Мультик} EMU_MINE=${EMU_MINE:-2}
A=${A:-$W/build/c965/accept}; mkdir -p "$A"; BAD=0
ok() { echo "  [ok]  $1"; }; bad() { echo "  [BAD] $1"; BAD=$((BAD + 1)); }
if [ "${QUICK:-0}" != 1 ]; then
  for v in "new:" "old:-DCOIN_GLINT965_OLD=1" "none:-DCOIN_GLINT_S=0.001f" "red2:-DCOIN_GLINT_LIFT=0.f"; do "$T/mk.sh" ${v%%:*} "${v#*:}" > "$A/mk_${v%%:*}.log" 2>&1; done
fi
for n in new old none red2; do [ -f viewer/build_k_$n/EBOOT.PBP ] || bad "нет сборки $n"; done
run() { OUT="$A" tools/emu_run.sh "$T/$1.txt" "$2" "viewer/build_k_$3/EBOOT.PBP" "${4:-400}" > "$A/$2.log" 2>&1; }
( run scenario new new & run scenario old old & wait ); ( run scenario none none & run scenario red2 red2 & wait )
( run lab1 lab1_new new 120 & run lab1 lab1_old old 120 & wait ); ( run lab2 lab2_new new 120 & run lab2 lab2_old old 120 & wait ); ( run glass glass_new new 200 & run glass glass_old old 200 & wait )
O=$A/out_; C="python3 $T/check.py"
echo "-- новая: размер и центр"; $C gate ${O}none ${O}old ${O}new && ok "блик вдвое меньше и в центре монеты" || bad "новая не прошла"
echo "-- красный 1: прежняя сборка"; $C gate ${O}none ${O}old ${O}old > "$A/red1.txt" 2>&1 && bad "красный (прежняя) прошёл гейт" || ok "красный (прежняя сборка) упал, как должен"
echo "-- красный 2: вдвое меньше, но без сдвига к глазу"; $C gate ${O}none ${O}old ${O}red2 > "$A/red2.txt" 2>&1 && bad "красный 2 прошёл гейт" || ok "красный 2 (без сдвига) упал, как должен"; tail -4 "$A/red2.txt"
echo "-- соседние блики (лист форм, звезда входа, стекло): new = old"
$C same ${O}lab1_new ${O}lab1_old lab lab2 && ok "лист форм и стекло-звезда на листе те же" || bad "лист форм изменился"
$C same ${O}lab2_new ${O}lab2_old lab lab_b && ok "звезда входа та же" || bad "звезда входа изменилась"
$C same ${O}glass_new ${O}glass_old g_pre g_a g_b g_c g_d g_e g_f --coins && ok "стекло L1 то же (кроме монет)" || bad "стекло L1 изменилось"
$C same ${O}glass_new ${O}glass_old g_a g_b g_c g_d g_e g_f > "$A/red3.txt" 2>&1 && bad "красный 3: гейт соседей не заметил смену блика монет" || ok "красный 3: без допуска у монет гейт соседей падает на блике монет, как должен"
[ $BAD = 0 ] && echo PASS || echo FAIL
