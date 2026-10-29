#!/usr/bin/env python3
"""Шрифт загрузочного экрана — встроенный шрифт PSPSDK (правка Роба 125, 01.10: «шрифт используй такой же, как в gebench на
PSPLink — системные пиксельные красивые шрифты под разрешение PSP»). Это тот самый шрифт, которым печатает pspDebugScreen
(tests/gebench/main.c): массив `msx` из libpspdebug.a (член font.o, секция .data, 2048 Б = 256 знаков × 8 строк по байту,
старший бит — левый пиксель, 1 бит без сглаживания). На PSP движок берёт его прямо из библиотеки (extern msx, ноль лишних
байт — он и так слинкован для pspDebugScreenInit); на Маке (превью, тесты) — копия viewer/bootmsx.h, которую пишет этот скрипт.
  tools/bootfont.py --msx      достать msx из pspdev/psp/sdk/lib/libpspdebug.a -> viewer/bootmsx.h
  tools/bootfont.py --check    копия viewer/bootmsx.h побайтно = msx в библиотеке (код 1 — расхождение; «вторая копия правды»)
Лицензия шрифта: PSPSDK, BSD 3-clause (pspdev/psp/share/licenses/pspsdk/LICENSE) — копирайт сохраняется в шапке bootmsx.h."""
import argparse, re, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / 'pspdev/psp/sdk/lib/libpspdebug.a'
BIN = ROOT / 'pspdev/bin'
OUT = ROOT / 'viewer/bootmsx.h'
HEAD = '''// Сгенерировано tools/bootfont.py --msx (правка Роба 125): встроенный шрифт PSPSDK `msx` из libpspdebug.a (font.o, .data),
// которым печатает pspDebugScreen (gebench на PSPLink). 256 знаков × 8 строк, байт = строка, старший бит — левый пиксель.
// Нужен только на Маке (превью и тесты): на PSP viewer/bootui.h берёт тот же массив прямо из библиотеки (extern msx).
// Проверка копии: tools/bootfont.py --check.
// Copyright (c) 2005 adresd, Marcus R. Brown, James Forshaw, John Kelley, Jesper Svennevid. All rights reserved.
// PSPSDK, BSD 3-clause license: pspdev/psp/share/licenses/pspsdk/LICENSE (redistributions of source code must retain
// the above copyright notice, this list of conditions and the following disclaimer).
'''


def lib_msx():
    with tempfile.TemporaryDirectory() as d:
        subprocess.run([str(BIN / 'psp-ar'), 'x', str(LIB), 'font.o'], cwd=d, check=True)
        subprocess.run([str(BIN / 'psp-objcopy'), '-O', 'binary', '-j', '.data', 'font.o', 'msx.bin'], cwd=d, check=True)
        b = (Path(d) / 'msx.bin').read_bytes()
    if len(b) != 2048: sys.exit(f'FAIL: .data font.o = {len(b)} Б, ждали 2048')
    return b


def header_bytes(p):
    t = p.read_text()
    m = re.search(r'bootMsx\[2048\] = \{(.*?)\};', t, re.S)
    return bytes(int(x, 0) for x in m.group(1).replace('\n', ' ').split(',') if x.strip()) if m else b''


ap = argparse.ArgumentParser(); ap.add_argument('--msx', action='store_true'); ap.add_argument('--check', action='store_true')
ap.add_argument('--out', default=str(OUT)); a = ap.parse_args()
out = Path(a.out)
if a.msx:
    b = lib_msx()
    rows = ['  ' + ','.join('0x%02x' % v for v in b[i:i + 16]) + ',' for i in range(0, 2048, 16)]
    out.write_text(HEAD + '#ifndef BOOTMSX_H\n#define BOOTMSX_H\nstatic const unsigned char bootMsx[2048] = {\n' + '\n'.join(rows) + '\n};\n#endif\n')
    print(f'{out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}: msx 2048 Б из {LIB.name}')
if a.check:
    lib = lib_msx(); cp = header_bytes(out) if out.exists() else b''
    if cp != lib:
        diff = sum(x != y for x, y in zip(cp, lib)) + abs(len(cp) - len(lib))
        print(f'RESULT: FAIL — {out.name} ({len(cp)} Б) не равна msx в libpspdebug.a (2048 Б): {diff} байт расходятся'); sys.exit(1)
    print(f'RESULT: OK — {out.name} = msx в libpspdebug.a, 2048 Б побайтно')
if not (a.msx or a.check): ap.print_help()
