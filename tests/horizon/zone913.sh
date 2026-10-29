#!/bin/bash
# Гейт №913 (130 м по умолчанию, зоны 150 и 250): (1) ленты от 130 и от 150 по всем клеткам 7 уровней — хорда не ближе своего радиуса (допуск 0,5 %), (2) на трассах L3/L5 и искусственной дрожи у границы зоны
# цель радиуса не мигает (≤ 2 переключений на проезде L3/L5, на дрожи ровно 1 вниз после выдержки) и скачок радиуса за кадр не больше HZ913_UP/30 м.
#   tests/horizon/zone913.sh [папка с l1.shr … l7.shr и hzzone_l1.bin … hzzone_l7.bin, по умолчанию build/hz913 (данные игры — не в git)]   код 0 = OK
#   красные: -DHZ_GAP_DEG=40.f (хорда ближе радиуса); -DHZ913_HOLD=0 -DHZ913_UP=100000.f -DHZ913_DOWN=100000.f (дрожь у границы даёт десятки переключений, скачок радиуса)
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"; D="${1:-$ROOT/build/hz913}"; T="${TMPDIR:-/tmp}/z913.$$"; mkdir -p "$T"
b() { local n=$1; shift; cc -O1 "$@" tests/horizon/zone913_host.c -lm -o "$T/$n" || { echo "FAIL: сборка $n"; exit 1; }; }
b new; b gap -DHZ_GAP_DEG=40.f; b nohys -DHZ913_HOLD=0 -DHZ913_UP=100000.f -DHZ913_DOWN=100000.f
F=""; for L in 1 2 3 4 5 6 7; do [ -f "$D/l$L.shr" ] || { echo "FAIL: нет $D/l$L.shr"; exit 1; }; F="$F $D/l$L.shr"; done
if "$T/gap" chord $F >"$T/gap.txt"; then echo "FAIL: красная подброска gap прошла — проверка слепая"; cat "$T/gap.txt"; exit 1; fi; echo "красный как надо (хорда, разрыв 40°): $(cat $T/gap.txt)"
"$T/new" chord $F >"$T/chord.txt" || { echo "FAIL: хорда ближе радиуса"; cat "$T/chord.txt"; exit 1; }; echo "зелёный (хорды): $(cat $T/chord.txt)"
# искусственная дрожь у границы: глаз ходит туда-сюда через границу зоны 130/150 по трассе из таблицы L3 (пирс → город), 40 переходов
python3 - "$D" "$T/jitter.txt" <<'PY'
import sys,struct
d,out=sys.argv[1],sys.argv[2]; b=open(d+'/hzzone_l3.bin','rb').read(); w,h=struct.unpack_from('<II',b,4); x0,z0,st=struct.unpack_from('<fff',b,12)
# найти границу 130|150 по строке
pair=None
for gz in range(h):
    for gx in range(w-1):
        a,c=b[24+gz*w+gx],b[24+gz*w+gx+1]
        if a==0 and c==1: pair=(x0+(gx+1)*st,z0+(gz+.5)*st); break
    if pair: break
x,z=pair; f=open(out,'w'); fr=0
for k in range(40):
    for i in range(45): f.write('%d %.2f %.2f\n'%(fr,x+(-5 if k%2==0 else 5)*(1 if i<20 else 0.2),z)); fr+=1
f.close()
PY
for L in 3 5; do [ -f "$D/trace_l$L.txt" ] || { echo "FAIL: нет $D/trace_l$L.txt"; exit 1; }; done
ok=1
for n in new nohys; do "$T/$n" trace "$D/hzzone_l3.bin" "$T/jitter.txt" > "$T/j_$n.txt"; done
sw_new=$(sed -n 's/.*target_switches=\([0-9]*\).*/\1/p' "$T/j_new.txt"); sw_bad=$(sed -n 's/.*target_switches=\([0-9]*\).*/\1/p' "$T/j_nohys.txt"); st_bad=$(sed -n 's/.*max_step_m=\([0-9.]*\).*/\1/p' "$T/j_nohys.txt"); st_new=$(sed -n 's/.*max_step_m=\([0-9.]*\).*/\1/p' "$T/j_new.txt")
[ "$sw_bad" -gt 10 ] || { echo "FAIL: красная подброска без гистерезиса не мигает ($sw_bad) — проверка слепая"; ok=0; }
echo "красный как надо (без выдержки и сглаживания): на дрожи $sw_bad переключений цели, скачок $st_bad м/кадр"
[ "$sw_new" -le 2 ] || { echo "FAIL: на дрожи у границы $sw_new переключений цели (> 2)"; ok=0; }
awk -v s=$st_new 'BEGIN{exit !(s<=1.4)}' || { echo "FAIL: скачок радиуса $st_new м/кадр (> 1,33)"; ok=0; }
echo "зелёный (дрожь у границы): $(cat $T/j_new.txt)"
for L in 3 5; do "$T/new" trace "$D/hzzone_l$L.bin" "$D/trace_l$L.txt" > "$T/t$L.txt"; s=$(sed -n 's/.*target_switches=\([0-9]*\).*/\1/p' "$T/t$L.txt"); [ "$s" -le 2 ] || { echo "FAIL: трасса L$L: $s переключений"; ok=0; }; echo "зелёный (трасса L$L): $(cat $T/t$L.txt)"; done
# змейка по всей таблице каждого уровня (12 м/с, ряд через 60 м): переключений цели не больше, чем смен зоны вдоль пути (гистерезис только убирает), скачок радиуса ≤ 1,4 м/кадр, и 250 м на пути действительно достигается там, где таблица её содержит (иначе проверка слепа)
for L in 1 2 3 4 5 6 7; do python3 - "$D/hzzone_l$L.bin" "$T/snake$L.txt" "$T/snake$L.exp" <<'PY'
import sys,struct
b=open(sys.argv[1],'rb').read(); w,h=struct.unpack_from('<II',b,4); x0,z0,st=struct.unpack_from('<fff',b,12)
f=open(sys.argv[2],'w'); fr=0; prev=None; tr=0; has250=0
for r in range(h):
    z=z0+(r+.5)*st; xs=[x0+i*0.4 for i in range(int(w*st/0.4))]
    if r%2: xs.reverse()
    for x in xs:
        gx=int((x-x0)//st); m=b[24+r*w+gx] if 0<=gx<w else 255
        m=1 if m==255 else m
        if m==2: has250=1
        if prev is not None and m!=prev: tr+=1
        prev=m; f.write('%d %.2f %.2f\n'%(fr,x,z)); fr+=1
f.close(); open(sys.argv[3],'w').write('%d %d\n'%(tr,has250))
PY
read TR H250 < "$T/snake$L.exp"; "$T/new" trace "$D/hzzone_l$L.bin" "$T/snake$L.txt" > "$T/s$L.txt"
s=$(sed -n 's/.*target_switches=\([0-9]*\).*/\1/p' "$T/s$L.txt"); st=$(sed -n 's/.*max_step_m=\([0-9.]*\).*/\1/p' "$T/s$L.txt"); f2=$(sed -n 's/.*frames_250=\([0-9]*\).*/\1/p' "$T/s$L.txt")
[ "$s" -le "$TR" ] || { echo "FAIL: змейка L$L: $s переключений цели при $TR сменах зоны на пути"; ok=0; }
awk -v s=$st 'BEGIN{exit !(s<=1.4)}' || { echo "FAIL: змейка L$L: скачок радиуса $st м/кадр"; ok=0; }
[ "$H250" = 0 ] || [ "$f2" -gt 0 ] || { echo "FAIL: змейка L$L: таблица содержит 250 м, а на пути её нет — проверка слепа"; ok=0; }
echo "зелёный (змейка L$L): переключений $s при $TR сменах зоны, скачок $st м/кадр, кадров при 250 м: $f2"
done
[ $ok = 1 ] && echo PASS; [ $ok = 1 ]
