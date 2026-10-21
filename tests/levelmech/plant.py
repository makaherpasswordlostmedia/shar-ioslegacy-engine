#!/usr/bin/env python3
"""Подложенные входы гейтов tests/levelmech (красные контроли): копия пакета с испорченным местом.

  plant.py shift-extra IN OUT DX   collect-l<N>.shr: экземпляры SPR1 без записей CLT1 (летающие актёры) сдвинуты по x на DX м
"""
import struct, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import spr1


def main():
    mode, src, dst = sys.argv[1:4]
    b = bytearray(Path(src).read_bytes())
    if mode == 'shift-extra':
        dx = float(sys.argv[4])
        u = struct.unpack_from('<15I', b, 4)
        spr_off, ncard, card_off, nwasp, wasp_off, ngag, gag_off = u[4], u[6], u[7], u[8], u[9], u[10], u[11]
        S = spr1.parse(bytes(b), spr_off)
        used = {struct.unpack_from('<H', b, card_off + 32 * i + 20)[0] for i in range(ncard)}
        used |= {v for i in range(nwasp) for v, fl, sh in [struct.unpack_from('<HHH', b, wasp_off + 80 * i + 64)] for v in ([v, sh] if fl & 2 else [v])}
        used |= {struct.unpack_from('<h', b, gag_off + 128 * i + 48)[0] for i in range(ngag)}
        ip, _ = S['parts']['inst']; n = 0
        for i in range(S['head']['ninst']):
            if i in used: continue
            x, = struct.unpack_from('<f', b, ip + 32 * i); struct.pack_into('<f', b, ip + 32 * i, x + dx); n += 1
        print(f'сдвинуто экземпляров: {n} на {dx} м')
    else:
        raise SystemExit('режим?')
    Path(dst).write_bytes(bytes(b))


if __name__ == '__main__':
    main()
