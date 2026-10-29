#!/bin/bash
# Камеры разговора в эмуляторе (правки Роба 40 и 38): сценарий tests/camera/convcam_scenario.txt через tools/smoke.sh (общая
# очередь tools/ppsspp_run.sh), разбор tests/camera/convcam_check.py emu — кадр 16:9 по камере, как она нарисована.
#   tests/camera/convcam_emu.sh [DIR]                  зелёный: m0 и m1 — лицо говорящего в кадре, к камере, не закрыто
#   tests/camera/convcam_emu.sh --negative rev [DIR]   красный: план на слушающем (flag convplant 1) — сверка обязана упасть
#   tests/camera/convcam_emu.sh --negative axis [DIR]  красный: глаз на оси за слушающим (flag convplant 2) — как камера пешком
#                                                      за спиной Гомера («Мардж за Гомером не видно»)
#   tests/camera/convcam_emu.sh --negative near [DIR]  красный: ближняя плоскость города 1.5 м (flag convplant 3) — крупный
#                                                      план срезает затылок слушающего, лицо «сквозь» голову (как до правки)
#   tests/camera/convcam_emu.sh --negative duck [DIR]  красный: разговор без шин «Letterbox» (flag lbnoduck) — музыка не
#                                                      приглушена (как до правки Роба 55)
# Красные — только разговор m0 (окно эмулятора стоит недолго).
set -u; cd "$(dirname "$0")/../.."
NEG=""; if [ "${1:-}" = --negative ]; then NEG="$2"; shift 2; fi
SRC="${1:-build}"; PY=.venv/bin/python; LOG=$(mktemp -d); SCN=tests/camera/convcam_scenario.txt
if [ -n "$NEG" ]; then
  N=1; [ "$NEG" = axis ] && N=2; [ "$NEG" = near ] && N=3
  FL="flag convplant $N"; [ "$NEG" = duck ] && FL="flag lbnoduck"
  SCN="$LOG/convcam_$NEG.txt"
  awk -v fl="$FL" '/^press triangle$/ && !d { print fl; d = 1 } { print } /^shot conv_m0_line1/ { exit }' tests/camera/convcam_scenario.txt > "$SCN"
  echo "wait 3" >> "$SCN"; echo "end" >> "$SCN"
fi
SMOKE_SCN="$SCN" tools/smoke.sh "$SRC" > "$LOG/smoke.txt" 2>&1
REP=$(sed -n 's/^отчёт: \(.*\)\/summary\.txt.*/\1/p' "$LOG/smoke.txt")
[ -n "$REP" ] || { echo "нет отчёта smoke: $(head -1 "$LOG/smoke.txt")"; exit 1; }
echo "прогон: $REP ($(head -1 "$LOG/smoke.txt"))"
grep -h '^TALKSHOT' "$REP/smoke.txt" | head -12
if [ -n "$NEG" ]; then $PY tests/camera/convcam_check.py emu "$REP/smoke.txt" --expect-red; exit $?; fi
$PY tests/camera/convcam_check.py emu "$REP/smoke.txt"
