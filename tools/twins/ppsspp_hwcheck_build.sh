#!/bin/bash
# Эмулятор-проверяльщик «как железо» (правка 252, 03.10): тот же PPSSPPHeadless близнецов + tools/twins/ppsspp_hwcheck.patch.
# PPSSPP прощает то, на чём настоящая PSP падает целиком (skill shar-hw-freeze §4). Проверяльщик (только интерпретатор, -i) пишет
# каждое такое место с адресом команды и потоком:
#   FPE_V/FPE_Z/FPE_O — 0/0, ∞−∞, sqrt(<0), x/0, переполнение (у PSP ловушки V Z O включены: FCR31 0x00000e00 при старте потока)
#   FPE_VCMP/FPE_VCVT — сравнение c.lt/c.le с NaN, float->int вне диапазона · NAN_IN — арифметика над NaN из памяти
#   UNALIGNED — lh/sh по нечётному, lw/sw/lwc1/swc1/lv.s/sv.s не по 4, lv.q/sv.q не по 16 · BADADDR — вне карты памяти PSP
#   BREAK — break (деление целых на ноль) · STACKOVF — стек потока у дна; в конце HWSUM (счёт) и HWSTACK (глубина стека потоков)
# Переменные запуска: SHAR_HWCHK=1, SHAR_HWCHK_LOG=файл, SHAR_HWCHK_TRAP=1 — остановиться на первом месте, где PSP дала бы
# исключение (как железо). Запуск сценариев — tests/crash_f10/hw_run.py (scen.py с этим бинарником).
#   tools/twins/ppsspp_hwcheck_build.sh      -> build/twins/bin-hw/PPSSPPHeadless (обёртка -i) и PPSSPPHeadless.real
# Обычный build/twins/bin/PPSSPPHeadless не трогает. Первая сборка ~10 мин (TWINS_J потоков, по умолчанию 4), дальше — секунды.
set -e
HERE="$(cd "$(dirname "$0")/../.." && pwd)"
DATA="${TWINS_ROOT:-$(cd "$HERE" && cd "$(git rev-parse --git-common-dir)/.." && pwd)}"
SRC0="${HWCHK_SRC0:-$DATA/build/twins/ppsspp/src}"      # исходник эмулятора близнецов (tools/twins/ppsspp_build.sh)
W="$DATA/build/twins/ppsspp-hw"; BIN="$DATA/build/twins/bin-hw"; PATCH="$HERE/tools/twins/ppsspp_hwcheck.patch"
[ -f "$SRC0/headless/Headless.cpp" ] || { echo "нет $SRC0 — сначала tools/twins/ppsspp_build.sh"; exit 2; }
STAMP="$W/src/.hwcheck_patch.md5"; SUM=$(md5 -q "$PATCH")
if [ "$(cat "$STAMP" 2>/dev/null)" != "$SUM" ]; then
  rm -rf "$W/src"; mkdir -p "$W"; cp -c -R -p "$SRC0" "$W/src"        # копия APFS: место не тратит
  ( cd "$W/src" && patch -p1 -s < "$PATCH" ) || { echo "патч проверяльщика не лёг на $SRC0"; exit 1; }
  echo "$SUM" > "$STAMP"
fi
mkdir -p "$W/build"; cd "$W/build"
[ -f CMakeCache.txt ] || nice -n 19 cmake "$W/src" -DCMAKE_BUILD_TYPE=Release -DHEADLESS=ON -DUSE_FFMPEG=OFF -DUSE_DISCORD=OFF \
  -DUSE_MINIUPNPC=OFF -DUSE_CCACHE=OFF -DUNITTEST=OFF -DATLAS_TOOL=OFF \
  -DCMAKE_C_FLAGS=-D_DARWIN_C_SOURCE -DCMAKE_CXX_FLAGS=-D_DARWIN_C_SOURCE > configure.log 2>&1 || { tail -30 configure.log; exit 1; }
nice -n 19 cmake --build . --target PPSSPPHeadless -j "${TWINS_J:-4}" > build.log 2>&1 || { grep -m5 -B2 -A8 "error" build.log; exit 1; }
mkdir -p "$BIN"; cp -f PPSSPPHeadless "$BIN/PPSSPPHeadless.real"
ln -sfn ../bin/assets "$BIN/assets"; ln -sfn ../bin/SDL2.framework "$BIN/SDL2.framework"   # данные и SDL — общие с build/twins/bin
install_name_tool -add_rpath @executable_path "$BIN/PPSSPPHeadless.real" 2>/dev/null || true
codesign -f -s - "$BIN/PPSSPPHeadless.real" 2>/dev/null || true
cat > "$BIN/PPSSPPHeadless" <<'W'
#!/bin/bash
# проверки идут только в интерпретаторе: -i всегда (HWMODE=jit — без проверок, для сравнения скорости)
H="$(cd "$(dirname "$0")" && pwd)"
[ "${HWMODE:-int}" = jit ] && exec "$H/PPSSPPHeadless.real" "$@"
exec "$H/PPSSPPHeadless.real" -i "$@"
W
chmod +x "$BIN/PPSSPPHeadless"
echo "$BIN/PPSSPPHeadless"
