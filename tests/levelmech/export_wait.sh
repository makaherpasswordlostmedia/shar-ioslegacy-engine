#!/bin/bash
# Экспорт в этой копии без столкновений (записка агента машины и ведущего 29.09): конвертер пишет psp_*.json/.bin с
# постоянными именами — два экспорта одновременно портят друг друга. Главная защита — своя папка временных файлов
# SHR_TMP на каждый запуск (psp_export, prp2/collect/interior её читают; tools/ship.sh основной копии делает так же).
# LM_WAIT=1 — дополнительно подождать настоящие процессы python экспортёров (строки шеллов и этот скрипт не считаются).
# Использование: export_wait.sh команда [аргументы]
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export SHR_TMP="${SHR_TMP:-$ROOT/build/tmp_conv/lm_$$}"
mkdir -p "$SHR_TMP"
busy() { ps -axo pid=,command= | grep -E '[Pp]ython[0-9.]* .*tools/(psp_export|prp2_export|traffic_export)' | grep -v " $$ " | head -3; }
n=0
while [ "${LM_WAIT:-0}" = 1 ] && [ -n "$(busy)" ] && [ $n -lt 240 ]; do   # не дольше 20 мин: с SHR_TMP ожидание — только вежливость
  [ $((n % 12)) -eq 0 ] && echo "жду чужой экспорт: $(busy | tr '\n' ';' | cut -c1-160)" >&2
  n=$((n + 1)); sleep 5
done
echo "экспорт: $*  SHR_TMP=$SHR_TMP ($(date '+%F %H:%M:%S'))" >&2
exec "$@"
