#!/usr/bin/env python3
"""Клон ISO с другой машиной игрока на L1 (оригинал game/Hit and Run.iso не трогается: cp -c, правится только клон).
Правятся два текстовых скрипта уровня 1 внутри RCF: level.mfk (LoadDisposableCar) и leveli.mfk (InitLevelPlayerVehicle):
famil_v -> имя машины. Файлы моделей и .con машины уже лежат на диске.
python3 -I tools/twins/ps2_car_swap.py bart_v   → build/ps2stend/iso/bart_v.iso (путь печатается)"""
import struct, subprocess, sys
from pathlib import Path
SRC = Path('/Users/USER/Downloads/shar-psp/game/Hit and Run.iso')
GAME = Path('/Users/USER/Downloads/shar-psp/hit-and-run-web/source/game')
OUT = Path(__file__).resolve().parents[2] / 'build/ps2stend/iso'
BASE = 34494464

def rcf(f, base):
    f.seek(base); h = f.read(0x28); assert h.startswith(b'RADCORE CEMENT LIBRARY\0')
    table, = struct.unpack_from('<I', h, 0x24)
    f.seek(base + table); cnt, names = struct.unpack('<II', f.read(8)); f.read(8)
    T = [struct.unpack('<III', f.read(12)) for _ in range(cnt)]
    order = sorted(range(cnt), key=lambda i: T[i][1]); cur = base + names + 8; nm = {}
    for i in order:
        f.seek(cur); ln, = struct.unpack('<I', f.read(4)); cur += 4; f.seek(cur)
        nm[f.read(ln).rstrip(b'\0').decode().lower().replace('\\', '/')] = i; cur += ln + 4
    return table, T, nm

def patch(f, want, data):
    table, T, nm = rcf(f, BASE); k = [n for n in nm if n.endswith(want)]; assert len(k) == 1, k
    i = nm[k[0]]; crc, off, size = T[i]; offs = sorted(x[1] for x in T); nxt = [o for o in offs if o > off]
    room = (nxt[0] if nxt else 10**12) - off
    assert len(data) <= room, (want, len(data), room)
    f.seek(BASE + off); f.write(data)
    f.seek(BASE + table + 16 + i * 12 + 8); f.write(struct.pack('<I', len(data)))
    print(k[0], 'size', size, '->', len(data), 'room', room)

def main(car):
    assert (GAME / f'art/cars/{car}.p3d').exists() and (GAME / f'scripts/cars/{car}.con').exists(), car
    OUT.mkdir(parents=True, exist_ok=True); dst = OUT / f'{car}.iso'
    if dst.exists(): dst.unlink()
    subprocess.run(['cp', '-c', str(SRC), str(dst)], check=True)
    f = open(dst, 'r+b')
    for rel in ('scripts/missions/level01/level.mfk', 'scripts/missions/level01/leveli.mfk'):
        d = (GAME / rel).read_bytes(); n = d.count(b'famil_v'); assert n >= 1
        patch(f, rel, d.replace(b'famil_v', car.encode()))
        print(rel, 'замен', n)
    f.close(); print(dst)

if __name__ == '__main__': main(sys.argv[1])
