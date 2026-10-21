#!/bin/bash
# Стены по PS2 (аудит пропусков 09.10, пункт 5; docs/handoff/СТЕНЫ_СВЕРКА_PS2_2026-10-09.md): сверка «постановка машины» L1 по всем
# пробам оригинала (163 точки, сверено 137) — порт текущего кода против записанных проб PS2 (build/twins/placement/l1/orig.jsonl,
# сессии с трассами; PCSX2 не запускается).
#   зелёный: расходящихся точек не больше базы tests/walls/ps2_placement_base.json (код до правки), ни одна совпадавшая точка не
#            разошлась, и в каждой пробе, где машина PS2 переехала забор с изнанки на лицо, машина порта в конце разгона тоже на
#            лице этого забора (центр кузова по нормали > 0 м)
#   авто-возврат (агент физики 09.10, аудит п. 17): за покой машина порта не уносится через карту (> 50 м); красный -DCAR_BELLY_HOME_OLD=1
#   забор наискось вперёд (агент физики 09.10): три пробы PS2 «едет вдоль забора» у порта не встают; красный -DCAR_WALL_FRICTION_OLD=1
#   склон (агент физики 09.10): в постановках, где машина PS2 к «settled» ещё катится, порт стоит реже базы (slope_standing)
#   красный: тот же порт с -DCOL_FENCE_BACK_OLD=1 (прежнее: изнанка толкает дальше на изнанку) обязан упасть по замеру — порт не
#            выезжает на лицо; второй красный -DCAR_SLOPE_HOLD_OLD=1 (покой на любом склоне) обязан упасть по склону
# Данные проб — в основной папке проекта (TWINS_ROOT, по умолчанию git common dir), как у tools/twins/placement.py
set -u
cd "$(dirname "$0")/../.."
PY=${PY:-.venv/bin/python}; [ -x "$PY" ] || PY=python3
"$PY" tools/twins/walls_family.py --level 1 --gate | grep -v 'порт: проб'; g=${PIPESTATUS[0]}
"$PY" tools/twins/walls_family.py --level 1 --gate --cflags=-DCOL_FENCE_BACK_OLD=1 | grep -v 'порт: проб'; r=${PIPESTATUS[0]}
[ "$r" != 0 ] && echo "красный (-DCOL_FENCE_BACK_OLD=1) упал, как должен" || echo "КРАСНЫЙ НЕ УПАЛ: гейт ничего не доказывает"
"$PY" tools/twins/walls_family.py --level 1 --gate --cflags=-DCAR_SLOPE_HOLD_OLD=1 | grep -v 'порт: проб'; r2=${PIPESTATUS[0]}
[ "$r2" != 0 ] && echo "красный склона (-DCAR_SLOPE_HOLD_OLD=1) упал, как должен" || { echo "КРАСНЫЙ СКЛОНА НЕ УПАЛ"; r=0; }
"$PY" tools/twins/walls_family.py --level 1 --gate --cflags=-DCAR_WALL_FRICTION_OLD=1 | grep -v 'порт: проб'; r3=${PIPESTATUS[0]}
[ "$r3" != 0 ] && echo "красный забора наискось (-DCAR_WALL_FRICTION_OLD=1) упал, как должен" || { echo "КРАСНЫЙ ЗАБОРА НАИСКОСЬ НЕ УПАЛ"; r=0; }
"$PY" tools/twins/walls_family.py --level 1 --gate --cflags=-DCAR_BELLY_HOME_OLD=1 | grep -v 'порт: проб'; r4=${PIPESTATUS[0]}
[ "$r4" != 0 ] && echo "красный авто-возврата (-DCAR_BELLY_HOME_OLD=1) упал, как должен" || { echo "КРАСНЫЙ АВТО-ВОЗВРАТА НЕ УПАЛ"; r=0; }
if [ "$g" = 0 ] && [ "$r" != 0 ]; then echo "ps2 placement gate: PASS"; exit 0; fi
echo "ps2 placement gate: FAIL"; exit 1
