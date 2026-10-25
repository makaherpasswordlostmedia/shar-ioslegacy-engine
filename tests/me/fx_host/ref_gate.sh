#!/bin/bash
# Эталон fx_ref313.c против текущего viewer/fx.c + fxdsp.c (долг «Чистоты» TEST60). Стенд fx_host.c гоняет 900 кадров частиц; вывод эталона (fx.c до правки 313) — построчная печать заливки и команд рисования.
# Факт: с 035c4be0 (perf: невидимые и внеэкранные квады не раздувают заливку fxFill) и последующими правками (№731, №839, №847, №899, №908, №910, №923, №937) вывод по умолчанию ушёл от эталона СОЗНАТЕЛЬНО.
# Закон «каждое новое поведение под *_OLD»: при ВСЕХ выключателях в 1 текущий fx.c обязан давать эталон побайтно (ничего не просочилось мимо выключателей).
#   зелёный: все *_OLD=1 -> вывод == fx_ref313;  красные: без FX_CULL_OLD / FX_VEC899_OLD / FX_CUTOUT_OLD (по одному) вывод обязан разойтись; по умолчанию (без *_OLD) расходится — так и должно быть
#   tests/me/fx_host/ref_gate.sh    последняя строка PASS или FAIL
set -u
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"; cd "$ROOT"
[ -d /Library/Developer/CommandLineTools/SDKs/MacOSX.sdk ] && export SDKROOT=${SDKROOT:-/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk}
SET=${SET:-$HOME/Downloads/shar-psp-integ/build/test59tour/PSP/GAME/SHARTEST15}; PK=${FXSHR:-$SET/fx.shr}; [ -f "$PK" ] || { echo "FAIL: нет пакета частиц $PK (SET= / FXSHR=)"; exit 2; }
H=tests/me/fx_host; V=viewer; O=${W:-build/gates/fxref}; rm -rf "$O"; mkdir -p "$O"
# FX_BOOM_OLD стенд держит всегда (взрыв №391 проверяется отдельно по нормалям дороги — как tests/me/run.py)
M="COIN_GLINT910_OLD FX_BOOM_OLD FX_CUTOUT_OLD FX_GLINT908_OLD FX_SOFTDUST847_OLD FX_SPARKLE937_OLD FX_STAR923_OLD FX_VEC_ROOM_OLD FX_VEC899_OLD FXD_GROUND_OLD GLOW_GLINT_OLD FX_CULL_OLD"
build() { n=$1; shift; cc -O2 -ffp-contract=off -w -I $H -I $V -DFXD_EXPF=expf "$@" -o "$O/$n" $H/fx_host.c ${SRC:-$V/fx.c $V/fxdsp.c} -lm > "$O/$n.cc.txt" 2>&1 || { echo "FAIL: сборка $n (см. $O/$n.cc.txt)"; exit 2; }; "$O/$n" "$PK" "$O/$n.txt" 900 > "$O/$n.out" 2>&1 || { echo "FAIL: запуск $n"; exit 2; }; }
ndiff() { diff "$O/ref.txt" "$O/$1.txt" | grep -c '^<'; }
SRC=$H/fx_ref313.c build ref -DFX_BOOM_OLD=1
FL=""; for m in $M; do FL="$FL -D$m=1"; done
build allold $FL; build dflt -DFX_BOOM_OLD=1
nz=$(ndiff allold); nd=$(ndiff dflt); fail=0
echo "  все *_OLD=1: расходящихся строк $nz (нужно 0); по умолчанию (без *_OLD): $nd (нужно > 1000: правки после 313 живые)"
[ "$nz" = 0 ] && cmp -s "$O/ref.txt" "$O/allold.txt" || { echo "КРАСНОЕ: при всех выключателях вывод не равен эталону 313"; fail=1; }
[ "$nd" -gt 1000 ] || { echo "КРАСНОЕ: по умолчанию вывод почти равен эталону (правки после 313 не видны на стенде)"; fail=1; }
for skip in FX_CULL_OLD FX_VEC899_OLD FX_CUTOUT_OLD; do fl=""; for m in $M; do [ $m = $skip ] || fl="$fl -D$m=1"; done; build "no_$skip" $fl; k=$(ndiff "no_$skip")
  echo "  красный: без $skip расходится в $k строках"; [ "$k" -gt 0 ] || { echo "КРАСНЫЙ НЕ ПОЙМАН: выключатель $skip не влияет на вывод"; fail=1; }; done
[ $fail = 0 ] && echo "PASS (fx_ref313: при всех выключателях побайтно один, три красных пойманы)" || echo "FAIL (fx_ref313)"; exit $fail
