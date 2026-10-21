#!/usr/bin/env python3
"""Лавка продавцов на L2–L7 (tests/shop/shops_levels.sh): по smoke.txt рядом с каждым продавцом уровня (SELLERGO — там, где он сейчас стоит) △ открыла лавку (SHOPV open),
и первой в ней выбрана машина ЭТОГО продавца ЭТОГО уровня (rewards.mfk: BindReward car forsale <уровень> <цена> gil|simpson). Исключение по данным: на L7 «zmale1» — одновременно
дающий гонку 3 (△ у него — разговор «START MISSION», правка 306: пока этап — разговор с этим продавцом, лавка не перехватывает), лавка там не открывается."""
import re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
RW = (ROOT / 'hit-and-run-web/source/game/scripts/missions/rewards.mfk').read_text(errors='replace')
ROWS = re.findall(r'BindReward\(\s*"(\w+)"\s*,\s*"[^"]*"\s*,\s*"car"\s*,\s*"forsale"\s*,\s*(\d+)\s*,\s*\d+\s*,\s*"(\w+)"', RW)
def first_car(level, shop):
    return next(n for n, l, s in ROWS if int(l) == level and s == shop)
MISSION_GIVER = {(7, 'zmale1')}
def main():
    log = (Path(sys.argv[1]) / 'smoke.txt').read_text(errors='replace'); fails = []; seen = 0
    for lv in range(2, 8):
        a = log.find('LEVEL ev=load n=%d ' % lv)
        if a < 0: fails.append('L%d: уровень не загрузился' % lv); continue
        b = log.find('LEVEL ev=free', a + 1); seg = log[a:b if b > 0 else len(log)]
        gos = list(re.finditer(r'SELLERGO (\d+) npc=(\w+) at=\S+ t=[\d.]+\n(.*?)(?=SELLERGO |\Z)', seg, re.S))
        if len(gos) < 2: fails.append('L%d: продавцов проверено %d (ждали 2)' % (lv, len(gos)))
        for m in gos:
            npc = m.group(2); shop = 'gil' if npc == 'gil' else 'simpson'; op = re.search(r'SHOPV open seller=\d+ item=\d+ coins=\d+ name=(\w+)', m.group(3))
            if (lv, npc) in MISSION_GIVER:
                if op: fails.append('L%d %s: лавка открылась, хотя △ должна идти разговору миссии' % (lv, npc))
                continue
            if not op: fails.append('L%d %s: лавка не открылась'% (lv, npc)); continue
            want = first_car(lv, shop); seen += 1
            if op.group(1) != want: fails.append('L%d %s: в лавке %s, по rewards.mfk первой %s' % (lv, npc, op.group(1), want))
    print('  лавок открыто и сверено: %d из 11 (+ L7 zmale1 — разговор миссии)' % seen)
    if fails: print('FAIL: ' + fails[0]); [print('  - ' + f) for f in fails[1:]]; sys.exit(1)
    print('OK: лавка продавцов открывается на L2–L7, своя машина каждого продавца по rewards.mfk')
main()
