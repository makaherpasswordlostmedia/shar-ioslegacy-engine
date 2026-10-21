#!/bin/bash
# Гейт обезьян l2/l5_monkiesgag (стейтпроп 47 слотов, маска SPR1 в 2 слова — §8 рецепта): настоящий код world.c + stateprops.c,
# собранный level.shr уровня. Машина на газу в объект: s0 -> s1 данных (удар), видны части со слотами 32+, объём снят, через 6 с
# (REMOVE_FROM_WORLD данных) объект ушёл из мира. Красный: цель сдвинута на 40 м (неверный локатор) — удара нет.
. "$(dirname "$0")/common.sh"
build_host
export BW_NO_COLLECT=1
red   "L2 неверный локатор 40 м"  build/levelmech/lvmech "$(LV 2 level.shr)" "$HOMER" --wide 40
for n in 2 5; do
  green "L$n обезьяны"            build/levelmech/lvmech "$(LV $n level.shr)" "$HOMER" --wide
done
grep -h "^M" "$LOGD"/green_*.log
echo "журнал: $LOGD"
[ $FAILS -eq 0 ] && echo "GATE monkeys: PASS" || echo "GATE monkeys: FAIL ($FAILS)"
exit $FAILS
