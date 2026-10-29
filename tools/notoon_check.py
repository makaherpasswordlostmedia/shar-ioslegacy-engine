#!/usr/bin/env python3
"""№788: сверка списков notoon.txt с level.shr набора — та же подпись, что проверяет движок (main_levels.h): «ntex N sig X»,
FNV-1a по номерам текстур всех кусков (Rec.tex @24). Не совпало — движок список не применит (картинка как без списка).
  python3 tools/notoon_check.py НАБОР      (L1 — level.shr и notoon.txt рядом с EBOOT, L2–L7 — в l<N>/)"""
import struct, sys
from pathlib import Path

def shr_sig(shr):
    h = open(shr, 'rb').read(104); ntex, npc = struct.unpack_from('<II', h, 4); toff = struct.unpack_from('<I', h, 76)[0]
    f = open(shr, 'rb'); f.seek(toff); tab = f.read(80 * npc); x = 2166136261
    for i in range(npc): x = ((x ^ struct.unpack_from('<I', tab, 80 * i + 24)[0]) * 16777619) & 0xffffffff
    return ntex, x

def main():
    S = Path(sys.argv[1]); bad = 0
    for L in range(1, 8):
        d = S if L == 1 else S / ('l%d' % L)
        nt = d / 'notoon.txt'
        if not nt.exists(): print('L%d: нет notoon.txt' % L); continue
        head = nt.read_text().split('\n', 1)[0].split()
        ntex, sig = shr_sig(d / 'level.shr')
        ok = len(head) == 4 and head[0] == 'ntex' and int(head[1]) == ntex and head[2] == 'sig' and int(head[3], 16) == sig
        bad += not ok
        print('L%d: %s (level.shr ntex %d sig %08x; список %s)' % (L, 'совпадает' if ok else 'НЕ СОВПАДАЕТ — список не применится', ntex, sig, ' '.join(head)))
    sys.exit(1 if bad else 0)

if __name__ == '__main__': main()
