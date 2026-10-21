#!/usr/bin/env python3
"""Заменить картинки меню PSP в готовом EBOOT.PBP без пересборки: --pic1 фон 480x272, --icon0 иконка 144x80,
--icon1 живой значок ICON1.PMF (правка Роба 110; пустой файл — убрать раздел), --snd0 музыка SND0.AT3 (правка 130; пустой — убрать).
tools/pbp_art.py IN.PBP OUT.PBP [--pic1 png] [--icon0 png] [--icon1 pmf] [--snd0 at3] [--sfo PARAM.SFO]"""
import argparse, struct
NAMES = ['PARAM.SFO', 'ICON0.PNG', 'ICON1.PMF', 'PIC0.PNG', 'PIC1.PNG', 'SND0.AT3', 'DATA.PSP', 'DATA.PSAR']
ap = argparse.ArgumentParser(); ap.add_argument('inp'); ap.add_argument('out'); ap.add_argument('--pic1'); ap.add_argument('--icon0'); ap.add_argument('--icon1'); ap.add_argument('--snd0'); ap.add_argument('--sfo')
a = ap.parse_args()
d = open(a.inp, 'rb').read(); assert d[:4] == b'\0PBP'
off = list(struct.unpack_from('<8I', d, 8)) + [len(d)]
parts = [d[off[i]:off[i + 1]] for i in range(8)]
if a.pic1: parts[4] = open(a.pic1, 'rb').read()
if a.sfo: parts[0] = open(a.sfo, 'rb').read()   # PARAM.SFO целиком (отрицательный контроль подписи, правка 146)
if a.icon0: parts[1] = open(a.icon0, 'rb').read()
if a.icon1 is not None: parts[2] = open(a.icon1, 'rb').read()
if a.snd0 is not None: parts[5] = open(a.snd0, 'rb').read()
hdr = bytearray(d[:8]); pos = 40; new = []
for p in parts: new.append(pos); pos += len(p)
out = bytes(hdr) + struct.pack('<8I', *new) + b''.join(parts)
open(a.out, 'wb').write(out); print({n: len(p) for n, p in zip(NAMES, parts)})
