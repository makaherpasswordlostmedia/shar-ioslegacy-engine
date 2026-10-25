#!/usr/bin/env python3
# №980: строки LVSTATE (viewer/main_levels.h lvStateLine) до и после каждой смены уровня. Условия «после»: будка, лавка, гардероб и пауза закрыты, значок цели — нового уровня (L<n>) или нет значка.
# Матрица не пустая: до смены хотя бы дважды была открыта будка и хотя бы раз пауза. Код 0 — все смены чистые.
import re, sys
rows = []
for l in open(sys.argv[1], encoding='utf-8', errors='replace'):
    if l.startswith('LVSTATE'):
        d = dict(re.findall(r'(\w+)=(\S+)', l)); rows.append(d)
before = [r for r in rows if r['when'] == 'before']; after = [r for r in rows if r['when'] == 'after']
nb = sum(r['phone'] == '1' or r['shop'] == '1' or r['ward'] == '1' for r in before); npause = sum(r['pause'] == '1' for r in before)
bad = []
for r in after:
    if r['phone'] != '0' or r['shop'] != '0' or r['ward'] != '0' or r['pause'] != '0': bad.append(f"уровень {r['level']}: будка {r['phone']} лавка {r['shop']} гардероб {r['ward']} пауза {r['pause']}")
    m = re.search(r'/L(\d+)/', r['icon'])
    if r['icon'] != '-/0/0/L0/-' and m and m.group(1) != r['level'] and not r['icon'].startswith('-/'): bad.append(f"уровень {r['level']}: значок {r['icon']}")
print(f"смен {len(after)}, экран открыт до смены {nb}, пауза {npause}; не закрыто после: {len(bad)}" + ('' if not bad else ' (' + '; '.join(bad[:4]) + ')'))
sys.exit(0 if (not bad and nb >= 2 and npause >= 1 and len(after) >= 4) else 1)
