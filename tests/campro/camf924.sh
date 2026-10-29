#!/bin/bash
# №939 (бывш. №924) гейт цены камеры в езде. Маршрут тура F_L4_CR / F_L7_CR (goto 214.9 172.3 -3.0, drive 18), L4 и L7. Три правки: CAM_NFREUSE (глубина ближней плоскости перелёта не считается дважды),
# CG_DIRTY (перебор клеток в покое только после загрузки клетки), CG_PEND (список недостроенных клеток вместо полного перебора 1100+ клеток каждый кадр). Старое = все три флага 1 (camnfreuseold, cgdirtyold, cgpendold).
#   camf924.sh EBOOT            зелёный: (1) детерминированно (camdet 1) поток CAMF нового кода равен старому побайтно (глаз, взгляд, near), (2) выбор клетки для стройки сетки на каждом кадре CGSEL равен побайтно,
#                               (3) быстрый путь списка реально работал (CAMIN pend= hits >= 50 у нового, 0 у старого), (4) замер: nfr и перебор клеток дешевле (мкс на кадр, Мак)
#   camf924.sh --red EBOOT_RED  красный контроль: EBOOT собран с -DCAM_NFREUSE_RED=1 или -DCG_PEND_RED=1; поток нового обязан разойтись со старым (зелёные потоки лежат в $OUT/camf_*, cgd_*); печатает FAIL
# Прогоны через tools/emu_run.sh (EMU_OWNER, общий предел эмуляторов). OUT — рабочая папка (по умолчанию tests/campro/out).
H=$(cd "$(dirname "$0")" && pwd); RUN=${RUN:-$H/../../tools/emu_run.sh}; export OUT=${OUT:-$H/out} EMU_OWNER=${EMU_OWNER:-geocam}; mkdir -p $OUT; rc=0
ext() { for L in 4 7; do for N in $1; do grep -E "^CAMF" $OUT/out_$2d$L$N/smoke.txt | cut -d' ' -f3- > $OUT/camf_$3$L$N.txt; grep -E "^CGSEL" $OUT/out_$2d$L$N/smoke.txt > $OUT/cgd_$3$L$N.txt; done; done; }
if [ "$1" = "--red" ]; then B=$2
  for t in d4n d7n; do bash $RUN $H/$t.txt r$t $B 900 >/dev/null 2>&1 & done; wait
  for L in 4 7; do grep -E "^CAMF" $OUT/out_rd${L}n/smoke.txt | cut -d' ' -f3- > $OUT/camf_r$L.txt; grep -E "^CGSEL" $OUT/out_rd${L}n/smoke.txt > $OUT/cgd_r$L.txt
    cmp -s $OUT/camf_r$L.txt $OUT/camf_${L}o.txt && a=0 || a=1; cmp -s $OUT/cgd_r$L.txt $OUT/cgd_${L}o.txt && b=0 || b=1; echo "L$L красный контроль: CAMF расходится=$a, CGSEL расходится=$b"; [ $((a + b)) -gt 0 ] && rc=1; done
  [ $rc = 1 ] && echo 'СВЕРКА FAIL (красный контроль красный, как и должно быть)' || echo 'СВЕРКА PASS (КРАСНЫЙ КОНТРОЛЬ НЕ КРАСНЫЙ)'; [ $rc = 1 ] && exit 1 || exit 0; fi
B=${1:-$H/../../viewer/build_t60/EBOOT.PBP}
for t in d4n d4o d7n d7o; do bash $RUN $H/$t.txt $t $B 900 >/dev/null 2>&1 & done; wait
for L in 4 7; do for N in n o; do grep -E "^CAMF" $OUT/out_d$L$N/smoke.txt | cut -d' ' -f3- > $OUT/camf_$L$N.txt; grep -E "^CGSEL" $OUT/out_d$L$N/smoke.txt > $OUT/cgd_$L$N.txt; done
  nf=$(wc -l < $OUT/camf_${L}n.txt); nd=$(wc -l < $OUT/cgd_${L}n.txt)
  cmp $OUT/camf_${L}n.txt $OUT/camf_${L}o.txt && [ "$nf" -gt 300 ] && echo "L$L: CAMF совпал ($nf кадров)" || { echo "L$L: CAMF РАЗОШЁЛСЯ или кадров мало ($nf)"; rc=1; }
  cmp $OUT/cgd_${L}n.txt $OUT/cgd_${L}o.txt && [ "$nd" -gt 100 ] && echo "L$L: выбор клетки стройки совпал ($nd кадров)" || { echo "L$L: CGSEL РАЗОШЁЛСЯ или кадров мало ($nd)"; rc=1; }
  hn=$(grep "^CAMIN" $OUT/out_d${L}n/smoke.txt | tail -1 | grep -o "pend=[0-9]*" | cut -d= -f2); ho=$(grep "^CAMIN" $OUT/out_d${L}o/smoke.txt | tail -1 | grep -o "pend=[0-9]*" | cut -d= -f2)
  [ "${hn:-0}" -ge 50 ] && [ "${ho:-1}" = 0 ] && echo "L$L: быстрый путь списка: новое $hn обращений, старое $ho" || { echo "L$L: быстрый путь списка не работал (новое ${hn:-?}, старое ${ho:-?})"; rc=1; }
done
for t in c4n c4o c7n c7o; do bash $RUN $H/$t.txt $t $B 900 >/dev/null 2>&1 & done; wait
cost() { python3 - $OUT/out_$1/smoke.txt <<'PYEOF'
import re, sys
n = nfr = pf = fr = 0; st = False; w = 0
for l in open(sys.argv[1], errors='replace'):
    if l.startswith('SCENE'): st = '_b' in l.split()[1]
    if st and l.startswith('CAMSUB'):
        n += 1; m = re.search(r'nfr=([-\d.]+)', l); nfr += float(m.group(1)) if m else 0
    if l.startswith('CAMIN') and ' frames=' in l:
        w += 1; m = re.search(r'frames=(\d+)', l); f = int(m.group(1)); m2 = re.search(r' pf=(\d+)/', l); p = int(m2.group(1))
        if w == 3: fr, pf = f, p     # окно второго проезда (сцена CR*_b): первое окно — загрузка, второе — первый проезд
print('%.1f %.1f' % (nfr / max(n, 1), pf / max(fr, 1)))
PYEOF
}
for L in 4 7; do read nn pn <<< "$(cost c${L}n)"; read no po <<< "$(cost c${L}o)"; echo "L$L цена (мкс на кадр, Мак): ближняя плоскость $no -> $nn, перебор клеток $po -> $pn"
  python3 -c "import sys; sys.exit(0 if $nn < $no and $pn < $po else 1)" || { echo "L$L: новое не дешевле старого"; rc=1; }; done
[ $rc = 0 ] && echo 'СВЕРКА PASS' || echo 'СВЕРКА FAIL'; exit $rc
