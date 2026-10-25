#!/usr/bin/env python3
"""№943 (Роб 24.10 вечер: «остаётся миссия "приехать домой" — первая миссия Гомера, где показывают дом Симпсонов; её не переставить, даже если поменять миссию»).
Правило: выбранная/активная миссия главнее стартовой цели; при смене уровня/миссии прежняя цель, маркер и реестр снимаются.
  check.py levels СМОУК   — tests/msnhome/s1_levels.txt (пауза -> MISSION SELECT -> ◄ ► -> ✕, настоящий интерфейс, два перехода уровней)
  check.py switch СМОУК   — tests/msnhome/s2_switch.txt (смена миссий на уровне)
Печатает по проверке PASS/FAIL, последняя строка — итог (PASS или FAIL (n)). Красный контроль — сборка -DMS_CURSOR_OLD=1 -DLVDEFER_OLD=1 -DMSN_SWITCH_OLD=1: обязана упасть."""
import re, sys
from pathlib import Path

KV = re.compile(r'(\w+)=("([^"]*)"|\S+)')


def kv(line):
    return {m.group(1): (m.group(3) if m.group(3) is not None else m.group(2)) for m in KV.finditer(line)}


def first(lines, start, pred):
    for i in range(start, len(lines)):
        if pred(lines[i]): return i
    return -1


def levels(lines, errs, notes):
    ups = [i for i, l in enumerate(lines) if l.startswith('LEVELUP ')]
    if len(ups) < 2: errs.append('переходов уровня %d вместо 2: сценарий не дошёл (LEVELUP)' % len(ups))
    for i in ups:
        u = kv(lines[i]); to = u['to']; tag = 'L%s->L%s' % (u['from'], to)
        j = first(lines, i, lambda l: l.startswith('FIRSTFRAME'))
        if j < 0: errs.append('%s: нет FIRSTFRAME' % tag); continue
        seg = lines[i:j]
        sel = [l for l in seg if l.startswith('MSN select ')]
        mis = [l for l in seg if l.startswith('MSN mission ')]
        stg = [l for l in seg if l.startswith('MSN stage ')]
        if not sel: errs.append('%s: выбранная строка не стартовала (нет MSN select)' % tag); continue
        sid = sel[0].split()[2]
        # A: курсор после ◄ ► стоял на текущей миссии выбранного уровня
        k = max((x for x in range(i) if lines[x].startswith('MSNSEL level=%s ' % to) and 'moved=1' in lines[x]), default=-1)
        w = max((x for x in range(i) if lines[x].startswith('MSNSEL want level=%s ' % to)), default=-1)
        if k < 0 or w < 0: errs.append('%s: нет строк MSNSEL (листание / выбор)' % tag)
        else:
            c = kv(lines[k]); row = kv(lines[w])['row']
            ok = c['sel'] == c['top'] and row == c['sel']
            (notes if ok else errs).append('%s: курсор после перелистывания sel=%s (статус %s), текущая строка уровня top=%s, выбрана строка %s' % (tag, c['sel'], c['st'], c['top'], row) +
                                          ('' if ok else ' — курсор не на текущей миссии (A)'))
        # C: стартовая цель уровня не ставится перед выбранной миссией
        ok = len(mis) == 1 and sel[0].split()[2] == mis[0].split()[2]
        (notes if ok else errs).append('%s: стартов миссии до первого кадра %d (%s), выбрана %s' % (tag, len(mis), ','.join(m.split()[2] for m in mis), sid) +
                                       ('' if ok else ' — до выбранной миссии стартовала стартовая цель уровня (C)'))
        # цель «домой» или любая чужая цель до первого кадра
        alien = [s for s in stg if s.split()[2].split('.')[0] != sid]
        if alien: errs.append('%s: этап чужой миссии до выбранной: %s' % (tag, alien[0][:90]))
        # D: цель HUD и маркер — одной миссии (MSNHUD после первого кадра)
        hs = [kv(l) for l in lines[j:] if l.startswith('MSNHUD ')]
        hs = [h for h in hs if h.get('cur')]
        if not hs: errs.append('%s: нет MSNHUD после загрузки' % tag); continue
        h0 = hs[0]
        bad = []
        if h0['cur'] != sid: bad.append('миссия рантайма %s, выбрана %s' % (h0['cur'], sid))
        if h0['stagetext'] != h0['obj']: bad.append('цель HUD "%s" не равна цели этапа "%s"' % (h0['obj'], h0['stagetext']))
        if h0['marker'] != h0['gmarker']: bad.append('маркер вида %s, маркер миссии %s' % (h0['marker'], h0['gmarker']))
        (errs if bad else notes).append('%s: после загрузки миссия %s этап %s.%s цель "%s" маркер %s' % (tag, h0['cur'], h0['phase'], h0['stage'], h0['obj'], h0['marker']) +
                                        (' — ' + '; '.join(bad) if bad else ''))
        if 'SIMPSONS HOUSE' in h0['stagetext'].upper() and sid != 'm1' and to != '1': errs.append('%s: цель «домой» при выбранной %s' % (tag, sid))


def switch(lines, errs, notes):
    sw = [(i, kv(l)) for i, l in enumerate(lines) if l.startswith('MSNSWITCH ')]
    if len(sw) < 4: errs.append('смен миссии %d вместо 4' % len(sw))
    for i, s in sw:
        bad = []
        if s['reg'] != '0': bad.append('реестр прежней миссии жив (%s записей)' % s['reg'])
        if s['obj'] != '': bad.append('цель HUD прежней миссии жива "%s"' % s['obj'])
        if s['marker'] != '0' or s['gmarker'] != '0': bad.append('маркер прежней цели жив (вид %s, миссия %s)' % (s['marker'], s['gmarker']))
        (errs if bad else notes).append('смена %s -> %s: ' % (s['from'], s['to']) + ('; '.join(bad) if bad else 'цель, маркер, реестр сняты'))
        # после смены — цель новой миссии
        h = next((kv(l) for l in lines[i:] if l.startswith('MSNHUD ')), None)
        if h is None: errs.append('после смены на %s нет MSNHUD' % s['to']); continue
        b2 = []
        if h['cur'] != s['to']: b2.append('миссия рантайма %s, выбрана %s' % (h['cur'], s['to']))
        if h['stagetext'] != h['obj']: b2.append('цель HUD "%s" != цель этапа "%s"' % (h['obj'], h['stagetext']))
        if h['marker'] != h['gmarker']: b2.append('маркер вида %s, миссии %s' % (h['marker'], h['gmarker']))
        (errs if b2 else notes).append('после смены на %s: этап %s.%s цель "%s" маркер %s' % (s['to'], h['phase'], h['stage'], h['obj'], h['marker']) + (' — ' + '; '.join(b2) if b2 else ''))


def main():
    mode, run = sys.argv[1], Path(sys.argv[2])
    lines = run.read_text(errors='replace').splitlines()
    errs, notes = [], []
    if not any(l == 'END' for l in lines): errs.append('нет END: сценарий не дошёл до конца')
    {'levels': levels, 'switch': switch}[mode](lines, errs, notes)
    for n in notes: print('  ok  ', n)
    for e in errs: print('  FAIL', e)
    print(('PASS' if not errs else 'FAIL (%d)' % len(errs)) + ' · tests/msnhome/check.py %s %s' % (mode, run.parent.name))
    return 1 if errs else 0


if __name__ == '__main__':
    sys.exit(main())
