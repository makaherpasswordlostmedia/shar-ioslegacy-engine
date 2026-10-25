#!/bin/bash
# Гейт №934 (дальние дороги и мосты до 520 м: viewer/road934.h, tools/road934_export.py, tools/road934_simplify.py). Порог — по слову дирижёра 24.10: ≤ 3 тыс. треугольников в кадре, ≤ 0,15 мс PSP, ≤ 120 КБ на уровень, IoU ≥ 0,98 с допуском 1 px.
#   tests/road934/road934.sh [ДАННЫЕ_КАТАЛОГ [EBOOT НАБОР [УРОВНИ...]]]    код 0 = PASS, последняя строка «ГЕЙТ №934: PASS|FAIL»
#   ДАННЫЕ_КАТАЛОГ — road934.shr уровня 1 в корне, остальные l<N>/road934.shr; не задан — слой экспортируется заново из reissue7 (LV_SRC) с настройками по умолчанию.
# (1) данные, Мак, только файлы, на каждом уровне:
#     а) размер файла ≤ SIZE_MAX (120000 Б);
#     б) IoU: настоящие (полные) треугольники дорог и мостов и треугольники из road934.shr (читает независимо tools/road934_view.py) проецируются в кадр 480×272 из ROAD_VIEWS точек обзора
#        (глаз на дороге + 30 м, взгляд вдоль самой длинной дороги), кольцо 270–500 м от глаза режется ПО ПИКСЕЛЮ (не по центру треугольника), допуск 1 px: IoU не ниже IOU_MIN (0,98).
#        Красные: (i) слой «как до правки» (кончается на 200 м) обязан дать IoU ниже порога; (ii) данные, упрощённые прежним fast-simplification (--eps 0 --reduce 0.9: двигает край дороги) обязаны упасть;
#     в) треугольников в кадре ≤ TRIS_MAX (3000): модель отбора движка (круг по рамке блока, боковые плоскости, запас RD_CMG) на 200 точках дороги × 24 курса × дальность города 130/150/200/250 м.
#        Красный: данные без упрощения (ROAD934_EPS=0, 23 тыс. треугольников) обязаны превысить предел.
# (2) движок в безголовом эмуляторе через tools/emu_run.sh (нужны EBOOT и НАБОР — набор тура; данные уровня кладутся поверх OVL-наложением): на каждый уровень виды a (слой сплошным пурпуром), b (слой обычный), c (слоя нет),
#     на каждом виде окна с переиспользованием отбора блоков (как в игре) и с отбором заново каждый кадр (flag farroad934cache 0). Метрики: охват эталона и точность пурпура (≥ COV_MIN, ≥ PREC_MIN); кадр c — пурпура 0;
#     в кадре ≤ TRIS_MAX треугольников; цена худшего вида (строки ROAD934 cost, окна по 60 кадров, наименьшее окно вида) ≤ COST_US (0,15 мс PSP = 26 мкс Мака при ×5,8); худший кадр с отбором заново ≤ FRESH_US (30 мкс = 0,174 мс, предел-страховка).
#     Красные: кадр без слоя вместо кадра со слоем; EBOOT_RED (сборка с -DFARROAD934_OLD=1) на уровнях RED_LEVELS (по умолчанию первый и последний) — охват обязан упасть до нуля.
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
PY="${PY:-$HOME/Downloads/shar-psp/.venv/bin/python}"; [ -x "$PY" ] || PY=python3
LV_SRC="${LV_SRC:-$HOME/Downloads/shar-psp-urovni-w/build/reissue7}"
ROAD_VIEWS="${ROAD_VIEWS:-6}"; IOU_MIN="${IOU_MIN:-0.98}"; COV_MIN="${COV_MIN:-0.30}"; PREC_MIN="${PREC_MIN:-0.90}"
SIZE_MAX="${SIZE_MAX:-120000}"; TRIS_MAX="${TRIS_MAX:-3000}"; COST_US="${COST_US:-26}"; FRESH_US="${FRESH_US:-30}"; FRAME_VIEWS="${FRAME_VIEWS:-200}"; ENGINE_VIEWS="${ENGINE_VIEWS:-4}"
DD="${1:-}"; EB="${2:-}"; SET="${3:-}"; shift 3 2>/dev/null || shift $# ; LV="${*:-1 2 3 4 5 6 7}"
export ROAD934_NAMES="${ROAD934_NAMES:-$ROOT/build/roads/texnames.json}"
if [ ! -f "$ROAD934_NAMES" ]; then mkdir -p "$(dirname "$ROAD934_NAMES")"; (cd "$ROOT" && "$PY" -c "import sys; sys.path.insert(0,'tools'); import notoon_list as N; N.names_by_digest('$ROAD934_NAMES')") > /dev/null 2>&1; fi
[ -f "$ROAD934_NAMES" ] || { echo "нет $ROAD934_NAMES (имена текстур диска: tools/notoon_list.py names_by_digest)"; echo "ГЕЙТ №934: FAIL"; exit 1; }
T="${TMPDIR:-/tmp}/road934.$$"; mkdir -p "$T"; trap 'rm -rf "$T"' EXIT
fail=0; LASTLV="${LV##* }"; RED_LEVELS="${RED_LEVELS:-${LV%% *} $LASTLV}"
datafile() { if [ "$1" = 1 ]; then echo "$DD/road934.shr"; else echo "$DD/l$1/road934.shr"; fi; }
check_level() {   # одна проверка данных уровня; строки — в stdout, провал — файл $T/fail$L
  L=$1; bad=0
  LS="$LV_SRC/l$L/level.shr"; [ -f "$LS" ] || { echo "L$L: нет $LS"; bad=1; touch "$T/fail$L"; return; }
  if [ -n "$DD" ]; then F="$(datafile "$L")"
  else F="$T/rd$L.shr"; "$PY" tools/road934_export.py "$LS" "$F" > "$T/exp$L.txt" 2>&1 || { echo "L$L: экспорт упал"; tail -3 "$T/exp$L.txt"; bad=1; touch "$T/fail$L"; return; }; fi
  [ -f "$F" ] || { echo "L$L: нет $F"; bad=1; touch "$T/fail$L"; return; }
  "$PY" tools/road934_view.py pick "$LS" "$ROAD_VIEWS" > "$T/views$L.txt" || { echo "L$L: виды не выбрались"; bad=1; touch "$T/fail$L"; return; }
  sz=$(stat -f %z "$F" 2>/dev/null || stat -c %s "$F"); [ "$sz" -le "$SIZE_MAX" ] || { echo "L$L: FAIL файл $sz Б больше $SIZE_MAX"; bad=1; }
  r=$("$PY" tools/road934_view.py data "$LS" "$F" --views "$ROAD_VIEWS" --min-iou "$IOU_MIN"); rc=$?
  rr=$("$PY" tools/road934_view.py data "$LS" "$F" --views "$ROAD_VIEWS" --min-iou "$IOU_MIN" --red); rrc=$?
  echo "L$L данные ($sz Б): $r"; echo "L$L красный (слой до 200 м): $rr"
  [ $rc = 0 ] || { echo "L$L: FAIL (IoU ниже $IOU_MIN)"; bad=1; }
  [ $rrc != 0 ] || { echo "L$L: красный контроль не упал — проверка слепая"; bad=1; }
  "$PY" tools/road934_export.py "$LS" "$T/fs$L.shr" --eps 0 --reduce 0.9 > /dev/null 2>&1
  rf=$("$PY" tools/road934_view.py data "$LS" "$T/fs$L.shr" --views "$ROAD_VIEWS" --min-iou "$IOU_MIN"); rfc=$?
  echo "L$L красный (прежнее fast-simplification, двигает край): $rf"
  [ $rfc != 0 ] || { echo "L$L: красный контроль fast-simplification не упал — проверка IoU слепая"; bad=1; }
  ft=$("$PY" tools/road934_view.py frametris "$LS" "$F" --views "$FRAME_VIEWS" --max-tris "$TRIS_MAX"); ftc=$?
  echo "L$L кадр: $ft"
  [ $ftc = 0 ] || { echo "L$L: FAIL (треугольников в кадре больше $TRIS_MAX)"; bad=1; }
  ROAD934_EPS=0 "$PY" tools/road934_export.py "$LS" "$T/old$L.shr" > /dev/null 2>&1
  fo=$("$PY" tools/road934_view.py frametris "$LS" "$T/old$L.shr" --views 60 --max-tris "$TRIS_MAX"); foc=$?
  echo "L$L красный (без упрощения): $fo"
  [ $foc != 0 ] || { echo "L$L: красный контроль без упрощения не упал — счёт треугольников слепой"; bad=1; }
  [ $bad = 0 ] || touch "$T/fail$L"
}
pids=""; for L in $LV; do check_level "$L" > "$T/chk$L.txt" 2>&1 & pids="$pids $!"; done; wait $pids   # уровни параллельно (только Python на файлах)
for L in $LV; do cat "$T/chk$L.txt"; [ -f "$T/fail$L" ] && fail=1; done
if [ -n "$EB" ] && [ -n "$SET" ]; then
  OUTD="${OUT:-$T/emu}"; mkdir -p "$OUTD"; EMU="$ROOT/tools/emu_run.sh"; pids=""
  for L in $LV; do
    LS="$LV_SRC/l$L/level.shr"; [ -f "$LS" ] || continue
    if [ -n "$DD" ]; then F="$(datafile "$L")"; else F="$T/rd$L.shr"; fi
    [ -f "$F" ] || continue
    OV="$T/ovl$L"; rm -rf "$OV"; mkdir -p "$OV"; if [ "$L" = 1 ]; then cp "$F" "$OV/road934.shr"; else mkdir -p "$OV/l$L"; cp "$F" "$OV/l$L/road934.shr"; fi
    head -n "$ENGINE_VIEWS" "$T/views$L.txt" > "$T/eviews$L.txt"   # в эмуляторе первые ENGINE_VIEWS видов (самые длинные дороги): прогон на уровень ~6 мин
    "$PY" tools/road934_view.py scen "$L" "$T/eviews$L.txt" > "$T/scen$L.txt"
    [ "${SKIP_EMU:-0}" = 1 ] && continue   # SKIP_EMU=1: только разбор готовых прогонов в OUT/out_r934_L* (тот же EBOOT), эмуляторы не запускать
    ( SET="$SET" OVL="$OV" OUT="$OUTD" EMU_OWNER="${EMU_OWNER:-road934}" "$EMU" "$T/scen$L.txt" "r934_L$L" "$EB" "${EMU_T:-3000}" > "$T/emu$L.log" 2>&1 ) & pids="$pids $!"
    case " $RED_LEVELS " in *" $L "*) if [ -n "${EB_RED:-}" ]; then
      ( SET="$SET" OVL="$OV" OUT="$OUTD" EMU_OWNER="${EMU_OWNER:-road934}" "$EMU" "$T/scen$L.txt" "r934red_L$L" "$EB_RED" "${EMU_T:-3000}" > "$T/emured$L.log" 2>&1 ) & pids="$pids $!"; fi;; esac
  done
  wait $pids
  for L in $LV; do
    LS="$LV_SRC/l$L/level.shr"; [ -f "$LS" ] || continue
    O="$OUTD/out_r934_L$L"
    grep -aq "^ROAD934 loaded level=$L" "$O/smoke.txt" 2>/dev/null || { echo "L$L: FAIL слой не загрузился в движке"; fail=1; continue; }
    ddv=$(grep -a "^ROAD934 cost" "$O/smoke.txt" | sed 's/.*drawDist=\([0-9]*\).*/\1/' | sort -n | head -1); ddv=${ddv:-150}
    "$PY" tools/road934_view.py shots "$LS" "$O" "$T/eviews$L.txt" --dd "$ddv" --cov-min "$COV_MIN" --prec-min "$PREC_MIN" > "$T/shots$L.txt"; src=$?; cat "$T/shots$L.txt"
    "$PY" tools/road934_view.py shots "$LS" "$O" "$T/eviews$L.txt" --dd "$ddv" --cov-min "$COV_MIN" --prec-min "$PREC_MIN" --red > "$T/shotsr$L.txt"; srr=$?
    echo "L$L красный (кадр без слоя вместо кадра со слоем): $(head -1 "$T/shotsr$L.txt")"
    [ $src = 0 ] || { echo "L$L: FAIL (движок: охват/точность)"; fail=1; }
    [ $srr != 0 ] || { echo "L$L: красный контроль движка не упал — проверка слепая"; fail=1; }
    cs=$("$PY" tools/road934_view.py cost "$O/smoke.txt" --max-tris "$TRIS_MAX" --cost-us "$COST_US" --fresh-us "$FRESH_US"); csc=$?
    echo "L$L цена в движке: $cs"
    [ $csc = 0 ] || { echo "L$L: FAIL (цена или треугольников в кадре больше предела)"; fail=1; }
    case " $RED_LEVELS " in *" $L "*) if [ -n "${EB_RED:-}" ]; then
      "$PY" tools/road934_view.py shots "$LS" "$OUTD/out_r934red_L$L" "$T/eviews$L.txt" --dd "$ddv" --cov-min "$COV_MIN" --prec-min "$PREC_MIN" > "$T/shotsold$L.txt"; sro=$?
      echo "L$L красный (сборка с -DFARROAD934_OLD=1): $(head -1 "$T/shotsold$L.txt")"
      [ $sro != 0 ] || { echo "L$L: красный контроль OLD не упал — проверка слепая"; fail=1; }
    fi;; esac
  done
fi
[ $fail = 0 ] && { echo "ГЕЙТ №934: PASS"; exit 0; }; echo "ГЕЙТ №934: FAIL"; exit 1
