#!/bin/bash
# Копирует входные данные выпуска в стабильный каталог build/release_inputs/ и пишет манифест tools/release_inputs.sha256 (в git):
#   ui-pkg-601, ui-pkg-598, ui-pkg-v5, ui-pkg-v7 (только *.shr) — интерфейс v3/v4/v5/v7 (v7 заменяет v6) Типографики; levels/lN/level.shr — уровни с правилом кустов (Стены); base1721/EBOOT.PBP — секции SFO/ICON/PIC/SND игры 1721.
#   tools/release_inputs_make.sh              (источники — переменные SRC_UI, SRC_LEVELS, SRC_BASE ниже)
set -eu; cd "$(dirname "$0")/.."
SRC_UI="${SRC_UI:-$HOME/Downloads/shar-psp-ifinal-2/build}"; SRC_LEVELS="${SRC_LEVELS:-$HOME/Downloads/shar-psp-sonnet-walls-1015/build/_rep/rebuild}"
SRC_BASE="${SRC_BASE:-$HOME/Downloads/shar-psp-sonnet-runs-w/build/final-20261011-1721}"
D=build/release_inputs; rm -rf "$D"; mkdir -p "$D/levels" "$D/base1721"
SRC_V7="${SRC_V7:-$HOME/Downloads/shar-psp-hud623/build/ui-pkg-v7}"   # v7 (№623, №632 значок дома + код клетки): ui.shr, поверх 598/v5
for k in 601 598 v5; do ( cd "$SRC_UI/ui-pkg-$k" && find . -name '*.shr' -type f | while read f; do mkdir -p "$OLDPWD/$D/ui-pkg-$k/$(dirname "$f")"; cp "$f" "$OLDPWD/$D/ui-pkg-$k/$f"; done ); done
( cd "$SRC_V7" && find . -name '*.shr' -type f | while read f; do mkdir -p "$OLDPWD/$D/ui-pkg-v7/$(dirname "$f")"; cp "$f" "$OLDPWD/$D/ui-pkg-v7/$f"; done )
for n in 1 2 3 4 5 6 7; do mkdir -p "$D/levels/l$n"; cp "$SRC_LEVELS/l$n/level.shr" "$D/levels/l$n/level.shr"; done
cp "$SRC_BASE/EBOOT.PBP" "$D/base1721/EBOOT.PBP"
( cd "$D" && find . -type f | sort | xargs shasum -a 256 ) > tools/release_inputs.sha256
echo "входов $(wc -l < tools/release_inputs.sha256), $(du -sh "$D" | cut -f1)"
