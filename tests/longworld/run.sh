#!/bin/bash
# Длинный мир (пункт 10б): стекло разбито -> уехал дальше 60 м -> вернулось (правило порта props.c: 5 с вне вида) ->
# вернулся и разбил снова. Повторы — нажатия каскадёра (tools/bots/explorer.c) до первого удара, дальше водитель навигатора.
# Контроль: тот же случай без возврата предметов (BW_NO_RESPAWN=1) обязан провалиться на «не вернулся / НЕ разбит». tests/longworld/run.sh -> PASS/FAIL
cd "$(dirname "$0")/../.."
BINS="game_headless longworld" tools/bots/build.sh >/dev/null || exit 1
A="build/level.shr build/homer.shr build/sandbox/roads-l1.bin"; ok=1
for g in 186 190; do build/bots/longworld $A tests/longworld/glass$g.in $g > /dev/null && echo "стекло $g: разбито дважды — OK" || { echo "стекло $g: FAIL"; ok=0; }; done
# контроль: возврат предметов выключен (BW_NO_RESPAWN=1) — стекло не возвращается и повторно не бьётся, тест обязан упасть на этом
c=$(BW_NO_RESPAWN=1 build/bots/longworld $A tests/longworld/glass190.in 190); rc=$?
if [ $rc = 0 ]; then echo "контроль без возврата предметов: прошёл — ТЕСТ НЕ ЛОВИТ"; ok=0
elif echo "$c" | grep -q "не вернулся" && echo "$c" | grep -q "НЕ разбит"; then echo "контроль без возврата предметов: FAIL — «не вернулся», «НЕ разбит» (красный, как надо)"
else echo "контроль без возврата предметов: FAIL по другой причине — не доказывает"; echo "$c" | tail -3; ok=0; fi
[ $ok = 1 ] && echo PASS || { echo FAIL; exit 1; }
