#!/usr/bin/env python3
"""Название игры в меню XMB PSP: из одного EBOOT.PBP делает набор TEST27 или финал.
Меняется только значение TITLE (и TITLE_xx, если есть) внутри PARAM.SFO, на месте, в границах max_len слота;
размер SFO, заголовок PBP и все остальные секции (ICON0, ICON1, PIC0, PIC1, SND0, DATA.PSP, DATA.PSAR) остаются побайтно прежними.
  tools/eboot_title.py IN.PBP --title "Название" OUT.PBP
  tools/eboot_title.py IN.PBP --preset test27|final OUT.PBP
  tools/eboot_title.py IN.PBP --show            печать TITLE из SFO"""
import struct, sys, argparse

PRESETS = {'test27': 'SHAR TEST27', 'final': 'The Simpsons Hit & Run'}
NAMES = ['SFO', 'ICON0', 'ICON1', 'PIC0', 'PIC1', 'SND0', 'DATA.PSP', 'DATA.PSAR']


def pbp_offsets(b):
    if b[:4] != b'\0PBP': raise ValueError('не PBP')
    return list(struct.unpack_from('<8I', b, 8))


def sfo_entries(b, o):
    s = o[0]
    if b[s:s + 4] != b'\0PSF': raise ValueError('нет PARAM.SFO')
    kt, dt, n = struct.unpack_from('<3I', b, s + 8)
    for i in range(n):
        ko, fmt, ln, mx, do = struct.unpack_from('<HHIII', b, s + 20 + i * 16)
        e = b.index(b'\0', s + kt + ko)
        yield i, b[s + kt + ko:e].decode('ascii'), fmt, ln, mx, s + dt + do


def get_titles(b):
    o = pbp_offsets(b)
    return {k: b[p:p + ln - 1].decode('utf-8') for _, k, fmt, ln, mx, p in sfo_entries(b, o) if k.startswith('TITLE')}


def set_title(b, title):
    o = pbp_offsets(b); out = bytearray(b); s = o[0]; hit = 0
    raw = title.encode('utf-8')
    for i, k, fmt, ln, mx, p in sfo_entries(b, o):
        if not (k == 'TITLE' or (k.startswith('TITLE_') and ln > 1)) or fmt != 0x0204: continue
        if len(raw) + 1 > mx: raise ValueError(f'название «{title}» длиннее слота {k} ({mx} Б)')
        out[p:p + mx] = raw + b'\0' * (mx - len(raw))
        struct.pack_into('<I', out, s + 20 + i * 16 + 4, len(raw) + 1); hit += 1
    if not hit: raise ValueError('в SFO нет TITLE')
    return bytes(out)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('inp'); ap.add_argument('out', nargs='?')
    ap.add_argument('--title'); ap.add_argument('--preset', choices=sorted(PRESETS)); ap.add_argument('--show', action='store_true')
    a = ap.parse_args(); b = open(a.inp, 'rb').read()
    if a.show: print(get_titles(b)); return
    t = a.title or (PRESETS[a.preset] if a.preset else None)
    if not t or not a.out: ap.error('нужны --title или --preset и OUT.PBP')
    r = set_title(b, t); assert len(r) == len(b)
    open(a.out, 'wb').write(r); print(f'{a.out}: TITLE «{t}», {len(r)} Б, секции кроме SFO без изменений')


if __name__ == '__main__': main()
