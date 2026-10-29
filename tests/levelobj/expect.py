#!/usr/bin/env python3
"""Host-проверка экспорта семей AnimCollision 0x3F00008 / Anim 0x3F0000C: level.shr против данных диска.

  python3 tests/levelobj/expect.py NEW.shr BASE.shr [--level 1]
BASE — тот же уровень, собранный без семей (SHR_NO_ANIMOBJ=1 tools/build_level.sh), NEW — с ними. Счёт по диску заново
(сущности, составной рисунок, объёмы, клипы — tools/animobj_export.gather + prp2_export.composite/joint_poses), правило
«что куда» пересчитано здесь, не взято у экспортёра:
  * объёмы: COL1 NEW − COL1 BASE (ящики + цилиндры) == объёмам CollisionObject всех AnimCollision на диске
  * живые объёмы ANM1 == объёмам на суставах с дорожкой PTRN (сам сустав или предок), и все указывают в добавленный хвост COL1
  * рисунок: слоты типов SPR1, добавленных в NEW, == частям, которые должны жить в SPR1 (объект с движением/PVIS — все
    части, неподвижный — только билборды); треугольники этих частей == треугольникам мешей диска
  * части в город (неподвижные меши) — счёт и треугольники диска (печать), > 0
  * объекты ANM1 == объектам с SPR1-частями, живыми объёмами или action-локатором; действия — как в локаторах
Итог: строки "CHECK имя ok|FAIL ..." и "RESULT PASS|FAIL n/m", код 0/1."""
import sys, struct
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools')); sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))
import animobj_export as AE          # noqa: E402
import prp2_export as PX              # noqa: E402
from p3d import read, string          # noqa: E402
from convert import geometry          # noqa: E402

ok_n = fail_n = 0
def check(name, ok, msg):
    global ok_n, fail_n
    print(f'CHECK {name:30s} {"ok  " if ok else "FAIL"} {msg}'); ok_n += ok; fail_n += (not ok)

def sections(path):
    b = Path(path).read_bytes()
    assert b[:4] == b'SHR7', path
    col, prp = struct.unpack_from('<2I', b, 92)
    nb, nc = struct.unpack_from('<2I', b, col + 28)
    psz, = struct.unpack_from('<I', b, prp + 40)
    so, ss = struct.unpack_from('<2I', b, prp + 32)
    ao, asz = struct.unpack_from('<2I', b, prp + 52)
    return b, dict(nbox=nb, ncyl=nc, prp=prp, spr=prp + so if ss else 0, anm=prp + ao if ao and asz else 0)

def spr_types(b, off):
    """-> [(firstPiece, nPiece, firstBill, nBill)], pieces [(ni, slot)], bills [slot]"""
    h = struct.unpack_from('<15I', b, off + 4)
    ntype, ninst, npiece, njoint, nkey, nvis, nstate, nevent, ncall, ncol, nbill, vlen, ilen, ndyn, nfx = h
    sizes = [vlen, ilen, npiece * 40, ntype * 84, njoint * 52, nkey * 28, nvis * 4, nstate * 80, nevent * 4, ncall * 8,
             ncol * 64, nbill * 40, ninst * 32]
    p = off + 64; offs = []
    for s in sizes:
        offs.append(p); p += s; p += -p % 16
    pieces = [(struct.unpack_from('<I', b, offs[2] + 40 * i + 28)[0], (struct.unpack_from('<I', b, offs[2] + 40 * i + 20)[0] >> 16) & 0xFF)
              for i in range(npiece)]
    types = [struct.unpack_from('<10H', b, offs[3] + 84 * i) for i in range(ntype)]
    bills = [struct.unpack_from("<B", b, offs[11] + 40 * i + 1)[0] for i in range(nbill)]
    return types, pieces, bills

def disk(level):
    art = (ROOT / 'hit-and-run-web/source/game').resolve() / 'art'
    acts = AE.action_locators(PX.level_files(art, level))
    d = dict(vols=0, live=0, spr_parts=0, spr_tris=0, city_parts=0, city_tris=0, objs=0, acts={})
    for f in PX.level_files(art, level):
        root = read(f)
        for ent in root.children:
            if ent.id not in AE.FAMILIES: continue
            name = string(ent.data)[0]; w = AE.gather(root, ent)
            props, effects = PX.composite(w)
            vols = AE.volumes(w, name) if ent.id == AE.ANIM_COLL else []
            if not props and not vols: continue
            joints, keys, nfr, ntrack, fps = PX.joint_poses(w); pv, _ = PX.pvis_tracks(w)
            moving = bool(ntrack) or bool(pv)
            meshes = {string(c.data)[0]: c for c in w.children if c.id == 0x10000}
            bbs = PX.billboards(w)
            nspr = 0
            for dn, joint, _ in props:
                tris = sum(len(q['indices']) // 3 for pg in meshes[dn].children if pg.id == 0x10002 for q in geometry(pg)[1]) if dn in meshes else 0
                if dn in meshes and not moving: d['city_parts'] += 1; d['city_tris'] += tris
                elif dn in meshes or dn in bbs: d['spr_parts'] += 1; d['spr_tris'] += tris; nspr += 1
            mv = AE.moving_joints(joints)
            typed = nspr or (moving and effects)   # тип SPR1 есть и у движущегося объекта только с частицами (пружина АЭС)
            live = sum(1 for o, _ in vols if o < len(mv) and mv[o]) if typed else 0
            d['vols'] += len(vols); d['live'] += live
            act = acts.get(name, (0,))[0]
            if typed or live or act: d['objs'] += 1
            if act: d['acts'][name] = act
    return d

def main():
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    level = int(sys.argv[sys.argv.index('--level') + 1]) if '--level' in sys.argv else 1
    new, base = a[0], a[1]
    D = disk(level)
    bn, sn = sections(new); bb, sb = sections(base)
    dv = (sn['nbox'] + sn['ncyl']) - (sb['nbox'] + sb['ncyl'])
    check('col.volumes', dv == D['vols'], f'COL1 +{dv} объёмов (ящиков {sn["nbox"] - sb["nbox"]}, цилиндров {sn["ncyl"] - sb["ncyl"]}), на диске {D["vols"]}')
    if not sn['anm']:
        check('anm.present', False, 'в PRP2 нет ANM1 (@52)'); return
    nobj, nvol, oo, ov = struct.unpack_from('<4I', bn, sn['anm'] + 8)
    check('anm.live', nvol == D['live'], f'живых объёмов ANM1 {nvol}, на диске на движущихся суставах {D["live"]}')
    tail = True
    for v in range(nvol):
        kind, _, obj, col = struct.unpack_from('<BBHI', bn, sn['anm'] + ov + 72 * v)
        tail &= col >= (sb['nbox'] if kind == 0 else sb['ncyl']) and col < (sn['nbox'] if kind == 0 else sn['ncyl'])
    check('anm.col_tail', tail, 'все живые объёмы — в добавленном хвосте COL1 (не чужие ящики уровня)')
    check('anm.objects', nobj == D['objs'], f'объектов ANM1 {nobj}, на диске {D["objs"]}')
    acts = [struct.unpack_from('<B', bn, sn['anm'] + oo + 80 * k + 8)[0] for k in range(nobj)]
    want = sorted(D['acts'].values()); got = sorted(x for x in acts if x)
    check('anm.actions', got == want, f'действия ANM1 {got}, в action-локаторах {want}')
    tn, pn, bln = spr_types(bn, sn['spr']); tb, _, _ = spr_types(bb, sb['spr'])
    slots, tris = 0, 0
    # 29.09: тип гаечного ключа (пункт 4, tools/psp_export.py sprops.add_wrenches) — последним в обоих уровнях; типы объектов
    # вставлены перед ним: новые = tn[len(tb) - 1 : -1], если хвосты совпадают по числу частей и билбордов
    same_tail = len(tb) and len(tn) > len(tb) and (tn[-1][1], tn[-1][9]) == (tb[-1][1], tb[-1][9])
    new_types = tn[len(tb) - 1:-1] if same_tail else tn[len(tb):]
    for t in new_types:
        fp, np_, fj, nj, fs, ns, fc, nc, fbl, nbl = t
        s = {pn[i][1] for i in range(fp, fp + np_)} | {bln[i] for i in range(fbl, fbl + nbl)}
        slots += len(s); tris += sum(pn[i][0] // 3 for i in range(fp, fp + np_))
    eff = 0   # слоты эффектов (системы частиц) в типах — не части рисунка: считаем только слоты с куском или билбордом
    check('spr.parts', slots == D['spr_parts'], f'частей в SPR1 {slots} (типов +{len(tn) - len(tb)}), на диске {D["spr_parts"]}')
    check('spr.tris', tris == D['spr_tris'], f'треугольников в SPR1 {tris}, на диске {D["spr_tris"]}')
    check('city.parts', D['city_parts'] > 0, f'неподвижных мешей в город {D["city_parts"]}, треугольников диска {D["city_tris"]}')

if __name__ == '__main__':
    main()
    print(f'RESULT {"PASS" if not fail_n else "FAIL"} {ok_n}/{ok_n + fail_n}')
    sys.exit(1 if fail_n else 0)
