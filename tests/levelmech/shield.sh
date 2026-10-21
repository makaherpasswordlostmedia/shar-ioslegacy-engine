#!/bin/bash
# Гейт щитов ос AddShield (уровни 5–7) — tests/levelmech/shield_check.py. Красные: пакет collect уровня 5 без щитов (прежний
# экспорт основной копии), сборка -DCOLL_SHIELD_ON=0 (щит не держит). Зелёные: уровни 5, 6, 7 — щит у каждой осы, удары пинком
# и машиной; уровень 1 — щитов нет, первый удар убивает осу (поведение уровня 1 прежнее).
. "$(dirname "$0")/common.sh"
build_host
SUF=_noshield bash tests/levelmech/build_host.sh -DCOLL_SHIELD_ON=0 > /dev/null || exit 2
unset BW_NO_COLLECT
# прежний экспорт без щитов: эталон build/levelmech/ref (сборка 01.10 до слияния механик); нет — пакет основной копии (так было до 03.10)
PRE5=build/levelmech/ref/collect-l5_pre_mech.shr; [ -f "$PRE5" ] || PRE5="$MAIN/build/levels/l5/collect-l5.shr"
red   "L5 пакет без щитов (прежний)"  $PY tests/levelmech/shield_check.py --level 5 --shr "$(LV 5 level.shr)" --collect "$PRE5"
red   "L5 сборка без щита"            $PY tests/levelmech/shield_check.py --level 5 --shr "$(LV 5 level.shr)" --collect "$(LV 5 collect-l5.shr)" --bin build/levelmech/lvmech_noshield
for n in 5 6 7 1; do
  green "L$n щиты ос"                 $PY tests/levelmech/shield_check.py --level $n --shr "$(LV $n level.shr)" --collect "$(LV $n collect-l$n.shr)"
done
grep -h "^диск\|^осы проверены\|^C" "$LOGD"/green_*.log
echo "журнал: $LOGD"
[ $FAILS -eq 0 ] && echo "GATE shield: PASS" || echo "GATE shield: FAIL ($FAILS)"
exit $FAILS
