#!/bin/bash
# Все пакеты интерфейса (ui.shr, boot/load/menu/pmenu/pextra/fsave/psave/shop/phone, bonus/mini) с текущими настройками Роба build/ui_typo.json.
#   tools/ui_packs.sh OUT [УРОВНИ=1..7]      OUT/ui.shr, OUT/l2..l7/ui.shr и остальные пакеты (общие для всех уровней — на уровне 1, у уровней 2..7 — свои ui, pextra, pmenu, psave, shop, phone)
#   UI_PLACE_CODE=1 tools/ui_packs.sh ...    код клетки паузы элементом PlaceCode (нужен движок №598, коммит e8974e0c; без движка не включать)
#   UI_TYPO=0 — без настроек панели (чистая раскладка диска); UI_TYPO=файл.json — другой файл настроек
# Данные Роба не меняются. Лог каждого пакета — OUT/logs/<имя>_l<N>.log, итог — OUT/logs/ALLDONE
set -u; cd "$(dirname "$0")/.."
OUT="${1:?usage: tools/ui_packs.sh OUT [LEVELS]}"; shift; LEVELS="${*:-1 2 3 4 5 6 7}"
export PSPDEV=$PWD/pspdev PATH=$PWD/pspdev/bin:$PATH
PY=$PWD/.venv/bin/python; [ -x "$PY" ] || PY=python3
mkdir -p "$OUT/logs"; OUT=$(cd "$OUT" && pwd)
one() {  # NAME LEVEL
  local name=$1 n=$2 d=$OUT cmd
  [ "$n" = 1 ] || { d=$OUT/l$n; mkdir -p "$d"; }
  case $name in
    ui)     cmd="tools/ui_export.py --out $d/ui.shr";;
    boot)   cmd="tools/load_export.py --pack boot --out $d/boot.shr";;
    load)   cmd="tools/load_export.py --pack load --out $d/load.shr";;
    menu)   cmd="tools/menu_export.py --pack menu --out $d/menu.shr";;
    pmenu)  cmd="tools/menu_export.py --pack pmenu --out $d/pmenu.shr";;
    pextra) cmd="tools/menu_export.py --pack pextra --out $d/pextra.shr";;
    fsave)  cmd="tools/save_export.py --pack fsave --out $d/fsave.shr";;
    psave)  cmd="tools/save_export.py --pack psave --out $d/psave.shr";;
    shop)   if [ "$n" = 1 ]; then cmd="tools/shop_export.py --ui-only --out $d/shop.shr"; else cmd="tools/shop_export.py --level $n --ui-only --out $d/shop.shr"; fi;;
    phone)  if [ "$n" = 1 ]; then cmd="tools/shop_export.py --phone-ui --out $d/phone.shr"; else cmd="tools/shop_export.py --level $n --phone-ui --out $d/phone.shr"; fi;;
    mini)   mkdir -p "$OUT/bonus"; cmd="tools/bonus/screens_export.py --out $OUT/bonus/mini.shr";;
  esac
  UI_SCRATCH=$(mktemp -d) LEVEL=$n nice $PY $cmd > "$OUT/logs/${name}_l$n.log" 2>&1; echo "rc=$?" >> "$OUT/logs/${name}_l$n.log"
}
for n in $LEVELS; do
  one ui $n &
  if [ "$n" = 1 ]; then for k in boot load menu pmenu pextra fsave psave shop phone mini; do one $k 1 & done
  else for k in pextra pmenu psave shop phone; do one $k $n & done; fi
  wait
done
bad=$(grep -L "^rc=0" "$OUT"/logs/*_l*.log 2>/dev/null | wc -l | tr -d ' ')
# Роб 17.10: в итоге — чья панель типографики в пакетах (TEST31 сводной ветки ушёл без неё); без панели — только явно UI_TYPO=0
TY="${UI_TYPO:-}"; [ -z "$TY" ] && { [ -f build/ui_typo.json ] && TY=build/ui_typo.json || TY=docs/typography/ui_typo_ROB.json; }
if [ "$TY" = 0 ]; then TYS=none; elif [ -f "$TY" ]; then TYS=$(shasum -a 256 "$TY" | cut -c1-8); else TYS=MISSING; bad=$((bad+1)); echo "НЕТ ПАНЕЛИ ТИПОГРАФИКИ: $TY"; fi
echo "ALLDONE bad=$bad typo=$TYS" > "$OUT/logs/ALLDONE"; cat "$OUT/logs/ALLDONE"
