#!/usr/bin/env python3
# №984: строки MSNNPC984 (viewer/main_loop.h, flag msnnpcstat) из smoke.txt прогона city.txt: calls — обращений к gameMsnNpc, miss — промахов кэша, bad — расхождений с перебором npcFind, lookup_us — мкс на поиск за отрезок.
# check.py FILE            — печатает итог; код 0, если кэш работал (calls > 0, промахов не больше 1 % и не больше 10 на отрезок) и расхождений нет
# check.py FILE REF_FILE   — то же и во сколько раз поиск быстрее прежнего (сумма lookup_us у REF_FILE, где кэша нет): код 0 только при ускорении не меньше 1,4 раза
import re, sys
def load(f):
    rows = []
    for l in open(f, encoding='utf-8', errors='replace'):
        if l.startswith('MSNNPC984'): rows.append({k: v for k, v in re.findall(r'(\w+)=(\S+)', l)})
    return rows
r = load(sys.argv[1])
calls = sum(int(x['calls']) for x in r); miss = sum(int(x['miss']) for x in r); bad = sum(int(x['bad']) for x in r); us = sum(int(x['lookup_us']) for x in r)
ok = calls > 0 and bad == 0 and miss <= 0.01 * calls and all(int(x['miss']) <= 10 for x in r)
msg = f'обращений {calls}, промахов {miss}, расхождений с перебором {bad}, поиск {us} мкс'
if len(sys.argv) > 2:
    ref = sum(int(x['lookup_us']) for x in load(sys.argv[2])); k = ref / us if us else 0
    msg += f'; прежний перебор {ref} мкс, быстрее в {k:.1f} раза'; ok = ok and k >= 1.4
print(msg); sys.exit(0 if ok else 1)
