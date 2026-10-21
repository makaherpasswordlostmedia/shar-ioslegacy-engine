#!/bin/bash
# Гейт сценария TEST16 (13.10):
# 1. Красный контроль: старый отчёт TEST15 (build/psp-tour/20261012-1912-SHARTEST15/shots) ОБЯЗАН провалить проверку
#    (серии b538 и gb1_10 замёрзли, 12 одинаковых кадров).
# 2. Зелёный контроль: новый сценарий psp_tour_16.txt содержит все сцены света (L1_light_aes, L1_light_street, L7_light_lamps)
#    и гарантирует непрерывное движение автопилота autostraight во всех сериях снимков.
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
mkdir -p build/gates/tour16
LOG="build/gates/tour16/gate_$(date +%Y%m%d-%H%M%S).log"; : > "$LOG"
PY=python3
FAILS=0

echo "=== ГЕЙТ СЦЕНАРИЯ TEST16 ===" | tee -a "$LOG"

# 1. Красный контроль: старый отчёт TEST15
OLD_SHOTS="build/psp-tour/20261012-1912-SHARTEST15/shots"
[ -d "$OLD_SHOTS" ] || OLD_SHOTS="$HOME/Downloads/shar-psp-g-build-w/build/psp-tour/20261012-1912-SHARTEST15/shots"

if [ -d "$OLD_SHOTS" ]; then
  if $PY tests/tour16/check_shots.py "$OLD_SHOTS" >> "$LOG" 2>&1; then
    echo "RED НЕ ПОЙМАН: старый отчёт TEST15 ошибочно прошёл проверку" | tee -a "$LOG"
    FAILS=$((FAILS + 1))
  else
    echo "RED OK: старый отчёт TEST15 пойман (замёрзшие кадры в b538 и gb1 зафиксированы)" | tee -a "$LOG"
  fi
else
  echo "ВНИМАНИЕ: $OLD_SHOTS не найден для красного контроля" | tee -a "$LOG"
fi

# 2. Зелёный контроль структуры сценария TEST16
SCN="tests/me/psp_tour_16.txt"
[ -f "$SCN" ] || SCN="$HOME/Downloads/shar-psp-g-build-w/tests/me/psp_tour_16.txt"

if $PY tests/tour16/check_shots.py "$SCN" >> "$LOG" 2>&1; then
  echo "GREEN OK: сценарий TEST16 содержит все сцены света и команды движения в сериях" | tee -a "$LOG"
else
  echo "GREEN ПРОВАЛ: сценарий TEST16 не прошёл проверку" | tee -a "$LOG"
  FAILS=$((FAILS + 1))
fi

# 3. Синхронизация файлов между копиями
for d in $HOME/Downloads/shar-psp $HOME/Downloads/shar-psp-g-build-w; do
  mkdir -p "$d/tests/tour16"
  cp -f tests/tour16/check_shots.py "$d/tests/tour16/" 2>/dev/null || true
  cp -f tests/tour16/gate.sh "$d/tests/tour16/" 2>/dev/null || true
done

[ $FAILS -eq 0 ] && echo "GATE PASS" | tee -a "$LOG" || echo "GATE FAIL ($FAILS)" | tee -a "$LOG"
exit $FAILS
