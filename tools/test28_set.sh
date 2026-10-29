#!/bin/bash
# TEST28 (из test27_set.sh): полный набор для карты из коммитов магистрали claude/trunk-1016 (16.10 вечер). Основа test26_set.sh + наложения:
#   уровни L1/L4/L7 reissue6 (level, mcpr, lmap; shar-psp-urovni-w/build), traffic.shr L1..L7 (shar-psp-persony-w/build/trf_release),
#   интерфейс ui-pkg-v10 (shar-psp-hud623/build/ui-pkg-v10; файлы, которые уже есть в наборе), interiors-l1(-gfx).bin перевыпуск №301 (build/ceil301), fonts-license из пакета данных, пустые файлы hudon и pfetchold рядом с EBOOT,
#   название EBOOT «SHAR TEST28» (tools/eboot_title.py --title "SHAR TEST28"). prereadold НЕ кладётся (PREREAD включён), loadsilent/newsiris/fogskyold тоже нет.
#   tools/test28_set.sh -> build/test28 (игровая: RELEASE+KEEP_DIAG+KEEP_HUD+JITTER_*_OLD) и build/test28tour (+KEEP_SMOKE, ящик асинхронный как у игрока; scenario.txt кладётся через SCN=файл)
#   FINAL=1: режим выпуска (SN=final): название «The Simpsons Hit & Run», без hudon, без тур-набора (тур-конфигурация собирается только для frame_gate); см. tools/release_build.sh
#   SN=имя меняет имя набора. Манифест SHA-256: MANIFEST_SHA256.txt рядом с PSP/. frame_gate обязателен (нет PASS — выход 1)
set -e
cd "$(dirname "$0")/.."
export PSPDEV="$HOME/Downloads/shar-psp/pspdev" PATH="$HOME/Downloads/shar-psp/pspdev/bin:$PATH"
DATA=${DATA:-build/t24d_emu}; if [ -z "${SCN:-}" ] && git cat-file -e a776d067 2>/dev/null; then SCN=build/tour28_scenario.txt; git show a776d067:tests/smoke_scenes/tour28.txt > $SCN; fi; CEIL=${CEIL_SRC:-build/ceil301}
LV=${LV_SRC:-$HOME/Downloads/shar-psp-urovni-w/build}; PERS=${PERS_SRC:-$HOME/Downloads/shar-psp-persony-w/build}; HZ=${HZ_SRC:-$HOME/Downloads/shar-psp-gorizont-w/build/horizon/test28}; TRF=${TRF_SRC:-$HOME/Downloads/shar-psp-persony-w/build/trf_release}; UI=${UI_SRC:-$HOME/Downloads/shar-psp-hud623/build/ui-pkg-v10}
[ -z "$(git status --porcelain --untracked-files=no)" ] || { echo "рабочая копия не чистая: собирать только из коммитов"; git status --short | grep -v '^??'; exit 1; }
for d in $LV/reissue6/l1 $LV/reissue6/l4 $LV/reissue6/l7 $TRF $UI $PERS/chars_release $PERS/msncars_release $HZ; do [ -d "$d" ] || { echo "нет источника $d"; exit 1; }; done
JF="-DJITTER_STRIPS_OLD=1 -DJITTER_CAR_OLD=1 -DFE_DEMO_PS2_OLD=1"   # FE_DEMO_PS2_OLD=1: титул 20 с без нажатий -> ролик demo по кругу (№109, №153; принято Робом на PSP)
build_cfg() {   # имя, доп. ключи, доп. флаги C
  ( cd viewer && { psp-cmake -S . -B build_$1 -DSHAR_RELEASE=ON -DSHAR_RELEASE_KEEP_DIAG=ON -DSHAR_RELEASE_KEEP_HUD=ON $2 -DCMAKE_C_FLAGS="$JF $3" >/dev/null 2>&1; }
    cmake --build build_$1 2>&1 | grep -E "error|Built target" || true )
}
build_cfg t28game "" ""
build_cfg t28tour "-DSHAR_RELEASE_KEEP_SMOKE=ON" ""   # тур без BB_SYNC_OLD: асинхронный ящик, как у игрока (синхронный давал рывки, которых у игрока нет); BBOLD=1 — старый синхронный ящик для разбора зависаний
[ "${BBOLD:-0}" = 1 ] && build_cfg t28tourbb "-DSHAR_RELEASE_KEEP_SMOKE=ON" "-DBB_SYNC_OLD=1"
ovl() {   # D: папка игры; наложения поверх пакета данных
  local A; A=$(cd $D && pwd)
  for f in level mcpr lmap; do cp $LV/reissue6/l1/$f.shr $D/$f.shr; cp $LV/reissue6/l4/$f.shr $D/l4/$f.shr; cp $LV/reissue6/l7/$f.shr $D/l7/$f.shr; done   # reissue6: основание ≤ 4 м, бочки L7 (Уровни)
  mkdir -p $D/chars; cp $PERS/chars_release/male2.chr $D/chars/male2.chr   # №314 п.1 водители миссий
  cp $PERS/msncars_release/l1/msncars-l1.shr $D/msncars-l1.shr; for n in 2 3 4 5 6 7; do cp $PERS/msncars_release/l$n/msncars-l$n.shr $D/l$n/msncars-l$n.shr; done
  cp $HZ/l3_horizon.shr $D/l3/horizon.shr; cp $HZ/l5_horizon.shr $D/l5/horizon.shr   # Горизонт d1c1cc52: только лежит, включается пустым файлом horizon (не кладём до выбора Роба)
  cp $TRF/l1/traffic.shr $D/traffic.shr; for n in 2 3 4 5 6 7; do cp $TRF/l$n/traffic.shr $D/l$n/traffic.shr; done
  ( cd $UI && find . -type f ! -path './logs/*' ! -name '*.fonts' | sort | while read f; do [ -e "$A/$f" ] && cp "$UI/$f" "$A/$f" || echo "  ui-pkg-v10: в наборе нет $f (не кладу)"; done )
  [ -d $DATA/fonts-license ] && { rm -rf $D/fonts-license; cp -R $DATA/fonts-license $D/fonts-license; }
  # №301 потолок дома (Стены e83cc928): interiors-l1(-gfx).bin перевыпускаются (SHR_TEX_CAP256=1 SHR_SMALL_MIPS=1 SHR_LAYERS=1 tools/interior_export.py --level 1 --outdir build/ceil301); L2–L7 не перевыпускались
  [ "$(shasum -a 256 $CEIL/interiors-l1-gfx.bin | cut -c1-8)" = 5171a6be ] && [ "$(shasum -a 256 $CEIL/interiors-l1.bin | cut -c1-8)" = d7b48d05 ] || { echo "interiors-l1 из $CEIL не совпали по SHA с 301 (5171a6be / d7b48d05)"; exit 1; }
  cp $CEIL/interiors-l1-gfx.bin $CEIL/interiors-l1.bin $D/
  if [ "${FINAL:-0}" != 1 ]; then : > $D/hudon; printf 8 > $D/horizon; : > $D/prereadold; fi   # тест: счётчик, горизонт включён (слово Роба: на причале силуэтов не видно), PREREAD выкл до разбора L6 (STALL TEST27); финал решает дирижёр
  : > $D/pfetchold   # финал: счётчика нет (hudon только у теста)
}
mkset() {   # имя_набора, build_dir, подпись флагов, smokelog(0/1)
  O=build/$1; D=$O/PSP/GAME/SHARTEST15; rm -rf $O; mkdir -p $D
  EBOOT_SRC=viewer/$2/EBOOT.PBP tools/pack_test.sh "$([ "${FINAL:-0}" = 1 ] && echo "The Simpsons Hit & Run" || echo "SHAR ${TITLE:-TEST28}")" build/$1_pack >/dev/null   # слот названия в SFO создаётся сразу нужной длины (финал длиннее 12 байт)
  if [ "${FINAL:-0}" = 1 ]; then python3 tools/eboot_title.py build/$1_pack/PSP/GAME/SHARTEST15/EBOOT.PBP --preset final $D/EBOOT.PBP >/dev/null; else python3 tools/eboot_title.py build/$1_pack/PSP/GAME/SHARTEST15/EBOOT.PBP --title "SHAR TEST28" $D/EBOOT.PBP >/dev/null; fi
  python3 - $D/EBOOT.PBP ${PBP_SRC:-$HOME/Downloads/shar-psp-g-build-w/build/tour/pbp} <<'PY' || { echo "pbp: секции EBOOT не совпали с пакетом иконки/фона/звука"; exit 1; }
import struct, sys
from pathlib import Path
b = Path(sys.argv[1]).read_bytes(); g = Path(sys.argv[2]); o = struct.unpack_from('<8I', b, 8); e = list(o[1:]) + [len(b)]
sec = {k: b[x:y] for k, x, y in zip(['SFO', 'ICON0', 'ICON1', 'PIC0', 'PIC1', 'SND0', 'DATA', 'PSAR'], o, e)}
bad = [k for k, f in (('ICON0', 'ICON0.PNG'), ('ICON1', 'ICON1.PMF'), ('PIC1', 'PIC1.PNG'), ('SND0', 'SND0.AT3')) if not sec[k] or sec[k] != (g / f).read_bytes()]
print('pbp-секции ICON0/ICON1/PIC1/SND0:', 'OK' if not bad else 'НЕ СОВПАЛИ ' + ','.join(bad), {k: len(v) for k, v in sec.items() if k in ('ICON0', 'ICON1', 'PIC1', 'SND0')})
sys.exit(1 if bad else 0)
PY
  SHIP_LEVELS="2 3 4 5 6 7" tools/ship_files.sh --pairs | cut -d'|' -f1 | while read f; do mkdir -p "$D/$(dirname "$f")"; [ -f "$DATA/$f" ] || { echo "  нет в DATA: $f (должно прийти наложением)"; continue; }; cp -c "$DATA/$f" "$D/$f" 2>/dev/null || cp "$DATA/$f" "$D/$f"; done
  for n in 2 5; do cp build/audio25/l$n/audio/sfx.sab build/audio25/l$n/audio/music.sap $D/l$n/audio/; done
  ovl
  [ "$4" = 1 ] && touch $D/smokelog
  cp build/$1_pack/BUILD_INFO.txt $O/BUILD_INFO.txt
  hh() { shasum -a 256 "$D/$1" | cut -c1-8; }
  FL=$(cd $D && ls hudon horizon prereadold pfetchold 2>/dev/null | tr '\n' ' ')
  sed -i '' "s|^флаги сборки:.*|флаги сборки: $3 $JF; данные (по SHA файлов набора): L1 level $(hh level.shr), L4 level $(hh l4/level.shr), L7 level $(hh l7/level.shr), male2.chr $(hh chars/male2.chr), msncars-l1 $(hh msncars-l1.shr), horizon L3 $(hh l3/horizon.shr) и L5 $(hh l5/horizon.shr)$([ "${FINAL:-0}" = 1 ] && echo ' (файла horizon нет)' || echo ' (файл horizon = 8 лежит: силуэты включены)'), traffic L1 $(hh traffic.shr), ui.shr $(hh ui.shr), interiors-l1-gfx $(hh interiors-l1-gfx.bin); файлы рядом с EBOOT: $FL; коммит $(git rev-parse --short HEAD)|" $O/BUILD_INFO.txt
  ( cd $D && find . -type f | sort | while read f; do printf "%s  %s\n" "$(shasum -a 256 "$f" | cut -d' ' -f1)" "$f"; done ) > $O/MANIFEST_SHA256.txt
  echo "$1: $(wc -l < $O/MANIFEST_SHA256.txt) файлов, EBOOT $(shasum -a 256 $D/EBOOT.PBP | cut -c1-8)"
}
mkset ${SN:-test28} build_t28game "SHAR_RELEASE=ON SHAR_RELEASE_KEEP_DIAG=ON SHAR_RELEASE_KEEP_HUD=ON (игровая сборка, ящик фоном)" 0
[ "${FINAL:-0}" = 1 ] || mkset ${SN:-test28}tour build_t28tour "SHAR_RELEASE=ON SHAR_RELEASE_KEEP_DIAG=ON SHAR_RELEASE_KEEP_HUD=ON SHAR_RELEASE_KEEP_SMOKE=ON BB_SYNC_OLD=1 (тур-сборка, ящик асинхронный как у игрока; scenario.txt: SCN=файл)" 1
[ "${FINAL:-0}" != 1 ] && [ -f "${SCN:-}" ] && { cp "$SCN" build/${SN:-test28}tour/PSP/GAME/SHARTEST15/scenario.txt; ( cd build/${SN:-test28}tour/PSP/GAME/SHARTEST15 && echo "$(shasum -a 256 scenario.txt | cut -d' ' -f1)  ./scenario.txt" >> ../../MANIFEST_SHA256.txt ); }
[ "${GATE:-1}" = 1 ] && {
  for s in $([ "${FINAL:-0}" = 1 ] || echo ${SN:-test28}tour) ${SN:-test28}; do
    tools/frame_gate.sh viewer/build_t28tour/EBOOT.PBP build/$s/PSP/GAME/SHARTEST15 build/${s}_gate || { echo "frame_gate: НЕТ PASS для $s — набор не годится"; exit 1; }
  done
}
echo "готово: build/${SN:-test28} и build/${SN:-test28}tour"
