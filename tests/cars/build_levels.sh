#!/bin/bash
# Пересборка level.shr уровней с машиной уровня в CAR1 v2 (29.09) — рецепт §4 шаг 3, флаги качества закона 1.
#   tests/cars/build_levels.sh [уровни, по умолчанию 1..7]
#   результат: build/levels/l<N>/level.shr (прежний -> level_pre_car1v2.shr), журнал build/levels/l<N>/level_car.log;
#   уровень 1 дополнительно -> build/level.shr (прежний -> build/level_pre_car1v2.shr)
# Строго по одному: экспортёр пишет временные файлы с постоянными именами в общую папку конвертера
# (hit-and-run-web/public/assets/psp_*.json|bin) — два экспорта сразу портят друг другу данные. Поэтому перед каждым
# уровнем ждём, пока не закончится чужой tools/psp_export.py (другие рабочие копии делят ту же папку).
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
export SHR_TEX_CAP256=1 SHR_SMALL_MIPS=1 SHR_LAYERS=1
busy() { pgrep -f "tools/psp_export.py" > /dev/null; }
for n in ${*:-1 2 3 4 5 6 7}; do
  d=build/levels/l$n; mkdir -p "$d"
  while busy; do sleep 5; done
  if LEVEL=$n nice -n 10 tools/build_level.sh "$ROOT/$d/level_new.shr" > "$d/level_car.log" 2>&1; then
    [ -f "$d/level.shr" ] && [ ! -f "$d/level_pre_car1v2.shr" ] && mv "$d/level.shr" "$d/level_pre_car1v2.shr"
    mv "$d/level_new.shr" "$d/level.shr"
    if [ "$n" = 1 ]; then [ -f build/level.shr ] && [ ! -f build/level_pre_car1v2.shr ] && mv build/level.shr build/level_pre_car1v2.shr; cp -c "$d/level.shr" build/level.shr; fi
    echo "уровень $n: OK $(date '+%H:%M') $(grep -m1 '  машина ' "$d/level_car.log" | cut -c1-150)"
  else echo "уровень $n: ОШИБКА $(date '+%H:%M') — $(tail -1 "$d/level_car.log")"; fi
done
echo "готово $(date '+%F %H:%M')"
