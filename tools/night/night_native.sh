#!/bin/bash
# Нативные боты Мака в ночном цикле (Роб 24.10: «всех ботов»): missioner (миссии настоящим вождением), chase (догонялки), explorer (каскадёр/пешеход), nav — CPU Мака, без эмулятора и окон.
# Каждый круг: боты собираются из ТЕКУЩЕГО кода render-w (физика порта сейчас), входы — из набора BOT_SET (уровень, Гомер, машины, миссии: данные EBOOT-а), не из render-w/build (там L1 от 17.10).
# Дороги/цели/маршруты L1 (sandbox/*, bots/targets-l1.tsv) — от графа дорог в shar-psp/build (геометрия L1 в 24.10 не менялась). Уровни 2–7 нативные боты не умеют (L1-only: roads-l1) — честно «не покрыто».
#   night_native.sh НАБОР_ТУРА NIGHT_DIR UNTIL_EPOCH [ПРОЦЕССОВ=2]       итоги — NIGHT_DIR/native/kN/, находки — NIGHT_DIR/native/findings.tsv (формат autoexplore: level x y z type weight seed frame description)
SET=$1; N=$2; END=$3; P=${4:-2}; W=$HOME/Downloads/shar-psp-render-w; PRE=$HOME/Downloads/shar-psp/build
NB=$N/native; IN=$NB/in; BIN=$NB/bin; mkdir -p "$NB" "$IN/sandbox" "$IN/bots" "$IN/missions" "$IN/audio" "$BIN"
log() { echo "$(date '+%H:%M') native: $*" >> "$N/night.log"; }
for f in level.shr homer.shr interiors-l1.bin collect-l1.shr traffic.shr msncars-l1.shr; do cp -c "$SET/$f" "$IN/$f" 2>/dev/null || log "нет $f в наборе"; done
cp -c "$SET/level01.msn" "$IN/missions/" 2>/dev/null || log "нет level01.msn в наборе"; cp -c "$SET/audio/sfx.sab" "$SET/audio/music.sap" "$IN/audio/" 2>/dev/null
for f in sandbox/roads-l1.bin sandbox/roads-l1.meta.tsv sandbox/routes-l1.tsv sandbox/routes-l1.json sandbox/colnames-l1.json bots/targets-l1.tsv; do cp -c "$PRE/$f" "$IN/$f" 2>/dev/null; done
# сборка из текущего кода: в свою папку, дерево render-w не пишется
( cd "$W" && OUT_DIR="$BIN" BINS="missioner chase explorer nav game_headless probe" bash tools/bots/build.sh > "$NB/build.log" 2>&1 ) || { log "сборка ботов НЕ удалась ($NB/build.log)"; exit 1; }
log "собрано из $(git -C $W rev-parse --short HEAD), входы: level.shr $(shasum -a 256 $IN/level.shr | cut -c1-8)"
export BOTS_ROOT=$W BOTS_IN=$IN BOTS_BIN=$BIN BOTS_NO_BUILD=1
k=1
while [ "$(date +%s)" -lt "$END" ]; do
  O=$NB/k$k; mkdir -p "$O"
  python3 "$W/tools/bots/missions.py" --secs 1200 --procs $P --out "$O/missions" > "$O/missions.log" 2>&1; log "круг $k миссии: $(grep -c '| пройдена' $O/missions/missions.md 2>/dev/null) пройдено из 13"
  [ "$(date +%s)" -ge "$END" ] && break
  python3 "$W/tools/bots/chase.py" --procs $P --gens 40 --pop 24 --rounds 4 --seed $k --out "$O/chase" > "$O/chase.log" 2>&1; log "круг $k догонялки: $(sed -n 3p $O/chase/chase.md 2>/dev/null | cut -c1-80)"
  [ "$(date +%s)" -ge "$END" ] && break
  python3 "$W/tools/bots/explorer.py" --procs $P --secs 600 --seed $k --out "$O/explore" > "$O/explore.log" 2>&1; log "круг $k каскадёр: $(sed -n 3p $O/explore/explore.md 2>/dev/null | cut -c1-80)"
  [ "$(date +%s)" -ge "$END" ] && break
  python3 "$W/tools/bots/nav.py" --routes 32 --procs $P --seed $k --out "$O/nav" > "$O/nav.log" 2>&1; log "круг $k навигатор: $(sed -n 3p $O/nav/nav.md 2>/dev/null | cut -c1-80)"
  python3 "$W/tools/night/native_findings.py" "$O" $k >> "$NB/findings.tsv" 2>> "$NB/findings.err"
  k=$((k + 1))
done
log "конец, кругов $((k - 1))"
