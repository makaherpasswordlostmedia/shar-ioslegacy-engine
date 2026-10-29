#!/bin/bash
# Экран покупки PurchaseRewards (пункт 6): пакеты tools/shop_export.py против данных диска.
#   tests/shop/export_gate.sh [DIR]   DIR — готовые shop.shr и reward-*.shr (по умолчанию build/); закон 5: сначала красные
#   (подложенные ошибки экспорта — каждая обязана упасть на своей проверке), потом зелёный на DIR. Итог «shop export gate: PASS/FAIL»
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
DIR="${1:-build}"; T=build/tmp/shop_gate; rm -rf "$T"; mkdir -p "$T"
export SHR_TMP="$ROOT/build/tmp_conv/shopgate"; mkdir -p "$SHR_TMP"
PY=.venv/bin/python; bad=0
red() {   # $1 подлог, $2 проверка, что обязана упасть, $3.. ключи экспорта
  local p="$1" chk="$2"; shift 2
  mkdir -p "$T/$p"; cp "$DIR"/reward-*.shr "$DIR"/shop.shr "$T/$p/" 2>/dev/null
  SHOP_PLANT="$p" $PY tools/shop_export.py --out-dir "$T/$p" "$@" > "$T/$p.export.txt" 2>&1 || { echo "FAIL: экспорт с подлогом $p"; bad=1; return; }
  SHOP_PLANT="$p" $PY tools/shop_export.py --check --out-dir "$T/$p" > "$T/$p.check.txt" 2>&1
  if [ $? -ne 0 ] && grep -q "CHECK $chk .*FAIL" "$T/$p.check.txt"; then echo "красный ($p): $(grep -m1 "CHECK $chk .*FAIL" "$T/$p.check.txt" | cut -c1-150)"
  else echo "КРАСНЫЙ НЕ ПОЙМАН ($p): $(tail -1 "$T/$p.check.txt")"; bad=1; fi
}
red stars "stars " --ui-only                 # звёзды без сдвига кадров: все пять звёзд строки показывают одно и то же
red order "names " --ui-only                 # машины не в порядке каталога рантайма
red nlerp "camera" --car cVan                # поворот сцены линейно по ключам: камера облёта «плывёт» в осях сцены
$PY tools/shop_export.py --check --out-dir "$DIR" > "$T/green.txt" 2>&1 || bad=1
grep "^CHECK\|shop check" "$T/green.txt"
[ $bad = 0 ] && echo "shop export gate: PASS" || echo "shop export gate: FAIL"; exit $bad
