#!/bin/bash
# Машины миссий с ИИ в эмуляторе (29.09): две короткие сцены уровня 1 одним запуском PPSSPP через общую очередь
# tools/ppsspp_run.sh (одно окно, короткий прогон, Роб видит окно):
#   race  — sr2 «Circuit Race» с чекпоинта основной части: три соперника (honor_v из пакета msncars-l1.shr, minivanA и schoolbu —
#           модели трафика), отсчёт, гонка; место в гонке (строки MCAR pos=…);
#   chase — m6 «Bonestorm Storm»: машина Мардж у игрока (SetForcedCar, модель пакета), фургон cBone уезжает по дорогам.
#   tests/aicar/emu.sh [DIR]              DIR — EBOOT.PBP и данные уровня 1 (по умолчанию build/ship_stage)
#   tests/aicar/emu.sh --negative [DIR]   красный: пакет машин миссий подменён обрезанным файлом (планка плохих данных) — модели
#                                         не читаются, проверка обязана упасть
# Проверка tests/aicar/emu_check.py: соперники едут (каждый ≥ 30 м), фургон едет, машина Мардж у игрока и её модель прочитана,
# место в гонке считается, ровные 30 FPS в сценах; куча: на старте уровня ≥ 20 МБ, модели машин миссий в памяти ≤ 0.5 МБ,
# в сценах race/chase — не ниже 17.5 МБ (миссия уже на старте берёт своё: персонажи, картинки, 19.7 МБ до машин).
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
NEG=0; [ "${1:-}" = --negative ] && { NEG=1; shift; }
SRC="${1:-build/ship_stage}"; case "$SRC" in /*) ;; *) SRC="$ROOT/$SRC" ;; esac
STAMP=$(date +%Y%m%d-%H%M%S); RUN="$ROOT/build/emu/aicar/$STAMP-$$"; OUT="$ROOT/build/gates/aicar/emu_$STAMP$([ $NEG = 1 ] && echo _neg)"
mkdir -p "$RUN" "$OUT"; trap 'rm -rf "$RUN"' EXIT
cp -c "$SRC/EBOOT.PBP" "$RUN/" 2>/dev/null || cp "$SRC/EBOOT.PBP" "$RUN/"
for f in $(SHIP_LEVELS="" tools/ship_files.sh); do
  [ -f "$SRC/$f" ] || { echo "нет $SRC/$f"; exit 1; }
  mkdir -p "$RUN/$(dirname "$f")"; cp -c "$SRC/$f" "$RUN/$f" 2>/dev/null || cp "$SRC/$f" "$RUN/$f"
done
if [ $NEG = 1 ]; then head -c 4096 "$SRC/msncars-l1.shr" > "$RUN/msncars-l1.shr"; echo "подложено: msncars-l1.shr обрезан до 4 КБ"; fi
cat > "$RUN/scenario.txt" <<'EOF'
scene spawn
wait 3
scene start
flag msn
wait 3
scene race
flag msnmain 9
wait 3
press cross
wait 6
shot race_start
wait 8
shot race_mid
wait 6
scene chase
flag msnmain 6
wait 3
press cross
wait 7
shot chase_start
wait 8
shot chase_mid
wait 4
end
EOF
touch "$RUN/smokelog"
MAXT=$(awk '$1=="wait"{s+=$2} $1=="shot"{s+=1} END{print int(s)+90}' "$RUN/scenario.txt")
PPSSPP_SHOTS="$RUN/smoke.txt" PPSSPP_SHOTDIR="$OUT" tools/ppsspp_run.sh "$RUN/EBOOT.PBP" "$MAXT" > "$OUT/ppsspp.txt" 2>&1
cp "$RUN/smoke.txt" "$RUN/scenario.txt" "$OUT/" 2>/dev/null
echo "прогон: ${OUT#$ROOT/}"
.venv/bin/python tests/aicar/emu_check.py "$OUT/smoke.txt"; R=$?
if [ $NEG = 1 ]; then
  if [ $R != 0 ]; then echo "PASS (отрицательный контроль: проверка упала, как должна)"; exit 0; fi
  echo "FAIL (отрицательный контроль прошёл — проверка ничего не ловит)"; exit 1
fi
exit $R
