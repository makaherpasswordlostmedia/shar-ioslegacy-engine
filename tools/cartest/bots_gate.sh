#!/bin/bash
# Гейт физических ботов: три поправки роя, у каждой красный контроль (тот же прогон с выключателем прежнего поведения должен покраснеть).
#   death    зоны DEATH применяются (L3: падение в воду у пристани не копит прыжки и возвраты)  выключатель --nodeath
#   phantom  проход прозрачной стены (ящик с материалом 2, правка 475) — справочно, не сквозной проезд  выключатель --nophantom
#   drill    застрявший, которого игрок выручил бы манёврами (7, в том числе газ-назад по кругу для №738), — застрял бот   выключатель --nodrill
#   backreturn отскок от забора, в который вошли с изнанки, — не проезд с лица                         выключатель --nobackret
#   escape   сдвиг собственного выхода игры (№738, перч, тупик 32) сквозь забор — не проезд           выключатель --noescape
#   escapefence цель плавного выхода (перч/№738) проверяется при твёрдом заборе, как её потом ставит carPlace  выключатель -DESCAPE_FENCE_OLD=1
#   wedge738 широкий поиск выхода зажатой (кольца до 40 м) и возврат на надёжное место через 9 с (car.c)  выключатели -DWEDGE738_WIDE_OLD=1, -DWEDGE738_RECOVER_OLD=1
# Проверки phantom и drill идут с --nodeath: те же прогоны, что в ночном отчёте (с DEATH траектории другие).
# Данные: BOT_SET (по умолчанию ~/Downloads/shar-psp/build/botset), BOT_ROADS (…/build/sandbox) — только чтение. Нет данных — пропуск (код 77).
set -u
HERE=$(cd "$(dirname "$0")" && pwd); ROOT=$(cd "$HERE/../.." && pwd)
BOT_SET=${BOT_SET:-$HOME/Downloads/shar-psp/build/botset}; BOT_ROADS=${BOT_ROADS:-$HOME/Downloads/shar-psp/build/sandbox}
[ -f "$BOT_SET/level.shr" ] && [ -f "$BOT_SET/l3/level.shr" ] && [ -f "$BOT_SET/l7/level.shr" ] || { echo "нет данных уровней в $BOT_SET — пропуск"; exit 77; }
T=$(mktemp -d "${TMPDIR:-/tmp}/botsgate.XXXXXX"); trap 'rm -rf "$T"' EXIT
cc -std=c99 -O2 -w "$HERE/bots_swarm.c" "$ROOT/viewer/car.c" "$ROOT/viewer/col.c" "$ROOT/viewer/props.c" "$ROOT/viewer/stateprops.c" "$ROOT/viewer/coins.c" -lm -o "$T/bs" || { echo "СБОРКА НЕ УДАЛАСЬ"; exit 1; }
for V in both:-DWEDGE738_WIDE_OLD=1\ -DWEDGE738_RECOVER_OLD=1 rec:-DWEDGE738_RECOVER_OLD=1 fence:-DESCAPE_FENCE_OLD=1; do
  cc -std=c99 -O2 -w ${V#*:} "$HERE/bots_swarm.c" "$ROOT/viewer/car.c" "$ROOT/viewer/col.c" "$ROOT/viewer/props.c" "$ROOT/viewer/stateprops.c" "$ROOT/viewer/coins.c" -lm -o "$T/bs_${V%%:*}" || { echo "СБОРКА (OLD) НЕ УДАЛАСЬ"; exit 1; }
done
lvl() { if [ "$1" = 1 ]; then echo "$BOT_SET/level.shr"; else echo "$BOT_SET/l$1/level.shr"; fi; }
run() {  # уровень seed секунд [флаги] -> строка итога в $T/last
  local L=$1 S=$2 N=$3; shift 3
  "$T/bs" --level "$(lvl $L)" --lvl "$L" --roads "$BOT_ROADS/roads-l$L.bin" --out "$T/o.tsv" --seed "$S" --cars 128 --seconds "$N" --cap 1000 "$@" 2> "$T/last"
  tail -n 1 "$T/last"
}
run_old() { local V=$1 L=$2 S=$3 N=$4; shift 4; "$T/bs_$V" --level "$(lvl $L)" --lvl "$L" --roads "$BOT_ROADS/roads-l$L.bin" --out "$T/o.tsv" --seed "$S" --cars 128 --seconds "$N" --cap 1000 "$@" 2> "$T/last"; tail -n 1 "$T/last"; }
get() { echo "$LINE" | sed -n "s/.* $1=\([0-9]*\)\/\([0-9]*\).*/\2/p"; }   # «всего» по типу
fail=0; ok() { echo "  ✓ $*"; }; bad() { echo "  ✗ $*"; fail=1; }
echo "death (L3 seed 2971351, 30 с)"
LINE=$(run 3 2971351 30); n_ramp=$(get ramp); n_death=$(get death)
LINE=$(run 3 2971351 30 --nodeath); o_ramp=$(get ramp); o_death=$(get death)
[ "${n_death:-0}" -ge 1 ] && [ "${n_ramp:-99}" -le 10 ] && ok "новое: death=$n_death ramp=$n_ramp (≤10)" || bad "новое: death=${n_death:-?} ramp=${n_ramp:-?}"
[ "${o_death:-1}" -eq 0 ] && [ "${o_ramp:-0}" -gt 10 ] && ok "красный контроль --nodeath: death=$o_death ramp=$o_ramp (>10, краснеет как надо)" || bad "контроль --nodeath не покраснел: death=${o_death:-?} ramp=${o_ramp:-?}"
echo "phantom (L1 seed 2981649, 4 с)"
LINE=$(run 1 2981649 4 --nodeath); n_thr=$(get through); n_ph=$(get phantom)
LINE=$(run 1 2981649 4 --nodeath --nophantom); o_thr=$(get through); o_ph=$(get phantom)
[ "${n_thr:-1}" -eq 0 ] && [ "${n_ph:-0}" -ge 1 ] && ok "новое: through=$n_thr phantom=$n_ph" || bad "новое: through=${n_thr:-?} phantom=${n_ph:-?}"
[ "${o_thr:-0}" -ge 1 ] && ok "красный контроль --nophantom: through=$o_thr (краснеет как надо)" || bad "контроль --nophantom не покраснел: through=${o_thr:-?}"
echo "drill (L7 seed 2983555, 17 с)"
LINE=$(run 7 2983555 17 --nodeath); n_st=$(get stuck); n_sb=$(get stuckbot)
LINE=$(run 7 2983555 17 --nodeath --nodrill); o_st=$(get stuck)
[ "${n_st:-1}" -eq 0 ] && [ "${n_sb:-0}" -ge 2 ] && ok "новое: stuck=$n_st stuckbot=$n_sb" || bad "новое: stuck=${n_st:-?} stuckbot=${n_sb:-?} (ждали 0 и ≥2)"
[ "${o_st:-0}" -ge 2 ] && ok "красный контроль --nodrill: stuck=$o_st (боты как ошибки, краснеет как надо)" || bad "контроль --nodrill не покраснел: stuck=${o_st:-?}"
echo "backreturn (L3 seed 2986151, 4 с): отскок через звено, в которое вошли с изнанки"
LINE=$(run 3 2986151 4 --nodeath); n_thr=$(get through); n_br=$(get backreturn)
LINE=$(run 3 2986151 4 --nodeath --nobackret); o_thr=$(get through)
[ "${n_thr:-1}" -eq 0 ] && [ "${n_br:-0}" -ge 1 ] && ok "новое: through=$n_thr backreturn=$n_br" || bad "новое: through=${n_thr:-?} backreturn=${n_br:-?}"
[ "${o_thr:-0}" -ge 1 ] && ok "красный контроль --nobackret: through=$o_thr" || bad "контроль --nobackret не покраснел: through=${o_thr:-?}"
echo "escape (L6 seed 2971354, 15 с): собственный сдвиг игры сквозь забор"
LINE=$(run_old both 6 2971354 15 --nodeath); n_thr=$(get through); n_es=$(get escape)
LINE=$(run_old both 6 2971354 15 --nodeath --noescape); o_thr=$(get through)
[ "${n_thr:-1}" -eq 0 ] && [ "${n_es:-0}" -ge 1 ] && ok "новое: through=$n_thr escape=$n_es" || bad "новое: through=${n_thr:-?} escape=${n_es:-?}"
[ "${o_thr:-0}" -ge 1 ] && ok "красный контроль --noescape: through=$o_thr" || bad "контроль --noescape не покраснел: through=${o_thr:-?}"
echo "escape-забор (L6 seed 2971948, 51 с): цель выхода на линии забора, settle выдавливает сквозь"
LINE=$(run 6 2971948 51); n_thr=$(get through)
LINE=$(run_old fence 6 2971948 51); o_thr=$(get through)
[ "${n_thr:-1}" -eq 0 ] && ok "новое: through=$n_thr" || bad "новое: through=${n_thr:-?}"
[ "${o_thr:-0}" -ge 1 ] && ok "красный контроль ESCAPE_FENCE_OLD=1: through=$o_thr (машина выдавлена на 3,5 м за забор)" || bad "контроль ESCAPE_FENCE_OLD не покраснел: through=${o_thr:-?}"
echo "wedge738: широкий поиск 12…40 м и возврат на надёжное место (берег L7 seed 2983555; яма L4 seed 2985852)"
LINE=$(run_old rec 7 2983555 17 --nodeath); r_st=$(get stuck)
LINE=$(run_old both 7 2983555 17 --nodeath); b_st=$(get stuck)
[ "${r_st:-1}" -eq 0 ] && ok "берег L7 без возврата (RECOVER_OLD): stuck=$r_st — одного широкого поиска хватает" || bad "берег L7 без возврата: stuck=${r_st:-?}"
[ "${b_st:-0}" -ge 1 ] && ok "красный контроль WIDE_OLD+RECOVER_OLD: stuck=$b_st (как до правки)" || bad "контроль WIDE_OLD+RECOVER_OLD не покраснел: stuck=${b_st:-?}"
LINE=$(run 4 2985852 16 --nodeath); n4=$(get stuck); LINE=$(run_old rec 4 2985852 16 --nodeath); o4=$(get stuck)
[ "${n4:-1}" -eq 0 ] && ok "яма L4 новое: stuck=$n4" || bad "яма L4 новое: stuck=${n4:-?}"
[ "${o4:-0}" -ge 1 ] && ok "красный контроль RECOVER_OLD (яма глубже ровной земли): stuck=$o4" || bad "контроль RECOVER_OLD не покраснел: stuck=${o4:-?}"
[ $fail = 0 ] && echo "ГЕЙТ БОТОВ: зелёный" || echo "ГЕЙТ БОТОВ: КРАСНЫЙ"
exit $fail
