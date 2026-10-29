#!/usr/bin/env python3
"""Разбор дампа кадра PPSSPP (.ppdmp): что уходит на видеочип. Только чтение, ресурсы игры не извлекаются.
   python tools/ppdmp_stats.py файл.ppdmp [--json]"""
import struct, sys, json, collections

HDR = 8 + 4 + 9
CT = {0: 'Init', 1: 'Registers', 2: 'Vertices', 3: 'Indices', 4: 'Clut', 5: 'TransferSrc', 6: 'Memset', 7: 'Memcpy',
      24: 'Display'}
for i in range(8): CT[8 + i] = 'Texture%d' % i
for i in range(8): CT[16 + i] = 'Framebuf%d' % i
PRIMS = ['points', 'lines', 'linestrip', 'tris', 'tristrip', 'trifan', 'sprites']
TFMT = {0: '5650', 1: '5551', 2: '4444', 3: '8888', 4: 'CLUT4', 5: 'CLUT8', 6: 'CLUT16', 7: 'CLUT32', 8: 'DXT1', 9: 'DXT3', 10: 'DXT5'}
VT_TC = ['-', 'u8', 'u16', 'f32']; VT_COL = ['-', '?', '?', '?', '565', '5551', '4444', '8888']
VT_NRM = ['-', 's8', 's16', 'f32']; VT_POS = ['-', 's8', 's16', 'f32']; VT_IDX = ['-', 'u8', 'u16', '?']


def _zstd(b):
    import subprocess
    return subprocess.run(['zstd', '-d', '-c'], input=b, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL).stdout


def parse(path):
    d = open(path, 'rb').read()
    assert d[:8] == b'PPSSPPGE', 'не PPSSPPGE'
    ver = struct.unpack_from('<I', d, 8)[0]
    o = 24
    n, bufsz, csz = struct.unpack_from('<III', d, o); o += 12
    cm = _zstd(d[o:o + csz]); o += csz
    bsz = struct.unpack_from('<I', d, o)[0]; o += 4
    buf = _zstd(d[o:o + bsz])
    cmds = [struct.unpack_from('<BII', cm, i * 9) for i in range(n)]
    return ver, cmds, buf


def analyze(path):
    ver, cmds, buf = parse(path)
    S = collections.Counter(); R = {}
    regs = [0] * 256
    draws = []; texsets = 0; tex_used = collections.Counter(); calls = 0
    texinfo = {}
    state_changes = collections.Counter()
    for (t, sz, ptr) in cmds:
        name = CT.get(t, 'T%d' % t)
        S['cmd_' + name] += 1
        if t == 0 and sz >= 4:       # Init: снимок регистров
            for i in range(min(sz // 4, 256)):
                v = struct.unpack_from('<I', buf, ptr + i * 4)[0]
            continue
        if t != 1: continue
        n = sz // 4
        for i in range(n):
            w = struct.unpack_from('<I', buf, ptr + i * 4)[0]
            c, a = w >> 24, w & 0xFFFFFF
            if c == 0x0A: calls += 1
            if c in (0x12, 0x1F, 0x21, 0x23, 0x1E, 0xC3, 0xCD, 0xCE, 0xCF, 0xDF, 0xE7, 0xDE, 0xD3, 0x1D, 0x22, 0xC9,
                     0xA0, 0xB8, 0xC5, 0xC6, 0xC7, 0xC8, 0xC2):
                if regs[c] != a: state_changes[c] += 1
            regs[c] = a
            if c == 0x04:
                cnt = a & 0xFFFF; pt = (a >> 16) & 7
                vt = regs[0x12]
                draws.append(dict(prim=PRIMS[pt] if pt < 7 else pt, n=cnt, vt=vt,
                                  tex=regs[0x1E] & 1, fog=regs[0x1F] & 1, blend=regs[0x21] & 1, ztest=regs[0x23] & 1,
                                  zwrite_off=regs[0xE7] & 1, clear=regs[0xD3] & 1, cull=regs[0x1D] & 1,
                                  alphatest=regs[0x22] & 1, texfmt=regs[0xC3] & 15, tw=1 << (regs[0xB8] & 15),
                                  th=1 << ((regs[0xB8] >> 8) & 15), levels=(regs[0xC8] >> 16) & 7,
                                  blendmode=regs[0xDF], texfunc=regs[0xC9] & 7, texaddr=regs[0xA0] | ((regs[0xA8] >> 8 & 0xFF0000)),
                                  through=(vt >> 23) & 1, fogfar=regs[0xCD], fogslope=regs[0xCE], wrap=regs[0xC7],
                                  swizzle=regs[0xC2] & 1, filt=regs[0xC6]))
    return dict(ver=ver, cmds=dict(S), calls=calls, draws=draws, state_changes={hex(k): v for k, v in state_changes.items()})


def tri_count(dr):
    n = dr['n']; p = dr['prim']
    return {'tris': n // 3, 'tristrip': max(n - 2, 0), 'trifan': max(n - 2, 0), 'sprites': n // 2 * 2}.get(p, 0)


def fmt_vt(vt):
    return 'tc=%s col=%s nrm=%s pos=%s idx=%s w=%d morph=%d thr=%d' % (
        VT_TC[vt & 3], VT_COL[(vt >> 2) & 7], VT_NRM[(vt >> 5) & 3], VT_POS[(vt >> 7) & 3], VT_IDX[(vt >> 11) & 3],
        ((vt >> 14) & 7) + 1 if (vt >> 9) & 3 else 0, ((vt >> 18) & 7) + 1 if (vt >> 18) & 7 else 0 if False else 0, (vt >> 23) & 1)


def report(path):
    A = analyze(path)
    D = A['draws']; real = [x for x in D if not x['clear']]
    tris = sum(tri_count(x) for x in real)
    L = ['файл %s версия %d' % (path, A['ver']), 'команды: %s' % A['cmds'],
         'PRIM всего %d (из них очистка %d), треугольников %d, CALL %d' % (len(D), len(D) - len(real), tris, A['calls'])]
    L.append('смен состояний (рег:число): %s' % A['state_changes'])
    c = collections.Counter(); tc = collections.Counter(); ct = collections.Counter()
    for x in real:
        c[(fmt_vt(x['vt']), x['prim'])] += tri_count(x)
        if x['tex']: tc[(TFMT.get(x['texfmt'], x['texfmt']), x['tw'], x['th'], 'swz' if x['swizzle'] else 'lin', 'mips%d' % x['levels'])] += 1
    L.append('форматы вершин × тип (треугольники):')
    for k, v in c.most_common(12): L.append('  %7d  %s %s' % (v, k[0], k[1]))
    L.append('текстуры (формат, размер, swizzle, мипы: число вызовов):')
    for k, v in tc.most_common(16): L.append('  %5d  %s' % (v, k))
    n = len(real) or 1
    L.append('доли вызовов: текстура %.0f%%, туман %.0f%%, блендинг %.0f%%, ztest %.0f%%, запись глубины выкл %.0f%%, through %.0f%%, спрайты %.0f%%' % (
        100 * sum(x['tex'] for x in real) / n, 100 * sum(x['fog'] for x in real) / n, 100 * sum(x['blend'] for x in real) / n,
        100 * sum(x['ztest'] for x in real) / n, 100 * sum(x['zwrite_off'] for x in real) / n,
        100 * sum(x['through'] for x in real) / n, 100 * sum(x['prim'] == 'sprites' for x in real) / n))
    bl = collections.Counter((hex(x['blendmode']), x['texfunc']) for x in real if x['blend'])
    L.append('блендинг (режим, texfunc): %s' % bl.most_common(8))
    fogs = collections.Counter((x['fogfar'], x['fogslope']) for x in real if x['fog'])
    L.append('туман (fog1, fog2 как есть): %s' % fogs.most_common(4))
    return '\n'.join(L), A


if __name__ == '__main__':
    txt, A = report(sys.argv[1])
    print(txt)
