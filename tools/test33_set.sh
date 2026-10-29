#!/bin/bash
# TEST33 (integ/test33 = TEST32 + render-perf, 18.10 ночь): наборы TEST32 побайтно, поверх замены: EBOOT обеих сборок,
# пакеты интерфейса (tools/ui_packs.sh с UI_PLACE_CODE=1 и панелью Роба), гардероб L1–L7, значки заданий msnart L1–L7 (поле верха значков, сдача терминала
# игры 21:27), и НОВЫЕ файлы из EXTRA (coinspr.bin — монета-спрайт, лента кадров 3D-монеты рядом с EBOOT); туру — tests/smoke_scenes/test33_game.txt
# (тур терминала игры TEST31 + блок рендера: тень деревьев с/без в одном месте, тени людей у Мардж, монета вблизи).
#   tools/test32_set.sh      -> build/test32 (игровая) и build/test32tour (тур), MANIFEST_SHA256.txt, ЗАМЕНЫ.txt; frame_gate обязателен
#   входы: UI=build/t32/ui, W=build/t32/w_new, MA=build/t32/ma (msnart_export --level N), EXTRA=build/t32/extra, движки viewer/build_t32game, viewer/build_g32tour
set -e
cd "$(dirname "$0")/.."
T30=${T32_SRC:-build}; UI=${UI_SRC:-build/t33/ui}; W=${W_SRC:-build/t33/w_new}; MA=${MA_SRC:-build/t32/ma}; EXTRA=${EXTRA_SRC:-build/t33/extra}
[ -z "$(git status --porcelain --untracked-files=no)" ] || { echo "рабочая копия не чистая: собирать только из коммитов"; exit 1; }
for d in $T30/test32/PSP/GAME/SHARTEST15 $T30/test32tour/PSP/GAME/SHARTEST15 $UI $W $MA $EXTRA; do [ -d "$d" ] || { echo "нет источника $d"; exit 1; }; done
grep -q "bad=0" $UI/logs/ALLDONE || { echo "пакеты интерфейса собраны с ошибками: $UI/logs"; exit 1; }
grep -q "typo=[0-9a-f]\{8\}" $UI/logs/ALLDONE || { echo "пакеты интерфейса собраны БЕЗ панели типографики Роба ($UI/logs/ALLDONE) — не годится"; exit 1; }
mkset() {   # имя, набор TEST30, папка сборки движка, тур(0/1)
  O=build/$1; D=$O/PSP/GAME/SHARTEST15; rm -rf $O; mkdir -p $O/PSP/GAME
  cp -c -R $T30/$2/PSP/GAME/SHARTEST15 $D
  EBOOT_SRC=viewer/$3/EBOOT.PBP tools/pack_test.sh "SHAR TEST33" build/$1_pack >/dev/null
  python3 tools/eboot_title.py build/$1_pack/PSP/GAME/SHARTEST15/EBOOT.PBP --title "SHAR TEST33" $D/EBOOT.PBP >/dev/null
  A=$(cd $D && pwd); : > $O/ЗАМЕНЫ.txt
  echo "EBOOT.PBP $(shasum -a 256 $T30/$2/PSP/GAME/SHARTEST15/EBOOT.PBP | cut -c1-8) -> $(shasum -a 256 $D/EBOOT.PBP | cut -c1-8)" >> $O/ЗАМЕНЫ.txt
  for src in $UI $W $MA; do
    ( cd $src && find . -type f ! -path './logs/*' ! -name '*.fonts' ! -name 'log.txt' | sort ) | while read f; do
      if [ -e "$A/$f" ]; then a=$(shasum -a 256 "$A/$f" | cut -c1-8); cp "$src/$f" "$A/$f"; b=$(shasum -a 256 "$A/$f" | cut -c1-8); [ $a = $b ] || echo "${f#./} $a -> $b" >> $O/ЗАМЕНЫ.txt
      else echo "  $src: в наборе нет $f (не кладу)"; fi
    done
  done
  ( cd $EXTRA && find . -type f | sort ) | while read f; do mkdir -p "$(dirname "$A/$f")"; cp "$EXTRA/$f" "$A/$f"; echo "+ ${f#./} $(shasum -a 256 "$A/$f" | cut -c1-8) (новый)" >> $O/ЗАМЕНЫ.txt; done
  [ "$4" = 1 ] && cp tests/smoke_scenes/test33_game.txt $D/scenario.txt
  { echo "BUILD_INFO · SHAR TEST33 · $(date '+%Y-%m-%d %H:%M')"; echo "основа: $T30/$2 (TEST32, коммит 52d02832); коммит integ/test33 $(git rev-parse --short HEAD)";
    echo "EBOOT: viewer/$3 ($( [ "$4" = 1 ] && echo 'тур: RELEASE+KEEP_DIAG+KEEP_HUD+KEEP_SMOKE, BB_SYNC_OLD=1' || echo 'игровая: RELEASE+KEEP_DIAG+KEEP_HUD'), JITTER_*_OLD, FE_DEMO_PS2_OLD)";
    echo "замены против TEST32: $(wc -l < $O/ЗАМЕНЫ.txt) файлов (ЗАМЕНЫ.txt)"; } > $O/BUILD_INFO.txt
  ( cd $D && find . -type f | sort | while read f; do printf "%s  %s\n" "$(shasum -a 256 "$f" | cut -d' ' -f1)" "$f"; done ) > $O/MANIFEST_SHA256.txt
  echo "$1: $(wc -l < $O/MANIFEST_SHA256.txt) файлов, EBOOT $(shasum -a 256 $D/EBOOT.PBP | cut -c1-8), заменено $(wc -l < $O/ЗАМЕНЫ.txt)"
}
mkset test33 test32 build_t33game 0
mkset test33tour test32tour build_g33tour 1
[ "${GATE:-1}" = 1 ] && for s in test33tour test33; do
  tools/frame_gate.sh viewer/build_g33tour/EBOOT.PBP build/$s/PSP/GAME/SHARTEST15 build/${s}_gate || { echo "frame_gate: НЕТ PASS для $s — набор не годится"; exit 1; }
done
echo "готово: build/test33 и build/test33tour"
