"""Чтение подсекции SPR1 (viewer/stateprops.h, tools/prp2_export.py section) из level.shr / collect-l<N>.shr — для гейтов
tests/levelmech. Только чтение собранных файлов; форматы записей — как struct.pack в prp2_export.py."""
import struct
from pathlib import Path

REC = dict(piece=40, type=84, joint=52, key=28, vis=4, state=80, event=4, call=8, col=64, bill=40, inst=32)
HEAD = ['ntype', 'ninst', 'npiece', 'njoint', 'nkey', 'nvis', 'nstate', 'nevent', 'ncall', 'ncol', 'nbill', 'vbytes',
        'ibytes', 'ndyn', 'nfxname']


def a16(n): return n + (-n % 16)


def parse(b, off):
    """SPR1 с начала off -> dict списков записей (распакованы нужные поля) или None, если не сходится."""
    if b[off:off + 4] != b'SPR1': return None
    h = dict(zip(HEAD, struct.unpack_from('<15I', b, off + 4)))
    if not (0 < h['ntype'] < 5000 and h['ninst'] < 100000): return None
    p = off + 64
    parts = {}
    order = [('vert', h['vbytes']), ('idx', h['ibytes']), ('piece', h['npiece'] * 40), ('type', h['ntype'] * 84),
             ('joint', h['njoint'] * 52), ('key', h['nkey'] * 28), ('vis', h['nvis'] * 4), ('state', h['nstate'] * 80),
             ('event', h['nevent'] * 4), ('call', h['ncall'] * 8), ('col', h['ncol'] * 64), ('bill', h['nbill'] * 40),
             ('inst', h['ninst'] * 32), ('dyn', h['ndyn']), ('fxname', h['nfxname'] * 32)]
    for name, n in order:
        if p + n > len(b): return None
        parts[name] = (p, n); p = a16(p + n)
    S = dict(head=h, end=p, parts=parts)
    tp, _ = parts['type']
    S['types'] = []
    for t in range(h['ntype']):
        u = struct.unpack_from('<10H2H4B4I2f2I3f3f', b, tp + 84 * t)
        S['types'].append(dict(firstPiece=u[0], nPiece=u[1], firstJoint=u[2], nJoint=u[3], firstState=u[4], nState=u[5],
                               firstCol=u[6], nCol=u[7], firstBill=u[8], nBill=u[9], kind=u[10], bindex=u[11], cls=u[12],
                               atc=u[13], fps=u[14], pool=u[15], keyOff=u[16], visOff=u[17], frames=u[18] & 0xFFFF,
                               ntrack=u[18] >> 16, pvisMask=u[19], mass=u[20], life=u[21], visWords=u[22], pvisX=u[23]))
    bp, _ = parts['bill']
    S['bills'] = [dict(joint=b[bp + 40 * k], slot=b[bp + 40 * k + 1], mode=b[bp + 40 * k + 2],
                       rgba=struct.unpack_from('<I', b, bp + 40 * k + 32)[0]) for k in range(h['nbill'])]
    sp_, _ = parts['state']
    S['states'] = []
    for k in range(h['nstate']):
        vis, auto, nev, ncall, pm, pmin, pmax, psp, pcy, fe, fcall, nfx, at = struct.unpack_from('<I4B2HfHHHHf', b, sp_ + 80 * k)
        S['states'].append(dict(vis=vis, auto=auto, nEvent=nev, nCall=ncall, poseMode=pm, poseMin=pmin, poseMax=pmax,
                                firstEvent=fe, firstCall=fcall, autoTime=at))
    ep, _ = parts['event']
    S['events'] = [struct.unpack_from('<BB', b, ep + 4 * k) for k in range(h['nevent'])]
    cp, _ = parts['call']
    S['calls'] = [struct.unpack_from('<BBHf', b, cp + 8 * k) for k in range(h['ncall'])]
    ip, _ = parts['inst']
    S['inst'] = [struct.unpack_from('<3f4fHH', b, ip + 32 * k) for k in range(h['ninst'])]
    vp, _ = parts['vis']
    S['vis'] = list(struct.unpack_from(f'<{h["nvis"]}I', b, vp))
    return S


def find(path):
    """Все SPR1 файла, которые разбираются целиком (магия может встречаться в данных — такие отбрасываются)."""
    b = Path(path).read_bytes(); out = []; i = b.find(b'SPR1')
    while i >= 0:
        s = parse(b, i)
        if s: out.append(s)
        i = b.find(b'SPR1', i + 4)
    return out
