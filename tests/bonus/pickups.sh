#!/bin/bash
# Гейт части «подборы, ловушки, огонь, DEATH» бонус-игры на Маке (правка 420, 09.10): tools/bonus/race_host.c на настоящих трассах.
#   tests/bonus/pickups.sh            (трассы — build/bonus/b0N.shr/.bns: python tools/bonus/export.py --all)
# ЗЕЛЁНЫЙ:
#   (1) счёт: в BNS2 трассы столько подборов, зон (ловушки, B04G, свет) и в JMP1 столько объёмов DEATH, сколько на диске
#       (tools/bonus/track.py pickups/hazards, Event 4 b0Ndata) — экспорт ничего не потерял; объект ловушки ANM1 связан (b04, b07);
#   (2) --probe на b01…b07 в оба хода: каждый ключ чинит (урон 0,8 -> 0) и возвращается через 5 с, каждое нитро разгоняет
#       (за 0,5 с быстрее на 1,5 м/с и больше, чем без него), каждый объём DEATH возвращает на точку данных курсом локатора (обратный
#       ход + π) вне зоны, каждый датчик ловушки поднимает живые объёмы объекта больше чем на 3 м и опускает назад, каждая сфера B04G
#       подбрасывает, только пока поршни выходят, зона света отдаёт цвет данных;
#   (3) гонка 3 круга b02…b07 по ходу (соперники ИИ, предел 400 с): подборы взяты хоть раз, ловушки b04 и b07 срабатывают в гонке,
#       на каждой трассе хоть одна машина доезжает (эффекты не держат машины навсегда).
# КРАСНЫЙ: тот же полигон, собранный с -DBONUS_PICKUPS_OLD=1 (как до этой части), обязан уронить (2) на каждой трассе с подборами
#   и (3). Журнал: build/gates/bonus/pickups_<время>.txt
cd "$(dirname "$0")/../.."
ulimit -n 65536
B=${BONUS_DATA:-build/bonus}; OUT=${BONUS_OUT:-build/gates/bonus}; mkdir -p "$OUT" "$B/bin"; LOG=$OUT/pickups_$(date +%Y%m%d-%H%M%S).txt
PY=.venv/bin/python; [ -x "$PY" ] || PY=python3
tools/bonus/build_host.sh "$B/bin/race_host" || { echo "FAIL: сборка полигона"; exit 2; }
EXTRA=-DBONUS_PICKUPS_OLD=1 tools/bonus/build_host.sh "$B/bin/race_host_old" || { echo "FAIL: сборка красного полигона"; exit 2; }
for t in 1 2 3 4 5 6 7; do [ -f $B/b0$t.shr ] && [ -f $B/b0$t.bns ] || { echo "нет $B/b0$t.shr/.bns: python tools/bonus/export.py --all"; exit 2; }; done
fail=0
# (1) ожидаемое — с диска
EXP=$("$PY" - <<'EOF'
import sys; sys.path.insert(0, 'tools/bonus')
import track as T
for n in range(1, 8):
    L = T.locators(n)
    d = sum(len(l['trig']) for l in L if l['type'] == 0 and l['data'] and l['data'][0] == T.EV_DEATH)
    tob = len([o for o in T.anim_collision(n) if o in ('spikes', 'pistons')])
    print(n, len(T.pickups(L)), len(T.hazards(L)), d, tob)
EOF
)
echo "ожидаемое с диска (трасса подборов зон DEATH объектов-ловушек):" | tee -a "$LOG"; echo "$EXP" | tee -a "$LOG"
probe() { "$B/bin/$1" $B/b0$2.shr $B/b0$2.bns $B/msncars-b.shr --probe ${3:-}; }
echo "== (1)+(2) зелёный --probe" | tee -a "$LOG"
while read -r t np nh nd nt; do
  for r in "" --reverse; do
    out=$(probe race_host $t $r); echo "$out" >> "$LOG"
    hdr=$(echo "$out" | head -1); res=$(echo "$out" | grep '^RESULT' | cut -c9-)
    got=$(echo "$hdr" | sed -n 's/.*подборов \([0-9]*\), зон \([0-9]*\), DEATH \([0-9]*\), объектов ловушек \([0-9-]*\).*/\1 \2 \3 \4/p')
    if [ "$got" != "$np $nh $nd $nt" ]; then echo "  (1) b0$t ${r:-forward}: в данных порта '$got', на диске '$np $nh $nd $nt'"; fail=1; fi
    if [ "$res" != "PASS" ] && [ $((np + nh + nd)) -gt 0 ]; then echo "  (2) b0$t ${r:-forward}: $(echo "$out" | grep -m3 'PROBE FAIL')"; fail=1; fi
    if [ $((np + nh + nd)) -eq 0 ]; then echo "  b0$t ${r:-forward}: подборов, зон и DEATH на диске нет — проверять нечего (счёт сошёлся)"
    else echo "  b0$t ${r:-forward}: $(echo "$out" | grep '^PROBE checks') $res"; fi
  done
done <<< "$EXP"
echo "== (3) зелёный: гонка 3 круга по ходу" | tee -a "$LOG"
tot=0
for t in 2 3 4 5 6 7; do
  out=$("$B/bin/race_host" $B/b0$t.shr $B/b0$t.bns $B/msncars-b.shr --laps 3 --secs 400); echo "$out" >> "$LOG"
  e=$(echo "$out" | grep '^EFFECTS'); fin=$(echo "$out" | grep -c 'доехал место'); echo "  b0$t: $e; доехали $fin/4 за 400 с"
  [ "$fin" -gt 0 ] || { echo "  (3) b0$t: с эффектами никто не доехал за 400 с (ловушка/DEATH держат машины)"; fail=1; }
  n=$(echo "$e" | sed -n 's/.*nitro=\([0-9]*\) wrench=\([0-9]*\).*/\1 \2/p'); tot=$((tot + ${n% *} + ${n#* }))
  if [ $t = 4 ] || [ $t = 7 ]; then tr=$(echo "$e" | sed -n 's/.* trap=\([0-9]*\).*/\1/p'); [ "${tr:-0}" -gt 0 ] || { echo "  (3) b0$t: ловушка в гонке не сработала"; fail=1; }; fi
done
[ $tot -gt 0 ] || { echo "  (3) за 6 гонок ни одного подбора"; fail=1; }
echo "  подборов за 6 гонок: $tot"
echo "== красный (-DBONUS_PICKUPS_OLD=1)" | tee -a "$LOG"
rfail=0; rn=0
while read -r t np nh nd nt; do
  [ $((np + nh + nd)) -gt 0 ] || continue
  rn=$((rn + 1)); out=$(probe race_host_old $t); prc=$?; echo "$out" >> "$LOG"
  pc=$(echo "$out" | sed -n 's/^PROBE checks=\([0-9]*\).*/\1/p')
  if [ "$prc" != 1 ] || [ "${pc:-0}" -le 0 ] || ! echo "$out" | grep -q '^RESULT: FAIL'; then
    echo "  красный b0$t: НЕТ реальных probe checks/FAIL (rc=$prc checks=$pc)"; rfail=1
  fi
  echo "$out" | grep -q '^RESULT: PASS' && { echo "  красный b0$t: probe ПРОШЁЛ — не пойман"; rfail=1; }
done <<< "$EXP"
out=$("$B/bin/race_host_old" $B/b07.shr $B/b07.bns $B/msncars-b.shr --laps 3); echo "$out" >> "$LOG"
e=$(echo "$out" | grep '^EFFECTS'); echo "  b07 гонка: $e"
echo "$e" | grep -q 'nitro=0 wrench=0 death=0 trap=0 launch=0 light=0' || { echo "  красный: в гонке эффекты есть — не пойман"; rfail=1; }
[ $rfail = 0 ] && echo "красный пойман: probe упал на $rn трассах из $rn, эффектов в гонке 0" || fail=1
echo "журнал: $LOG"
[ $fail = 0 ] && echo "ГЕЙТ tests/bonus/pickups: PASS" || echo "ГЕЙТ tests/bonus/pickups: FAIL"
exit $fail
