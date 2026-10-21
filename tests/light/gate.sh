#!/bin/bash
# Гейт «свет уровня» (29.09, docs/РЕЦЕПТ_УРОВНЯ.md §12), часть без эмулятора. Каждый контроль сначала красный на подложенном.
#   tests/light/gate.sh            журнал build/gates/light/gate_<время>.log, последняя строка GATE PASS / GATE FAIL
# 1. разбор чанков диска: 0x13008 (у источников, всегда 1) и 0x12110f (постоянная метка у каналов) — подложенное значение не проходит
# 2. движок читает блок LGT1 так же, как его пишет экспорт (tests/light/parse_host.c = код EBOOT): испорченная сумма, чужая
#    версия, обрезанная секция — отказ; на всех уровнях — свет своего уровня, цвета персонажей = skin.h × множители
# 3. блок света и светотень машин = диск (tests/light/light_check.py): подложенный день на уровне 6 (level.shr и traffic.shr до
#    света уровня; дневной блок уровня 1 в LGT1 уровня 6) — FAIL; уровни 1–7 — PASS; уровень 1 побайтно прежний, кроме CAR1
# Эмулятор (яркость на экране против мира, 30 FPS, куча) — tests/light/emu_gate.sh.
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
mkdir -p build/gates/light; LOG="build/gates/light/gate_$(date +%Y%m%d-%H%M%S).log"; : > "$LOG"
PY=.venv/bin/python; FAILS=0
red() { local name="$1"; shift; if "$@" >> "$LOG" 2>&1; then echo "RED НЕ ПОЙМАН: $name" | tee -a "$LOG"; FAILS=$((FAILS + 1)); else echo "RED OK: $name" | tee -a "$LOG"; fi; }
green() { local name="$1"; shift; if "$@" >> "$LOG" 2>&1; then echo "GREEN OK: $name" | tee -a "$LOG"; else echo "GREEN ПРОВАЛ: $name" | tee -a "$LOG"; FAILS=$((FAILS + 1)); fi; }
lv() { [ "$1" = 1 ] && [ -f build/level.shr ] && echo build/level.shr || echo "build/levels/l$1/level.shr"; }

# 1. чанки диска
red "0x13008 = 2 у источника" $PY tests/light/light_check.py --chunks --plant-13008
red "0x12110f не постоянная метка" $PY tests/light/light_check.py --chunks --plant-12110f
green "0x13008 и 0x12110f на всём диске" $PY tests/light/light_check.py --chunks

# 2. разбор в движке
cc -O1 -Wall -DSKIN_HOST -o build/gates/light/parse_host tests/light/parse_host.c || { echo "GATE FAIL (parse_host не собрался)"; exit 1; }
for p in sum ver cut; do red "LGT1 уровня 6: $p" build/gates/light/parse_host "$(lv 6)" "$p"; done
red "level.shr уровня 6 до света уровня (CAR1 v2/v1)" build/gates/light/parse_host build/levels/l6/level_pre_light.shr
parse_ok() {   # движок прочитал свет уровня N; цвета персонажей = skin.h × множители (как считает tools/level_light.py)
  local n="$1" out; out=$(build/gates/light/parse_host "$(lv "$n")") || { echo "$out"; return 1; }; echo "$out"
  $PY - "$n" "$out" <<'EOF'
import sys, re; sys.path.insert(0, 'tools'); import level_light as ll
n, out = int(sys.argv[1]), sys.argv[2]; kv = dict(re.findall(r'(\w+)=(\S+)', out)); L = ll.level_light(n); _, sun, amb = ll.skin_consts()
sc = lambda c, s: (c & 0xff000000) | sum(min(255, int(((c >> (8 * i)) & 255) * s[i] + .5)) << (8 * i) for i in range(3))
want = dict(level=str(n), skinSun='%08x' % sc(sun, L['dirS']), skinAmb='%08x' % sc(amb, L['ambS']))
bad = [k for k, v in want.items() if kv.get(k) != v]
print('движок:', {k: kv.get(k) for k in want}, 'ждали', want); sys.exit(1 if bad else 0)
EOF
}
for n in 1 2 3 4 5 6 7; do green "движок читает свет уровня $n" parse_ok $n; done

# 3. блок и светотень против диска
red "уровень 6: level.shr и traffic.shr до света уровня (день)" $PY tests/light/light_check.py --level 6 --shr build/levels/l6/level_pre_light.shr --traffic build/levels/l6/traffic_pre_light.shr
red "уровень 6: в LGT1 — дневной свет уровня 1" $PY tests/light/light_check.py --level 6 --plant-lgt1 1
$PY tests/light/plant_day.py build/levels/l6/level.shr build/levels/l6/level_pre_light.shr > build/gates/light/l6_day.shr 2>> "$LOG" &&
  red "уровень 6: машина в дневной светотени, CAR1 v2 (tests/light/plant_day.py)" $PY tests/light/light_check.py --level 6 --shr build/gates/light/l6_day.shr
red "уровень 4: трафик до света уровня" $PY tests/light/light_check.py --level 4 --traffic build/levels/l4/traffic_pre_light.shr
green "уровень 1 побайтно прежний, кроме CAR1 (v3 + LGT1)" $PY tests/light/light_check.py --level 1 --same-as build/levels/l1/level_pre_light.shr
green "уровни 1–7: свет и светотень = диск" $PY tests/light/light_check.py --level 1 2 3 4 5 6 7
[ $FAILS = 0 ] && echo "GATE PASS" | tee -a "$LOG" || echo "GATE FAIL ($FAILS)" | tee -a "$LOG"
echo "журнал: $LOG"
[ $FAILS = 0 ]
