#!/bin/bash
# Гейт правок Роба 153–155 в эмуляторе: сценарий tests/boot_flow/scenario.txt через tools/smoke.sh (общая очередь
# tools/ppsspp_run.sh), разбор tests/boot_flow/check.py. Сначала КРАСНЫЙ — тот же сценарий с «flag noiris», «flag demotv»,
# «flag musold» (без ириса, демо в рамке, звук уровня без удержания): обязан провалить demo_tv, iris_in, iris_exit, music;
# потом ЗЕЛЁНЫЙ. DIR — EBOOT.PBP и данные (boot.shr, iris.shr, movies/demo.smv, movies/fmv1a.smv; по умолчанию build/).
#   tests/boot_flow/emu.sh [--green-only] [DIR]     первая строка итог, код 0 = OK
set -u; cd "$(dirname "$0")/../.."
GO=0; [ "${1:-}" = --green-only ] && { GO=1; shift; }
SRC="${1:-build}"; PY=.venv/bin/python; LOG=$(mktemp -d)
run() {   # $1 сценарий -> папка прогона
  SMOKE_SCN="$1" tools/smoke.sh "$SRC" > "$LOG/smoke.txt" 2>&1
  REP=$(sed -n 's/^отчёт: \(.*\)\/summary\.txt.*/\1/p' "$LOG/smoke.txt")
  [ -n "$REP" ] || { echo "нет отчёта smoke: $(head -1 "$LOG/smoke.txt")" >&2; return 2; }
  echo "$REP"
}
if [ $GO = 0 ]; then
  awk '{print} /^flag newgamefmv$/{print "flag noiris"; print "flag demotv"; print "flag musold"}' tests/boot_flow/scenario.txt > "$LOG/planted.txt"
  R=$(run "$LOG/planted.txt") || exit 1; echo "красный прогон: $R"
  $PY tests/boot_flow/check.py "$R" --expect-fail demo_tv,iris_in,iris_exit,music || { echo "boot_flow: красный НЕ красный — проверка слепая"; exit 1; }
fi
R=$(run tests/boot_flow/scenario.txt) || exit 1
$PY tests/boot_flow/check.py "$R"; rc=$?
echo "прогон: $R"; exit $rc
