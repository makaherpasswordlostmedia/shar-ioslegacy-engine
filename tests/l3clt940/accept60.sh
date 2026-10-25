#!/bin/bash
# №940 приёмка (окно l3fix): L3 набережная, память длинных треугольников заплатки №921 (carLongTris): отказ запоминается, нет утечки, предел построек на кадр, уплотнение участка, сортировка Шелла, пропуск обхода при неизменном кадре.
#   tests/l3clt940/accept60.sh   — сама собирает три EBOOT (новый; красный -DCLT_FIX940_OLD=1; красный уплотнения -DCLT_BREAK940=1), гоняет сценарии в эмуляторе (EMU_OWNER=l3fix, tools/emu_run.sh), печатает последней строкой PASS или FAIL.
#   Проверки:  (A) patch_us в сценах L3 при пределе участка 6000 байт: новый <= 10 % прежнего (красный EBOOT, прежнее поведение; у него >= 200 мс за сцены);
#              (B) красный контроль проверки (A): красный против самого себя обязан дать FAIL;
#              (C) уплотнение под нагрузкой (cltstress940: ключ кэша меняется каждый кадр): уплотнений >= 5, сверка содержимого cbad == 0;  (D) красный -DCLT_BREAK940=1 обязан дать cbad > 0;
#              (E) гейт tests/dropfix921 (L1, L3, L4, L5) на новом EBOOT: PASS; (F) тот же гейт в режиме 0 (красный контроль самого гейта): FAIL.
W="$(cd "$(dirname "$0")/../.." && pwd)"; T=$W/tests/l3clt940; export EMU_OWNER=l3fix OUT=$W/run/acc940; mkdir -p "$OUT"
export PATH=$HOME/Downloads/shar-psp/build/xcshim/bin:$PATH; export PSPDEV=$W/pspdev PATH=$W/pspdev/bin:$PATH
BASEF="-DJITTER_STRIPS_OLD=1 -DJITTER_CAR_OLD=1 -DFE_DEMO_PS2_OLD=1 -DBB_SYNC_OLD=1"
build() { local n=$1 extra=$2; ( cd $W/viewer && psp-cmake -S . -B build_acc940_$n -DSHAR_RELEASE=ON -DSHAR_RELEASE_KEEP_DIAG=ON -DSHAR_RELEASE_KEEP_HUD=ON -DSHAR_RELEASE_KEEP_SMOKE=ON -DCMAKE_C_FLAGS="$BASEF $extra" >/dev/null && cmake --build build_acc940_$n -j2 >$OUT/build_$n.log 2>&1 ) || { echo "сборка $n упала, см. $OUT/build_$n.log"; echo FAIL; exit 1; }; }
echo "сборка трёх EBOOT (новый, красный OLD, красный BREAK)"
build n "" & build r "-DCLT_FIX940_OLD=1" & build b "-DCLT_BREAK940=1" & wait
EBN=$W/viewer/build_acc940_n/EBOOT.PBP; EBR=$W/viewer/build_acc940_r/EBOOT.PBP; EBB=$W/viewer/build_acc940_b/EBOOT.PBP
for e in $EBN $EBR $EBB; do [ -f $e ] || { echo "нет $e"; echo FAIL; exit 1; }; done
sed 's/^POOLLIM$/flag cltpool940 6000/' $T/tour_l3_acc.txt > $OUT/tour_pool.txt
sed 's/^EXTRA$/flag cltstress940 1/' $T/short.txt > $OUT/short_stress.txt
echo "прогоны в эмуляторе (новый и красный на хвосте L3 с пределом участка; стресс уплотнения на новом и BREAK)"
$W/tools/emu_run.sh $OUT/tour_pool.txt tn $EBN 900 >/dev/null &
$W/tools/emu_run.sh $OUT/tour_pool.txt tr $EBR 900 >/dev/null &
$W/tools/emu_run.sh $OUT/short_stress.txt sn $EBN 600 >/dev/null &
$W/tools/emu_run.sh $OUT/short_stress.txt sb $EBB 600 >/dev/null &
wait
echo "гейт dropfix921 на новом (режим 1) и красный контроль гейта (режим 0)"
G1=$($W/tests/dropfix921/gate.sh $EBN 1 2>&1); echo "$G1" | tail -3
G0=$($W/tests/dropfix921/gate.sh $EBN 0 2>&1); echo "$G0" | tail -3
python3 - "$OUT" "$G1" "$G0" <<'PYEOF'
import re, sys
OUT, G1, G0 = sys.argv[1], sys.argv[2], sys.argv[3]
SC = ('F_FLAT_L3S', 'F_FLAT_L3B', 'F_L3_FAR1', 'F_L3_FAR0')
def rows(name):
    try: return [dict(re.findall(r'(\w+)=(\S+)', l)) for l in open('%s/out_%s/smoke.txt' % (OUT, name), errors='replace') if l.startswith('CARPATCH ')]
    except OSError: return []
def cost(name):
    r = [x for x in rows(name) if x.get('sc') in SC]
    return sum(int(x['patch_us']) for x in r), len(r), sum(int(x['box']) for x in r)
ok = True
def verdict(good, text, expect_fail=False):
    global ok
    res = good != expect_fail
    print('  %-6s %s' % ('ok' if res else 'СБОЙ', text)); ok = ok and res
n, r = cost('tn'), cost('tr')
print('A. L3 хвост тура, участок 6000 Б: patch_us новый %d мкс (строк %d, box %d), прежний %d мкс (строк %d, box %d); на PSP ×5,8 = %.0f и %.0f мс за все сцены' % (n[0], n[1], n[2], r[0], r[1], r[2], n[0] * 5.8 / 1000, r[0] * 5.8 / 1000))
def chk(a, b): return b[0] >= 200000 and b[1] >= 15 and a[1] >= 15 and a[0] <= 0.10 * b[0]
verdict(chk(n, r), 'новый <= 10 %% прежнего (%.1f %%), прежний >= 200 мс' % (100.0 * n[0] / max(1, r[0])))
verdict(chk(r, r), 'красный контроль проверки A: прежний против прежнего обязан дать FAIL', expect_fail=True)
sn = [x for x in rows('sn')]; sb = [x for x in rows('sb')]
cn = int(sn[-1]['compact']) if sn else -1; bn = int(sn[-1]['cbad']) if sn else -1
cb = int(sb[-1]['compact']) if sb else -1; bb = int(sb[-1]['cbad']) if sb else -1
print('C. стресс уплотнения (новый): compact=%d cbad=%d;  D. BREAK: compact=%d cbad=%d' % (cn, bn, cb, bb))
verdict(cn >= 5 and bn == 0, 'уплотнений >= 5, содержимое после сдвига совпадает (cbad == 0)')
verdict(cb >= 5 and bb > 0, 'красный BREAK обязан дать cbad > 0', expect_fail=False)
verdict(G1.strip().splitlines()[-1] == 'PASS' if G1.strip() else False, 'E. гейт dropfix921 (L1, L3, L4, L5) на новом: PASS')
verdict(G0.strip().splitlines()[-1] == 'FAIL' if G0.strip() else False, 'F. тот же гейт, режим 0 (красный контроль гейта): FAIL')
print('PASS' if ok else 'FAIL')
PYEOF
