#!/bin/bash
# Гейт реплик героя и соперников (аудит 09.10 п. 12/58): tests/sound/vo_host.c на пакете звука уровня 1. Мак, CPU, без эмулятора.
#   пакет НОВЫЙ — tools/sound_export.py как есть -> build/vo/new; пакет ПРЕЖНИЙ — VO_OLD = True -> build/vo/old (~1 мин каждый)
#   КРАСНЫЙ 1: прежний пакет (новый движок) обязан упасть на pack, say, rival — дорожек 0
#   КРАСНЫЙ 2: прежний движок (-DSND_VO_OLD=1) на новом пакете обязан упасть на say и rival
#   ЗЕЛЁНЫЙ: новый движок, новый пакет — всё; числа «у диска» — счёт ресурсов dialog.spt
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
OUT=build/vo; mkdir -p "$OUT"; PY=.venv/bin/python
SPT=hit-and-run-web/source/game/sound/scripts/dialog.spt
[ -f "$OUT/new/music.sap" ] && [ -z "${VO_REBUILD:-}" ] || "$PY" tools/sound_export.py --out "$OUT/new" > "$OUT/export_new.txt" 2>&1 || { echo "FAIL: экспорт"; tail -3 "$OUT/export_new.txt"; exit 2; }
[ -f "$OUT/old/music.sap" ] && [ -z "${VO_REBUILD:-}" ] || (cd tools && ../"$PY" -c "
import sys; sys.argv=['sound_export.py','--out','../$OUT/old']
import sound_export as S; S.VO_OLD=True; S.main()") > "$OUT/export_old.txt" 2>&1 || { echo "FAIL: экспорт (прежний)"; tail -3 "$OUT/export_old.txt"; exit 2; }
# у диска: ресурсы семейства (имя в пакете — строчные)
SPEC=""
for fam in Card Mvic Mfail Springboard Fall NewAI Pass Passed HitByC Tail AIDestroy Turbo Dodge LongJump; do
  n=$(grep -c "^create daSoundResourceData named W_${fam}_Hom_" "$SPT"); [ "$n" -gt 0 ] || continue; SPEC="$SPEC $(echo "w_${fam}_hom_" | tr 'A-Z' 'a-z')=$n"; done
for fam in Mvic Mfail Damage Tail HitCar; do for code in Skn Skin Smi; do
  n=$(grep -c "^create daSoundResourceData named V_${fam}_${code}_" "$SPT"); [ "$n" -gt 0 ] && SPEC="$SPEC $(echo "v_${fam}_${code}_" | tr 'A-Z' 'a-z')=$n"; done; done
for fam in HitByC NHitByC HitByW; do
 n=$(grep -c "^create daSoundResourceData named P_${fam}_Brn_" "$SPT"); SPEC="$SPEC p_$(echo "$fam" | tr 'A-Z' 'a-z')_barney_=$n"
done
n=$(grep -c '^create daSoundResourceData named W_Doorbell_Qim_' "$SPT"); SPEC="$SPEC db_quimby_=$n"
echo "у диска:$SPEC"
B="cc -std=c11 -O2 -w -DAUDIO_HOST -I viewer tests/sound/vo_host.c viewer/sound.c viewer/audio.c -lm"
$B -o "$OUT/host" && $B -DSND_VO_OLD=1 -o "$OUT/host_old" || { echo "FAIL: сборка"; exit 2; }
red=0
"$OUT/host" "$OUT/old/" "$SPEC" > "$OUT/red_pack.txt" 2>&1
for c in pack say rival named door; do grep -q "CHECK $c .*FAIL" "$OUT/red_pack.txt" || { echo "КРАСНЫЙ 1 НЕ ПОЙМАН: $c"; red=-9; }; done
[ $red -ge 0 ] && { echo "красный 1 (прежний пакет): $(grep -c 'FAIL' "$OUT/red_pack.txt") провалов, напр. $(grep -m1 'CHECK pack .*FAIL' "$OUT/red_pack.txt" | cut -c1-90)"; red=$((red + 1)); }
"$OUT/host_old" "$OUT/new/" "$SPEC" > "$OUT/red_engine.txt" 2>&1
r2=1; for c in say rival named door; do grep -q "CHECK $c .*FAIL" "$OUT/red_engine.txt" || { echo "КРАСНЫЙ 2 НЕ ПОЙМАН: $c"; r2=0; }; done
[ $r2 = 1 ] && { echo "красный 2 (прежний движок): $(grep -m1 'CHECK say .*FAIL' "$OUT/red_engine.txt" | cut -c1-110)"; red=$((red + 1)); }
"$OUT/host" "$OUT/new/" "$SPEC" > "$OUT/green.txt" 2>&1; rc=$?; cat "$OUT/green.txt"
[ $red = 2 ] && [ $rc = 0 ] && echo "PASS (красный 2/2 пойман, зелёный сошёлся)" || { echo "FAIL"; exit 1; }
