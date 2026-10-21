#!/bin/bash
# TEST34 (integ/test34 = integ/test33 + render-perf: смена уровня — участок памяти под уровень №775/№776, сторож с шагом и ожиданиями,
# Settings с подстраницами №777, контур и цвета мультика №779–№781): наборы TEST33 побайтно (build/test33, build/test33tour), поверх замены:
# EBOOT обеих сборок, пакеты меню (pmenu.shr / menu.shr из UI_SRC, если есть), сценарий тура tests/smoke_scenes/test34_game.txt;
# полная игра — EBOOT_SHARVIEW.PBP (PARAM.SFO движка «The Simpsons Hit & Run» + ICON0/ICON1/PIC1/SND0 игры + DATA.PSP движка, как 12.10 и TEST33).
#   входы: движки viewer/build_t34game (игра) и viewer/build_g34tour (тур), UI_SRC (папка с новыми pmenu.shr/menu.shr; пусто — меню TEST33)
set -e
cd "$(dirname "$0")/.."; export PSPDEV="$PWD/pspdev" PATH="$PWD/pspdev/bin:$PATH"
B=${T33_SRC:-build}; UI=${UI_SRC:-build/t34/ui}
G=${PBP_SRC:-$HOME/Downloads/shar-psp-g-build-w/build/tour/pbp}
[ -z "$(git status --porcelain --untracked-files=no)" ] || { echo "рабочая копия не чистая: собирать только из коммитов"; exit 1; }
for d in $B/test33/PSP/GAME/SHARTEST15 $B/test33tour/PSP/GAME/SHARTEST15 viewer/build_t34game viewer/build_g34tour $G; do [ -d "$d" ] || { echo "нет источника $d"; exit 1; }; done
mkset() {   # имя, набор TEST33, папка сборки движка, тур(0/1)
  O=build/$1; D=$O/PSP/GAME/SHARTEST15; rm -rf $O; mkdir -p $O/PSP/GAME
  cp -c -R $B/$2/PSP/GAME/SHARTEST15 $D
  EBOOT_SRC=viewer/$3/EBOOT.PBP tools/pack_test.sh "SHAR TEST34" build/$1_pack >/dev/null
  python3 tools/eboot_title.py build/$1_pack/PSP/GAME/SHARTEST15/EBOOT.PBP --title "SHAR TEST34" $D/EBOOT.PBP >/dev/null
  A=$(cd $D && pwd); : > $O/ЗАМЕНЫ.txt
  echo "EBOOT.PBP $(shasum -a 256 $B/$2/PSP/GAME/SHARTEST15/EBOOT.PBP | cut -c1-8) -> $(shasum -a 256 $D/EBOOT.PBP | cut -c1-8)" >> $O/ЗАМЕНЫ.txt
  if [ -n "$UI" ]; then ( cd $UI && find . -type f \( -name pmenu.shr -o -name menu.shr \) | sort ) | while read f; do f=${f#./}
    if [ -e "$A/$f" ]; then a=$(shasum -a 256 "$A/$f" | cut -c1-8); cp "$UI/$f" "$A/$f"; b=$(shasum -a 256 "$A/$f" | cut -c1-8); [ $a = $b ] || echo "$f $a -> $b" >> $O/ЗАМЕНЫ.txt
    else echo "  $UI: в наборе нет $f (не кладу)"; fi; done; fi
  [ "$4" = 1 ] && cp tests/smoke_scenes/test34_game.txt $D/scenario.txt
  { echo "BUILD_INFO · SHAR TEST34 · $(date '+%Y-%m-%d %H:%M')"; echo "основа: $B/$2 (TEST33); коммит integ/test34 $(git rev-parse --short HEAD)";
    echo "EBOOT: viewer/$3 ($( [ "$4" = 1 ] && echo 'тур: RELEASE+KEEP_DIAG+KEEP_HUD+KEEP_SMOKE, BB_SYNC_OLD=1' || echo 'игровая: RELEASE+KEEP_DIAG+KEEP_HUD'), JITTER_*_OLD, FE_DEMO_PS2_OLD)";
    echo "замены против TEST33: $(wc -l < $O/ЗАМЕНЫ.txt) файлов (ЗАМЕНЫ.txt)"; } > $O/BUILD_INFO.txt
  ( cd $D && find . -type f | sort | while read f; do printf "%s  %s\n" "$(shasum -a 256 "$f" | cut -d' ' -f1)" "$f"; done ) > $O/MANIFEST_SHA256.txt
  echo "$1: $(wc -l < $O/MANIFEST_SHA256.txt) файлов, EBOOT $(shasum -a 256 $D/EBOOT.PBP | cut -c1-8), заменено $(wc -l < $O/ЗАМЕНЫ.txt)"
}
mkset test34 test33 build_t34game 0
mkset test34tour test33tour build_g34tour 1
# полная игра для SHARVIEW: название «The Simpsons Hit & Run» из PARAM.SFO движка, картинки и звук меню PSP — игры
P=build/test34_sv; rm -rf $P; mkdir -p $P/unp; (cd $P/unp && unpack-pbp "$OLDPWD/viewer/build_t34game/EBOOT.PBP" >/dev/null)
pack-pbp build/test34/EBOOT_SHARVIEW.PBP viewer/build_t34game/PARAM.SFO $G/ICON0.PNG $G/ICON1.PMF NULL $G/PIC1.PNG $G/SND0.AT3 $P/unp/DATA.PSP NULL >/dev/null
echo "SHARVIEW: build/test34/EBOOT_SHARVIEW.PBP $(shasum -a 256 build/test34/EBOOT_SHARVIEW.PBP | cut -c1-8)"
[ "${GATE:-1}" = 1 ] && for s in test34tour test34; do
  tools/frame_gate.sh viewer/build_g34tour/EBOOT.PBP build/$s/PSP/GAME/SHARTEST15 build/${s}_gate || { echo "frame_gate: НЕТ PASS для $s — набор не годится"; exit 1; }
done
echo "готово: build/test34, build/test34tour, build/test34/EBOOT_SHARVIEW.PBP"
