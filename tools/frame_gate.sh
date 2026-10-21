#!/bin/bash
# Гейт «КАДР ИГРОКА» (слово Роба 16.10: «поставь себе проверку»): безголовый путь игрока на сохранении Роба и проверка, что кадр ВИДЕН, а не только сосчитан.
#   tools/frame_gate.sh EBOOT.PBP НАБОР [ВЫХОД]
#   EBOOT — тур-конфигурация сборки (SHAR_RELEASE + KEEP_DIAG + KEEP_SMOKE: сценарий и журнал смоука); НАБОР — папка с данными (как build/test23_emu: level.shr, l2…l7, звук, интерфейс)
# Путь 1 (tools/frame_gate_scenario.txt): RESUME (сохранение Роба в ~/.ppsspp/PSP/SAVEDATA, flag nosave — тур ничего не пишет) → гараж у АЭС → посадка (flag repair) →
# езда по улице у дома с прохожими и трафиком. Путь 2 (tools/frame_gate_new.txt): NEW GAME, 35 с игры. Проверки и пороги — tools/frame_gate.py.
# Итог — одна строка «КАДР ИГРОКА: PASS|FAIL …» и лист кадров ВЫХОД/frame_gate_sheet.png; код выхода 0 только при PASS. Эмулятор только безголовый, без звука.
# GATE_EXPECT_FAIL="а,б" — отрицательный контроль: строка PASS, если упали именно эти проверки (EBOOT TEST25 f0551e4b обязан упасть по а и б).
set -u
cd "$(dirname "$0")/.."; ROOT=$PWD
EB=${1:?EBOOT.PBP}; PK=${2:?НАБОР (папка данных)}; OUT=${3:-$ROOT/build/frame_gate/$(date +%H%M%S)}
[ -f "$EB" ] || { echo "КАДР ИГРОКА: FAIL нет EBOOT $EB"; exit 2; }; [ -d "$PK" ] || { echo "КАДР ИГРОКА: FAIL нет набора $PK"; exit 2; }
mkdir -p "$OUT" "$ROOT/build"; TMP="$ROOT/build/gate_pkg_$$"
cleanup() { [ -n "${TMP:-}" ] && [ -d "$TMP" ] && rm -rf "${TMP:?}"; }; trap cleanup EXIT
cp -cR "$PK" "$TMP" 2>/dev/null || cp -R "$PK" "$TMP"; cp "$EB" "$TMP/EBOOT.PBP"
SAV="$HOME/.ppsspp/PSP/SAVEDATA"; [ -d "$SAV" ] && find "$SAV" -type f -exec shasum {} \; | sort > "$OUT/savedata_before.sha"
run() {   # run ИМЯ СЦЕНАРИЙ МАКС_С
  ( SHIP_LEVELS="2 3 4 5 6 7" SMOKE_HEADLESS=1 SMOKE_FILEDATA="meaudio=3" SMOKE_SCN="$2" SMOKE_MAXT=$3 nice -n 20 tools/smoke.sh "$TMP" ) > "$OUT/$1.out" 2>&1
  D="$ROOT/build/smoke/$(ls -t "$ROOT/build/smoke" | head -1)"; cp -R "$D" "$OUT/$1"
}
run resume "$ROOT/tools/frame_gate_scenario.txt" 220
run new "$ROOT/tools/frame_gate_new.txt" 160
[ -d "$SAV" ] && find "$SAV" -type f -exec shasum {} \; | sort > "$OUT/savedata_after.sha"
python3 "$ROOT/tools/frame_gate.py" "$OUT" ${GATE_EXPECT_FAIL:+--expect-fail "$GATE_EXPECT_FAIL"}
