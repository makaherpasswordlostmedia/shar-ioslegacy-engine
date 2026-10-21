#!/bin/bash
# Пересборка level.shr и traffic.shr уровней со светом уровня (29.09, рецепт §12): CAR1 v3 + LGT1, машины и освещаемые предметы
# мира запечены светом группы sun своего уровня. Флаги качества закона 1.
#   tests/light/build_levels.sh [уровни, по умолчанию 1 6 4 7 2 3 5]
# Результат: build/levels/l<N>/level.shr и traffic.shr (прежние -> *_pre_light.shr, если были), журналы build/levels/l<N>/light_*.log;
# уровень 1 дополнительно -> build/level.shr и build/traffic.shr.
# Строго по одному и только когда нет чужого экспорта (python psp_export/prp2_export/traffic_export): конвертер пишет
# временные файлы с постоянными именами; свои кладём в build/tmp_conv/light (SHR_TMP), но очередь всё равно соблюдаем.
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
export SHR_TEX_CAP256=1 SHR_SMALL_MIPS=1 SHR_LAYERS=1 SHR_TMP="$ROOT/build/tmp_conv/light_$$"
busy() { ps -axo pid=,command= | grep -E "^ *[0-9]+ [^ ]*[Pp]ython[0-9.]* .*tools/(psp_export|prp2_export|traffic_export)\.py" | grep -v grep > /dev/null; }
wait_turn() { local n=0; while busy; do [ $((n % 24)) -eq 0 ] && echo "  жду чужой экспорт $(date '+%H:%M:%S')"; n=$((n + 1)); sleep 5; done; }
for n in ${*:-1 6 4 7 2 3 5}; do
  d=build/levels/l$n; mkdir -p "$d"
  wait_turn
  if LEVEL=$n nice -n 10 tools/build_level.sh "$ROOT/$d/level_new.shr" > "$d/light_level.log" 2>&1; then
    [ -f "$d/level.shr" ] && [ ! -f "$d/level_pre_light.shr" ] && mv "$d/level.shr" "$d/level_pre_light.shr"
    mv "$d/level_new.shr" "$d/level.shr"
    [ "$n" = 1 ] && cp -c "$d/level.shr" build/level.shr 2>/dev/null || { [ "$n" = 1 ] && cp "$d/level.shr" build/level.shr; }
    echo "уровень $n level.shr: OK $(date '+%H:%M') $(grep -m1 '^свет уровня (' "$d/light_level.log" | cut -c1-160)"
  else echo "уровень $n level.shr: ОШИБКА $(date '+%H:%M') — $(tail -1 "$d/light_level.log")"; fi
  wait_turn
  if nice -n 10 .venv/bin/python tools/traffic_export.py --level "$n" --out "$ROOT/$d/traffic_new.shr" > "$d/light_traffic.log" 2>&1; then
    [ -f "$d/traffic.shr" ] && [ ! -f "$d/traffic_pre_light.shr" ] && mv "$d/traffic.shr" "$d/traffic_pre_light.shr"
    mv "$d/traffic_new.shr" "$d/traffic.shr"
    [ "$n" = 1 ] && cp "$d/traffic.shr" build/traffic.shr
    echo "уровень $n traffic.shr: OK $(date '+%H:%M')"
  else echo "уровень $n traffic.shr: ОШИБКА $(date '+%H:%M') — $(tail -1 "$d/light_traffic.log")"; fi
done
rm -rf "$SHR_TMP"
echo "готово $(date '+%F %H:%M')"
