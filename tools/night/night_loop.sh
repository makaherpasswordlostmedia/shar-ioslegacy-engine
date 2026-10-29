#!/bin/bash
# Ночной ЦИКЛ ботов (Роб 24.10: «до утра, а не на один час»): круг за кругом night_run.sh (исследователь L1–L7 + гэги, долгая игра) до времени UNTIL,
# каждый круг — новые точки (make_scenarios --seed круга), набор тура последнего собранного TEST. Отчёт каждого круга — NIGHT_DIR/rN/report.html.
#   night_loop.sh [UNTIL=08:00] [NIGHT_DIR]
UNTIL=${1:-08:00}; N=${2:-$HOME/Downloads/shar-psp/build/night/loop-$(date +%Y-%m-%d_%H%M)}; W=$HOME/Downloads/shar-psp-render-w; I=$HOME/Downloads/shar-psp-integ
end=$(date -j -f "%H:%M" "$UNTIL" +%s); [ "$end" -le "$(date +%s)" ] && end=$(date -j -v+1d -f "%H:%M" "$UNTIL" +%s)   # +1 день календарём (переход на зимнее время)
mkdir -p "$N"; echo "цикл старт $(date '+%d.%m %H:%M') до $(date -r $end '+%d.%m %H:%M')" >> "$N/loop.log"
caffeinate -i -w $$ &
# нативные боты Мака (missioner, chase, explorer, nav; Роб 24.10): отдельная дорожка на весь цикл до UNTIL, без эмулятора; NATIVE_PROCS — процессов на дорожку (по умолчанию 2)
T0=$(ls -d $I/build/test*tour 2>/dev/null | sed 's/.*test\([0-9]*\)tour/\1/' | sort -n | tail -1); SET0=$I/build/test${T0}tour/PSP/GAME/SHARTEST15; [ -n "$BOT_SET" ] && SET0=$BOT_SET
[ -z "$NO_NATIVE" ] && { bash "$W/tools/night/night_native.sh" "$SET0" "$N" "$end" "${NATIVE_PROCS:-2}" > /dev/null 2>&1 & }
r=1
while [ "$(date +%s)" -lt "$end" ]; do
  T=$(ls -d $I/build/test*tour 2>/dev/null | sed 's/.*test\([0-9]*\)tour/\1/' | sort -n | tail -1)
  SET=$I/build/test${T}tour/PSP/GAME/SHARTEST15; [ -n "$BOT_SET" ] && SET=$BOT_SET   # BOT_SET: набор с EBOOT свежего кода (render-perf)
  R=$N/r$r; mkdir -p "$R"; python3 "$W/tools/night/make_scenarios.py" "$R/scen" --seed $r > /dev/null
  echo "$(date '+%H:%M') круг $r TEST$T EBOOT $(shasum -a 256 $SET/EBOOT.PBP | cut -c1-8)" >> "$N/loop.log"
  bash "$W/tools/night/night_run.sh" "$SET" "$R"
  echo "$(date '+%H:%M') круг $r конец: $(tail -1 $R/night.log)" >> "$N/loop.log"; r=$((r + 1))
done
echo "цикл конец $(date '+%d.%m %H:%M'), кругов $((r - 1))" >> "$N/loop.log"
