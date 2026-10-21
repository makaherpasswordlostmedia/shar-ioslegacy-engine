#!/bin/bash
# TEST27: полный набор для карты из коммитов магистрали claude/trunk-1016 (16.10 вечер). Основа test26_set.sh + наложения:
#   уровни L1 reissue2, L4 reissue3, L7 прежний (level, mcpr, lmap; shar-psp-urovni-w/build), traffic.shr L1..L7 (shar-psp-persony-w/build/trf_release),
#   интерфейс ui-pkg-v10 (shar-psp-hud623/build/ui-pkg-v10; файлы, которые уже есть в наборе), interiors-l1(-gfx).bin перевыпуск №301 (build/ceil301), fonts-license из пакета данных, пустые файлы hudon и pfetchold рядом с EBOOT,
#   название EBOOT «SHAR TEST27» (tools/eboot_title.py --preset test27). prereadold НЕ кладётся (PREREAD включён), loadsilent/newsiris/fogskyold тоже нет.
#   tools/test27_set.sh -> build/test27 (игровая: RELEASE+KEEP_DIAG+KEEP_HUD+JITTER_*_OLD) и build/test27tour (+KEEP_SMOKE, ящик синхронный -DBB_SYNC_OLD=1; scenario.txt кладёт тот, кому нужен тур)
#   SN=имя меняет имя набора. Манифест SHA-256: MANIFEST_SHA256.txt рядом с PSP/. frame_gate обязателен (нет PASS — выход 1)
set -e
cd "$(dirname "$0")/.."
export PSPDEV="$HOME/Downloads/shar-psp/pspdev" PATH="$HOME/Downloads/shar-psp/pspdev/bin:$PATH"
DATA=${DATA:-build/t24d_emu}; CEIL=${CEIL_SRC:-build/ceil301}
LV=${LV_SRC:-$HOME/Downloads/shar-psp-urovni-w/build}; TRF=${TRF_SRC:-$HOME/Downloads/shar-psp-persony-w/build/trf_release}; UI=${UI_SRC:-$HOME/Downloads/shar-psp-hud623/build/ui-pkg-v10}
[ -z "$(git status --porcelain --untracked-files=no)" ] || { echo "рабочая копия не чистая: собирать только из коммитов"; git status --short | grep -v '^??'; exit 1; }
for d in $LV/reissue2/l1 $LV/reissue3/l4 $TRF $UI; do [ -d "$d" ] || { echo "нет источника $d"; exit 1; }; done
JF="-DJITTER_STRIPS_OLD=1 -DJITTER_CAR_OLD=1"
build_cfg() {   # имя, доп. ключи, доп. флаги C
  ( cd viewer && { [ -d build_$1 ] || psp-cmake -S . -B build_$1 -DSHAR_RELEASE=ON -DSHAR_RELEASE_KEEP_DIAG=ON -DSHAR_RELEASE_KEEP_HUD=ON $2 -DCMAKE_C_FLAGS="$JF $3" >/dev/null 2>&1; }
    cmake --build build_$1 2>&1 | grep -E "error|Built target" || true )
}
build_cfg t27game "" ""
build_cfg t27tour "-DSHAR_RELEASE_KEEP_SMOKE=ON" "-DBB_SYNC_OLD=1"
ovl() {   # D: папка игры; наложения поверх пакета данных
  local A; A=$(cd $D && pwd)
  for f in level mcpr lmap; do cp $LV/reissue2/l1/$f.shr $D/$f.shr; cp $LV/reissue3/l4/$f.shr $D/l4/$f.shr; done   # L7 — прежний far2_out (reissue2/l7 красный по humps G: капсула 459 твёрдая, слово Дирижёра 16.10)
  cp $TRF/l1/traffic.shr $D/traffic.shr; for n in 2 3 4 5 6 7; do cp $TRF/l$n/traffic.shr $D/l$n/traffic.shr; done
  ( cd $UI && find . -type f ! -path './logs/*' ! -name '*.fonts' | sort | while read f; do [ -e "$A/$f" ] && cp "$UI/$f" "$A/$f" || echo "  ui-pkg-v10: в наборе нет $f (не кладу)"; done )
  [ -d $DATA/fonts-license ] && { rm -rf $D/fonts-license; cp -R $DATA/fonts-license $D/fonts-license; }
  # №301 потолок дома (Стены e83cc928): interiors-l1(-gfx).bin перевыпускаются (SHR_TEX_CAP256=1 SHR_SMALL_MIPS=1 SHR_LAYERS=1 tools/interior_export.py --level 1 --outdir build/ceil301); L2–L7 не перевыпускались
  [ "$(shasum -a 256 $CEIL/interiors-l1-gfx.bin | cut -c1-8)" = 5171a6be ] && [ "$(shasum -a 256 $CEIL/interiors-l1.bin | cut -c1-8)" = d7b48d05 ] || { echo "interiors-l1 из $CEIL не совпали по SHA с 301 (5171a6be / d7b48d05)"; exit 1; }
  cp $CEIL/interiors-l1-gfx.bin $CEIL/interiors-l1.bin $D/
  : > $D/hudon; : > $D/pfetchold
}
mkset() {   # имя_набора, build_dir, подпись флагов, smokelog(0/1)
  O=build/$1; D=$O/PSP/GAME/SHARTEST15; rm -rf $O; mkdir -p $D
  EBOOT_SRC=viewer/$2/EBOOT.PBP tools/pack_test.sh "SHAR ${TITLE:-TEST27}" build/$1_pack >/dev/null
  python3 tools/eboot_title.py build/$1_pack/PSP/GAME/SHARTEST15/EBOOT.PBP --preset test27 $D/EBOOT.PBP >/dev/null
  SHIP_LEVELS="2 3 4 5 6 7" tools/ship_files.sh --pairs | cut -d'|' -f1 | while read f; do mkdir -p "$D/$(dirname "$f")"; cp -c "$DATA/$f" "$D/$f" 2>/dev/null || cp "$DATA/$f" "$D/$f"; done
  for n in 2 5; do cp build/audio25/l$n/audio/sfx.sab build/audio25/l$n/audio/music.sap $D/l$n/audio/; done
  ovl
  [ "$4" = 1 ] && touch $D/smokelog
  cp build/$1_pack/BUILD_INFO.txt $O/BUILD_INFO.txt
  sed -i '' "s|^флаги сборки:.*|флаги сборки: $3 $JF; наложения: L1 reissue2, L4 reissue3, L7 прежний far2_out, traffic trf_release, ui-pkg-v10; файлы hudon, pfetchold; коммит $(git rev-parse --short HEAD)|" $O/BUILD_INFO.txt
  ( cd $D && find . -type f | sort | while read f; do printf "%s  %s\n" "$(shasum -a 256 "$f" | cut -d' ' -f1)" "$f"; done ) > $O/MANIFEST_SHA256.txt
  echo "$1: $(wc -l < $O/MANIFEST_SHA256.txt) файлов, EBOOT $(shasum -a 256 $D/EBOOT.PBP | cut -c1-8)"
}
mkset ${SN:-test27} build_t27game "SHAR_RELEASE=ON SHAR_RELEASE_KEEP_DIAG=ON SHAR_RELEASE_KEEP_HUD=ON (игровая сборка, ящик фоном)" 0
mkset ${SN:-test27}tour build_t27tour "SHAR_RELEASE=ON SHAR_RELEASE_KEEP_DIAG=ON SHAR_RELEASE_KEEP_HUD=ON SHAR_RELEASE_KEEP_SMOKE=ON BB_SYNC_OLD=1 (тур-сборка; scenario.txt кладётся отдельно)" 1
[ -f "${SCN:-}" ] && { cp "$SCN" build/${SN:-test27}tour/PSP/GAME/SHARTEST15/scenario.txt; ( cd build/${SN:-test27}tour/PSP/GAME/SHARTEST15 && echo "$(shasum -a 256 scenario.txt | cut -d' ' -f1)  ./scenario.txt" >> ../../MANIFEST_SHA256.txt ); }
[ "${GATE:-1}" = 1 ] && {
  for s in ${SN:-test27}tour ${SN:-test27}; do
    tools/frame_gate.sh viewer/build_t27tour/EBOOT.PBP build/$s/PSP/GAME/SHARTEST15 build/${s}_gate || { echo "frame_gate: НЕТ PASS для $s — набор не годится"; exit 1; }
  done
}
echo "готово: build/${SN:-test27} и build/${SN:-test27}tour"
