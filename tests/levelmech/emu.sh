#!/bin/bash
# Механики уровней 2–7 в эмуляторе: короткая сцена на уровне N через общую очередь tools/ppsspp_run.sh (одно окно, короткий
# прогон), проверка tests/levelmech/emu_check.py: свободная куча на старте ≥ 20 МБ, ровные 30 FPS сцены, прогон до END.
#   tests/levelmech/emu.sh barriers N [--negative]   L2/L5: машина в 12 м от барьера лицом к нему (место — lvmech --barriers
#        на том же level.shr), снимок огней, газ 3 с — барьер ломается, снимок. --negative: level.shr без барьеров (основная
#        копия, как до 29.09) — проверка «барьер есть в SPR1 уровня» обязана упасть
#   tests/levelmech/emu.sh ufo 7 [--negative]        L7: машина в 45 м от локатора корабля лицом к нему, снимки; --negative —
#        пакет collect без летающих актёров (основная копия)
# EBOOT — viewer/build/EBOOT.PBP этой копии; набор уровня 1 — из основной копии build/ (только чтение, клон файлов).
set -u
MODE=${1:?barriers|ufo}; N=${2:?уровень}; NEG=0; [ "${3:-}" = --negative ] && NEG=1
. "$(dirname "$0")/common.sh"
STAMP=$(date +%Y%m%d-%H%M%S); RUN="$PWD/build/emu/levelmech/$STAMP-$$"; OUT="$PWD/build/gates/levelmech/emu_${MODE}_l${N}_$STAMP"
[ $NEG = 1 ] && OUT="${OUT}_neg"
mkdir -p "$RUN" "$OUT"; trap 'rm -rf "$RUN"' EXIT
cp viewer/build/EBOOT.PBP "$RUN/" || exit 2
while IFS='|' read -r f src; do   # набор уровня 1: где лежит в основной копии (tools/ship_files.sh --pairs)
  [ -f "$MAIN/$src" ] || { echo "нет $src (персонаж/ролик другого уровня) — без него" >&2; continue; }
  mkdir -p "$RUN/$(dirname "$f")"; cp -c "$MAIN/$src" "$RUN/$f" 2>/dev/null || cp "$MAIN/$src" "$RUN/$f" || exit 2
done < <(SHIP_LEVELS="" tools/ship_files.sh --pairs)
L=$MAIN/build/levels/l$N; SHR=$(LV $N level.shr); COLL=$(LV $N collect-l$N.shr)
if [ $NEG = 1 ]; then case $MODE in barriers) SHR=$L/level.shr ;; ufo|shield) COLL=$L/collect-l$N.shr ;; esac; fi
mkdir -p "$RUN/l$N"
cp -c "$SHR" "$RUN/l$N/level.shr"; for f in fx.shr ui.shr traffic.shr msnart.shr msncam.shr; do [ -f "$L/$f" ] && cp -c "$L/$f" "$RUN/l$N/$f"; done
cp -cR "$L/audio" "$RUN/l$N/"
for f in interiors-l$N.bin interiors-l$N-gfx.bin zonecam-l$N.shr; do cp -c "$L/$f" "$RUN/l$N/$f"; done   # набор уровня — папка l<N>/ (main.c levelFile)
cp -c "$COLL" "$RUN/l$N/collect-l$N.shr"; cp -c "$L/missions/level0$N.msn" "$RUN/l$N/level0$N.msn"
build_host
case $MODE in
  barriers)
    START=$(build/levelmech/lvmech "$(LV $N level.shr)" "$HOMER" --barriers 2>/dev/null | awk -F'\t' '/^H\t/ && /сломан/ {print $9; exit}')
    read -r _ SX SZ SH <<< "$START"
    [ -n "${SX:-}" ] || { echo "нет места подъезда к барьеру (lvmech --barriers)"; exit 2; }
    { echo "flag level $N"; printf 'scene spawn\nwait 3\nshot spawn\n'
      printf 'scene barrier\ngoto %s %s %s\nwait 2\nshot lights_a\nwait 0.4\nshot lights_b\nflag autostraight 3\nwait 3.5\nflag stop\nshot after\nwait 1\nend\n' "$SX" "$SZ" "$SH"; } > "$RUN/scenario.txt" ;;
  ufo)
    P=$($PY - "$N" <<'EOF'
import sys, math
sys.path.insert(0, 'tests/levelmech'); import flying_check as F
w = [a for a in F.disk_actors(int(sys.argv[1])) if a['pos']][0]
x, y, z = w['pos']; h = float(__import__("os").environ.get("UFO_H", "0")); d = float(__import__("os").environ.get("UFO_D", "45"))
print(f'{x - math.sin(h) * d:.2f} {z - math.cos(h) * d:.2f} {h:.4f}')
EOF
)
    read -r SX SZ SH <<< "$P"
    { echo "flag level $N"; printf 'scene spawn\nwait 3\nshot spawn\n'
      printf 'scene ufo\ngoto %s %s %s\nwait 3\nshot ufo_a\nwait 2\nshot ufo_b\nend\n' "$SX" "$SZ" "$SH"; } > "$RUN/scenario.txt" ;;
  shield)   # машина в 6 м к югу от осы со щитом (запись CLT1 пакета прогона), лицом к ней: оса появляется со щитом
    P=$($PY tests/levelmech/wasp_pos.py "$RUN/l$N/collect-l$N.shr" "${WASP:-w_hospital}")
    read -r SX SZ SH <<< "$P"
    [ -n "${SX:-}" ] || { echo "в пакете прогона нет ос со щитом"; SX=0; SZ=0; SH=0; }
    { echo "flag level $N"; printf 'scene spawn\nwait 3\nshot spawn\n'
      printf 'scene shield\ngoto %s %s %s\nwait 3\nshot shield_a\nwait 2\nshot shield_b\nend\n' "$SX" "$SZ" "$SH"; } > "$RUN/scenario.txt" ;;
esac
touch "$RUN/smokelog"
MAXT=$(awk '$1=="wait"{s+=$2} $1=="shot"{s+=1} END{print int(s)+90}' "$RUN/scenario.txt")
PPSSPP_SHOTS="$RUN/smoke.txt" PPSSPP_SHOTDIR="$OUT" tools/ppsspp_run.sh "$RUN/EBOOT.PBP" "$MAXT" > "$OUT/ppsspp.txt" 2>&1
cp "$RUN/smoke.txt" "$RUN/scenario.txt" "$OUT/" 2>/dev/null
echo "прогон: $OUT"
ARGS="--level $N --mode $MODE --shr $RUN/l$N/level.shr --collect $RUN/l$N/collect-l$N.shr"
$PY tests/levelmech/emu_check.py "$OUT/smoke.txt" $ARGS
