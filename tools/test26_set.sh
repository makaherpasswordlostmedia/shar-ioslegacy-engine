#!/bin/bash
# TEST26: полный набор для карты целиком (не дельта) из коммитов магистрали claude/trunk-1016.
#   tools/test26_set.sh   ->  build/test26 (игровая сборка: SHAR_RELEASE + KEEP_DIAG + KEEP_HUD) и build/test26tour (то же + KEEP_SMOKE + пустой smokelog, scenario.txt кладёт Карта/дирижёр)
# Данные = файлы из `SHIP_LEVELS="2 3 4 5 6 7" tools/ship_files.sh --pairs` (без служебных json, nojitter, сценариев) из пакета DATA (по умолчанию build/t24d_emu: far2_out уровни, UI, всё как в TEST25),
# звук L2/L5 с музыкой клуба из build/audio25; pv2s.shr не кладётся. Манифест SHA-256 всех файлов: MANIFEST_SHA256.txt рядом с PSP/.
set -e
cd "$(dirname "$0")/.."
export PSPDEV="$HOME/Downloads/shar-psp/pspdev" PATH="$HOME/Downloads/shar-psp/pspdev/bin:$PATH"
DATA=${DATA:-build/t24d_emu}
[ -z "$(git status --porcelain --untracked-files=no)" ] || { echo "рабочая копия не чистая: собирать только из коммитов"; git status --short | grep -v '^??'; exit 1; }
JF="-DJITTER_STRIPS_OLD=1 -DJITTER_CAR_OLD=1"
build_cfg() {   # имя, доп. ключи
  ( cd viewer && [ -d build_$1 ] || psp-cmake -S . -B build_$1 -DSHAR_RELEASE=ON -DSHAR_RELEASE_KEEP_DIAG=ON -DSHAR_RELEASE_KEEP_HUD=ON $2 -DCMAKE_C_FLAGS="$JF" >/dev/null 2>&1
    cmake --build build_$1 2>&1 | grep -E "error|Built target" || true )
}
build_cfg t26game ""
build_cfg t26tour "-DSHAR_RELEASE_KEEP_SMOKE=ON"
mkset() {   # имя_набора, build_dir, подпись флагов, smokelog(0/1)
  O=build/$1; D=$O/PSP/GAME/SHARTEST15; rm -rf $O; mkdir -p $D
  EBOOT_SRC=viewer/$2/EBOOT.PBP tools/pack_test.sh "SHAR ${TITLE:-TEST26}" build/$1_pack >/dev/null
  cp build/$1_pack/PSP/GAME/SHARTEST15/EBOOT.PBP $D/
  SHIP_LEVELS="2 3 4 5 6 7" tools/ship_files.sh --pairs | cut -d'|' -f1 | while read f; do mkdir -p "$D/$(dirname "$f")"; cp -c "$DATA/$f" "$D/$f" 2>/dev/null || cp "$DATA/$f" "$D/$f"; done
  for n in 2 5; do cp build/audio25/l$n/audio/sfx.sab build/audio25/l$n/audio/music.sap $D/l$n/audio/; done
  [ "$4" = 1 ] && touch $D/smokelog
  cp build/$1_pack/BUILD_INFO.txt $O/BUILD_INFO.txt
  sed -i '' "s|^флаги сборки:.*|флаги сборки: $3 $JF; DD_SIGMA_ON=0 TQ_FAST_ON=0 (по коду магистрали)|" $O/BUILD_INFO.txt
  ( cd $D && find . -type f | sort | while read f; do printf "%s  %s\n" "$(shasum -a 256 "$f" | cut -d' ' -f1)" "$f"; done ) > $O/MANIFEST_SHA256.txt
  echo "$1: $(wc -l < $O/MANIFEST_SHA256.txt) файлов, EBOOT $(shasum -a 256 $D/EBOOT.PBP | cut -c1-8)"
}
mkset ${SN:-test26} build_t26game "SHAR_RELEASE=ON SHAR_RELEASE_KEEP_DIAG=ON SHAR_RELEASE_KEEP_HUD=ON (игровая сборка)" 0
mkset ${SN:-test26}tour build_t26tour "SHAR_RELEASE=ON SHAR_RELEASE_KEEP_DIAG=ON SHAR_RELEASE_KEEP_HUD=ON SHAR_RELEASE_KEEP_SMOKE=ON (тур-сборка; scenario.txt кладётся отдельно)" 1
[ -f "${SCN:-}" ] && { cp "$SCN" build/${SN:-test26}tour/PSP/GAME/SHARTEST15/scenario.txt; ( cd build/${SN:-test26}tour/PSP/GAME/SHARTEST15 && echo "$(shasum -a 256 scenario.txt | cut -d" " -f1)  ./scenario.txt" >> ../../../MANIFEST_SHA256.txt ); echo "сценарий: $SCN"; }
# обязательный гейт «КАДР ИГРОКА» (Аудит-FPS, tools/frame_gate.sh): нет PASS — нет набора. Тур-конфигурация того же кода на данных каждого набора; лист: build/<имя>_gate/frame_gate_sheet.png
[ "${GATE:-1}" = 1 ] && {
  for s in ${SN:-test26}tour ${SN:-test26}; do
    tools/frame_gate.sh viewer/build_t26tour/EBOOT.PBP build/$s/PSP/GAME/SHARTEST15 build/${s}_gate || { echo "frame_gate: НЕТ PASS для $s — набор не годится"; exit 1; }
  done
}
