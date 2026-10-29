#!/usr/bin/env python3
"""Гейт «ящик у игрока не пишет синхронно» (аудит диагностики 16.10, наряд Дирижёра).
  tools/bb_sync_gate.py smoke.txt [smoke.txt ...] [--expect-fail]
Читает строки BBOP (… sync=N … syncn=K) и BBSYNC first (первая секунда) из журнала смоука тур-сборки на пути игрока.
Счётчик syncn — число РЕАЛЬНО выполненных синхронных записей ящика с главного потока за прогон (bbFlush, ветка sync). Допустимы только записи по op fail (и melad: лестница ME
по команде сценария). PASS: syncn последнего BBOP/BBSYNC <= число BBOP fail/melad в журнале и ни одной строки BBOP с sync=1, кроме fail/melad.
--expect-fail: отрицательный контроль, строка PASS, если гейт упал (журнал старого кода или сборка BB_SYNC_OLD=1 обязаны упасть)."""
import re, sys

ALLOWED = ('fail', 'melad')


def check(path):
    n_allowed = bad_lines = last = 0; bad_ops = {}; seen = False
    for ln in open(path, errors='replace'):
        m = re.match(r'BBOP (\S+) \S+ sync=(\d)\b.*?(?:syncn=(\d+))?\s+t=', ln)
        if m:
            seen = True; op, sy = m.group(1), m.group(2)
            if m.group(3): last = max(last, int(m.group(3)))
            if op in ALLOWED: n_allowed += 1
            elif sy == '1': bad_lines += 1; bad_ops[op] = bad_ops.get(op, 0) + 1
            continue
        m = re.match(r'BBSYNC first syncn=(\d+)', ln)
        if m: seen = True; last = max(last, int(m.group(1)))
    return seen, last, n_allowed, bad_lines, bad_ops


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]; exp = '--expect-fail' in sys.argv
    if not args: print(__doc__); return 2
    ok = True; parts = []
    for p in args:
        seen, last, na, bl, bo = check(p)
        good = seen and bl == 0 and last <= na
        ok &= good
        parts.append(f'{p}: синхронных записей {last} (разрешено fail/melad: {na}), BBOP sync=1 не из fail/melad: {bl}' + (f' {bo}' if bo else '') + ('' if seen else ' — НЕТ строк BBOP (сборка без смоука?)'))
    res = ('PASS' if ok else 'FAIL')
    if exp:
        print(f'ЯЩИК БЕЗ СИНХРОННЫХ ЗАПИСЕЙ (отрицательный контроль): {"PASS (гейт упал, как должен)" if not ok else "FAIL (гейт НЕ поймал старое поведение)"}'); [print('  ' + x) for x in parts]; return 0 if not ok else 1
    print(f'ЯЩИК БЕЗ СИНХРОННЫХ ЗАПИСЕЙ: {res}'); [print('  ' + x) for x in parts]
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
