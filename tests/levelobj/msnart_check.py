#!/usr/bin/env python3
"""Host-проверка предметов и маркеров миссий (msnart.shr, формат MSA2) против данных диска.

  python3 tests/levelobj/msnart_check.py [build/msnart.shr] [--plant]   (--plant: испорченная копия обязана упасть)
Счёт по диску заново (скрипты уровня 1 -> LoadP3DFile -> составные рисунки, шейдеры, клипы PTRN, квады):
  * формат MSA2 (у MSA1 нет поз по кадрам — старый пакет обязан упасть)
  * у каждого рисунка с циклическим клипом PTRN и движущимися суставами — столько же кадров позы, сколько в клипе;
    у остальных — 1 кадр; доллар (поза покоя скелета на 0.72 м в стороне от кадра 0) стоит в позе кадра 0
  * режим рисования мешей из шейдера и альфы: BLMD 2 -> сложение, BLMD 3 -> вычитание, BLMD 1 с непрозрачной текстурой
    и вершинами -> непрозрачный с записью глубины (раньше просвечивал сам через себя)
  * dist квадов (свечения/звёзды за предметом) перенесён как в данных
  * все персонажи скриптов уровня (tools/npc_list.py) есть в списке моделей движка viewer/msn_view.c
Итог: "CHECK ... ok|FAIL" и "RESULT PASS|FAIL n/m"."""
import sys, struct, re
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[2]
for p in ('tools', 'tools/missions', 'hit-and-run-web/tools'): sys.path.insert(0, str(ROOT / p))
from p3d import read, string, Chunk   # noqa: E402
import prp2_export as PX              # noqa: E402
import msnart_export as ME            # noqa: E402
import npc_list                       # noqa: E402

ok_n = fail_n = 0
def check(name, ok, msg):
    global ok_n, fail_n
    print(f'CHECK {name:26s} {"ok  " if ok else "FAIL"} {msg}'); ok_n += ok; fail_n += (not ok)

def draws(b):
    """-> {путь: {имя: dict(nfr, njoint, frames, meshes[(blend, mode, joint)], bills[dist])}}"""
    n, ot = struct.unpack_from('<2I', b, 4); out = {}
    for i in range(n):
        path = b[ot + 96 * i: ot + 96 * i + 80].split(b'\0')[0].decode(); off, size = struct.unpack_from('<2I', b, ot + 96 * i + 80)
        e = b[off:off + size]; ntex, ndraw, nimg, oT, oD, oI = struct.unpack_from('<6I', e, 0); dd = {}
        for k in range(ndraw):
            name = e[oD + 64 * k: oD + 64 * k + 32].split(b'\0')[0].decode()
            nb, ob, nm, om, nj, nfr = struct.unpack_from('<6I', e, oD + 64 * k + 32); fps, oj = struct.unpack_from('<fI', e, oD + 64 * k + 56)
            fr = np.frombuffer(e, '<f4', nj * nfr * 12, oj).reshape(nfr, nj, 12) if nj and nfr else None
            meshes = [(fl & 0xFF, (fl >> 8) & 0xFF, fl >> 16) for fl in (struct.unpack_from('<I', e, om + 16 * q + 4)[0] for q in range(nm))]
            bills = [struct.unpack_from('<f', e, ob + 80 * q + 76)[0] for q in range(nb)]
            dd[name] = dict(nfr=nfr, njoint=nj, frames=fr, meshes=meshes, bills=bills)
        out[path] = dd
    return out

def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    f = Path(args[0]) if args else ROOT / 'build/msnart.shr'
    b = f.read_bytes()
    if '--plant' in sys.argv and b[:4] == b'MSA2':   # отрицательный контроль: позы в 1 кадр, меши полупрозрачные, dist 0
        b = bytearray(b); n, ot = struct.unpack_from('<2I', b, 4)
        for i in range(n):
            off, size = struct.unpack_from('<2I', b, ot + 96 * i + 80); ndraw, oD = struct.unpack_from('<I', b, off + 4)[0], struct.unpack_from('<I', b, off + 16)[0]
            for k in range(ndraw):
                d = off + oD + 64 * k; nb, ob, nm, om = struct.unpack_from('<4I', b, d + 32)
                struct.pack_into('<I', b, d + 52, 1)
                for q in range(nm):
                    fl, = struct.unpack_from('<I', b, off + om + 16 * q + 4); struct.pack_into('<I', b, off + om + 16 * q + 4, (fl & ~0xFF00) | (2 << 8))
                for q in range(nb): struct.pack_into('<f', b, off + ob + 80 * q + 76, 0.0)
        b = bytes(b)
    check('format', b[:4] == b'MSA2', f'магия {b[:4]!r} (нужно MSA2: позы по кадрам, режим мешей, dist)')
    if b[:4] != b'MSA2': return
    D = draws(b)
    anim_bad, anim_n, mode_bad, mode_n, dist_bad, dist_n, dollar = [], 0, [], 0, [], 0, None
    for p in ME.load_scripts(1):
        if not p.startswith('art/missions/') or p not in D: continue
        root = read(ME.GAME / p); texs = ME.textures_of(root); sh = ME.shaders_of(root); bbs = ME.billboards(root)
        skels = {string(c.data)[0]: c for c in root.children if c.id == 0x4500}
        meshes = {string(c.data)[0]: c for c in root.children if c.id == 0x10000}
        for cd in (c for c in root.children if c.id == 0x4512):
            cname, q = string(cd.data); skn, _ = string(cd.data, q)
            if cname not in D[p]: continue
            got = D[p][cname]
            an = [c for c in root.children if c.id == 0x121000 and string(c.data, 4)[0] in ('PTRN_' + cname, 'PTRN_' + skn)]
            loop = 0
            for c in an:
                _, qq = string(c.data, 4)
                if c.data[qq:qq + 4] == b'PTRN': loop = struct.unpack_from('<ffI', c.data, qq + 4)[2]
            if skn in skels:
                joints, keys, nfr, ntrack, fps = PX.joint_poses(Chunk(0, b'', [skels[skn]] + an))
                want = nfr if (ntrack and loop and nfr > 1) else 1
                anim_n += want > 1
                if got['nfr'] != want: anim_bad.append(f'{cname}: кадров {got["nfr"]}, в данных {want}')
                if cname == 'dollar':
                    J0 = PX.rest_world(joints); dollar = max(float(np.abs(got['frames'][0, i, 9:] - J0[i][:3, 3]).max()) for i in range(len(J0)))
            # режим мешей и dist квадов — в порядке частей составного рисунка, как в экспорте
            k = bi = 0
            for lst in cd.children:
                for el in lst.children:
                    if el.id != 0x4516: continue
                    dn = string(el.data)[0]
                    if dn in bbs:
                        for qd in bbs[dn]['quads']:
                            dist_n += 1
                            if bi >= len(got['bills']) or abs(got['bills'][bi] - qd[5]) > 1e-5: dist_bad.append(f'{cname}/{dn}')
                            bi += 1
                        continue
                    if dn not in meshes: continue
                    for pg in meshes[dn].children:
                        if pg.id != 0x10002: continue
                        s_name, parts = ME.geometry(pg); s_ = sh.get(s_name, {}); blm = int(s_.get('BLMD', 0) or 0)
                        if not parts: continue
                        if k >= len(got['meshes']): mode_bad.append(f'{cname}: меньше мешей'); break
                        gb, gm, gj = got['meshes'][k]; k += 1; mode_n += 1
                        img = texs.get(s_.get('TEX', ''))
                        va = min(int(np.clip(pt.get('alpha', np.ones((1, 1))).min(), 0, 1) * 255) for pt in parts)
                        opaque = img is not None and np.asarray(img.convert('RGBA'))[..., 3].min() >= 250 and va >= 250
                        want_m = 3 if blm == 2 else 4 if blm == 3 else (0 if blm == 1 and opaque else None)
                        if want_m is not None and gm != want_m: mode_bad.append(f'{cname}/{dn}: режим {gm}, по данным {want_m} (BLMD {blm})')
    check('anim.frames', not anim_bad, f'рисунков с циклом позы {anim_n}; расхождений {len(anim_bad)} {anim_bad[:3]}')
    check('anim.dollar', dollar is not None and dollar < 1e-3, f'доллар в позе кадра 0 клипа (отклонение {dollar})')
    check('mesh.mode', not mode_bad, f'мешей {mode_n}; расхождений {len(mode_bad)} {mode_bad[:3]}')
    check('bill.dist', dist_n > 0 and not dist_bad, f'квадов {dist_n}; расхождений dist {len(dist_bad)}')
    src = (ROOT / 'viewer/msn_view.c').read_text()
    names = [r['name'] for r in npc_list.npcs(1) if r['ok'] and r['name'] != 'homer']
    miss = [n for n in names if f'"chars/{n}.chr"' not in src]
    check('npc.models', not miss, f'персонажей скриптов уровня {len(names)}, без модели в движке {len(miss)} {miss[:6]}')

if __name__ == '__main__':
    main()
    print(f'RESULT {"PASS" if not fail_n else "FAIL"} {ok_n}/{ok_n + fail_n}')
    sys.exit(1 if fail_n else 0)
