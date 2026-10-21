#!/bin/bash
# Гейт 04.10 («подтяни все объекты миссий», замечание Роба к m2: «на месте прошлого предмета свечение-звёздочка без предмета,
# подъехал — „пчпуньк“»): цель goto carsphere/triggersphere и точки гонок.
#   * эффект SetCollectibleEffect (viewer/collectfx.c, данные viewer/collectfx_data.h <- tools/collectfx_export.py): при въезде
#     в сферу цели / точку гонки — квады свечения и голубые искры wrench_collect (запись PS2 10:34.7, 5:21);
#   * под маркером цели — его пятно <рисунок>_shadow (carsphere_shadow — кольцо на земле, запись PS2 10:34.1–10:34.3, 5:32).
# 0) заголовок эффектов совпадает с диском (tools/collectfx_export.py --check);
# 1) безголовый эмулятор (~/.claude/skills/shar-level-polish/scripts/scen.py): m2 этап 9 (въезд в объём цели у дома Фландерса)
#    и гонка sr1 (первая точка). КРАСНЫЙ — тот же сценарий с «flag cfxold 1» и «flag mkshadowold 1» (прежнее поведение) обязан
#    провалить сверку tests/missions/collect_fx_check.py; ЗЕЛЁНЫЙ — сверка строк MSN marker / MSN cfx и пикселей против красного.
#   tests/missions/collect_fx.sh            EBOOT — viewer/build/EBOOT.PBP (или EBOOT=путь), данные — build/ основной копии
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
OUT=build/gates/collect_fx; mkdir -p "$OUT"; PY=.venv/bin/python; SCEN=~/.claude/skills/shar-level-polish/scripts/scen.py
EB="${EBOOT:-$ROOT/viewer/build/EBOOT.PBP}"; F=build/twins/scen/full; TAG="${TAG:-cfx}"
"$PY" tools/collectfx_export.py --check > "$OUT/header.txt" 2>&1 || { tail -1 "$OUT/header.txt"; echo "FAIL: viewer/collectfx_data.h устарел"; exit 1; }
echo "заголовок эффектов: $(tail -1 "$OUT/header.txt")"
goto_scn() {   # $1 — служебные флаги прежнего поведения или пусто
  printf '%s\n' 'flag msn' 'wait 2'; [ -n "$1" ] && printf '%s\n' 'flag cfxold 1' 'flag mkshadowold 1'
  printf '%s\n' 'flag msnmainat 209' 'wait 3' 'press cross' 'wait 2' 'press cross' 'wait 2' \
    'goto 232 160.4 1.08' 'wait 1.2' 'shot ap_a' 'goto 241.5 164.5 1.08' 'wait 1.0' 'shot ap_b' \
    'goto 243.2 165.4 1.08' 'wait 0.02' 'shot fx_a' 'wait 0.06' 'shot fx_b' 'wait 0.08' 'shot fx_c' 'wait 0.12' 'shot fx_d' \
    'wait 0.4' 'shot fx_e' 'wait 1.5' 'shot fx_f' 'end'
}
race_scn() {
  printf '%s\n' 'flag msn' 'wait 2'; [ -n "$1" ] && printf '%s\n' 'flag cfxold 1' 'flag mkshadowold 1'
  printf '%s\n' 'flag msnsel 8' 'wait 3' 'press cross' 'wait 2' 'press cross' 'wait 6' \
    'goto 437.1 -390 0' 'wait 1.2' 'shot r_a' 'goto 437.1 -373 0' 'wait 0.05' 'shot r_b' 'wait 0.1' 'shot r_c' \
    'wait 0.15' 'shot r_d' 'wait 0.4' 'shot r_e' 'end'
}
run() { "$2" "$3" > "$OUT/$1.txt"; SCEN_EBOOT="$EB" SCEN_HOME="$ROOT/$OUT/home" "$PY" "$SCEN" "${TAG}_$1" "$OUT/$1.txt" > "$OUT/$1_run.txt" 2>&1; }
run goto_old goto_scn old; run race_old race_scn old; run goto_new goto_scn ""; run race_new race_scn ""
echo "красный (flag cfxold 1, flag mkshadowold 1):"
"$PY" tests/missions/collect_fx_check.py $F/${TAG}_goto_old $F/${TAG}_race_old > "$OUT/red.txt"; rc=$?
sed 's/^/  /' "$OUT/red.txt"
if [ $rc = 0 ]; then echo "FAIL: прежнее поведение прошло сверку — проверка слепая"; exit 1; fi
echo "  упал, как должен"
echo "зелёный:"
"$PY" tests/missions/collect_fx_check.py $F/${TAG}_goto_new $F/${TAG}_race_new --base $F/${TAG}_goto_old $F/${TAG}_race_old | tee "$OUT/green.txt" | sed 's/^/  /'
[ "${PIPESTATUS[0]}" = 0 ] && { echo "PASS collect_fx (кадры: $F/${TAG}_*_new, прежнее: $F/${TAG}_*_old)"; exit 0; }
echo "FAIL collect_fx"; exit 1
