#!/usr/bin/env python3
"""Снимок всей памяти EE (32 МБ) через PINE: tools/ps2ref/dump.py OUT.bin  (≈5 с; эмулятор при этом идёт)."""
import struct, sys, time
sys.path.insert(0, __import__('os').path.dirname(__file__)); from pine import Pine, MSG
p = Pine(timeout=30); t = time.time(); out = bytearray(); step = 4096 * 8
for a in range(0, 32 << 20, step): out += p.batch([(MSG['r64'], struct.pack('<I', a + k)) for k in range(0, step, 8)])
open(sys.argv[1], 'wb').write(out); print(sys.argv[1], len(out) >> 20, 'МБ', round(time.time() - t, 1), 'с')
