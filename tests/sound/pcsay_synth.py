#!/usr/bin/env python3
"""Синтетический звуковой пакет для tests/sound/pcsay_host.c без диска игры (облако 05.10, миссии и боты, п.3).

  python3 tests/sound/pcsay_synth.py OUTDIR [--code hom] [--no-gic]

sfx.sab — пустой банк (SAB1, без ресурсов); music.sap (SAP1) — дорожки реплик водителя (шина 2, тишина PS-ADPCM 1 с):
W_Mstart_<код>_01..04, W_GOC_<код>_legs/walk/horse, W_GIC_<код>_01..04 (имена — как кладёт tools/sound_export.py, строчные).
--no-gic — пакет «как до правки» (без W_GIC_): красный контроль гейта. Форматы — tools/audio_export.py (SAB1 96 Б, SAP1 64 Б + 64 Б на дорожку).
"""
import os, struct, sys


def main():
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    out = a[0]; code = a[a.index('--code') + 1] if '--code' in a else 'hom'
    names = [f'w_mstart_{code}_0{i}' for i in range(1, 5)] + [f'w_goc_{code}_{s}' for s in ('legs', 'walk', 'horse')]
    if '--driver-events' in a:
        names += [f'd_bcrash_{code}_01', f'w_bcrash_{code}_02', f'd_damage_{code}_01']
    if '--no-gic' not in a:
        names += [f'w_gic_{code}_0{i}' for i in range(1, 5)]
    os.makedirs(out, exist_ok=True)
    hdr = b'SAB1' + struct.pack('<IIIIIIIIII', 1, 0, 0, 0, 96, 96, 96, 96, 128, 0)
    hdr += struct.pack('<6f3f', 1, 1, 1, 1, 1, 1, .1, 1, .8) + struct.pack('<II', 0, 0)
    open(os.path.join(out, 'sfx.sab'), 'wb').write(hdr + b'\0' * (128 - len(hdr)))
    rate, nsamp = 22050, 22050
    nblk = (nsamp + 27) // 28
    blob = b'\0' * (nblk * 16 * 2)                       # стерео: блоки L и R, нулевой блок — тишина
    blob += b'\0' * (-len(blob) % 2048)
    base = (64 + 64 * len(names) + 2047) & ~2047
    tbl = bytearray()
    for i, n in enumerate(names):
        tbl += n.encode().ljust(28, b'\0') + struct.pack('<IIIIIHBBhh4h', base + i * len(blob), nblk, nsamp, 0, nsamp, rate,
                                                         2, 0, -1, 2, 0, 0, 0, 0)
    sap = b'SAP1' + struct.pack('<III', 1, len(names), 64) + b'\0' * 48 + tbl
    sap += b'\0' * (base - len(sap)) + blob * len(names)
    open(os.path.join(out, 'music.sap'), 'wb').write(sap)
    print(f'{out}: {len(names)} дорожек реплик ({code}){" без W_GIC_" if "--no-gic" in a else ""}')


if __name__ == '__main__':
    main()
