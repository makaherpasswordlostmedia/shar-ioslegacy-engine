#!/bin/bash
# Сцены эмулятора механик уровней одним заходом (по одному окну через очередь tools/ppsspp_run.sh, короткие прогоны):
# зелёные barriers 2, barriers 5, ufo 7, shield 5; с --negative — ещё отрицательные контроли (данные прогона без механики).
cd "$(dirname "$0")/../.." || exit 2
rc=0
run() { out=$(bash tests/levelmech/emu.sh "$@" 2>&1); r=$?; echo "$out" | grep -E "^(прогон|куча|FPS|уровень|  ПРОВАЛ)"; return $r; }
for m in "barriers 2" "barriers 5" "ufo 7" "shield 5"; do run $m || rc=1; done
if [ "${1:-}" = --negative ]; then
  for m in "barriers 2" "ufo 7" "shield 5"; do if run $m --negative; then echo "RED НЕ ПОЙМАН: $m"; rc=1; else echo "RED OK: $m"; fi; done
fi
[ $rc -eq 0 ] && echo "СЦЕНЫ ЭМУЛЯТОРА: PASS" || echo "СЦЕНЫ ЭМУЛЯТОРА: FAIL"
exit $rc
