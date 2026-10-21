#!/bin/bash
# Близнецы (docs/handoff/БЛИЗНЕЦЫ_2026-10-01.md §1): свой PPSSPP без окна для стороны «Порт, полный».
# Сборка PPSSPPHeadless из открытого кода PPSSPP (GPL-2.0) той же версии, что общий PPSSPPSDL (1.20.4), с заплаткой
# tools/twins/ppsspp_headless.patch: кадр по строке "SHOT имя" в smoke.txt движка (как tools/ppsspp_run.sh, но без окна).
# Общий PPSSPPSDL, его ~/.config/ppsspp и tools/ppsspp_run.sh не трогает: у нашей копии своя папка (HOME=build/twins/ppsspp_home).
#   tools/twins/ppsspp_build.sh [--check]    собрать (если нет) и поставить в <данные>/build/twins/bin/; --check — только проверить
# Процессор: сборка с nice 19 и TWINS_J (по умолчанию 2) потоками — ночью ядра у ботов, мы берём только свободное.
set -e
HERE="$(cd "$(dirname "$0")/../.." && pwd)"                       # рабочая копия с кодом (worktree или main)
DATA="${TWINS_ROOT:-$(cd "$HERE" && cd "$(git rev-parse --git-common-dir)/.." && pwd)}"   # данные: основная папка проекта
VER=v1.20.4
CACHE="${TWINS_PPSSPP:-$HERE/build/twins/ppsspp}"; SRC="$CACHE/src"; BLD="$CACHE/build"
BIN="$DATA/build/twins/bin"
if [ "$1" = "--check" ]; then
  [ -x "$BIN/PPSSPPHeadless" ] && [ -d "$BIN/assets/flash0" ] && grep -q "SHAR twins" "$SRC/headless/Headless.cpp" 2>/dev/null \
    && { echo "OK: $BIN/PPSSPPHeadless ($VER + заплатка близнецов)"; exit 0; }
  echo "НЕТ: $BIN/PPSSPPHeadless — запустить tools/twins/ppsspp_build.sh"; exit 1
fi
mkdir -p "$CACHE" "$BIN"
if [ ! -d "$SRC/.git" ]; then
  git clone --depth 1 --branch "$VER" https://github.com/hrydgard/ppsspp.git "$SRC"
  ( cd "$SRC" && git submodule update --init --depth 1 ext/armips ext/glslang ext/SPIRV-Cross ext/rapidjson ext/zstd SDL/macOS \
      ext/cpu_features ext/rcheevos ext/naett ext/libchdr ext/lua ext/freetype ext/nanosvg ext/aemu_postoffice ios/MoltenVK \
      ext/miniupnp ext/discord-rpc ext/OpenXR-SDK ext/libadrenotools && cd ext/armips && git submodule update --init --recursive --depth 1 )
fi
[ -f "$BLD/CMakeCache.txt" ] && ! grep -q "Configuring done" "$BLD/configure.log" 2>/dev/null && rm -f "$BLD/CMakeCache.txt"   # прошлая настройка упала
if ! grep -q "SHAR twins" "$SRC/headless/Headless.cpp"; then ( cd "$SRC" && git apply "$HERE/tools/twins/ppsspp_headless.patch" ); fi
mkdir -p "$BLD"; cd "$BLD"
# _DARWIN_C_SOURCE: FileUtil.cpp объявляет _POSIX_SOURCE, а SDK macOS 26 тогда прячет fseeko/ftello/ftruncate
grep -q "_DARWIN_C_SOURCE" CMakeCache.txt 2>/dev/null || rm -f CMakeCache.txt
[ -f CMakeCache.txt ] || nice -n 19 cmake "$SRC" -DCMAKE_BUILD_TYPE=Release -DHEADLESS=ON -DUSE_FFMPEG=OFF -DUSE_DISCORD=OFF \
  -DUSE_MINIUPNPC=OFF -DUSE_CCACHE=OFF -DUNITTEST=OFF -DATLAS_TOOL=OFF \
  -DCMAKE_C_FLAGS=-D_DARWIN_C_SOURCE -DCMAKE_CXX_FLAGS=-D_DARWIN_C_SOURCE > configure.log 2>&1 || { tail -30 configure.log; exit 1; }
nice -n 19 cmake --build . --target PPSSPPHeadless -j "${TWINS_J:-2}" > build.log 2>&1 || { grep -m5 -B2 -A8 "error" build.log; exit 1; }
cp -f "$BLD/PPSSPPHeadless" "$BIN/PPSSPPHeadless"
rm -rf "$BIN/assets" "$BIN/SDL2.framework"; cp -R "$SRC/assets" "$BIN/assets"
cp -R "$SRC/SDL/macOS/SDL2.framework" "$BIN/SDL2.framework"   # ссылка @rpath/SDL2 (рендер программный, окно SDL не создаётся); DYLD_FRAMEWORK_PATH=bin
# 03.10: запуск через nice (scen.py, порт) срезает DYLD_* (SIP), и бинарник жил только старым rpath папки сборки — после снятия
# рабочей копии эмулятор перестал стартовать (rc -6). Rpath «рядом с собой»: bin/SDL2.framework находится без переменных окружения
install_name_tool -add_rpath @executable_path "$BIN/PPSSPPHeadless" 2>/dev/null; codesign -f -s - "$BIN/PPSSPPHeadless" 2>/dev/null
echo "OK: $BIN/PPSSPPHeadless ($VER + заплатка близнецов)"
