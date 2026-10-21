#!/bin/bash
# Гейт правки 347: исход миссий с машинами миссий не зависит от того, когда игрок начал миссию относительно трафика.
#   tests/missions/start_shift.sh [--quick] [МИССИИ] [СДВИГИ]      по умолчанию МИССИИ="6 1", СДВИГИ="0 0.5 1 1.5 2"
# Бот-миссионер (tools/bots/missioner.c) проходит миссию уровня 1, стоя до первого ввода S с (MISSIONER_DELAY): мир и трафик идут,
# бот стоит — как другой радиус разговора (правка 345 сдвинула старт погони m6 на 0,5 с, и бот перестал её проходить).
# Зелёный: каждая миссия пройдена при каждом сдвиге (ночь 05.10 на HEAD 28d6ba0: m6 провал при 0, 0,25 и 2 с; m1 — при 0, 0,25, 0,5).
# Красные — прежнее поведение флагами (каждый обязан провалить хотя бы один сдвиг своей миссии):
#   m6 MISSIONER_RAM_OLD=1 MISSIONER_PASS_OLD=1 — прежний бот-таран: тормоз под машину ЗА целью, упор в фургон без удара
#      (сближение < 1 м/с), за машиной трафика с её скоростью
#   m1 -DMC_LEDGE_OLD=1 + MISSIONER_PASS_OLD=1  — прежние пути машин миссий и бота (вверх по срезу 13 в стену 2 м) и гонщик,
#      который не обгоняет Скиннера
# --quick — только зелёный. Журналы: build/gates/start_shift/<время>/<вариант>/m<N>_<S>/m<N>.log; итог — последней строкой.
# Ядер не больше 3 (PROCS); один прогон m6 ~20 с, m1 до ~10 мин (попытки гонки и навигатор).
cd "$(dirname "$0")/../.."
QUICK=0; [ "$1" = --quick ] && { QUICK=1; shift; }
MS=${1:-"6 1"}; SH=${2:-"0 0.5 1 1.5 2"}; P=${PROCS:-3}
OUT=build/gates/start_shift/$(date +%Y%m%d-%H%M%S); mkdir -p "$OUT"
ARGS="build/level.shr build/homer.shr build/sandbox/roads-l1.bin build/missions/level01.msn"
build() { OUT_DIR="$OUT/$1/bin" BINS=missioner tools/bots/build.sh $2 > "$OUT/$1.build.txt" 2>&1 || { echo "сборка $1 не удалась"; exit 1; }; }
build new ""
[ $QUICK = 1 ] || build ledgeold "-DMC_LEDGE_OLD=1"
run() {   # вариант, миссия, сдвиг, [окружение ...]
  local v=$1 m=$2 s=$3 d="$OUT/$1/m$2_$3"; shift 3; mkdir -p "$d"
  env "$@" MISSIONER_DELAY=$s BW_FRAMES=1 "$OUT/${v%%_*}/bin/missioner" $ARGS --mission $m --secs 900 -v --out "$d" > "$d/m$m.log" 2>&1
  local r; r=$(grep -aE '^M	' "$d/m$m.log" | tail -1 | cut -f5); echo "$v m$m $s ${r:-нет итога}"
}
export -f run; export OUT ARGS
JOBS=$(for m in $MS; do for s in $SH; do echo "new $m $s"; done; done
  if [ $QUICK = 0 ]; then
    for m in $MS; do for s in $SH; do
      [ $m = 6 ] && echo "new_ramold $m $s MISSIONER_RAM_OLD=1 MISSIONER_PASS_OLD=1"
      [ $m = 1 ] && echo "ledgeold $m $s MISSIONER_PASS_OLD=1"
    done; done
  fi)
echo "$JOBS" | xargs -P "$P" -L 1 bash -c 'run "$0" "$@"' | sort | tee "$OUT/runs.txt"
fail=0
for m in $MS; do
  bad=$(grep -c "^new m$m .*" "$OUT/runs.txt"); ok=$(grep -c "^new m$m .* пройдена" "$OUT/runs.txt")
  [ "$ok" = "$bad" ] && echo "PASS зелёный m$m: пройдена при всех сдвигах ($ok/$bad)" || { echo "FAIL зелёный m$m: пройдена $ok из $bad сдвигов"; fail=1; }
  if [ $QUICK = 0 ]; then
    rv=$([ $m = 6 ] && echo new_ramold || echo ledgeold)
    n=$(grep -c "^$rv m$m " "$OUT/runs.txt"); k=$(grep -c "^$rv m$m .* пройдена" "$OUT/runs.txt")
    [ "$k" -lt "$n" ] && echo "PASS красный m$m ($rv): провалена при $((n - k)) из $n сдвигов" || { echo "FAIL красный m$m ($rv) не пойман: пройдена при всех $n сдвигах"; fail=1; }
  fi
done
echo "журналы: $OUT"
[ $fail = 0 ] && echo "ИТОГ: PASS" || echo "ИТОГ: FAIL"
exit $fail
