#!/usr/bin/env python3
"""Проверка записи «пройдено всё» по печати build/chist60/svdump (чтение настоящим savegame.c).
  check_save.py SVDUMP.txt [--expect-fail]    код 0 — PASS; с --expect-fail код 0, только если проверка УПАЛА (красный контроль: испорченная запись)."""
import re, sys
t = open(sys.argv[1], errors='replace').read(); exp = '--expect-fail' in sys.argv; errs = []
m = re.search(r'svRead=(-?\d+)', t)
if not m or int(m.group(1)) != 0: errs.append('svRead != 0 (запись не читается / CRC)')
else:
    g = lambda pat: re.search(pat, t)
    if not g(r'level=7 msnLevel=7 msnCompleted=([0-9a-f]+)'): errs.append('уровень записи не 7')
    cards = re.findall(r'L(\d)=([0-9a-f]{2})', g(r'cards:(.*)').group(1)) if g(r'cards:(.*)') else []
    wasps = re.findall(r'L(\d)=([0-9a-f]+)', g(r'wasps:(.*)').group(1)) if g(r'wasps:(.*)') else []
    gags = re.findall(r'L(\d)=([0-9a-f]+)', g(r'gags:(.*)').group(1)) if g(r'gags:(.*)') else []
    owned = re.findall(r'L(\d)=([0-9a-f]+)', g(r'owned:(.*)').group(1)) if g(r'owned:(.*)') else []
    if len(cards) != 7 or any(int(v, 16) != 0x7f for _, v in cards): errs.append('карточки не 7x7')
    if len(wasps) != 7 or any(int(v, 16) != 0xfffff for _, v in wasps): errs.append('осы не 20x7')
    if len(gags) != 7 or any(int(v, 16) == 0 for _, v in gags): errs.append('гэги: пустой уровень')
    if len(owned) != 7 or any(int(v, 16) != 0xffff for _, v in owned): errs.append('купленное не на всех уровнях')
    if not g(r'svLvReached=7'): errs.append('достигнуто не 7 уровней')
    lv = re.findall(r'L(\d)\[(\d+) ([0-9a-f]{8}) ([0-9a-f]{2})\]', t)
    if len(lv) != 7 or any(int(s) != 2 or int(mk, 16) == 0 or int(r, 16) != 0xff for _, s, mk, r in lv): errs.append('миссии: у уровня нет записи / маски / строк MISSION SELECT')
    c = g(r'coins=(\d+)')
    if not c or int(c.group(1)) < 9999: errs.append('кошелёк < 9999')
print(('PASS' if not errs else 'FAIL ' + '; '.join(errs)) + ' · check_save.py ' + sys.argv[1].split('/')[-1])
sys.exit((0 if errs else 1) if exp else (0 if not errs else 1))
