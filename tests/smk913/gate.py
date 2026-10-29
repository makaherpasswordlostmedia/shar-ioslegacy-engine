# №913: журнал секунды смоука растянут на 7 кадров (SMK_SPREAD_OLD=0, viewer/main_loop.h, smoke.h): самый тяжёлый кадр блока — строка SECBLK max=мкс — должен стать меньше, журнал — тем же по составу.
# Запуск: python3 gate.py smoke_старый.txt smoke_новый.txt   (одна и та же сцена, старый — сборка с -DSMK_SPREAD_OLD=1; код выхода 0 = OK)
# Красный: старый самый тяжёлый кадр ≥ 2000 мкс (если меньше — сцена слишком лёгкая, проверка слепая, код 2); зелёный: новый медиана max ≤ 1300 мкс и ≤ 0,5 от старого, сумма за секунду в пределах 15 %, типы строк те же (±8 на тип).
import sys,re,collections
def rd(f):
    v=[tuple(int(x) for x in re.findall(r'us=(\d+) max=(\d+)',l)[0]) for l in open(f,errors='replace') if l.startswith('SECBLK')]
    ty=collections.Counter(l.split(' ',1)[0] for l in open(f,errors='replace') if re.match(r'[A-Z0-9_]+ ',l))
    return v,ty
(vo,to),(vn,tn)=rd(sys.argv[1]),rd(sys.argv[2])
if len(vo)<10 or len(vn)<10: print('ОШИБКА: мало строк SECBLK (%d / %d)'%(len(vo),len(vn))); sys.exit(2)
med=lambda x: sorted(x)[len(x)//2]
mo,mn=med([b for a,b in vo]),med([b for a,b in vn]); so,sn=med([a for a,b in vo]),med([a for a,b in vn])
print('старый: самый тяжёлый кадр медиана %d мкс, сумма за секунду %d; новый: %d мкс, сумма %d'%(mo,so,mn,sn))
if mo<2000: print('ОШИБКА: старый не красный (медиана %d < 2000) — проверка слепа'%mo); sys.exit(2)
ok=True
if mn>1300 or mn>0.5*mo: print('FAIL: новый самый тяжёлый кадр %d мкс (нужно ≤ 1300 и ≤ 0,5 от %d)'%(mn,mo)); ok=False
if abs(sn-so)>0.15*so: print('FAIL: сумма за секунду %d против %d'%(sn,so)); ok=False
bad={k:(to[k],tn[k]) for k in set(to)|set(tn) if abs(to[k]-tn[k])>8}
if bad: print('FAIL: типы строк журнала различаются:',bad); ok=False
print('PASS' if ok else 'FAIL'); sys.exit(0 if ok else 1)
