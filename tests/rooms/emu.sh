#!/bin/bash
# Комнаты уровня 1 в эмуляторе (пункт 11.2): сценарий tests/rooms/emu_scenario.txt через tools/smoke.sh (очередь
# tools/ppsspp_run.sh), разбор — tests/rooms/emu_check.py.
#   tests/rooms/emu.sh [DIR]              зелёный: три комнаты нарисованы (снимки внутри, в кадре не город), Kwik-E-Mart
#                                         5 кругов вход/выход, куча после выхода = до входа (±64 КБ), FPS в комнатах не ниже 30
#   tests/rooms/emu.sh --cams [DIR]       камеры комнат: снимок из каждой из 17 камер (tests/rooms/emu_cams.txt), движок снимал
#                                         ровно той камерой, в чьём триггере Гомер (разбор данных — tests/rooms/cams.sh)
#   tests/rooms/emu.sh --negative [DIR]   красный: копия набора с пустым пакетом рисования и с битым блобом Kwik-E-Mart —
#                                         зелёная проверка обязана упасть, игра при этом цела, Гомер остаётся на улице
# DIR — EBOOT.PBP и данные (по умолчанию build/), как у tools/smoke.sh. Исходный набор не меняется.
set -u; cd "$(dirname "$0")/../.."
NEG=0; [ "${1:-}" = --negative ] && { NEG=1; shift; }
CAMS=0; [ "${1:-}" = --cams ] && { CAMS=1; shift; }
SRC="${1:-build}"; PY=.venv/bin/python; LOG=$(mktemp -d)
run() {   # $1 набор [$2 сценарий] -> отчёт tools/smoke.sh в $REP, код в $RC
  SMOKE_SCN=${2:-tests/rooms/emu_scenario.txt} tools/smoke.sh "$1" > "$LOG/smoke.txt" 2>&1; RC=$?
  REP=$(sed -n 's/^отчёт: \(.*\)\/summary\.txt.*/\1/p' "$LOG/smoke.txt")
  [ -n "$REP" ] || { echo "нет отчёта smoke: $(head -1 "$LOG/smoke.txt")"; exit 1; }
}
if [ $CAMS = 1 ]; then run "$SRC" tests/rooms/emu_cams.txt; $PY tests/rooms/emu_check.py "$REP" --cams; exit $?; fi   # FPS коротких сцен не в счёт
if [ $NEG = 0 ]; then run "$SRC"; $PY tests/rooms/emu_check.py "$REP" --smoke-rc $RC; exit $?; fi
fail=0
for kind in empty garbled; do
  N=build/rooms_neg_$kind; rm -rf "$N"; mkdir -p "$N"
  for f in EBOOT.PBP $(tools/ship_files.sh); do mkdir -p "$N/$(dirname "$f")"; cp -c "$SRC/$f" "$N/$f" 2>/dev/null || cp "$SRC/$f" "$N/$f" || exit 1; done
  $PY tests/rooms/emu_check.py --break $kind "$N/interiors-l1-gfx.bin" || exit 1
  run "$N"; $PY tests/rooms/emu_check.py "$REP" --smoke-rc $RC --expect-broken $kind || fail=1
  rm -rf "$N"
done
[ $fail = 0 ] && echo "PASS (красные прогоны пойманы)" || { echo "FAIL (красный прогон не пойман)"; exit 1; }
