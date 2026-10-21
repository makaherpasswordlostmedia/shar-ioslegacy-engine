#!/bin/bash
# Набор замены TEST20 к SHARTEST15: интерфейс (601 → 598 → v5 → v7 из build/release_inputs) + уровни с дальними версиями (build/far_lv/lN.shr, L3 — build/far_l3.shr) + файлы far_plain (D = 140 м) + EBOOT + scenario.txt; сравнение с картой (только чтение)
#   tools/test20_set.sh [CARD_APP]   -> build/${T}set/
set -e; cd "$(dirname "$0")/.."; T="${T:-test20}"   # T=test20b — набор TEST20b (build/test20b, tests/smoke_scenes/test20b.txt)
CARD="${1:-/Volumes/PSP/PSP/GAME/SHARTEST15}"; FARD="${FARD:-140}"
S=build/t20stage; rm -rf $S; mkdir -p $S build/t20empty
for k in 601 598 v5 v7; do cp -R build/release_inputs/ui-pkg-$k/. $S/; done
for n in 1 2 3 4 5 6 7; do
  if [ -d "${LVOUT:-}" ]; then   # LVOUT=build/far2_out: уровни TEST21 (level.shr в порядке секций Загрузки 2 + mcpr.shr + lmap.shr), L1 — lvout/l1 -> корень
    if [ $n = 1 ]; then dd=$S; else dd=$S/l$n; fi; mkdir -p $dd; cp "$LVOUT/l$n/level.shr" "$LVOUT/l$n/mcpr.shr" "$LVOUT/l$n/lmap.shr" $dd/; printf '%s' "$FARD" > $dd/far_plain; continue
  fi
  src=build/far_lv/l$n.shr; [ $n = 3 ] && src=build/far_l3.shr
  [ -f "$src" ] || { echo "нет $src"; exit 1; }
  if [ $n = 1 ]; then dst=$S/level.shr; fp=$S/far_plain; else mkdir -p $S/l$n; dst=$S/l$n/level.shr; fp=$S/l$n/far_plain; fi
  cp "$src" "$dst"; printf '%s' "$FARD" > "$fp"
done
# far_plain — не .shr: test17_set.py берёт только *.shr, поэтому добавляем их отдельным проходом ниже
python3 tools/test17_set.py "$CARD" $S build/t20empty build/$T/PSP/GAME/SHARTEST15/EBOOT.PBP tests/smoke_scenes/$T.txt build/${T}set
for f in $(cd $S && find . -name far_plain | sed 's|^\./||'); do
  c="$CARD/$f"; if [ ! -f "$c" ] || ! cmp -s "$S/$f" "$c"; then mkdir -p "build/${T}set/PSP/GAME/SHARTEST15/$(dirname $f)"; cp "$S/$f" "build/${T}set/PSP/GAME/SHARTEST15/$f"; echo "far_plain | $f | D=$FARD | на карте: $([ -f "$c" ] && cat "$c" || echo нет)" >> build/${T}set/ЗАМЕНА.txt; fi
done
cp build/$T/BUILD_INFO.txt build/${T}set/BUILD_INFO.txt
sed -i '' "s/ЗАМЕНА TEST19/ЗАМЕНА ${T}/" build/${T}set/ЗАМЕНА.txt 2>/dev/null || true
echo "набор: build/${T}set/"; cut -c1-110 build/${T}set/ЗАМЕНА.txt | head -30
