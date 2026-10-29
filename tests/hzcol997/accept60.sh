#!/bin/bash
# №997 приёмка (окно «Управление», TEST71): лента горизонта красится цветом фасадов дальних домов (хвост HCL1 в horizon.shr, расчёт на Маке: средний цвет текстуры × свет вершин, палитра 16 цветов,
# смешано с прежним тоном силуэта по расстоянию), ниже горизонта (дальняя земля) прежний цвет. Выключатели: HZCOL997_OLD=1 / файл hzcol997old рядом с EBOOT / flag hzcol997 0. Последняя строка: PASS или FAIL.
#   tests/hzcol997/accept60.sh      данные: HZDATA (по умолчанию ~/Downloads/shar-psp/build/t71/data_hzcol997: horizon.shr, l2..l7/horizon.shr с хвостом HCL1; собираются tools/horizon_export.py, ~10 мин на 4 процессах)
#                                   SRC — набор тура TEST70 (данные без хвоста: красный контроль и прежний движок); REUSE=1 — не пересобирать EBOOT
export PATH=$HOME/Downloads/shar-psp/build/xcshim/bin:$PATH
set -u
W="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$W"
export PSPDEV=$W/pspdev PATH=$W/pspdev/bin:$PATH
T=$HOME/Downloads/shar-psp/build/t71; B=${B997_OUT:-$T/work_hzcol997}; SH=${B997_SHOTS:-$T/shots_hzcol997}; mkdir -p "$B" "$SH"
D=${HZDATA:-$T/data_hzcol997}; SRC=${SRC:-$HOME/Downloads/shar-psp-integ/build/test70tour/PSP/GAME/SHARTEST15}
export EMU_OWNER=Управление EMU_MINE=2; export OUT=$B
BASEF="-DJITTER_STRIPS_OLD=1 -DJITTER_CAR_OLD=1 -DFE_DEMO_PS2_OLD=1 -DBB_SYNC_OLD=1 -DZF932_OLD=1"
rc=0; say() { echo "$*"; }
f1() { [ "$1" = 1 ] && echo "$D/horizon.shr" || echo "$D/l$1/horizon.shr"; }
# --- 1 формат
F=(); for L in 1 2 3 4 5 6 7; do F+=("$(f1 $L)"); done
say "— 1 формат: HCL1 и совместимость с прежним читателем (7 уровней)"; python3 tests/hzcol997/fmt.py "${F[@]}" | tail -2; python3 tests/hzcol997/fmt.py "${F[@]}" >/dev/null || rc=1
say "— красный: порча хвоста поймана"; python3 tests/hzcol997/fmt.py --red "$(f1 7)" | tail -6; python3 tests/hzcol997/fmt.py --red "$(f1 7)" >/dev/null || rc=1
say "— красный: прежние данные (без хвоста) не проходят"; if python3 tests/hzcol997/fmt.py "$SRC/l7/horizon.shr" >/dev/null; then say "  ЗЕЛЁНЫЙ (красный не пойман)"; rc=1; else say "  красный (как нужно)"; fi
# --- 2 сборка
build() { [ "${REUSE:-0}" = 1 ] && [ -f "$B/eboot_$1.PBP" ] && return 0
  ( cd viewer && psp-cmake -S . -B "build_b997_$1" -DSHAR_RELEASE=ON -DSHAR_RELEASE_KEEP_DIAG=ON -DSHAR_RELEASE_KEEP_HUD=ON -DSHAR_RELEASE_KEEP_SMOKE=ON -DCMAKE_C_FLAGS="$BASEF $2" >/dev/null 2>&1 \
    && cmake --build "build_b997_$1" -j4 >"$B/build_$1.log" 2>&1 && cp "build_b997_$1/EBOOT.PBP" "$B/eboot_$1.PBP" ); }
build new "" & build old "-DHZCOL997_OLD=1" & wait
for v in new old; do [ -f "$B/eboot_$v.PBP" ] || { echo "нет сборки $v ($B/build_$v.log)"; echo FAIL; exit 2; }; done
# --- 3 наборы: с хвостом (SETN) и прежний
SETN=$B/set_new; rm -rf "$SETN"; cp -c -R "$SRC" "$SETN" && cp "$(f1 1)" "$SETN/horizon.shr" && for L in 2 3 4 5 6 7; do cp "$(f1 $L)" "$SETN/l$L/horizon.shr"; done
run() { SET=$3 bash tools/emu_run.sh "tests/hzcol997/$2_scenario.txt" "$1" "$4" 240 >/dev/null 2>&1 || true; }   # run ИМЯ СЦЕНАРИЙ НАБОР EBOOT -> $B/out_ИМЯ
for L in 1 2 4 5 7; do run hi${L}_new hi_l$L "$SETN" "$B/eboot_new.PBP" & run hi${L}_old hi_l$L "$SETN" "$B/eboot_old.PBP" & wait; done
run c_flag0 hi_l2_flag0 "$SETN" "$B/eboot_new.PBP" & run c_olddata hi_l2 "$SRC" "$B/eboot_new.PBP" & wait
run c_t70 hi_l2 "$SETN" "$SRC/EBOOT.PBP" & wait
# --- 4 кадры: лента меняется (не пусто), не выпрыгивает (мало и мягко), красные контроли
python3 - "$B" "$SH" <<'PY' || rc=1
import sys, re
from pathlib import Path
from PIL import Image
import numpy as np
B, SH = Path(sys.argv[1]), Path(sys.argv[2]); ok = True
def diff(a, b, pref, views):
    n = 0; ds = []
    for i in views:
        A = np.array(Image.open(B / f'out_{a}/{pref}_d{i}.png').convert('RGB')).astype(int); C = np.array(Image.open(B / f'out_{b}/{pref}_d{i}.png').convert('RGB')).astype(int)
        d = np.abs(A - C).sum(2); m = d > 6; n += int(m.sum()); ds += list(d[m] / 3.0)
    return n, (float(np.mean(ds)) if ds else 0.0)
def cost(name):
    t = (B / f'out_{name}/smoke.txt').read_text(); v = sorted(int(x) for x in re.findall(r'HORIZON cost level=\d+ avg_us=(\d+)', t)); return v[len(v) // 2] if v else -1
views = {1: (2, 3), 2: (0, 5), 4: (3, 5), 5: (0, 1), 7: (3, 5)}
print('— 4 кадры дальних видов (A/B флагом hzcol997 на одних данных: новый EBOOT и EBOOT -DHZCOL997_OLD=1), по два вида на уровень')
for L, vs in views.items():
    n, md = diff(f'hi{L}_old', f'hi{L}_new', f'h{L}', vs); cn, co = cost(f'hi{L}_new'), cost(f'hi{L}_old')
    good = n >= 400 and md <= 60 and (cn - co) * 5.8 <= 150
    ok &= good
    print(f'  L{L}: изменилось {n} px (≥ 400), средняя правка {md:.0f}/255 на канал (≤ 60), цена ленты (медиана окон, Мак) {cn} мкс против {co}: +{(cn - co) * 5.8:.0f} мкс PSP (≤ 150) {"ok" if good else "ПАДАЕТ"}')
print('— красные контроли на L2 (виды 0, 5): те же кадры, что у нового, но лента прежняя — изменение обязано быть пустым')
for nm, lab in (('c_flag0', 'flag hzcol997 0 на новой сборке'), ('c_olddata', 'новая сборка на данных без хвоста')):
    n, md = diff('hi2_old', nm, 'h2', (0, 5))
    red = n < 400
    ok &= red; print(f'  {lab}: изменилось {n} px против прежней: {"красный (как нужно)" if red else "ЗЕЛЁНЫЙ — лента осталась цветной (красный не пойман)"}')
t = (B / 'out_c_t70/smoke.txt').read_text(); m = re.findall(r'HZLOAD level=2 bytes=(\d+) dst=(\d)', t); f = len(re.findall(r'FAULT|STALL', t))
good = bool(m) and m[0][1] == '1' and f == 0; ok &= good
print(f'— прежний движок (EBOOT TEST70) читает новые данные: HZLOAD level=2 bytes={m[0][0] if m else "-"} dst={m[0][1] if m else "-"}, сбоев {f}: {"ok" if good else "ПАДАЕТ"}')
# листы TEST70 / стало: слева прежнее (флаг), справа новое
for L, vs in views.items():
    rows = []
    for i in vs:
        im = Image.new('RGB', (966, 272), (30, 30, 30)); im.paste(Image.open(B / f'out_hi{L}_old/h{L}_d{i}.png').convert('RGB'), (0, 0)); im.paste(Image.open(B / f'out_hi{L}_new/h{L}_d{i}.png').convert('RGB'), (486, 0)); rows.append(im)
    s = Image.new('RGB', (966, 276 * len(rows)), (30, 30, 30))
    for k, r in enumerate(rows): s.paste(r, (0, 276 * k))
    s.save(SH / f'test70_stalo_L{L}.png')
print('листы:', SH)
sys.exit(0 if ok else 1)
PY
[ $? = 0 ] || rc=1
[ $rc = 0 ] && echo PASS || echo FAIL
exit $rc
