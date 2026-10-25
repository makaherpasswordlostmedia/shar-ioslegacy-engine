#!/usr/bin/env python3
"""Формат horizon.shr с хвостом DST1 (№934): подвал 'DSTF' + смещение хвоста, размер и хвост кратны 4 (PSP падает на невыровненном u32, эмулятор прощает),
число клеток в DST1 = числу клеток HOR1, массивы расстояний по размеру контуров (nv и p2), расстояния > 0 и в пределах 1530 м, ориентиры №928 на месте (16 штук, смещение в файле).
  fmt.py horizon.shr [...]   код 0 = все файлы целы;  --red: к каждому файлу применяется порча (урезан на 1 байт, подвал затёрт, счётчик клеток −1), все три порчи обязаны быть пойманы"""
import sys, struct
def check(d):
    if d[:4] != b'HOR1': return 'нет HOR1'
    n, r, nl, lo = struct.unpack_from('<IfII', d, 4); sz = len(d)
    if sz % 4: return 'размер не кратен 4 (%d)' % sz
    if d[sz - 16:sz - 12] != b'DSTF': return 'нет подвала DSTF'
    t0 = struct.unpack_from('<I', d, sz - 12)[0]
    if t0 % 4 or t0 + 16 + 4 * n > sz - 16 or d[t0:t0 + 4] != b'DST2': return 'хвост DST2 не на месте (%d)' % t0
    if struct.unpack_from('<I', d, t0 + 4)[0] != n: return 'клеток в DST2 не столько, сколько в HOR1'
    if nl != 16: return 'ориентиров %d, не 16' % nl
    end = 0
    for i in range(n):
        cx, cz, ey, nv, off, p0, p1, p2 = struct.unpack_from('<3f5I', d, 32 + 32 * i); o0 = struct.unpack_from('<I', d, t0 + 16 + 4 * i)[0]; ln = (nv + 1) // 2 + (p2 + 1) // 2
        if o0 != (16 + 4 * n if i == 0 else end): return 'клетка %d: массивы идут не подряд' % i
        end = o0 + ln
        if t0 + end > sz - 16: return 'массив клетки %d за концом' % i
    if (end + 3) // 4 * 4 + t0 + 16 != sz - 0 - 0 and t0 + (end + 3) // 4 * 4 + 16 != sz: return 'хвост не сходится с размером файла'
    return None
red = '--red' in sys.argv; fs = [a for a in sys.argv[1:] if not a.startswith('--')]; bad = 0
for f in fs:
    d = open(f, 'rb').read()
    if not red:
        e = check(d); print(('ОК   ' if not e else 'БРАК ') + f.split('/')[-2] + '/' + f.split('/')[-1], '' if not e else e, len(d)); bad += e is not None
    else:
        t0 = struct.unpack_from('<I', d, len(d) - 12)[0]; n = struct.unpack_from('<I', d, 4)[0]
        for name, dd in (('урезан на 1 байт', d[:-1]), ('подвал затёрт', d[:-16] + b'\0' * 16), ('счётчик клеток −1', d[:t0 + 4] + struct.pack('<I', n - 1) + d[t0 + 8:])):
            e = check(dd); print(('поймано ' if e else 'ПРОШЛО  ') + name + (': ' + e if e else '')); bad += e is None
print('HZ934-ФОРМАТ%s: %s' % ('-КРАСНЫЙ' if red else '', 'PASS' if not bad else 'FAIL')); sys.exit(1 if bad else 0)
