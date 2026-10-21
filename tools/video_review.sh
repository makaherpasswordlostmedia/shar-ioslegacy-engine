#!/bin/bash
# Разбор видео тестовой сборки одной командой (профиль метки: test18 по умолчанию, PROFILE=test17 для старых видео).
#   tools/video_review.sh VIDEO.mov SMOKE.txt CORNERS OUTDIR
#   CORNERS — углы экрана PSP в пикселях видео: x0,y0,x1,y1,x2,y2,x3,y3 (верх-лево, верх-право, низ-лево, низ-право)
# Шаги: уменьшенная копия 1280x720 -> нарезка по меткам (ИНДЕКС.tsv + клипы) -> отчёт (OUTDIR/review/report.md, events/*.png)
set -e
V="$1"; S="$2"; C="$3"; O="$4"; P="${PROFILE:-test18}"
[ -n "$O" ] || { sed -n 2,5p "$0"; exit 1; }
HERE="$(cd "$(dirname "$0")" && pwd)"; PY="${PY:-python3}"; mkdir -p "$O"
W=$(ffprobe -v error -select_streams v:0 -show_entries stream=width -of default=nw=1:nk=1 "$V")
if [ "$W" -gt 1280 ]; then   # углы пересчитываются под копию
  H=$(ffprobe -v error -select_streams v:0 -show_entries stream=height -of default=nw=1:nk=1 "$V")
  SMALL="$O/video_720.mp4"
  [ -s "$SMALL" ] || nice -n 20 ffmpeg -v error -i "$V" -vf scale=1280:720 -an -c:v h264_videotoolbox -b:v 8M "$SMALL"
  C=$(echo "$C" | awk -F, -v w="$W" -v h="$H" '{for(i=1;i<=8;i++){printf "%s%.2f",(i>1?",":""),$i*(i%2?1280/w:720/h)}}')
  V="$SMALL"
fi
"$PY" "$HERE/video_split_scenes.py" "$V" --smoke "$S" --corners "$C" --profile "$P" --out "$O"
"$PY" "$HERE/video_test_review.py" "$V" --smoke "$S" --corners "$C" --profile "$P" --index "$O/ИНДЕКС.tsv" --cache "$O/blocks.npy" --out "$O/review"
echo "готово: $O/review/report.md"
