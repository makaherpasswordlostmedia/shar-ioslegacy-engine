#!/bin/bash
# №683 (шум под чёрными машинами будки): гейт палитры страниц CLUT8 интерфейса. Пакет меню (быстрый) и будки собираются с замером
# UI_QUANT_STATS=1 (строки QSTAT: op — непрозрачных пикселей страницы, leak — из них ставших прозрачнее после палитры).
#   зелёный: leak = 0 на всех страницах; красный контроль: UI_QUANT_OPAQUE_OLD=1 (прежний общий k-means) — leak > 0, иначе гейт ничего не ловит
set -u; cd "$(dirname "$0")/../.."; PY=.venv/bin/python; [ -x "$PY" ] || PY=python3
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT; fail=0
for m in new old; do
  E=""; [ $m = old ] && E="UI_QUANT_OPAQUE_OLD=1"
  env $E UI_QUANT_STATS=1 UI_SCRATCH=$T LEVEL=1 $PY tools/menu_export.py --pack menu --out $T/menu_$m.shr > $T/menu_$m.txt 2>&1 &
  env $E UI_QUANT_STATS=1 UI_SCRATCH=$T LEVEL=1 $PY tools/shop_export.py --phone-ui --out $T/phone_$m.shr > $T/phone_$m.txt 2>&1 &
done; wait
for m in new old; do
  L=$(cat $T/menu_$m.txt $T/phone_$m.txt | sed -n 's/.*QSTAT [^ ]* op=[0-9]* leak=\([0-9]*\).*/\1/p' | awk '{s+=$1; n++} END {print s+0, n+0}')
  echo "$m: утечка непрозрачного $L (пикселей, страниц)"
  set -- $L; [ "${2:-0}" -gt 0 ] || { echo "FAIL $m: нет строк QSTAT"; fail=1; }
  if [ $m = new ] && [ "$1" != 0 ]; then echo "FAIL: непрозрачные пиксели стали прозрачнее"; fail=1; fi
  if [ $m = old ] && [ "$1" = 0 ]; then echo "FAIL: красный контроль не покраснел"; fail=1; fi
done
[ $fail = 0 ] && echo "PASS quant683"; exit $fail
