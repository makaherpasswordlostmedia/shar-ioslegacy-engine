#!/usr/bin/env python3
"""№907: перепись кусков с флагом 2 (полупрозрачное; не аддитивное, не небо), у которых смешивание ничего не делает: текстура целиком
непрозрачна (уровень 0, альфа 255) и у вершин альфа >= 250. Такой кусок уходит в очередь полупрозрачного без записи глубины, рисуется
в порядке файла — у закрытого предмета (автомат с газировкой) задняя стенка ложится поверх ближней, виден «вывернутый» предмет.
Читает только level.shr (PRP1, SPR1, город). Вывод: по каждому уровню — кусков и экземпляров «пустого смешивания» у пропов и стейтпропов,
кусков города (по текстуре).
    python tests/inside907/census.py LEVEL.shr [LEVEL.shr ...]      (код возврата 1, если что-то нашлось: красный до правки, зелёный после)"""
import sys, struct
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
import tex_gate

F_ADD, F_SKY = 1 << 24, 4
NOOP_ALPHA = 250


def tex_opaque(b):
    recs, end, toff, start = tex_gate.walk(b)
    out = []
    for r in recs:
        try: out.append(bool(tex_gate.level0(b, r)[..., 3].min() >= 255))
        except Exception: out.append(False)
    return out


def verts_opaque(b, off, nv, fl):
    """16-байтовые вершины: байт 7 — альфа ABGR; 12-байтовые (флаг 32) — альфа 255"""
    if fl & 32 or nv <= 0: return True
    return bool(np.frombuffer(b, np.uint8, nv * 16, off).reshape(nv, 16)[:, 7].min() >= NOOP_ALPHA)


def pieces_of(b):
    """-> (props, sprops, city): props/sprops = [(tex, flags, nv, vertex_off, экземпляров)], city = [(tex, flags)]"""
    prp, = struct.unpack_from('<I', b, 96); props, sprops = [], []
    if prp and b[prp:prp + 4] in (b'PRP1', b'PRP2'):
        hsz = 64 if b[prp:prp + 4] == b'PRP2' else 32
        npc, nty, nin, vb, ib = struct.unpack_from('<5I', b, prp + 4)
        vo = prp + hsz; po = vo + vb + ib; to = po + 40 * npc; io = to + 20 * nty
        cnt = [0] * nty
        for i in range(nin): cnt[struct.unpack_from('<I', b, io + 32 * i + 28)[0]] += 1
        for t in range(nty):
            first, n = struct.unpack_from('<II', b, to + 20 * t + 12)
            for k in range(n):
                _, _, _, _, tex, fl, nv, ni, vOff, iOff = struct.unpack_from('<4f2i4I', b, po + 40 * (first + k))
                props.append((tex, fl, nv, vo + vOff, cnt[t], po + 40 * (first + k) + 20))
        if b[prp:prp + 4] == b'PRP2':
            so, ss = struct.unpack_from('<II', b, prp + 32)
            if ss:
                s = prp + so
                nt, ni_, npc2, nj, nk, nvis, ns, ne, nc, ncol, nb, vb2, ib2, nd, _ = struct.unpack_from('<15I', b, s + 4)
                al = lambda x: (x + 15) & ~15
                p = s + 64; vo2 = p; p = al(p + vb2); p = al(p + ib2); po2 = p; p = al(p + 40 * npc2); ty0 = p
                q = al(ty0 + 84 * nt); q = al(q + 52 * nj); q = al(q + 28 * nk); q = al(q + 4 * nvis); q = al(q + 80 * ns); q = al(q + 4 * ne)
                q = al(q + 8 * nc); q = al(q + 64 * ncol); q = al(q + 40 * nb); inst0 = q
                cnt2 = [0] * nt
                for i in range(ni_): cnt2[struct.unpack_from('<H', b, inst0 + 32 * i + 28)[0]] += 1
                for t in range(nt):
                    first, n = struct.unpack_from('<HH', b, ty0 + 84 * t)
                    for k in range(n):
                        _, _, _, _, tex, fl, nv, ni, vOff, iOff = struct.unpack_from('<4f2i4I', b, po2 + 40 * (first + k))
                        sprops.append((tex, fl, nv, vo2 + vOff, cnt2[t], po2 + 40 * (first + k) + 20))
    ptab, = struct.unpack_from('<I', b, 76); npc_city, = struct.unpack_from('<I', b, 8)
    city = []
    for i in range(npc_city):
        tex, fl, nv, ni, owner = struct.unpack_from('<5i', b, ptab + 80 * i + 24)
        if owner == 0: city.append((tex, fl))
    return props, sprops, city


def noop(b, topq, lst):
    """кусок: флаг 2, не аддитивный, не небо, текстура непрозрачна, вершины непрозрачны -> смешивание пустое"""
    out = []
    for (tex, fl, nv, voff, cnt, rec) in lst:
        if not (fl & 2) or (fl & (F_ADD | F_SKY)): continue
        if 0 <= tex < len(topq) and topq[tex] and verts_opaque(b, voff, nv, fl): out.append((tex, fl, nv, cnt, rec))
    return out


def census(path):
    b = Path(path).read_bytes(); topq = tex_opaque(b); props, sprops, city = pieces_of(b)
    pn, sn = noop(b, topq, props), noop(b, topq, sprops)
    cb = [c for c in city if (c[1] & 2) and not (c[1] & (F_ADD | F_SKY))]
    cn = [c for c in cb if 0 <= c[0] < len(topq) and topq[c[0]]]
    return dict(props_pieces=len(props), props_blend=sum(1 for p in props if p[1] & 2), props_noop=len(pn), props_noop_inst=sum(x[3] for x in pn),
                sprops_pieces=len(sprops), sprops_blend=sum(1 for p in sprops if p[1] & 2), sprops_noop=len(sn), sprops_noop_inst=sum(x[3] for x in sn),
                city_blend=len(cb), city_blend_opaque_tex=len(cn))


if __name__ == '__main__':
    bad = 0
    for p in [a for a in sys.argv[1:] if not a.startswith('--')]:
        r = census(p); print(p.split('/')[-2] + '/' + p.split('/')[-1] if '/' in p else p, r)
        bad += r['props_noop'] + r['sprops_noop']
    print('КРАСНОЕ: кусков пропов и стейтпропов с пустым смешиванием %d' % bad if bad else 'ЗЕЛЁНОЕ: 0'); sys.exit(1 if bad else 0)
