#!/bin/bash
# Гейт барьеров 0x3F0000F (уровни 2 и 5: «проезд закрыт» 20 шт. и знак переезда 8 шт. на уровень).
# 1) данные (tests/levelmech/barriers_check.py, диск Роба, экспорт без конвертера) — все 7 уровней;
#    красные: как до 29.09 (SHR_NO_ANIMPHYS=1), перепутанные номера обломков, порог огня выше единицы;
# 2) игра (tests/levelmech/lvmech --barriers, настоящий код world.c + stateprops.c, собранный level.shr уровня):
#    красные: цель сдвинута на 15 м (неверный локатор), сборка без мигания огней (-DSP_BILL_PVIS_ON=0);
#    зелёный: у всех барьеров огни мигают, машина ломает барьер каждого типа и не останавливается о него.
. "$(dirname "$0")/common.sh"
build_host
SUF=_nopvis bash tests/levelmech/build_host.sh -DSP_BILL_PVIS_ON=0 > /dev/null || exit 2
export BW_NO_COLLECT=1
red   "данные: как до 29.09"            env SHR_NO_ANIMPHYS=1 $PY tests/levelmech/barriers_check.py --levels 2
red   "данные: номера обломков"         $PY tests/levelmech/barriers_check.py --levels 5 --swap-atc
red   "данные: огонь никогда не горит"  $PY tests/levelmech/barriers_check.py --levels 2 --half 1.1
green "данные: уровни 1-7"              $PY tests/levelmech/barriers_check.py --levels 1-7
for n in ${LEVELS:-2 5}; do
  L=$(LV $n level.shr)
  if ! grep -q "барьер 0x3F0000F" "$(dirname "$L")/level.log" 2>/dev/null; then
    echo "уровень $n: $L собран без барьеров (нет строки в level.log) — пересобрать: LEVEL=$n tools/build_level.sh"; FAILS=$((FAILS + 1)); continue
  fi
  red   "L$n игра: неверный локатор 15 м"  build/levelmech/lvmech "$L" "$HOMER" --barriers 15
  red   "L$n игра: без мигания"            build/levelmech/lvmech_nopvis "$L" "$HOMER" --barriers
  green "L$n игра: огни и удар"            build/levelmech/lvmech "$L" "$HOMER" --barriers
  grep -hE "^(огни|удар)" "$LOGD"/green_L$n*.log
done
echo "журнал: $LOGD"
[ $FAILS -eq 0 ] && echo "GATE barriers: PASS" || echo "GATE barriers: FAIL ($FAILS)"
exit $FAILS
