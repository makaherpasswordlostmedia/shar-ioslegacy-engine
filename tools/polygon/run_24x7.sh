#!/bin/bash
# Полигон v2 на CPU Мака круглосуточно (план Роба docs/ПОЛИГОН_ПЛАН_2026-10-05.md): без ИИ, без окон и звука, nice 15, не больше
# POLY_PROCS (≤ 6) счётных процессов одновременно — этапы идут друг за другом. Круг уровней POLY_LEVELS (по умолчанию 1→7):
#   1) рой исследователей tools/bots/anatomy.py swarm (до насыщения или POLY_SWARM_MIN мин) и карта анатомии (playable, ЧТО_ГДЕ);
#   2) инспектор tools/polygon/roles.py inspect — обход клеток роя машиной, пешком, прыжками + гэги и двери (tools/bots/inspector);
#   3) догоняющий и убегающий tools/polygon/roles.py chase (tools/bots/chase, 2 процесса);
#   4) регистратор tools/polygon/registry.py — типы, склейка мест, реестр уровня, ИТОГ_L<N>.md (≤ 5 КБ) и карта.png;
#   5) очередь сверки с оригиналом tools/polygon/twinq.py plan + run (скрытый PCSX2 по одному, POLY_TWIN_MIN мин на уровень);
#   6) общий build/polygon/ИТОГ.md (≤ 5 КБ): по строке на уровень + верх итога каждого уровня.
# Насыщение: у уровня POLY_QUIET кругов подряд нет новых мест — он пропускается, пока не насытятся все; тогда пауза 1 ч и круг заново.
# Стоп: файл build/polygon/STOP. Журнал: build/polygon/run.log. POLY_V1=1 — прежний круг (tools/polygon/run_v1.sh: рой + сверка L1).
set -o pipefail
cd "$(dirname "$0")/../.." || exit 1
[ "${POLY_V1:-0}" = 1 ] && exec bash tools/polygon/run_v1.sh
# тихо: Мак не засыпает, пока идёт круг (проверка: pmset -g assertions); без окон — всё в фоне, звук ботам не нужен
if [ "${POLY_MANAGED:-0}" != 1 ]; then
  PY=.venv/bin/python; [ -x "$PY" ] || PY=python3
  exec "$PY" tools/polygon/control.py start
fi
P=build/polygon; mkdir -p "$P"; LOG="$P/run.log"
PROCS=${POLY_PROCS:-6}
LEVELS=${POLY_LEVELS:-1 2 3 4 5 6 7}; QUIET=${POLY_QUIET:-3}
PY=.venv/bin/python; [ -x "$PY" ] || PY=python3
for V in "$PROCS" "$QUIET" "${POLY_SWARM_MIN:-120}" "${POLY_CHASE_GENS:-12}" "${POLY_TWIN_MIN:-60}"; do
  case "$V" in ''|*[!0-9]*) echo "Некорректные параметры полигона" >&2; exit 2;; esac
  [ "$V" -gt 0 ] || { echo "Параметры должны быть больше нуля" >&2; exit 2; }
done
[ "$PROCS" -gt 6 ] && PROCS=6
CHASE_PROCS=2; [ "$PROCS" -lt 2 ] && CHASE_PROCS=1
for N in $LEVELS; do case "$N" in [1-7]) ;; *) echo "Уровень должен быть от 1 до 7" >&2; exit 2;; esac; done
summary() {
  {
    echo "# Полигон v2 · итог $(date '+%d.%m %H:%M')"
    for L in $LEVELS; do
      F="$P/L$L/ИТОГ_L$L.md"
      if [ -f "$P/L$L/error" ]; then echo; echo "## L$L: ошибка, не насыщение"; cat "$P/L$L/error"; fi
      [ -f "$F" ] || continue
      echo; echo "## L$L · тихих кругов: $(cat "$P/L$L/quiet" 2>/dev/null || echo 0)"
      sed -n '2,3p' "$F"; grep -m 6 '^- ' "$F"
    done
  } | head -c 5000 > "$P/ИТОГ.tmp"
  mv "$P/ИТОГ.tmp" "$P/ИТОГ.md"
}
say() { echo "$(date '+%d.%m %H:%M') $*" > "$P/этап.txt"; echo "$(date '+%d.%m %H:%M') $*" | tee -a "$LOG"; }
failed() { say "L$N: $1 не завершён; результаты сохранены в $D"; echo "$1; $D" > "$P/L$N/error"; echo 0 > "$Q"; summary; }
lvdata() { if [ "$1" = 1 ]; then echo "build/level.shr"; else echo "build/levels/l$1/level.shr"; fi; }
say "подготовка ботов из текущих исходников"
BINS="inspector chase explorer tops" nice -n 15 bash tools/bots/build.sh >> "$LOG" 2>&1 || { say "сборка ботов не завершена; см. run.log"; exit 1; }
say "старт полигона v2: уровни «$LEVELS», $PROCS процессов, nice 15"
while [ ! -f "$P/STOP" ]; do
  RAN=0
  for N in $LEVELS; do
    [ -f "$P/STOP" ] && break
    Q="$P/L$N/quiet"; mkdir -p "$P/L$N"
    if [ -f "$(lvdata "$N")" ] && [ ! -f "build/sandbox/roads-l$N.bin" ]; then
      mkdir -p build/sandbox
      if $PY tools/cartest/roads.py --level "$N" --out "build/sandbox/roads-l$N.bin" >> "$LOG" 2>&1; then
        echo 0 > "$Q"; say "L$N: дороги подготовлены, уровень возвращён в очередь"
      fi
    fi
    q=$(cat "$Q" 2>/dev/null || echo 0)
    if [ "$q" -ge "$QUIET" ]; then continue; fi
    T=$(date +%Y%m%d-%H%M%S)-$$; D="$P/L$N/$T"; mkdir -p "$D"
    say "L$N рой → $D"
    nice -n 15 $PY tools/bots/anatomy.py swarm --level "$N" --procs "$PROCS" --max-min "${POLY_SWARM_MIN:-120}" --out "$D/swarm" >> "$LOG" 2>&1
    rc=$?
    if [ "$rc" -ne 0 ]; then
      say "L$N: рой не завершён (код $rc, см. run.log), это не насыщение; результаты сохранены"
      echo "рой: код $rc; $D" > "$P/L$N/error"; echo 0 > "$Q"; summary; continue
    fi
    if [ -f "$P/L$N/error" ]; then mv "$P/L$N/error" "$D/previous_error.txt"; fi
    RAN=$((RAN + 1))
    nice -n 15 $PY tools/bots/anatomy.py map --level "$N" --swarm "$D/swarm" --out "$D/map" >> "$LOG" 2>&1 || { failed карта; continue; }
    [ -f "$P/STOP" ] && break
    say "L$N инспектор"
    nice -n 15 $PY tools/polygon/roles.py points --level "$N" --swarm "$D/swarm" --out "$D/points.txt" >> "$LOG" 2>&1 &&
      nice -n 15 $PY tools/polygon/roles.py inspect --level "$N" --points "$D/points.txt" --procs "$PROCS" --out "$D/inspector" >> "$LOG" 2>&1 || { failed инспектор; continue; }
    [ -f "$P/STOP" ] && break
    say "L$N догоняющий и убегающий"
    nice -n 15 $PY tools/polygon/roles.py chase --level "$N" --procs "$CHASE_PROCS" --gens "${POLY_CHASE_GENS:-12}" --out "$D/chase" >> "$LOG" 2>&1 || { failed догонялки; continue; }
    say "L$N регистратор"
    OUTR=$(nice -n 15 $PY tools/polygon/registry.py --level "$N" --run "$D" --logs build/smoke --level-shr "$(lvdata "$N")" 2>>"$LOG" | tee -a "$LOG") || { failed регистратор; continue; }
    NEW=$(echo "$OUTR" | sed -n 's/^новых мест \([0-9]*\)$/\1/p' | tail -1)
    if [ "${NEW:-1}" = 0 ]; then echo $((q + 1)) > "$Q"; else echo 0 > "$Q"; fi
    if [ ! -f "$P/STOP" ]; then
      say "L$N сверка с оригиналом (очередь)"
      nice -n 15 $PY tools/polygon/twinq.py plan --level "$N" >> "$LOG" 2>&1 || { failed очередь_PS2; continue; }
      nice -n 15 $PY tools/polygon/twinq.py run --level "$N" --budget-min "${POLY_TWIN_MIN:-60}" >> "$LOG" 2>&1 || { failed сверка_PS2; continue; }
      nice -n 15 $PY tools/polygon/registry.py --level "$N" --level-shr "$(lvdata "$N")" >> "$LOG" 2>&1 || { failed итог_PS2; continue; }
    fi
    summary
    say "итог обновлён: $P/ИТОГ.md"
  done
  if [ ! -f "$P/STOP" ] && [ "$RAN" -eq 0 ]; then
    say "все уровни насыщены или без данных — пауза 1 ч, потом круг заново (счётчики тишины сброшены)"
    sleep 3600; for N in $LEVELS; do [ -d "$P/L$N" ] && echo 0 > "$P/L$N/quiet"; done
  fi
done
say "стоп (файл STOP)"
