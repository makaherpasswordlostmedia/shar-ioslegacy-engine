#!/bin/bash
# Общее окружение гейтов tests/*/gate.sh (TEST60, «Чистота»): подключается строкой
#   ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; . "$ROOT/tools/gate_env.sh"
# Даёт ROOT, RUN (общий раннер tools/emu_run.sh: СЦЕНАРИЙ ИМЯ EBOOT [МАКС_С] -> $OUT/out_ИМЯ/smoke.txt), PY (python с numpy/PIL), EMU_OWNER (для общей очереди эмуляторов).
# Гейт сам ставит W (рабочая папка, по умолчанию build/gates/<имя>) и export OUT=$W — итоги прогонов лежат в $W/out_ИМЯ. Окно-хозяин не нужно: старые раннеры ~/.claude/jobs/shar1023/.../run5x.sh удалены.
# Переопределяется снаружи: RUN, PY, SET (набор данных, по умолчанию тур TEST59 внутри emu_run.sh), OVL (наложение данных), EMU_OWNER, EMU_SLOTS, EMU_MINE.
ROOT=${ROOT:-"$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"}
RUN=${RUN:-$ROOT/tools/emu_run.sh}
PY=${PY:-$ROOT/.venv/bin/python}; [ -x "$PY" ] || PY=python3
export EMU_OWNER=${EMU_OWNER:-gates}
export SET=${SET:-$HOME/Downloads/shar-psp-integ/build/test59tour/PSP/GAME/SHARTEST15}
[ -f "$SET/EBOOT.PBP" ] || { echo "гейт: нет набора данных $SET (задайте SET=папка с level.shr и EBOOT.PBP)" >&2; exit 2; }
# Сборка EBOOT тура со смоуком (набор TEST60): tour_build ПАПКА [-DЧТО_OLD=1 ...] -> $ROOT/viewer/ПАПКА/EBOOT.PBP (инкрементально; красный контроль = тот же набор + -D..._OLD=1 в отдельную папку)
tour_build() {
  local nm="$1" d="$ROOT/viewer/$1" lg="$ROOT/build/gates/tour_logs"; mkdir -p "$lg"; shift
  ( export PATH="$HOME/Downloads/shar-psp/build/xcshim/bin:$PATH"; export PSPDEV="${PSPDEV:-$ROOT/pspdev}"; export PATH="$PSPDEV/bin:$PATH"
    psp-cmake -S "$ROOT/viewer" -B "$d" -DSHAR_RELEASE=ON -DSHAR_RELEASE_KEEP_DIAG=ON -DSHAR_RELEASE_KEEP_HUD=ON -DSHAR_RELEASE_KEEP_SMOKE=ON \
      -DCMAKE_C_FLAGS="-DJITTER_STRIPS_OLD=1 -DJITTER_CAR_OLD=1 -DFE_DEMO_PS2_OLD=1 -DBB_SYNC_OLD=1 $*" > "$lg/$nm.cmake.txt" 2>&1 && cmake --build "$d" -j4 > "$lg/$nm.build.txt" 2>&1 ) \
    || { echo "tour_build $nm: сборка упала (см. $lg/$1.build.txt)" >&2; return 1; }
  [ -f "$d/EBOOT.PBP" ]
}
