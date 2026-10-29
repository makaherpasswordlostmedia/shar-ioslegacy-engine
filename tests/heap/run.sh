#!/bin/bash
# Честный счётчик свободной памяти (пункт 12б): один EBOOT дважды в эмуляторе — без балласта и с файлом «ballast» (10 МБ
# рядом с EBOOT: движок занимает и заполняет их до замера). Счётчик «heap free at start» обязан упасть на 10 ± 0,5 МБ.
#   tests/heap/run.sh [EBOOT] [DATA_DIR]      по умолчанию viewer/build/EBOOT.PBP и данные из build/
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
EB="${1:-$ROOT/viewer/build/EBOOT.PBP}"; SRC="${2:-$ROOT/build}"
one() {   # $1 = МБ балласта (0 — без файла) -> печатает «свободно МБ»
  local RUN="$ROOT/build/emu/heap/$(date +%Y%m%d-%H%M%S)-$$-$1"; mkdir -p "$RUN"
  cp "$EB" "$RUN/EBOOT.PBP"
  for f in $("$ROOT/tools/ship_files.sh"); do case "$f" in l[0-9]/*|movies/fmv*) continue ;; esac; mkdir -p "$RUN/$(dirname "$f")"; cp -c "$SRC/$f" "$RUN/$f" 2>/dev/null || cp "$SRC/$f" "$RUN/$f"; done
  printf 'scene spawn\nwait 2\nend\n' > "$RUN/scenario.txt"; touch "$RUN/smokelog"
  [ "$1" != 0 ] && echo "$1" > "$RUN/ballast"
  PPSSPP_SHOTS="$RUN/smoke.txt" PPSSPP_SHOTDIR="$RUN" "$ROOT/tools/ppsspp_run.sh" "$RUN/EBOOT.PBP" 120 >/dev/null 2>&1
  sed -n 's/^# heap free at start \([0-9.]*\) MB.*/\1/p' "$RUN/smoke.txt" 2>/dev/null | head -1
  [ -n "${KEEP:-}" ] || rm -rf "$RUN"
}
A=$(one 0); B=$(one 10)
[ -n "$A" ] && [ -n "$B" ] || { echo "FAIL: нет замера (без балласта «$A», с балластом «$B»)"; exit 1; }
python3 - "$A" "$B" <<'PY'
import sys
a, b = map(float, sys.argv[1:3]); d = a - b
print(f'свободно без балласта {a:.2f} МБ, с балластом 10 МБ {b:.2f} МБ, разница {d:.2f} МБ -> ' + ('PASS' if abs(d - 10) <= .5 else 'FAIL'))
sys.exit(0 if abs(d - 10) <= .5 else 1)
PY
