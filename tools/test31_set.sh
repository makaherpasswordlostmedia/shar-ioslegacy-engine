#!/bin/bash
# TEST31 (терминал игры, ветка game-polish): наборы TEST30 (sonnet-16b-w build/test30f, test30ftour — по SHA как на карте) побайтно,
# поверх — только правки терминала игры: EBOOT обеих сборок из этого коммита, пакеты интерфейса (tools/ui_packs.sh с UI_PLACE_CODE=1, как у TEST30),
# гардероб L1–L7 (tools/skins_export.py: запечённые лучи №703 + №732; в TEST30 лежал пакет 07:44 без них), туру — сценарий tests/smoke_scenes/test31_game.txt.
#   tools/test31_set.sh      -> build/test31 (игровая) и build/test31tour (тур), MANIFEST_SHA256.txt, ЗАМЕНЫ.txt; frame_gate обязателен
#   входы: UI=build/t31/ui (tools/ui_packs.sh), W=build/t31/w_new (skins_export --level N), движки viewer/build_t31game, viewer/build_g31tour
set -e
N=${TEST_N:-31}   # номер теста в названии и папках: TEST_N=32 tools/test31_set.sh -> «SHAR TEST32», build/test32, build/test32tour
cd "$(dirname "$0")/.."
T30=${T30_SRC:-$HOME/Downloads/shar-psp-sonnet-16b-w/build}; UI=${UI_SRC:-build/t31/ui}; W=${W_SRC:-build/t31/w_new}
[ -z "$(git status --porcelain --untracked-files=no)" ] || { echo "рабочая копия не чистая: собирать только из коммитов"; exit 1; }
for d in $T30/test30f/PSP/GAME/SHARTEST15 $T30/test30ftour/PSP/GAME/SHARTEST15 $UI $W; do [ -d "$d" ] || { echo "нет источника $d"; exit 1; }; done
grep -q "bad=0" $UI/logs/ALLDONE || { echo "пакеты интерфейса собраны с ошибками: $UI/logs"; exit 1; }
grep -q "typo=[0-9a-f]\{8\}" $UI/logs/ALLDONE || { echo "пакеты интерфейса собраны БЕЗ панели типографики Роба ($UI/logs/ALLDONE) — не годится"; exit 1; }
mkset() {   # имя, набор TEST30, папка сборки движка, тур(0/1)
  O=build/$1; D=$O/PSP/GAME/SHARTEST15; rm -rf $O; mkdir -p $O/PSP/GAME
  cp -c -R $T30/$2/PSP/GAME/SHARTEST15 $D
  EBOOT_SRC=viewer/$3/EBOOT.PBP tools/pack_test.sh "SHAR TEST$N" build/$1_pack >/dev/null
  python3 tools/eboot_title.py build/$1_pack/PSP/GAME/SHARTEST15/EBOOT.PBP --title "SHAR TEST$N" $D/EBOOT.PBP >/dev/null
  A=$(cd $D && pwd); : > $O/ЗАМЕНЫ.txt
  echo "EBOOT.PBP $(shasum -a 256 $T30/$2/PSP/GAME/SHARTEST15/EBOOT.PBP | cut -c1-8) -> $(shasum -a 256 $D/EBOOT.PBP | cut -c1-8)" >> $O/ЗАМЕНЫ.txt
  for src in $UI $W; do
    ( cd $src && find . -type f ! -path './logs/*' ! -name '*.fonts' ! -name 'log.txt' | sort ) | while read f; do
      if [ -e "$A/$f" ]; then a=$(shasum -a 256 "$A/$f" | cut -c1-8); cp "$src/$f" "$A/$f"; b=$(shasum -a 256 "$A/$f" | cut -c1-8); [ $a = $b ] || echo "${f#./} $a -> $b" >> $O/ЗАМЕНЫ.txt
      else echo "  $src: в наборе нет $f (не кладу)"; fi
    done
  done
  [ "$4" = 1 ] && cp tests/smoke_scenes/test31_game.txt $D/scenario.txt
  { echo "BUILD_INFO · SHAR TEST$N · $(date '+%Y-%m-%d %H:%M')"; echo "основа: $T30/$2 (TEST30, коммит cda14c90); коммит game-polish $(git rev-parse --short HEAD)";
    echo "EBOOT: viewer/$3 ($( [ "$4" = 1 ] && echo 'тур: RELEASE+KEEP_DIAG+KEEP_HUD+KEEP_SMOKE, BB_SYNC_OLD=1' || echo 'игровая: RELEASE+KEEP_DIAG+KEEP_HUD'), JITTER_*_OLD, FE_DEMO_PS2_OLD)";
    echo "замены против TEST30: $(wc -l < $O/ЗАМЕНЫ.txt) файлов (ЗАМЕНЫ.txt)"; } > $O/BUILD_INFO.txt
  ( cd $D && find . -type f | sort | while read f; do printf "%s  %s\n" "$(shasum -a 256 "$f" | cut -d' ' -f1)" "$f"; done ) > $O/MANIFEST_SHA256.txt
  echo "$1: $(wc -l < $O/MANIFEST_SHA256.txt) файлов, EBOOT $(shasum -a 256 $D/EBOOT.PBP | cut -c1-8), заменено $(wc -l < $O/ЗАМЕНЫ.txt)"
}
mkset test$N test30f build_t31game 0
mkset test${N}tour test30ftour build_g31tour 1
[ "${GATE:-1}" = 1 ] && for s in test${N}tour test$N; do
  tools/frame_gate.sh viewer/build_g31tour/EBOOT.PBP build/$s/PSP/GAME/SHARTEST15 build/${s}_gate || { echo "frame_gate: НЕТ PASS для $s — набор не годится"; exit 1; }
done
echo "готово: build/test$N и build/test${N}tour"
