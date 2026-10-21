#!/bin/bash
# Гейт сохранений в эмуляторе PPSSPP (утилита сохранений эмулируется): четыре запуска игры подряд через tools/smoke.sh.
#   1 новая игра -> отметка прогресса -> пауза -> SAVE GAME -> слот 1 -> QUIT GAME (вопрос о записи) — эмулятор закрывается
#   2 новый запуск -> LOAD GAME -> слот 1 -> прогресс тот же (tests/savegame/emu_check.py)
#   3 новый запуск -> RESUME GAME (самое свежее сохранение, прочитанное при запуске) -> тот же прогресс
#   4 DATA.BIN слота 1 испорчен -> игра не падает, сообщает, удаляет запись, NEW GAME с нуля
#   tests/savegame/emu.sh [DIR]              DIR — EBOOT + данные (по умолчанию build/ship_stage); первая строка итог, код 0 = OK
#   tests/savegame/emu.sh --negative [DIR]   красный: «сборка без записи» (flag svnowrite в прогоне 1) — сверка обязана упасть
# Сохранения эмулятора: ~/.config/ppsspp/PSP/SAVEDATA (SV_SAVEDATA=... — другой путь); трогаются только папки SLES51897NN
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
NEG=0; [ "${1:-}" = --negative ] && { NEG=1; shift; }
SRC="${1:-$ROOT/build/ship_stage}"; case "$SRC" in /*) ;; *) SRC="$PWD/$SRC" ;; esac
SD="${SV_SAVEDATA:-$HOME/.config/ppsspp/PSP/SAVEDATA}"
[ -d "$SD" ] || { echo "FAIL: нет папки сохранений эмулятора $SD"; exit 1; }
[ -f "$SRC/EBOOT.PBP" ] && [ -f "$SRC/psave.shr" ] && [ -f "$SRC/fsave.shr" ] || { echo "FAIL: в $SRC нет EBOOT.PBP / psave.shr / fsave.shr (tools/ship.sh)"; exit 1; }
clean() { rm -rf "$SD"/SLES51897[0-9][0-9]; }
T="$ROOT/build/savegame"; mkdir -p "$T"
run() {   # сценарий -> папка прогона smoke.sh (печатает путь)
  local log; log=$(SMOKE_SCN="$1" "$ROOT/tools/smoke.sh" "$SRC" 2>&1)
  echo "$ROOT/$(echo "$log" | sed -n 's/^отчёт: \(.*\)\/summary.txt.*/\1/p' | tail -1)"
}
clean
S1="$T/scn_save.txt"; cp tests/savegame/emu_save.txt "$S1"
if [ $NEG = 1 ]; then   # «сборка без записи»: запись в прогоне 1 не выполняется
  awk '{print} /^flag svmark$/{print "flag svnowrite"}' tests/savegame/emu_save.txt > "$S1"
fi
D1=$(run "$S1"); L1=$(ls "$SD/SLES5189700" 2>/dev/null | tr '\n' ' ')
D2=$(run tests/savegame/emu_load.txt)
if [ $NEG = 1 ]; then
  R=$(python3 tests/savegame/emu_check.py "$D1" "$D2"); RC=$?; clean
  if [ $RC != 0 ]; then echo "PASS (отрицательный контроль: без записи прогресс слетел, сверка упала) — $R"; echo "прогоны: ${D1#$ROOT/} ${D2#$ROOT/}"; exit 0; fi
  echo "FAIL (отрицательный контроль прошёл сверку) — $R"; exit 1
fi
D3=$(run tests/savegame/emu_resume.txt)
F=$(ls -d "$SD"/SLES5189700 2>/dev/null)
if [ -n "$F" ] && [ -f "$F/DATA.BIN" ]; then   # порча: байты в середине файла
  cp "$F/DATA.BIN" "$T/DATA.BIN.good"; python3 - "$F/DATA.BIN" <<'EOF'
import sys
p = sys.argv[1]; b = bytearray(open(p, 'rb').read()); n = len(b)
for i in range(n // 3, n // 3 + 24): b[i] ^= 0x5a
open(p, 'wb').write(bytes(b))
EOF
fi
D4=$(run tests/savegame/emu_corrupt.txt)
GONE=1; [ -f "$SD/SLES5189700/DATA.BIN" ] && GONE=0
R=$(python3 tests/savegame/emu_check.py "$D1" "$D2" "$D3" "$D4"); RC=$?
[ -n "$F" ] || { R="FAIL: после прогона 1 нет папки SLES5189700 в $SD; $R"; RC=1; }
[ $GONE = 1 ] || { R="$R; испорченная запись осталась на карте"; RC=1; }
echo "$R"; echo "карта после прогона 1: SLES5189700/ $L1; после прогона 4 запись удалена: $GONE"
echo "прогоны: ${D1#$ROOT/} ${D2#$ROOT/} ${D3#$ROOT/} ${D4#$ROOT/}"
clean; exit $RC
