#!/bin/bash
# Ночные боты (№876): безголовый PPSSPP без звука и окон на наборе текущего TEST. Две дорожки параллельно:
#   А: фото-исследователь L1–L7, затем гэги L1–L7;  Б: долгая игра (круг L1→L7 ×5).  Мак не засыпает, пока идут (caffeinate -i на время работы).
#   night_run.sh НАБОР_ТУРА NIGHT_DIR     (NIGHT_DIR/scen — сценарии tools/night/make_scenarios.py)
SET=$1; N=$2; I=$HOME/Downloads/shar-psp-integ
mkdir -p "$N/runs"; echo "старт $(date '+%H:%M') набор $SET EBOOT $(shasum -a 256 $SET/EBOOT.PBP | cut -c1-8)" > "$N/night.log"
run() { local scn=$1 lbl=$2 t=$3; local R=$N/rr_$lbl; rm -rf "$R" "$N/runs/$lbl"; mkdir -p "$N/runs/$lbl"; cp -c -R "$SET" "$R" || return
  rm -f "$R/smoke.txt"; cp "$N/scen/$scn" "$R/scenario.txt"; touch "$R/smokelog"
  python3 "$I/tools/smoke_headless.py" "$R" "$N/runs/$lbl" "$t" > /dev/null 2>&1; cp "$R/smoke.txt" "$R/blackbox.txt" "$N/runs/$lbl/" 2>/dev/null; rm -rf "$R"
  echo "$(date '+%H:%M') $lbl: END $(grep -a -c '^END$' "$N/runs/$lbl/smoke.txt" 2>/dev/null) снимков $(ls "$N/runs/$lbl"/*.png 2>/dev/null | wc -l | tr -d ' ')" >> "$N/night.log"; }
laneA() { for L in 1 2 3 4 5 6 7; do run explore_L$L.txt explore_L$L 1500; done; for L in 1 2 3 4 5 6 7; do run gags_L$L.txt gags_L$L 900; done; }
laneB() { run soak.txt soak 9000; }
laneA & A=$!; sleep 5; laneB & B=$!
caffeinate -i -w $A & caffeinate -i -w $B &
wait $A $B; echo "конец $(date '+%H:%M')" >> "$N/night.log"
python3 "$HOME/Downloads/shar-psp-render-w/tools/night/night_report.py" "$N" >> "$N/night.log" 2>&1
