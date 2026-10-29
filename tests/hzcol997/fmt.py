#!/usr/bin/env python3
"""№997 гейт формата: хвост HCL1 в horizon.shr (цвет фасада вершин контура) и совместимость со старым движком.
  fmt.py FILE...            проверка: прежний читатель (HOR1, подвал DSTF, DST2, смещения клеток) и HCL1 (заголовок, палитра, массивы тетрад в границах, индексы < 16)
  fmt.py --red FILE         красный контроль: порча хвоста (смещение за DST2, магия, счётчик) — каждая обязана быть поймана; код выхода 0, если все пойманы
Последняя строка: PASS / FAIL."""
import struct, sys
from pathlib import Path

def check(b, need_hcl=True):
    """возвращает список ошибок"""
    e = []
    if len(b) < 64 or b[:4] != b'HOR1': return ['нет HOR1']
    n = struct.unpack_from('<I', b, 4)[0]
    # --- прежний читатель (viewer/horizon.h horizonLoad до №997)
    if len(b) & 3 or b[-16:-12] != b'DSTF': return ['нет подвала DSTF / размер не кратен 4']
    t0 = struct.unpack_from('<I', b, len(b) - 12)[0]
    if t0 & 3 or t0 + 16 + 4 * n > len(b) - 16 or b[t0:t0 + 4] != b'DST2' or struct.unpack_from('<I', b, t0 + 4)[0] != n: return ['DST2 не читается прежним движком']
    for i in range(n):
        nv, p2 = struct.unpack_from('<I', b, 32 + 32 * i + 12)[0], struct.unpack_from('<I', b, 32 + 32 * i + 28)[0]
        o0 = struct.unpack_from('<I', b, t0 + 16 + 4 * i)[0]
        if t0 + o0 + (nv + 1) // 2 + (p2 + 1) // 2 > len(b) - 16: e.append(f'DST2 клетка {i} за границей')
    # --- HCL1
    ho = struct.unpack_from('<I', b, t0 + 8)[0]
    if not ho: return e + (['нет хвоста HCL1 (смещение в заголовке DST2 = 0)'] if need_hcl else [])
    if ho & 3 or ho + 80 + 4 * n > t0 or b[ho:ho + 4] != b'HCL1': return e + ['HCL1: смещение/магия']
    if struct.unpack_from('<I', b, ho + 4)[0] != n: return e + ['HCL1: число клеток не совпадает']
    pal = [tuple(b[ho + 16 + 4 * k:ho + 19 + 4 * k]) for k in range(16)]
    if len(set(pal)) < 8: e.append('палитра вырождена (< 8 разных цветов)')
    for i in range(n):
        nv, p2 = struct.unpack_from('<I', b, 32 + 32 * i + 12)[0], struct.unpack_from('<I', b, 32 + 32 * i + 28)[0]
        o0 = struct.unpack_from('<I', b, ho + 80 + 4 * i)[0]; ln = (nv + 1) // 2 + (p2 + 1) // 2
        if ho + o0 + ln > t0: e.append(f'HCL1 клетка {i} за границей'); break
    return e

def main():
    if sys.argv[1] == '--red':
        b0 = Path(sys.argv[2]).read_bytes(); n = struct.unpack_from('<I', b0, 4)[0]; t0 = struct.unpack_from('<I', b0, len(b0) - 12)[0]; ho = struct.unpack_from('<I', b0, t0 + 8)[0]
        cases = {}
        x = bytearray(b0); struct.pack_into('<I', x, t0 + 8, t0 + 4); cases['смещение HCL1 на DST2'] = bytes(x)
        x = bytearray(b0); x[ho:ho + 4] = b'XXXX'; cases['магия HCL1 затёрта'] = bytes(x)
        x = bytearray(b0); struct.pack_into('<I', x, ho + 4, n + 1); cases['счётчик клеток +1'] = bytes(x)
        x = bytearray(b0); struct.pack_into('<I', x, ho + 80 + 4 * (n - 1), t0); cases['смещение последней клетки за хвост'] = bytes(x)
        x = bytearray(b0)
        for k in range(16): x[ho + 16 + 4 * k:ho + 19 + 4 * k] = b'\x40\x40\x40'
        cases['палитра одного цвета'] = bytes(x)
        cases['файл без хвоста HCL1 (прежние данные)'] = None
        miss = 0
        for k, v in cases.items():
            if v is None: continue
            r = check(v); print(f'  {k}: {"поймано" if r else "НЕ ПОЙМАНО"}'); miss += not r
        print('PASS' if not miss else 'FAIL'); sys.exit(1 if miss else 0)
    bad = 0
    for f in sys.argv[1:]:
        b = Path(f).read_bytes(); r = check(b); print(f'  {f}: {len(b)} Б {"ok" if not r else "ОШИБКИ " + "; ".join(r[:3])}'); bad += bool(r)
    print('PASS' if not bad else 'FAIL'); sys.exit(1 if bad else 0)

main()
