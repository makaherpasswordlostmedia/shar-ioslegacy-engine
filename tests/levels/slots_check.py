#!/usr/bin/env python3
"""Слоты рисунка стейтпропов и гэгов больше 32 (блокер экспорта уровней 2, 3, 5, 6; docs/РЕЦЕПТ_УРОВНЯ.md §3.1, 29.09).

Какие объекты: все стейтпропы (AnimDynaPhys 0x3F0000E) районов и зон уровней 1–7 и все сцены гэгов level.mfk уровней 1–7,
у которых в составном рисунке больше 32 слотов (props + эффекты): обезьяны l2/l5_monkiesgag, сигнализация gag_alrm,
летучие мыши gag_bats, gag_matt, gag_sqsh. Экспорт — тот же код, что у уровня (tools/prp2_export.py через
tools/collect_export.Builder), движок — viewer/stateprops.c (tests/levels/slots_host.c).
Ожидание — с диска, своим разбором: порядок слотов — рисунки 0x4516, потом эффекты 0x4518 составного рисунка 0x4512;
слот куска — рисунок-меш 0x10000 с геометрией, слот билборда — группа 0x17002; видимость по состояниям — VisibilityData
0x8020002 машины состояний (рисунок, не названный в состоянии: prop виден, эффект нет — правило экспорта), у гэгов — три
состояния порта: ждёт (props), играет (все слоты), сыграл (props).
  slots_check.py --make SPR1.bin [--plant]   собрать подсекцию SPR1 и ожидание SPR1.json; --plant — как до 29.09: маска в одно
                                             слово, номер слота 5 бит (слоты 32+ теряются) — обязан дать FAIL
  slots_check.py --truncate SPR1.bin КОПИЯ   то же подложение готовой подсекции
  slots_check.py HOST_OUT SPR1.json          сверить движок с диском: 0 = PASS"""
import sys, json, struct, re
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools')); sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))
from p3d import read, walk, string   # noqa: E402  (MIT, разбор контейнера)
GAME = (ROOT / 'hit-and-run-web/source/game').resolve()
N = lambda c: string(c.data)[0]
NV = lambda c: string(c.data, 4)[0]


def comp_slots(container):
    """-> (имена слотов по порядку, число props) из составного рисунка контейнера (свой разбор)."""
    cd = next((c for c in walk(container) if c.id == 0x4512), None)
    props, effs = [], []
    for l in cd.children if cd else []:
        for e in l.children:
            if e.id == 0x4516: props.append(N(e))
            elif e.id == 0x4518: effs.append(N(e))
    return props + effs, len(props)


def disk_objects():
    """[(вид, уровень, файл, имя, контейнер, машина состояний или None)] — объекты уровней 1–7 больше 32 слотов."""
    out, seen = [], set()
    art = GAME / 'art'
    for lv in range(1, 8):
        for f in [art / f'l{lv}_terra.p3d'] + sorted(art.glob(f'l{lv}r*.p3d')) + sorted(art.glob(f'l{lv}z*.p3d')):
            for ent in read(f).children:
                if ent.id != 0x3f0000e: continue
                w = next((c for c in ent.children if c.id == 0x3f00010), None)
                if w is None or N(ent) in seen: continue
                slots, _ = comp_slots(w)
                if len(slots) > 32:
                    seen.add(N(ent)); out.append(('stateprop', lv, f, N(ent), ent, w))
        for line in (GAME / f'scripts/missions/level0{lv}/level.mfk').read_text(errors='replace').splitlines():
            m = re.match(r'\s*GagBegin\("([^"]+)\.p3d"\)', line)
            if not m or m.group(1) in seen: continue
            f = art / 'nis/gags' / (m.group(1) + '.p3d')
            if not f.exists(): continue
            root = read(f); slots, _ = comp_slots(root)
            if len(slots) > 32: seen.add(m.group(1)); out.append(('gag', lv, f, m.group(1), root, None))
    return out


def expected(kind, container, w):
    slots, nprops = comp_slots(container)
    meshes = {N(c) for c in (w if w is not None else container).children if c.id == 0x10000 and any(x.id == 0x10002 for x in walk(c))}
    bills = {NV(c) for c in (w if w is not None else container).children if c.id == 0x17002}
    mesh_slots = sorted(i for i, s in enumerate(slots[:nprops]) if s in meshes)
    bill_slots = sorted(i for i, s in enumerate(slots[:nprops]) if s in bills)
    if kind == 'gag':
        props = list(range(nprops)); states = [props, list(range(len(slots))), props]
    else:
        from stateprop_dump import parse_stateprop   # чтение StatePropData диска
        sp = parse_stateprop(next(c for c in walk(w) if c.id == 0x8020000))
        states = []
        for st in sp['states']:
            names = dict(st['vis'])
            states.append([i for i, s in enumerate(slots) if names.get(s, 1 if i < nprops else 0)])
    return dict(slots=len(slots), props=nprops, mesh_slots=mesh_slots, bill_slots=bill_slots, states=states)


def make(out, plant):
    import collect_export as CX
    import numpy as np
    B = CX.Builder(1, verbose=False)
    objs = disk_objects(); exp = []
    for kind, lv, f, name, cont, w in objs:
        B.conv.resources(read(f))
        if kind == 'gag': B.gag_type(name, (0.0, 0.0, 0.0), 0)
        else:
            row = dict(file=f, ent=cont, w=w, inst=[('x', np.eye(4))], files={f.stem: 1})
            B.sp._add_stateprop(name, row)
        exp.append(dict(kind=kind, level=lv, file=f.name, name=name, **expected(kind, cont, w)))
        print(f'  {kind:9s} l{lv} {f.name:14s} {name:24s} слотов {exp[-1]["slots"]}, кусков {len(B.sp.types[-1]["pieces"])}, '
              f'состояний {len(B.sp.types[-1]["states"])}', flush=True)
    tmap = {t: i for i, t in enumerate(sorted(B.sp.textures()))}
    body = bytearray(B.sp.section(tmap, []))
    if plant: truncate32(body)
    Path(out).write_bytes(bytes(body)); Path(out).with_suffix('.json').write_text(json.dumps(exp, ensure_ascii=False, indent=1))
    print(f'-> {out}: {len(body)} Б, объектов {len(exp)}' + (' (ПОДЛОЖЕНО: маска 32 бита, слот 5 бит)' if plant else ''))


def truncate32(b):
    """Как до 29.09: SpType.visWords = 0 (одно слово), слот куска 5 бит, слот билборда и окна EFX & 31."""
    h = struct.unpack_from('<15I', b, 4)
    ntype, npiece, nbill, vlen, ilen = h[0], h[2], h[10], h[11], h[12]
    sizes = [vlen, ilen, npiece * 40, ntype * 84, h[3] * 52, h[4] * 28, h[5] * 4, h[6] * 80, h[7] * 4, h[8] * 8, h[9] * 64, nbill * 40]
    p, offs = 64, []
    for s in sizes: offs.append(p); p += s; p += -p % 16
    for i in range(npiece):
        o = offs[2] + 40 * i + 20; fl, = struct.unpack_from('<I', b, o); struct.pack_into('<I', b, o, fl & ~(0xE0 << 16))
    for i in range(ntype): struct.pack_into("<2I", b, offs[3] + 84 * i + 52, 0, 0)   # SpType @52 visWords, @56 pvisX
    for i in range(nbill): o = offs[11] + 40 * i + 1; b[o] &= 31
    for i in range(h[6]):   # окна EFX состояний: слот & 31 (иначе движок отвергнет подсекцию целиком — тоже красный, но немой)
        for k in range(4): b[offs[7] + 80 * i + 28 + 12 * k] &= 31


def check(host, js):
    exp = json.loads(Path(js).read_text()); bad = []
    T, P, Bl, S = {}, {}, {}, {}
    for l in Path(host).read_text().splitlines():
        f = l.split()
        if not f: continue
        if f[0] == 'T': T[int(f[1])] = int(f[2])
        elif f[0] == 'P': P.setdefault(int(f[1]), set()).add(int(f[3]))
        elif f[0] == 'B': Bl.setdefault(int(f[1]), set()).add(int(f[3]))
        elif f[0] == 'S': S.setdefault(int(f[1]), {})[int(f[2])] = f[3]
    if len(T) != len(exp): bad.append(f'типов в движке {len(T)}, объектов {len(exp)}')
    for t, e in enumerate(exp):
        nm = f"{e['name']} (l{e['level']}, {e['slots']} слотов)"
        if T.get(t, 0) < e['slots']: bad.append(f'{nm}: движок держит {T.get(t)} слотов'); continue
        if P.get(t, set()) != set(e['mesh_slots']):
            bad.append(f"{nm}: слоты кусков в движке {sorted(P.get(t, set()) - set(e['mesh_slots']))[:6]} лишние, "
                       f"{sorted(set(e['mesh_slots']) - P.get(t, set()))[:6]} потеряны")
        if Bl.get(t, set()) != set(e['bill_slots']):
            bad.append(f"{nm}: слоты билбордов расходятся: лишние {sorted(Bl.get(t, set()) - set(e['bill_slots']))[:6]}, "
                       f"потеряны {sorted(set(e['bill_slots']) - Bl.get(t, set()))[:6]}")
        for s, want in enumerate(e['states']):
            got = S.get(t, {}).get(s)
            if got is None: bad.append(f'{nm}: нет состояния {s} в движке'); continue
            on = {i for i, ch in enumerate(got) if ch == '1'}
            if on != set(want):
                bad.append(f'{nm} состояние {s}: включены в движке и не на диске {sorted(on - set(want))[:6]}, '
                           f'на диске и не в движке {sorted(set(want) - on)[:6]}')
    print(f"объектов больше 32 слотов: {len(exp)} — " + ', '.join(f"{e['name']} l{e['level']} {e['slots']}" for e in exp))
    for l in bad[:12]: print('  ПРОВАЛ:', l)
    print('PASS' if not bad else f'FAIL ({len(bad)})')
    return 0 if not bad else 1


def main():
    a = sys.argv[1:]
    if a and a[0] == '--make': make(a[1], '--plant' in a); return 0
    if a and a[0] == '--truncate':   # готовая подсекция -> подложенная копия (как --plant, без повторного экспорта)
        b = bytearray(Path(a[1]).read_bytes()); truncate32(b); Path(a[2]).write_bytes(bytes(b))
        Path(a[2]).with_suffix('.json').write_text(Path(a[1]).with_suffix('.json').read_text()); return 0
    return check(a[0], a[1])


if __name__ == '__main__':
    sys.exit(main())
