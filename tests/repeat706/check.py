#!/usr/bin/env python3
"""№706: шаги списка за зажатие 1,5 с. check.py ИМЯ smoke.txt -> «ИМЯ tap=1 hold=M» и код 0, если M >= порога (повтор работает)
и одиночный нажим дал ровно один шаг. Сценарий: короткий нажим (0,15 с), пауза 1,2 с, зажатие 1,5 с; поэтому шагов всего 1 + M.
Строки шага: booth PHONEV sel, wardrobe WARDV sel, shop SHOPV step, menu MENUSEL key=right, pause PAUSEKEY (список упирается в край)."""
import re, sys
name, path = sys.argv[1], sys.argv[2]
pat = {'booth': r'^PHONEV sel ', 'wardrobe': r'^WARDV sel ', 'shop': r'^SHOPV step ', 'menu': r'^MENUSEL key=right', 'pause': r'^PAUSEKEY '}[name]
need = {'booth': 7, 'wardrobe': 7, 'shop': 7, 'menu': 7, 'pause': 2}[name]
rows = []
for l in open(path, errors='replace'):
    if re.search(pat, l):
        m = re.search(r'\bt=([0-9.]+)', l); rows.append(float(m.group(1)) if m else None)
n = len(rows); hold = n - 1
tap_ok = n >= 1 and not (n >= 2 and rows[0] is not None and rows[1] is not None and rows[1] - rows[0] < .9)
span = (rows[-1] - rows[1]) if n >= 3 and rows[1] is not None and rows[-1] is not None else None
print('%-9s шагов всего %2d: tap=%s hold=%d%s' % (name, n, 1 if tap_ok else '>1', max(hold, 0), '' if span is None else ' (шаги зажатия за %.2f с)' % span))
sys.exit(0 if (n >= 1 and tap_ok and hold >= need) else 1)
