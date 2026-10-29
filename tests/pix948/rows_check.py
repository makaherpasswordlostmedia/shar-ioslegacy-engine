#!/usr/bin/env python3
# №948б: у каждой картинки (слота) пакета .shr низ (v+h) обязан лежать в хранимых строках страницы (UiTex.rows): иначе GE читает за концом данных — мусор снизу картинки.
#   rows_check.py PACK.shr [PREV.shr]   -> печатает число слотов с низом глубже rows; с PREV — ещё и «начало данных страниц не изменилось» (новый хранит старые строки как были)
#   выход 0 — все слоты внутри, и (с PREV) данные не испорчены; последняя строка OK/BAD
import struct, sys
def load(p):
    d = open(p, 'rb').read(); assert d[:4] != b'', p
    h = struct.unpack_from('<4sI18I', d, 0)   # magic, version, ntex, offTex, nitem, offItem, nscreen, offScreen, nfont, offFont, nstr, offStr, nsfont, offSfont, nicon, offIcon, nslot, offSlot, npts, offPts
    ntex, offTex, nslot, offSlot = h[2], h[3], h[16], h[17]
    tex = [struct.unpack_from('<4H6I', d, offTex + 32 * i) for i in range(ntex)]   # psm flags w h offPix offClut nclut bufw rows res
    slots = [struct.unpack_from('<5H3h', d, offSlot + 16 * i) for i in range(nslot)]   # tex u v w h x y pad
    return d, tex, slots
d, tex, slots = load(sys.argv[1])
bad = [s for s in slots if s[0] < len(tex) and tex[s[0]][0] == 5 and False]
short = []
for s in slots:
    t, u, v, w, hh = s[:5]
    if t >= len(tex): continue
    rows = tex[t][8]
    if v + hh > rows: short.append((t, u, v, w, hh, rows))
print('%s: страниц %d, слотов %d, с низом глубже хранимых строк: %d' % (sys.argv[1].split('/')[-1], len(tex), len(slots), len(short)))
for s in short[:5]: print('  страница %d слот u=%d v=%d w=%d h=%d, хранится строк %d' % s)
ok = not short
if len(sys.argv) > 2:
    d0, tex0, _ = load(sys.argv[2])
    same = 0; diff = 0
    for a, b in zip(tex, tex0):
        n = min(a[7] * a[8], b[7] * b[8]) // (2 if a[0] == 4 else 1)
        if d[a[4]:a[4] + n] == d0[b[4]:b[4] + n] and a[2:4] == b[2:4]: same += 1
        else: diff += 1
    print('страницы с прежними данными в общих строках: %d из %d' % (same, same + diff)); ok = ok and diff == 0
print('OK' if ok else 'BAD'); sys.exit(0 if ok else 1)
