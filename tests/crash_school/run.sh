#!/bin/bash
# Правка 103 (повтор 01.10 ~09:40 на 7dec8b30): «приехал на спортивную площадку у школы — завис, приставка выключилась».
# Один прогон эмулятора (tools/smoke.sh, общая очередь) по сценарию tests/crash_school/scenario.txt: режим игрока, подсказки
# Барта, миссии (NEW GAME, потом m6 у школы), журнал звуков, машина и Гомер по бейсбольному полю, детской площадке, трамплинам
# jumpzone16/jumpzone2, у Вилли и Луи. Как у настоящей PSP: куча — балласт BALLAST МБ (по умолчанию 9: эмулятор отдаёт больше),
# карта памяти — медленная (служебный файл slowio, 1,5 МБ/с; FLAGS — свой набор), журнал PPSSPP — места, которые эмулятор
# пропускает, а PSP на них падает (плохой адрес, ловушка break 7). Разбор — tests/crash_school/check.py (выход 0 — зелёный).
# Сцена dog_freeze (v2): «flag freeze 7» — главный поток стоит 7 с в фазе gesync, сторож самописца обязан записать ящик сам.
#   tests/crash_school/run.sh [EBOOT] [метка]      по умолчанию viewer/build/EBOOT.PBP; данные — из build/ (как smoke.sh)
#   SCN=файл — другой сценарий (по умолчанию tests/crash_school/scenario.txt)
# Красный: EBOOT старого кода (до правки) обязан упасть (самописец: ящик раз в минуту, без действий, без сторожа); зелёный — новый.
# Разбор готового прогона без эмулятора: .venv/bin/python tests/crash_school/check.py build/smoke/<время>
# На железо — tests/crash_school/scenario_psp.txt (тот же маршрут без балласта и медленной карты, в конце проверка сторожа).
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
EB="${1:-viewer/build/EBOOT.PBP}"; TAG="${2:-run}"
[ -f "$EB" ] || { echo "FAIL: нет $EB"; exit 2; }
D="build/crash_school/$TAG"; rm -rf "$D"; mkdir -p "$D"; cp "$EB" "$D/EBOOT.PBP"
LOG=$(SMOKE_SCN="${SCN:-$ROOT/tests/crash_school/scenario.txt}" SMOKE_BALLAST="${BALLAST:-9}" SMOKE_PPSSPPLOG=1 \
      SMOKE_FLAGS="${FLAGS-slowio}" tools/smoke.sh "$D" 2>&1)
OUT=$(printf '%s\n' "$LOG" | sed -n 's#^отчёт: \(build/smoke/[^/]*\)/summary.txt.*#\1#p' | tail -1)
[ -n "$OUT" ] && [ -d "$OUT" ] || { echo "FAIL: смоук не дал отчёта"; printf '%s\n' "$LOG" | tail -5; exit 2; }
echo "прогон: $OUT ($TAG, $(shasum -a 256 "$D/EBOOT.PBP" | cut -c1-8))"
"$ROOT/.venv/bin/python" tests/crash_school/check.py "$OUT"
