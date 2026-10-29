#!/usr/bin/env python3
"""Гейт tools/eboot_title.py: из одного EBOOT получается TEST27 и финал, отличается только PARAM.SFO (TITLE).
  eboot_title_check.py [EBOOT.PBP]      зелёный: заголовок и все секции кроме SFO побайтно равны, в SFO отличаются только байты TITLE,
                                        unpack-pbp (pspdev) даёт те же файлы; красные контроли: испорченная секция и испорченный заголовок ловятся"""
import os, struct, subprocess, sys, tempfile, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
import eboot_title as T

ROOT = Path(__file__).resolve().parents[2]
src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / 'Downloads/shar-psp/viewer/build_smk/EBOOT.PBP'
if not src.exists(): sys.exit(f'FAIL: нет EBOOT {src}')
b = src.read_bytes()


def sections(d):
    o = T.pbp_offsets(d); e = o[1:] + [len(d)]
    return {n: d[x:y] for n, x, y in zip(T.NAMES, o, e)}


def diff_report(a, c):
    """список нарушений: что отличается, кроме TITLE в SFO"""
    bad = []
    if T.pbp_offsets(a) != T.pbp_offsets(c): bad.append('смещения заголовка PBP отличаются')
    if len(a) != len(c): bad.append('размер файла отличается')
    sa, sc = sections(a), sections(c)
    for n in T.NAMES[1:]:
        if sa[n] != sc[n]: bad.append(f'секция {n} отличается')
    o = T.pbp_offsets(a); allowed = set()
    for _, k, fmt, ln, mx, p in T.sfo_entries(a, o):
        if k.startswith('TITLE'): allowed |= set(range(p, p + mx))
        if k.startswith('TITLE'):
            i = [e[0] for e in T.sfo_entries(a, o) if e[1] == k][0]; allowed |= set(range(o[0] + 20 + i * 16 + 4, o[0] + 20 + i * 16 + 8))
    outside = [i for i in range(o[0], o[1]) if a[i] != c[i] and i not in allowed]
    if outside: bad.append(f'в SFO отличаются байты вне TITLE (первый {outside[0]})')
    return bad


fails = []; tmp = Path(tempfile.mkdtemp(prefix='ebt_'))
try:
    base_sec = {n: len(v) for n, v in sections(b).items()}
    print('секции исходного EBOOT (байт):', ', '.join(f'{n} {v}' for n, v in base_sec.items()))
    outs = {}
    for preset, want in T.PRESETS.items():
        p = tmp / f'{preset}.PBP'
        subprocess.run([sys.executable, str(ROOT / 'tools/eboot_title.py'), str(src), '--preset', preset, str(p)], check=True, capture_output=True)
        c = p.read_bytes(); outs[preset] = c
        t = T.get_titles(c)
        if t.get('TITLE') != want: fails.append(f'{preset}: TITLE «{t.get("TITLE")}» вместо «{want}»')
        for m in diff_report(b, c): fails.append(f'{preset}: {m}')
        print(f'  {preset}: TITLE «{t.get("TITLE")}», отличий вне TITLE нет' if not diff_report(b, c) else f'  {preset}: нарушения')
    # unpack-pbp: файлы секций те же, кроме PARAM.SFO
    ub = shutil.which('unpack-pbp') or str(Path.home() / 'Downloads/shar-psp/pspdev/bin/unpack-pbp')
    if os.path.exists(ub):
        for nm, d in (('src', b), ('test27', outs['test27']), ('final', outs['final'])):
            (tmp / nm).mkdir(); (tmp / f'{nm}.PBP').write_bytes(d)
            subprocess.run([ub, str(tmp / f'{nm}.PBP')], cwd=tmp / nm, check=True, capture_output=True)
        for nm in ('test27', 'final'):
            names = sorted(x.name for x in (tmp / 'src').iterdir())
            if names != sorted(x.name for x in (tmp / nm).iterdir()): fails.append(f'unpack-pbp {nm}: набор файлов другой')
            for f in names:
                same = (tmp / 'src' / f).read_bytes() == (tmp / nm / f).read_bytes()
                if f == 'PARAM.SFO' and same and T.get_titles(b).get('TITLE') != T.PRESETS[nm]: fails.append(f'unpack-pbp {nm}: PARAM.SFO не изменился')
                if f != 'PARAM.SFO' and not same: fails.append(f'unpack-pbp {nm}: {f} отличается')
        print('  unpack-pbp: все файлы кроме PARAM.SFO побайтно равны')
    else:
        print('  unpack-pbp не найден, проверка только своим разбором')
    # красные контроли
    o = T.pbp_offsets(outs['final'])
    for nm, pos in (('DATA.PSP', o[6] + 100), ('ICON0', o[1] + 8), ('DATA.PSAR', o[7] + 4 if o[7] + 4 < len(b) else len(b) - 1)):
        x = bytearray(outs['final']); x[pos] ^= 0xFF
        if not diff_report(b, bytes(x)): fails.append(f'красный контроль {nm}: испорченная секция не поймана')
    x = bytearray(outs['final']); x[o[0] + 16 + 5] ^= 0x01
    if not diff_report(b, bytes(x)) : fails.append('красный контроль: байт SFO вне TITLE не пойман')
    x = bytearray(outs['final']); struct.pack_into('<I', x, 12, o[1] + 16)
    if not diff_report(b, bytes(x)): fails.append('красный контроль: испорченный заголовок не пойман')
    print('  красные контроли: секция, SFO вне TITLE, заголовок — пойманы' if not [f for f in fails if 'красный' in f] else '  красные контроли не прошли')
finally:
    shutil.rmtree(tmp, ignore_errors=True)
if fails: print('FAIL: ' + fails[0]); [print('  - ' + f) for f in fails[1:]]; sys.exit(1)
print('OK: TEST27 и финал отличаются от исходного только названием в PARAM.SFO')
