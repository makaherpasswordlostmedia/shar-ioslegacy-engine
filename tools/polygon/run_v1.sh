#!/bin/bash
# ПРЕЖНИЙ круг полигона (до v2, 05.10): запускается из run_24x7.sh при POLY_V1=1. Не менять — это красный контроль/откат.
# Полигон на CPU Мака круглосуточно (план Роба docs/ПОЛИГОН_ПЛАН_2026-10-05.md; 05.10: «до четверга только локально, отдай
# процессору половину, а то и две трети мощности, чтобы круглосуточно гонял»). Без ИИ, без окон и звука, nice 15.
# Круг: рой исследователей L1 (tools/bots/anatomy.py swarm, 6 процессов из 10 ядер) до насыщения или 4 ч → карта и ЧТО_ГДЕ →
# сверка точек с оригиналом скрытым PCSX2 (tools/twins/placement.py --points auto, по одному) → короткий итог для ИИ
# build/polygon/ИТОГ.md (≤ 5 КБ). Потом снова. Стоп: файл build/polygon/STOP. Журнал: build/polygon/run.log
# Уровни 2–7 (облако 05.10): круг по POLY_LEVELS (по умолчанию «1»; например POLY_LEVELS="1 2 3 4 5 6 7"). Уровню нужны
# build/levels/l<N>/level.shr и дороги build/sandbox/roads-l<N>.bin (python tools/cartest/roads.py --level N --out …) — нет данных:
# anatomy.py пишет, чего не хватает, уровень пропускается. Сверка PCSX2 (placement.py) — только L1, как прежде
cd "$(dirname "$0")/../.." || exit 1
P=build/polygon; mkdir -p "$P"; LOG="$P/run.log"; PROCS=${POLY_PROCS:-6}
say() { echo "$(date '+%d.%m %H:%M') $*" | tee -a "$LOG"; }
say "старт полигона: $PROCS процессов, nice 15"
LEVELS=${POLY_LEVELS:-1}
while [ ! -f "$P/STOP" ]; do
  RAN=0
  for N in $LEVELS; do
    [ -f "$P/STOP" ] && break
    T=$(date +%Y%m%d-%H%M); D="$P/L$N/$T"; mkdir -p "$D"
    say "L$N рой → $D"
    nice -n 15 .venv/bin/python tools/bots/anatomy.py swarm --level "$N" --procs "$PROCS" --max-min 240 --out "$D/swarm" >> "$LOG" 2>&1
    if [ $? -eq 2 ]; then say "L$N: нет данных уровня (см. run.log) — пропуск"; rmdir "$D" 2>/dev/null; continue; fi
    RAN=$((RAN + 1))
    nice -n 15 .venv/bin/python tools/bots/anatomy.py map --level "$N" --swarm "$D/swarm" --out "$D/map" >> "$LOG" 2>&1
    [ -f "$P/STOP" ] && break
    if [ "$N" = 1 ]; then
      say "L1 сверка с оригиналом (скрытый PCSX2)"
      nice -n 15 .venv/bin/python tools/twins/placement.py --level 1 --points auto --budget-min 120 >> "$LOG" 2>&1
    fi
    {
      echo "# Полигон · итог $(date '+%d.%m %H:%M') · только для ИИ"
      for L in $LEVELS; do
        M=$(ls -d "$P/L$L"/*/map 2>/dev/null | tail -1); [ -n "$M" ] || continue
        echo; echo "## L$L тупики и провалы (последний рой, топ 12) — $M/ЧТО_ГДЕ.txt"
        grep -E "^  L$L " "$M/ЧТО_ГДЕ.txt" 2>/dev/null | head -12
      done
      echo; echo "## L1 сверка постановкой PS2/PSP — build/СВЕРКА_PS2_PSP_L1/ОТЧЁТ.md (первые строки)"
      head -20 build/СВЕРКА_PS2_PSP_L1/ОТЧЁТ.md 2>/dev/null
    } | head -c 5000 > "$P/ИТОГ.md"
    say "итог обновлён: $P/ИТОГ.md"
  done
  if [ "$RAN" -eq 0 ] && [ ! -f "$P/STOP" ]; then say "ни у одного уровня из «$LEVELS» нет данных — пауза 10 мин"; sleep 600; fi
done
say "стоп (файл STOP)"
