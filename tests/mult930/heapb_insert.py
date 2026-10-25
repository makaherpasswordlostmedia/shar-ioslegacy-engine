#!/usr/bin/env python3
"""№930: вставляет в viewer/smoke.h строку смоука HEAPB (свободная куча раз в секунду: счёт игры, живые байты malloc, арена; замер приёмки) — в базу при сборке accept60.sh; в ветке mult она уже есть (повторный запуск ничего не меняет)
  heapb_insert.py ПУТЬ/smoke.h"""
import sys
p = sys.argv[1]; l = open(p, encoding='utf8').read()
if 'HEAPB' in l: sys.exit(0)
anchor = "  smkSecMissed = smkSecMissVis = 0.f;\n  smkWrite(s);\n"
assert l.count(anchor) == 1, 'нет места вставки'
ins = '  { char hb_[200]; struct mallinfo mi_ = mallinfo(); snprintf(hb_, sizeof hb_, "HEAPB t=%.1f scene=%s bytes=%u blk=%u used=%u arena=%u free=%u\\n", smkT, smkScene, heapFreeBytes(), memMaxBlock ? memMaxBlock() : 0u, (unsigned)mi_.uordblks, (unsigned)mi_.arena, (unsigned)mi_.fordblks); smkWrite(hb_); }   // №930 служебно (приёмка кучи)\n'
open(p, 'w', encoding='utf8').write(l.replace(anchor, anchor + ins))
