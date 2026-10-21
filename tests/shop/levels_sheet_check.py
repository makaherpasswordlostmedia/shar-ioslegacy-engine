#!/usr/bin/env python3
"""Будка и гардероб на L2, L4, L7 (tests/shop/levels_sheet.sh): по smoke.txt — на уровне открылась СВОЯ будка (машина игрока уровня первой
в списке и выбранной), СВОЙ гардероб (персонаж уровня, 4 костюма, второй костюм с ценой из rewards.mfk уровня, читается с диска независимо).
Ожидания с диска Роба: scripts/missions/rewards.mfk (BindReward skin forsale / уровень), игрок уровня — leveli.mfk (AddCharacter)."""
import re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
RW = (ROOT / 'hit-and-run-web/source/game/scripts/missions/rewards.mfk').read_text(errors='replace')
OWN = {2: ('honor_v', 'bart'), 4: ('marge_v', 'marge'), 7: ('homer_v', 'homer')}   # машина игрока уровня и его имя в гардеробе (WARDV open name=)
def second_skin(level):
    rows = re.findall(r'BindReward\(\s*"(\w+)"\s*,\s*"[^"]*"\s*,\s*"skin"\s*,\s*"forsale"\s*,\s*%d\s*,\s*(\d+)\s*,\s*"interior"' % level, RW)
    return rows[0]    # первый костюм «на продажу» уровня — второй в гардеробе (первый — обычный)
def main():
    d = Path(sys.argv[1]); log = (d / 'smoke.txt').read_text(errors='replace'); fails = []
    for lv, (car, who) in OWN.items():
        a = log.find('LEVEL ev=load n=%d ' % lv)
        if a < 0: fails.append('L%d: уровень не загрузился' % lv); continue
        b = log.find('LEVEL ev=free', a + 1); seg = log[a:b if b > 0 else len(log)]
        m = re.search(r'PHONEV open n=\d+ cur=\d+ name=(\w+)', seg)
        if not m: fails.append('L%d: будка не открылась (нет PHONEV open)' % lv)
        elif m.group(1) != car: fails.append('L%d: в будке %s, ждали машину игрока %s' % (lv, m.group(1), car))
        m = re.search(r'WARDV open n=(\d+) cur=0 coins=\d+ name=(\w+)', seg)
        if not m: fails.append('L%d: гардероб не открылся (нет WARDV open)' % lv)
        else:
            if m.group(2) != who: fails.append('L%d: гардероб персонажа %s, ждали %s' % (lv, m.group(2), who))
            if m.group(1) != '4': fails.append('L%d: костюмов %s, ждали 4' % (lv, m.group(1)))
        sk, pr = second_skin(lv)
        m = re.search(r'WARDV sel 1 name=(\w+) price=(\d+)', seg)
        if not m: fails.append('L%d: нет выбора второго костюма' % lv)
        elif (m.group(1), m.group(2)) != (sk, pr): fails.append('L%d: второй костюм %s %s, по rewards.mfk %s %s' % (lv, m.group(1), m.group(2), sk, pr))
    for lv in OWN: print('  L%d: %s' % (lv, 'проверено'))
    if fails: print('FAIL: ' + fails[0]); [print('  - ' + f) for f in fails[1:]]; sys.exit(1)
    print('OK: будка и гардероб на L2, L4, L7 свои (машина и персонаж уровня, костюмы и цены по rewards.mfk)')
main()
