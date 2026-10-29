#!/bin/bash
# Гейт «сохранение несёт уровень» в эмуляторе (утилита сохранений PPSSPP): запись в уровне 2 -> новый запуск -> LOAD GAME -> уровень 2,
# ещё запуск -> RESUME GAME (самое свежее сохранение) -> уровень 2.
# Сначала КРАСНЫЙ: прогон загрузки с «flag lvnosave» (загрузка берёт уровень 1, а не уровень записи — прежнее поведение порта)
# обязан провалить сверку; потом ЗЕЛЁНЫЙ. Сверка — tests/levels/save_level_check.py.
#   tests/levels/save_level.sh [DIR]   DIR — EBOOT + данные (по умолчанию build/ship_stage); первая строка итог, код 0 = OK
# Сохранения эмулятора: ~/.config/ppsspp/PSP/SAVEDATA (SV_SAVEDATA=... — другой путь). Папки SLES51897NN не удаляются:
# до прогона прежние уходят в build/savegame/archive/<время>/before, после — записи гейта в .../after, прежние возвращаются
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
SRC="${1:-$ROOT/build/ship_stage}"; case "$SRC" in /*) ;; *) SRC="$PWD/$SRC" ;; esac
SD="${SV_SAVEDATA:-$HOME/.config/ppsspp/PSP/SAVEDATA}"
[ -d "$SD" ] || { echo "FAIL: нет папки сохранений эмулятора $SD"; exit 1; }
[ -f "$SRC/EBOOT.PBP" ] && [ -f "$SRC/l2/level.shr" ] && [ -f "$SRC/psave.shr" ] && [ -f "$SRC/fsave.shr" ] || {
  echo "FAIL: в $SRC нет EBOOT.PBP / l2/level.shr / psave.shr / fsave.shr (tools/ship.sh --no-install)"; exit 1; }
A="$ROOT/build/savegame/archive/$(date +%Y%m%d-%H%M%S)-$$"; mkdir -p "$A/before" "$A/after_red" "$A/after"
park() { for d in "$SD"/SLES51897[0-9][0-9]; do [ -d "$d" ] && mv "$d" "$1/"; done; }
park "$A/before"
run() {
  local log; log=$(SMOKE_SCN="$1" "$ROOT/tools/smoke.sh" "$SRC" 2>&1)
  echo "$ROOT/$(echo "$log" | sed -n 's/^отчёт: \(.*\)\/summary.txt.*/\1/p' | tail -1)"
}
PY="$ROOT/.venv/bin/python"; res=""; ok=1
# красный: запись та же, загрузка — «без уровня записи»
NS="$A/load_nosave.txt"; awk '{print} /^flag saves$/{print "flag lvnosave"}' tests/levels/save_level_load.txt > "$NS"
R1=$(run tests/levels/save_level_save.txt); R2=$(run "$NS")
"$PY" tests/levels/save_level_check.py "$R1" "$R2" > "$A/red.txt" 2>&1
if [ $? = 0 ]; then ok=0; res="$res; КРАСНЫЙ НЕ ПОЙМАН: загрузка без уровня записи"; else res="$res; красный (загрузка без уровня записи): $(grep -m1 'ПРОВАЛ' "$A/red.txt" | sed 's/^ *ПРОВАЛ: //' | cut -c1-110)"; fi
park "$A/after_red"
# зелёный
G1=$(run tests/levels/save_level_save.txt); G2=$(run tests/levels/save_level_load.txt); G3=$(run tests/levels/save_level_resume.txt)
"$PY" tests/levels/save_level_check.py "$G1" "$G2" "$G3" > "$A/green.txt" 2>&1
if [ $? = 0 ]; then res="$res; зелёный: PASS"; else ok=0; res="$res; НЕ ЗЕЛЁНЫЙ: $(grep -m1 'ПРОВАЛ' "$A/green.txt" | sed 's/^ *ПРОВАЛ: //' | cut -c1-140)"; fi
park "$A/after"
for d in "$A/before"/SLES51897[0-9][0-9]; do [ -d "$d" ] && mv "$d" "$SD/"; done   # прежние сохранения эмулятора — на место
echo "$([ $ok = 1 ] && echo PASS || echo FAIL)${res}"
echo "прогоны: красный ${R1#$ROOT/} ${R2#$ROOT/}; зелёный ${G1#$ROOT/} ${G2#$ROOT/} ${G3#$ROOT/}; сохранения гейта — ${A#$ROOT/}"
cat "$A/green.txt"
[ $ok = 1 ]
