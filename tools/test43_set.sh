#!/bin/bash
# TEST43 (integ/test43 = integ/test42 + render-perf после TEST42: №853 тени и кузов машины у камеры без выброса GE (мигание пола L6); ранее TEST42: №852 скорость L3 (значки, синхронизация, пятна и свет на полу); ранее: №837 пол камер, №838 цена кадра, №794 по умолчанию; TEST36: №789 №793 №800 №805 №811 №813 №817 №821–№835 и помощники; ранее TEST35: плоское меню OPTIONS №783, Draw Distance №795, пропуск перебивок №792,
# △ в паузе №806, будка №809/№810, кружение персонажей №813, векторное свечение №793, камера бампера №791, спрайты монеты/ключа/трубки/«!»
# №802/№803/№812/№814/№815, мультик №784/№790/№796/№797/№801): наборы TEST34 побайтно (build/test34, build/test34tour), поверх замены:
# EBOOT обеих сборок, пакеты меню и будки (pmenu.shr / menu.shr / phone.shr из UI_SRC), новые данные спрайтов рядом с EBOOT (DATA_SRC),
# сценарий тура tests/smoke_scenes/test35_game.txt (тот же, что TEST35); полная игра — EBOOT_SHARVIEW.PBP (как TEST35).
#   входы: движки viewer/build_t43game (игра) и viewer/build_g35tour (тур), UI_SRC, DATA_SRC (build/t43/ui, build/t43/data)
set -e
cd "$(dirname "$0")/.."; export PSPDEV="$PWD/pspdev" PATH="$PWD/pspdev/bin:$PATH"
B=${T42_SRC:-build}; UI=${UI_SRC:-build/t43/ui}; DA=${DATA_SRC:-build/t43/data}
G=${PBP_SRC:-$HOME/Downloads/shar-psp-g-build-w/build/tour/pbp}
[ -z "$(git status --porcelain --untracked-files=no)" ] || { echo "рабочая копия не чистая: собирать только из коммитов"; exit 1; }
for d in $B/test42/PSP/GAME/SHARTEST15 $B/test42tour/PSP/GAME/SHARTEST15 viewer/build_t43game viewer/build_g43tour $G $DA; do [ -d "$d" ] || { echo "нет источника $d"; exit 1; }; done
mkset() {   # имя, набор TEST42, папка сборки движка, тур(0/1)
  O=build/$1; D=$O/PSP/GAME/SHARTEST15; rm -rf $O; mkdir -p $O/PSP/GAME
  cp -c -R $B/$2/PSP/GAME/SHARTEST15 $D
  EBOOT_SRC=viewer/$3/EBOOT.PBP tools/pack_test.sh "SHAR TEST43" build/$1_pack >/dev/null
  python3 tools/eboot_title.py build/$1_pack/PSP/GAME/SHARTEST15/EBOOT.PBP --title "SHAR TEST43" $D/EBOOT.PBP >/dev/null
  A=$(cd $D && pwd); : > $O/ЗАМЕНЫ.txt
  echo "EBOOT.PBP $(shasum -a 256 $B/$2/PSP/GAME/SHARTEST15/EBOOT.PBP | cut -c1-8) -> $(shasum -a 256 $D/EBOOT.PBP | cut -c1-8)" >> $O/ЗАМЕНЫ.txt
  if [ -n "$UI" ]; then ( cd $UI && find . -type f \( -name pmenu.shr -o -name menu.shr -o -name phone.shr \) | sort ) | while read f; do f=${f#./}
    if [ -e "$A/$f" ]; then a=$(shasum -a 256 "$A/$f" | cut -c1-8); cp "$UI/$f" "$A/$f"; b=$(shasum -a 256 "$A/$f" | cut -c1-8); [ $a = $b ] || echo "$f $a -> $b" >> $O/ЗАМЕНЫ.txt
    else echo "  $UI: в наборе нет $f (не кладу)"; fi; done; fi
  ( cd $DA && find . -type f | sort ) | while read f; do f=${f#./}; mkdir -p "$(dirname "$A/$f")"   # спрайты №802/№803/№812/№814 рядом с EBOOT; №788 notoon.txt рядом с level.shr уровня
    a=$( [ -e "$A/$f" ] && shasum -a 256 "$A/$f" | cut -c1-8 || echo нет); cp "$DA/$f" "$A/$f"; b=$(shasum -a 256 "$A/$f" | cut -c1-8)
    [ "$a" = "$b" ] || echo "$f $a -> $b" >> $O/ЗАМЕНЫ.txt; done
  python3 tools/notoon_check.py $D >/dev/null || { echo "$1: списки notoon.txt не совпали с level.shr набора (tools/notoon_check.py)"; exit 1; }
  [ "$4" = 1 ] && cp tests/smoke_scenes/test35_game.txt $D/scenario.txt
  { echo "BUILD_INFO · SHAR TEST43 · $(date '+%Y-%m-%d %H:%M')"; echo "основа: $B/$2 (TEST42); коммит integ/test43 $(git rev-parse --short HEAD)";
    echo "EBOOT: viewer/$3 ($( [ "$4" = 1 ] && echo 'тур: RELEASE+KEEP_DIAG+KEEP_HUD+KEEP_SMOKE, BB_SYNC_OLD=1' || echo 'игровая: RELEASE+KEEP_DIAG+KEEP_HUD'), JITTER_*_OLD, FE_DEMO_PS2_OLD)";
    echo "замены против TEST42: $(wc -l < $O/ЗАМЕНЫ.txt) файлов (ЗАМЕНЫ.txt)"; } > $O/BUILD_INFO.txt
  ( cd $D && find . -type f | sort | while read f; do printf "%s  %s\n" "$(shasum -a 256 "$f" | cut -d' ' -f1)" "$f"; done ) > $O/MANIFEST_SHA256.txt
  echo "$1: $(wc -l < $O/MANIFEST_SHA256.txt) файлов, EBOOT $(shasum -a 256 $D/EBOOT.PBP | cut -c1-8), заменено $(wc -l < $O/ЗАМЕНЫ.txt)"
}
mkset test43 test42 build_t43game 0
mkset test43tour test42tour build_g43tour 1
# полная игра для SHARVIEW: название «The Simpsons Hit & Run» из PARAM.SFO движка, картинки и звук меню PSP — игры
P=build/test43_sv; rm -rf $P; mkdir -p $P/unp; (cd $P/unp && unpack-pbp "$OLDPWD/viewer/build_t43game/EBOOT.PBP" >/dev/null)
pack-pbp build/test43/EBOOT_SHARVIEW.PBP viewer/build_t43game/PARAM.SFO $G/ICON0.PNG $G/ICON1.PMF NULL $G/PIC1.PNG $G/SND0.AT3 $P/unp/DATA.PSP NULL >/dev/null
echo "SHARVIEW: build/test43/EBOOT_SHARVIEW.PBP $(shasum -a 256 build/test43/EBOOT_SHARVIEW.PBP | cut -c1-8)"
[ "${GATE:-1}" = 1 ] && for s in test43tour test43; do
  tools/frame_gate.sh viewer/build_g43tour/EBOOT.PBP build/$s/PSP/GAME/SHARTEST15 build/${s}_gate || { echo "frame_gate: НЕТ PASS для $s — набор не годится"; exit 1; }
done
echo "готово: build/test43, build/test43tour, build/test43/EBOOT_SHARVIEW.PBP"
