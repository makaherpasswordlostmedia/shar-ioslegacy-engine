#!/bin/bash
# Правка 309 (04.10): PPSSPPHeadlessPad — безоконный PPSSPP близнецов (tools/twins/ppsspp_build.sh) с двумя добавками для гейта окна
# сохранения PSP (tests/savegame/dialog/run.py), заплатка tools/twins/ppsspp_headless_pad.patch поверх заплатки близнецов:
#   строка "TWPAD hex" в smoke.txt -> кнопки в контроллере эмулятора (окна системной утилиты читают его, а не pad.Buttons игры;
#   движок пишет её из viewer/main.c svmDialogFrame, пока окно на экране); TWINS_PPGE=1 -> атлас PPGe (буквы окон на снимках).
# Не пересобирает PPSSPP: компилирует один headless/Headless.cpp с флагами готовой сборки близнецов и линкует с её объектами и
# библиотеками (минуты нет — секунды). Общий PPSSPPHeadless, его папка сборки и исходники не меняются: копия файла — во временной папке.
#   tools/twins/ppsspp_pad_build.sh [--check]   -> <данные>/build/twins/bin/PPSSPPHeadlessPad (рядом assets, SDL2.framework)
set -e
HERE="$(cd "$(dirname "$0")/../.." && pwd)"
DATA="${TWINS_ROOT:-$(cd "$HERE" && cd "$(git rev-parse --git-common-dir 2>/dev/null || echo .git)/.." && pwd)}"
CACHE="${TWINS_PPSSPP:-$DATA/build/twins/ppsspp}"; SRC="$CACHE/src"; BLD="$CACHE/build"; BIN="$DATA/build/twins/bin"
OUT="$BIN/PPSSPPHeadlessPad"
if [ "$1" = "--check" ]; then
  [ -x "$OUT" ] && strings "$OUT" | grep -q "TWPAD %x" && { echo "OK: $OUT"; exit 0; }
  echo "НЕТ: $OUT — запустить tools/twins/ppsspp_pad_build.sh"; exit 1
fi
D="$BLD/CMakeFiles/PPSSPPHeadless.dir"
[ -f "$D/flags.make" ] && [ -f "$D/link.txt" ] && grep -q "SHAR twins" "$SRC/headless/Headless.cpp" \
  || { echo "FAIL: нет сборки близнецов в $CACHE (tools/twins/ppsspp_build.sh)"; exit 1; }
# сборка близнецов могла настраиваться в другой рабочей копии: её пути в флагах -> нынешние
OLDSRC=$(sed -n 's/^CMAKE_HOME_DIRECTORY:INTERNAL=//p' "$BLD/CMakeCache.txt"); OLDBLD=$(sed -n 's/^CMAKE_CACHEFILE_DIR:INTERNAL=//p' "$BLD/CMakeCache.txt")
fix() { sed -e "s#$OLDSRC#$SRC#g" -e "s#$OLDBLD#$BLD#g"; }
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
cp "$SRC/headless/Headless.cpp" "$TMP/Headless.cpp"
patch -s -d "$TMP" -p2 < "$HERE/tools/twins/ppsspp_headless_pad.patch" || { echo "FAIL: заплатка ppsspp_headless_pad.patch не легла"; exit 1; }
DEF=$(sed -n 's/^CXX_DEFINES = //p' "$D/flags.make"); INC=$(sed -n 's/^CXX_INCLUDES = //p' "$D/flags.make" | fix)
FL=$(sed -n 's/^CXX_FLAGS = //p' "$D/flags.make" | fix)
eval nice -n 10 /usr/bin/c++ $DEF -I"$SRC/headless" $INC $FL -c "$TMP/Headless.cpp" -o "$TMP/Headless.cpp.o" 2> "$TMP/cc.log" \
  || { grep -m5 error "$TMP/cc.log"; exit 1; }
L=$(fix < "$D/link.txt" | sed -e "s#CMakeFiles/PPSSPPHeadless.dir/headless/Headless.cpp.o#$TMP/Headless.cpp.o#" \
      -e "s#CMakeFiles/PPSSPPHeadless.dir/headless/\([A-Za-z]*\).cpp.o#$D/headless/\1.cpp.o#g" -e "s# lib/# $BLD/lib/#g" \
      -e "s#-o PPSSPPHeadless#-o $TMP/PPSSPPHeadlessPad#")
mkdir -p "$BIN"; ( cd "$BLD" && eval nice -n 10 $L ) 2> "$TMP/ld.log" || { grep -m5 -i error "$TMP/ld.log"; exit 1; }
cp -f "$TMP/PPSSPPHeadlessPad" "$OUT"
[ -d "$BIN/assets" ] || cp -R "$SRC/assets" "$BIN/assets"
[ -d "$BIN/SDL2.framework" ] || cp -R "$SRC/SDL/macOS/SDL2.framework" "$BIN/SDL2.framework"
install_name_tool -add_rpath @executable_path "$OUT" 2>/dev/null; codesign -f -s - "$OUT" 2>/dev/null
echo "OK: $OUT (близнецы + TWPAD + TWINS_PPGE)"
