#!/bin/bash
# Свет уровня в эмуляторе (29.09, рецепт §12): один короткий прогон PPSSPP через общую очередь tools/ppsspp_run.sh.
#   tests/light/emu.sh N [--pre] [DIR]    DIR — EBOOT.PBP и данные уровня 1 (по умолчанию build/ship_stage)
#     --pre   «подложенный день»: тот же level.shr уровня N, но куски машины — в дневной светотени уровня 1 (из
#             build/levels/l<N>/level_pre_light.shr, tests/light/plant_day.py), CAR1 v2 (без LGT1: персонажам свет уровня 1),
#             трафик до света уровня — база сравнения той же машины и красный контроль
# Сцены: spawn — старт уровня (снимок, куча); car — машина в точке сравнения (у карты Evergreen 1/4/7 — телепорт «Simpsons'
# House», у Squidport 3/6 — «Krustylu Studios»), снимок и снимок-ключ (flag lumakey: машина и Гомер сплошным цветом —
# маска для замера яркости); exit — △, Гомер пешком: снимок и снимок-ключ; drive — △ за руль, 3 с газа (30 FPS).
# Итог: build/gates/light/emu_l<N>[_pre]_<время>/ — снимки, smoke.txt, measure.json (tests/light/emu_check.py --measure).
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
PRE=0; [ "${2:-}" = --pre ] && { PRE=1; set -- "$1" "${@:3}"; }
N="${1:?уровень}"; SRC="${2:-build/ship_stage}"; case "$SRC" in /*) ;; *) SRC="$ROOT/$SRC" ;; esac
L=build/levels/l$N
# точка сравнения — телепорт уровня, где запечённый мир дня и ночи темнеет как весь уровень в среднем (яркость цвета вершин
# города в 15 м: Simpsons' House L4/L1 0.64 при 0.67 по уровню, L7/L1 0.56 при 0.57; Krustylu Studios L6/L3 1.03 при 1.00;
# у старта L6 земля студии на L3 почти чёрная — 1.23, не годится)
case "$N" in 1|4|7) PLACE="220 172 1.5708" ;; 3|6) PLACE="-325.4 -237.6 4.644" ;; *) PLACE="" ;; esac
TAG=l$N; [ $PRE = 1 ] && TAG=${TAG}_pre
STAMP=$(date +%Y%m%d-%H%M%S); RUN="$ROOT/build/emu/light/$STAMP-$$"; OUT="$ROOT/build/gates/light/emu_${TAG}_$STAMP"; mkdir -p "$RUN" "$OUT"
trap 'rm -rf "$RUN"' EXIT
cp -c "$SRC/EBOOT.PBP" "$RUN/" 2>/dev/null || cp "$SRC/EBOOT.PBP" "$RUN/"
for f in $(tools/ship_files.sh); do case "$f" in l[0-9]/*|movies/fmv*) continue ;; esac
  [ -f "$SRC/$f" ] || { echo "нет $SRC/$f"; exit 1; }; mkdir -p "$RUN/$(dirname "$f")"; cp -c "$SRC/$f" "$RUN/$f" 2>/dev/null || cp "$SRC/$f" "$RUN/$f"; done
SHR="$L/level.shr"; TRF="$L/traffic.shr"
if [ $PRE = 1 ]; then   # тот же level.shr, машина — в дневной светотени, CAR1 v2 (tests/light/plant_day.py); трафик — до света уровня
  SHR="$RUN/level_day.shr"; TRF="$L/traffic_pre_light.shr"
  .venv/bin/python tests/light/plant_day.py "$L/level.shr" "$L/level_pre_light.shr" > "$SHR" || { echo "не подложить день"; exit 1; }
fi
if [ "$N" != 1 ]; then
  mkdir -p "$RUN/l$N"
  cp -c "$SHR" "$RUN/l$N/level.shr"; cp -c "$TRF" "$RUN/l$N/traffic.shr"; for f in fx.shr ui.shr; do cp -c "$L/$f" "$RUN/l$N/$f"; done; cp -cRL "$L/audio" "$RUN/l$N/"
  for f in interiors-l$N.bin interiors-l$N-gfx.bin collect-l$N.shr zonecam-l$N.shr; do cp -c "$L/$f" "$RUN/$f"; done
  cp -c "$L/missions/level0$N.msn" "$RUN/level0$N.msn"
else cp -c "$SHR" "$RUN/level.shr"; cp -c "$TRF" "$RUN/traffic.shr"; fi
{ [ "$N" != 1 ] && echo "flag level $N"
  printf 'scene spawn\nwait 3\nshot spawn\n'
  [ -n "$PLACE" ] && echo "goto $PLACE"
  printf 'scene car\nwait 3\nshot car\nflag lumakey 1\nwait 0.3\nshot carkey\nflag lumakey 0\n'
  printf 'scene exit\npress triangle\nwait 4\nshot homer\nflag lumakey 1\nwait 0.3\nshot homerkey\nflag lumakey 0\n'
  printf 'scene enter\npress triangle\nwait 5\nscene drive\nflag autostraight 3\nwait 4\nshot drive\nflag stop\nend\n'; } > "$RUN/scenario.txt"
echo "$ROOT/$L/level.shr" > "$OUT/level_shr.txt"   # мир этого прогона (у --pre тот же): яркость запечённого мира — emu_check
touch "$RUN/smokelog"
MAXT=$(awk '$1=="wait"{s+=$2} $1=="shot"{s+=1} END{print int(s)+90}' "$RUN/scenario.txt")
PPSSPP_SHOTS="$RUN/smoke.txt" PPSSPP_SHOTDIR="$OUT" tools/ppsspp_run.sh "$RUN/EBOOT.PBP" "$MAXT" > "$OUT/ppsspp.txt" 2>&1
cp "$RUN/smoke.txt" "$RUN/scenario.txt" "$OUT/" 2>/dev/null
echo "прогон: ${OUT#$ROOT/}"
.venv/bin/python tests/light/emu_check.py --measure "$OUT" --level "$N"
