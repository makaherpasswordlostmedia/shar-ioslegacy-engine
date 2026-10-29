#!/bin/bash
# Гейт летающих актёров не-ос (уровень 7: корабль на l7_spaceship и его луч UFO_BEAM_ALWAYS_ON) — tests/levelmech/flying_check.py
# (ожидание с диска, игра — lvmech --actors на настоящем коде). Красные: пакет collect без актёров (прежний экспорт основной
# копии), пакет со сдвинутыми на 5 м актёрами (неверный локатор). Зелёные: уровень 7 — корабль и луч на месте; уровни 1–6 —
# лишних экземпляров нет (пакеты уровней 1–6 экспорт не меняет: у них AddFlyingActorByLocator нет).
. "$(dirname "$0")/common.sh"
build_host
C7=build/levels/l7/collect-l7.shr
[ -f "$C7" ] || { echo "нет $C7 — python3 tools/collect_export.py --level 7 --out $C7"; exit 2; }
S7=$(LV 7 level.shr)
$PY tests/levelmech/plant.py shift-extra "$C7" build/levelmech/collect-l7-shift.shr 5 > /dev/null
# прежний экспорт без актёров: эталон build/levelmech/ref (сборка 01.10 до слияния механик); нет — пакет основной копии (так было до 03.10)
PRE7=build/levelmech/ref/collect-l7_pre_mech.shr; [ -f "$PRE7" ] || PRE7="$MAIN/build/levels/l7/collect-l7.shr"
red   "L7 пакет без актёров (прежний)"   $PY tests/levelmech/flying_check.py --level 7 --shr "$S7" --collect "$PRE7"
red   "L7 актёры сдвинуты на 5 м"        $PY tests/levelmech/flying_check.py --level 7 --shr "$S7" --collect build/levelmech/collect-l7-shift.shr
green "L7 корабль и луч"                 $PY tests/levelmech/flying_check.py --level 7 --shr "$S7" --collect "$C7"
for n in 1 2 3 4 5 6; do
  green "L$n без летающих актёров"       $PY tests/levelmech/flying_check.py --level $n --shr "$(LV $n level.shr)" --collect "$(LV $n collect-l$n.shr)"
done
grep -h "Planet\|RESULT" "$LOGD"/green_L7*.log
echo "журнал: $LOGD"
[ $FAILS -eq 0 ] && echo "GATE flying: PASS" || echo "GATE flying: FAIL ($FAILS)"
exit $FAILS
