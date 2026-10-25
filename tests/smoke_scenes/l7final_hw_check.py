#!/usr/bin/env python3
"""Проверка журнала тура l7final_hw.txt: финал L7 -> запись -> титры -> меню. Использование: l7final_hw_check.py [--skip] smoke.txt [...]  (--skip: пустого слота нет, запись должна отмениться: ENDSAVE skip, без SAVE_SUCCESSFUL)
Порядок строк: LEVELDONE n=7 code=2 -> ENDSAVE open=1 -> SVMSG SAVE_SUCCESSFUL -> ENDSAVE closed -> CREDITS on -> FEBACK -> END; без STALL/ошибок записи."""
import sys, re
SKIP = '--skip' in sys.argv; ARGS = [a for a in sys.argv[1:] if not a.startswith('--')]
STEPS = [('LEVELDONE n=7 code=2', r'^LEVELDONE n=7 code=2'), ('ENDSAVE open=1', r'^ENDSAVE open=1'), ('SVPICK slot', r'^SVPICK slot=') if not SKIP else ('ENDSAVE skip', r'^ENDSAVE skip'), ('SAVE_SUCCESSFUL', r'^SVMSG key=MSG_SAVE_SUCCESSFUL') if not SKIP else None,
         ('ENDSAVE closed', r'^ENDSAVE closed'), ('CREDITS on', r'^CREDITS on'), ('FEBACK после титров', r'^FEBACK'), ('END', r'^END$')]
bad = 0
for fn in ARGS:
    L = open(fn, errors='replace').read().splitlines(); i = 0; miss = []
    for st in STEPS:
        if st is None: continue
        name, rx = st
        j = next((k for k in range(i, len(L)) if re.search(rx, L[k])), None)
        if j is None: miss.append(name); continue
        i = j + 1
    shots = [l for l in L if l.startswith('SHOT fin_')]
    err = [l for l in L if re.search(r'STALL|error=[1-9]|^SVMSG.*ERROR|crash|EXC', l)]
    if SKIP: err += [l for l in L if l.startswith('SVMSG key=MSG_SAVE_SUCCESSFUL') or l.startswith('SVMSG key=MSG_SAVING')]   # отмена: запись не должна была начаться
    ok = not miss and not err and len(shots) == 8
    print('%s: %s  снимков %d/8%s%s' % (fn, 'PASS' if ok else 'FAIL', len(shots), '  нет: ' + ', '.join(miss) if miss else '', '  ошибки: ' + '; '.join(err[:3]) if err else ''))
    bad += not ok
sys.exit(1 if bad else 0)
