#!/bin/bash
# Гейт пункта 12: обход трамплинов ↑ / ↓ в машине, один запуск эмулятора через общую очередь tools/ppsspp_run.sh.
#   tools/cartest/routes_gate.sh [--no-routes] [EBOOT]   EBOOT по умолчанию viewer/build/EBOOT.PBP; данные из build/
#   --no-routes   рядом с EBOOT нет routes.txt: ↑ / ↓ ничего не делают (routes_gate.py --still)
# Своя чистая папка build/emu/routes/<время>-<pid>/ (EBOOT + данные tools/ship_files.sh + build/routes.txt + сценарий
# tools/cartest/routes_scenario.txt + smokelog), после прогона удаляется. Итог: build/routes_gate/<время>/ — снимки
# r0 r1 r2 r3 r2back, smoke.txt, gate.txt. Код выхода 0 = PASS (tools/cartest/routes_gate.py).
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
NOR=0; [ "${1:-}" = --no-routes ] && { NOR=1; shift; }
EB="${1:-$ROOT/viewer/build/EBOOT.PBP}"; case "$EB" in /*) ;; *) EB="$PWD/$EB" ;; esac
[ -f "$EB" ] || { echo "routes_gate: нет $EB"; exit 1; }
[ $NOR = 1 ] || [ -f "$ROOT/build/routes.txt" ] || { echo "routes_gate: нет build/routes.txt (python3 tools/cartest/routes_txt.py)"; exit 1; }
STAMP=$(date +%Y%m%d-%H%M%S); RUN="$ROOT/build/emu/routes/$STAMP-$$"; OUT="$ROOT/build/routes_gate/$STAMP"
[ -e "$OUT" ] && OUT="$OUT-$$"
mkdir -p "$RUN" "$OUT"; trap 'rm -rf "$RUN"' EXIT
cp -c "$EB" "$RUN/EBOOT.PBP" 2>/dev/null || cp "$EB" "$RUN/EBOOT.PBP"
for f in $("$ROOT/tools/ship_files.sh"); do
  [ "$f" = routes.txt ] && continue
  [ -f "$ROOT/build/$f" ] || { echo "routes_gate: нет build/$f"; exit 1; }
  mkdir -p "$RUN/$(dirname "$f")"; cp -c "$ROOT/build/$f" "$RUN/$f" 2>/dev/null || cp "$ROOT/build/$f" "$RUN/$f" || exit 1
done
[ $NOR = 1 ] || cp "$ROOT/build/routes.txt" "$RUN/routes.txt"
cp "$ROOT/tools/cartest/routes_scenario.txt" "$RUN/scenario.txt"; touch "$RUN/smokelog"
echo "$EB$([ $NOR = 1 ] && echo ' (без routes.txt)')" > "$OUT/eboot.txt"
PPSSPP_SHOTS="$RUN/smoke.txt" PPSSPP_SHOTDIR="$OUT" "$ROOT/tools/ppsspp_run.sh" "$RUN/EBOOT.PBP" 120
cp "$RUN/smoke.txt" "$OUT/" 2>/dev/null
[ $NOR = 1 ] || cp "$RUN/routes.txt" "$OUT/"
"$ROOT/.venv/bin/python" "$ROOT/tools/cartest/routes_gate.py" "$OUT" "$ROOT/build/routes.txt" $([ $NOR = 1 ] && echo --still); RC=$?
echo "итог: ${OUT#$ROOT/}/gate.txt"
exit $RC
