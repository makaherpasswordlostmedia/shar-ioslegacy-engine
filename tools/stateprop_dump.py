"""Разбор стейтпропов SHAR (AnimDynaPhys 0x3F0000E и глобальные StatePropData) и обломков BreakableObject 0x3001000.
Только чтение, ничего не пишет (кроме --json). Опора: hit-and-run-web/tools/p3d.py (MIT), donut/dev/Chunks.md (GPL),
форматы StateProp* 0x8020000..5 — восстановлены по данным диска (в donut только номера чанков).

python tools/stateprop_dump.py                      -> машины состояний l1_crate, l1_vending, l1_phonestop, l1z6_powerbox, l1_shrubround
python tools/stateprop_dump.py l1_gaspump l1_fence  -> только эти (имя стейтпропа или сущности, подстрока)
python tools/stateprop_dump.py --inventory [N]      -> все DynaPhys/InstStatPhys/AnimDynaPhys/Breakable уровня N (1)
python tools/stateprop_dump.py --breakables [N]     -> содержимое BreakableObject уровня N + l0N_fx
python tools/stateprop_dump.py --deep NAME          -> + скелет, составной рисунок, меши, анимации, коллизия
python tools/stateprop_dump.py --file art/l01_fx.p3d beecamera   -> любой файл
python tools/stateprop_dump.py --json out.json [N]  -> весь уровень в JSON (для экспорта)

ФОРМАТЫ (строка = u8 длина + байты, дополнено нулями до 4; всё little-endian):
  StatePropData            0x8020000: u32 version(1), str name, str objectFactoryName, u32 numStates
   StatePropStateData      0x8020001: str name, u32 autoTransition, u32 outState, u32 numDrawables,
                                      u32 numFrameControllers, u32 numEvents, u32 numCallbacks, f32 outFrame
                                      outFrame (и onFrame у вызовов) — СЕКУНДЫ от входа в состояние, не кадры:
                                      beecamera s0 PTRN 0..75 кадров @30/с x скорость 2 = 1.25 с = outFrame 1.25
    VisibilityData         0x8020002: str drawableName (имя из CompositeDrawable: prop или effect), u32 isVisible
    FrameControllerData    0x8020003: str controllerName (PTRN_/BQG_/EFX_/PVIS_...), u32 isCyclic, u32 numCycles,
                                      u32 holdFrame, f32 minFrame, f32 maxFrame, f32 relativeSpeed
    EventData              0x8020004: str eventName (HIT, STOMP, VEHICLE_HIT, DESTROYED, ...), u32 toState, u32 eventId
    CallbackData           0x8020005: str callbackName (SPAWN_10_COINS, REMOVE_FROM_WORLD, ...), u32 callbackId, f32 onFrame
  BreakableObject          0x3001000: u32 index (тип обломка, BreakablesEnum), u32 count (размер пула)
"""
import sys, struct, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))
from p3d import read, walk, string

GAME = ROOT / 'hit-and-run-web/source/game'
ART = GAME / 'art'
N = lambda c: string(c.data)[0]              # имя в начале данных
NV = lambda c: string(c.data, 4)[0]          # версия u32, потом имя

def level_files(level=1):
    fs = [f'l{level}_terra'] + sorted(p.stem for p in ART.glob(f'l{level}r*.p3d')) + sorted(p.stem for p in ART.glob(f'l{level}z*.p3d'))
    return [ART / f'{f}.p3d' for f in fs]

# ---------------------------------------------------------------- StateProp
def parse_stateprop(c):
    ver, = struct.unpack_from('<I', c.data); name, p = string(c.data, 4); fac, p = string(c.data, p)
    nstates, = struct.unpack_from('<I', c.data, p)
    states = []
    for s in c.children:
        if s.id != 0x8020001: continue
        sn, p = string(s.data)
        auto, out, nd, nf, ne, ncb, outf = struct.unpack_from('<6If', s.data, p)
        st = dict(name=sn, auto=auto, outState=out, outFrame=outf, vis=[], fc=[], events=[], callbacks=[])
        for k in s.children:
            kn, p = string(k.data)
            if k.id == 0x8020002: st['vis'].append((kn, struct.unpack_from('<I', k.data, p)[0]))
            elif k.id == 0x8020003:
                cyc, ncy, hold, lo, hi, spd = struct.unpack_from('<3I3f', k.data, p)
                st['fc'].append(dict(name=kn, cyclic=cyc, cycles=ncy, hold=hold, min=lo, max=hi, speed=spd))
            elif k.id == 0x8020004: st['events'].append((kn,) + struct.unpack_from('<2I', k.data, p))
            elif k.id == 0x8020005: st['callbacks'].append((kn,) + struct.unpack_from('<If', k.data, p))
        assert (len(st['vis']), len(st['fc']), len(st['events']), len(st['callbacks'])) == (nd, nf, ne, ncb), sn
        states.append(st)
    assert len(states) == nstates
    return dict(version=ver, name=name, factory=fac, states=states)

def print_stateprop(sp, ind='  '):
    print(f"{ind}StateProp '{sp['name']}' factory '{sp['factory']}' — {len(sp['states'])} состояний")
    for i, st in enumerate(sp['states']):
        auto = f"  АВТО -> s{st['outState']} через {st['outFrame']:g} с" if st['auto'] else ''
        print(f"{ind}  s{i} {st['name']}{auto}")
        vis = ' '.join(f"{n}{'+' if v else '-'}" for n, v in st['vis'])
        print(f"{ind}    видно: {vis}")
        for f in st['fc']:
            mode = 'цикл' if f['cyclic'] else ('держать' if f['hold'] else 'раз')
            if f['min'] == f['max']: mode = 'стоп'
            print(f"{ind}    кадры {f['name']}: {f['min']:g}..{f['max']:g} {mode}"
                  f"{' x%d' % f['cycles'] if f['cycles'] else ''}{' hold' if f['hold'] else ''} скорость {f['speed']:g}")
        for n, to, eid in st['events']: print(f"{ind}    событие {n}({eid}) -> s{to}")
        for n, cid, fr in st['callbacks']: print(f"{ind}    вызов {n}({cid}) через {fr:g} с")

# ---------------------------------------------------------------- составной рисунок / скелет / анимации
def mesh_info(g):
    """Geometry 0x10000 -> (имя, [(шейдер, вершин, индексов)])."""
    prims = []
    for pg in g.children:
        if pg.id != 0x10002: continue
        _, p = string(pg.data, 4); ptype, has, nv, ni, nm = struct.unpack_from('<5I', pg.data, p)
        prims.append((string(pg.data, 4)[0], nv, ni))
    return N(g), prims

def skeleton(sk):
    js = []
    for j in sk.children:
        if j.id != 0x4501: continue
        n, p = string(j.data); parent, = struct.unpack_from('<I', j.data, p)
        m = struct.unpack_from('<16f', j.data, p + 24)
        js.append(dict(name=n, parent=parent, t=m[12:15]))
    return js

def composite(cd):
    name, p = string(cd.data); skel, _ = string(cd.data, p)
    props, effects = [], []
    for l in cd.children:
        for e in l.children:
            if e.id == 0x4516:
                n, p = string(e.data); trans, joint = struct.unpack_from('<2I', e.data, p); props.append((n, joint, trans))
            elif e.id == 0x4518:
                n, p = string(e.data); joint, = struct.unpack_from('<I', e.data, p); effects.append((n, joint))
    return dict(name=name, skeleton=skel, props=props, effects=effects)

def animation(a):
    ver, = struct.unpack_from('<I', a.data); name, p = string(a.data, 4)
    typ = a.data[p:p + 4].rstrip(b'\0').decode('latin1'); nfr, rate, loop = struct.unpack_from('<2fI', a.data, p + 4)
    groups = []
    for gl in a.children:
        if gl.id != 0x121002: continue
        for g in gl.children:
            gn, q = string(g.data, 4); gid, nch = struct.unpack_from('<2I', g.data, q)
            chans = []
            for ch in g.children:
                param = ch.data[4:8].rstrip(b'\0').decode('latin1')
                off = 8                                          # version, param[4], numFrames
                if ch.id in (0x121102, 0x121103): off = 8 + 2 + 12   # Vector1/2Channel: mapping u16 + constants vec3
                if ch.id == 0x121108: off = 10                        # BoolChannel: startState u16, numFrames u32
                nk, = struct.unpack_from('<I', ch.data, off)
                chans.append(f'{ch.id & 0xFFF:03x}:{param}x{nk}')
            groups.append((gn, gid, chans))
    return dict(name=name, type=typ, frames=nfr, rate=rate, loop=loop, groups=groups)

def collision_summary(co):
    """CollisionObject 0x7010000 -> список листьев (box/cyl/sphere) + владелец-сустав."""
    out = []
    def rec(v):
        kids = [k for k in v.children if k.id == 0x7010001]
        if kids:
            for k in kids: rec(k)
            return
        owner, = struct.unpack_from('<I', v.data)
        for k in v.children:
            kind = {0x7010002: 'sphere', 0x7010003: 'cyl', 0x7010004: 'obox', 0x7010005: 'wall'}.get(k.id)
            if kind: out.append((kind, owner))
    for v in co.children:
        if v.id == 0x7010001: rec(v)
    return out

def wrapper_info(w):
    """AnimObjectWrapper 0x3F00010 (или BreakableObject / l0N_fx корень) -> всё, что нужно движку."""
    info = dict(skel=[], composite=None, meshes=[], anims=[], billboards=[], particles=[], physics=[], collision=[],
                fc=[], stateprop=None)
    for c in w.children:
        if c.id == 0x4500: info['skel'] = skeleton(c)
        elif c.id == 0x4512: info['composite'] = composite(c)
        elif c.id == 0x10000: info['meshes'].append(mesh_info(c))
        elif c.id == 0x121000: info['anims'].append(animation(c))
        elif c.id == 0x17002: info['billboards'].append(string(c.data, 4)[0])
        elif c.id in (0x15800, 0x15801): info['particles'].append((hex(c.id), string(c.data, 4)[0]))
        elif c.id == 0x7011000:
            n, p = string(c.data); info['physics'].append((n,) + struct.unpack_from('<3If', c.data, p)[2:])
        elif c.id == 0x7010000: info['collision'] = collision_summary(c)
        elif c.id == 0x121200: info['fc'].append(string(c.data, 4)[0])
        elif c.id == 0x8020000: info['stateprop'] = parse_stateprop(c)
    return info

def print_deep(info, ind='    '):
    sk = info['skel']
    if sk: print(f"{ind}скелет {len(sk)} суставов: " + ', '.join(f"{i}:{j['name']}<{j['parent'] if j['parent'] != i else '-'}" for i, j in enumerate(sk)))
    cd = info['composite']
    if cd:
        print(f"{ind}составной рисунок: " + ', '.join(f"{n}@{j}{'(alpha)' if t else ''}" for n, j, t in cd['props'])
              + (' | эффекты: ' + ', '.join(f'{n}@{j}' for n, j in cd['effects']) if cd['effects'] else ''))
    for n, prims in info['meshes']:
        print(f"{ind}меш {n}: " + ', '.join(f'{s} v{v} i{i}' for s, v, i in prims))
    for a in info['anims']:
        print(f"{ind}анимация {a['name']} [{a['type']}] {a['frames']:g} кадров @{a['rate']:g}/с "
              f"{'цикл' if a['loop'] else ''}: " + '; '.join(f"{g[0]}={','.join(g[2])}" for g in a['groups']))
    if info['billboards']: print(f"{ind}билборды: {', '.join(info['billboards'])}")
    if info['particles']: print(f"{ind}частицы: {', '.join(n for _, n in info['particles'])}")
    if info['collision']: print(f"{ind}коллизия: {', '.join(f'{k}@{o}' for k, o in info['collision'])}")

# ---------------------------------------------------------------- размещение и атрибуты
def instances(ent):
    """[(x, y, z) в координатах диска (z НЕ отзеркален)] из InstanceList 0x3000008 (вложенные матрицы перемножаются,
    вектор-строка: мир = лок @ родитель — как col_instances в psp_export.py)."""
    import numpy as np
    out = []
    def rec(c, m):
        if c.id == 0x120103:
            _, p = string(c.data); m = np.frombuffer(c.data, '<f4', 16, p + 4).reshape(4, 4).astype(float) @ m
        if c.id == 0x120107: out.append(tuple(round(float(v), 2) for v in m[3, :3]))
        for s in c.children: rec(s, m)
    for c in ent.children:
        if c.id == 0x3000008: rec(c, np.eye(4))
    return sorted(set(out))

def atc_table():
    c = next(x for x in walk(read(ART / 'atc/atc.p3d')) if x.id == 0x3000602)
    d = c.data; n, = struct.unpack_from('<I', d); p = 4; rows = []
    for _ in range(n):
        snd, p = string(d, p); part, p = string(d, p); brk, p = string(d, p)
        f = struct.unpack_from('<3f', d, p); p += 12
        rows.append(dict(sound=snd, particle=part, breakable=brk, f=f))
    return rows

def entity_attr(ent):
    eff = next((c for c in ent.children if c.id == 0x3000600), None)
    if not eff: return None
    cls, mat = struct.unpack_from('<II', eff.data); return dict(cls=cls, phys=mat, sound=string(eff.data, 8)[0])

KIND = {0x3f00002: 'DynaPhys', 0x3f0000a: 'InstStatPhys', 0x3f0000e: 'AnimDynaPhys'}

def scan_level(level=1, want=None):
    """-> список сущностей с файлами, атрибутами, экземплярами, стейтпропом."""
    rows = []
    for f in level_files(level):
        root = read(f)
        for ent in root.children:
            if ent.id not in KIND: continue
            name = N(ent)
            if want and not any(w in name for w in want): continue
            row = dict(file=f.stem, kind=KIND[ent.id], name=name, attr=entity_attr(ent), inst=instances(ent))
            if ent.id == 0x3f0000e:
                w = next((c for c in ent.children if c.id == 0x3f00010), None)
                row['info'] = wrapper_info(w) if w else None
            elif ent.id == 0x3f00002:
                row['info'] = dict(meshes=[mesh_info(g) for g in ent.children if g.id == 0x10000])
            rows.append(row)
    return rows

def breakables(files):
    out = []
    for f in files:
        if not f.exists(): continue
        for c in read(f).children:
            if c.id != 0x3001000: continue
            idx, cnt = struct.unpack_from('<2I', c.data)
            out.append(dict(file=f.stem, index=idx, count=cnt, info=wrapper_info(c)))
    return out

# ---------------------------------------------------------------- вывод
def cmd_states(names, level=1, deep=False, file=None):
    atc = atc_table()
    if file:
        root = read(GAME / file)
        for c in walk(root):
            if c.id == 0x8020000 and any(n in NV(c) for n in names):
                print(f'{file}:'); print_stateprop(parse_stateprop(c))
        return
    seen = set()
    for r in scan_level(level, names):
        info = r.get('info') or {}
        sp = info.get('stateprop')
        key = (r['name'], json.dumps(sp, sort_keys=True) if sp else '')
        a = r['attr']; atcr = atc[a['phys']] if a and a['phys'] < len(atc) else None
        print(f"{r['file']}: {r['kind']} {r['name']} x{len(r['inst'])}"
              + (f"  cls={a['cls']} phys={a['phys']} звук={a['sound']}" if a else '')
              + (f"  ATC[{a['phys']}]={atcr['sound']}/{atcr['particle']}/{atcr['breakable']} {atcr['f']}" if atcr else ''))
        if deep and info: print_deep(info)
        if sp and key not in seen: print_stateprop(sp); seen.add(key)
        elif sp: print('  (машина состояний та же, что выше)')

def cmd_inventory(level=1):
    atc = atc_table(); tot = {}
    for r in scan_level(level):
        a = r['attr'] or dict(cls='-', phys='-', sound='')
        sp = (r.get('info') or {}).get('stateprop')
        k = (r['kind'], r['name']); t = tot.setdefault(k, dict(n=0, files=[], a=a, sp=sp))
        t['n'] += len(r['inst']); t['files'].append(f"{r['file']}:{len(r['inst'])}")
    for (kind, name), t in sorted(tot.items()):
        a = t['a']; atcr = atc[a['phys']] if isinstance(a['phys'], int) and a['phys'] < len(atc) else None
        print(f"{kind:13s} {name:32s} {t['n']:4d}  cls={a['cls']} phys={a['phys']} {a['sound']:22s}"
              f"{(atcr['particle'] + '/' + atcr['breakable']) if atcr else '':34s} "
              f"{'SP' + str(len(t['sp']['states'])) if t['sp'] else ''}  {' '.join(t['files'])}")

def cmd_breakables(level=1, deep=True):
    seen = {}
    for b in breakables(level_files(level) + [ART / f'l0{level}_fx.p3d', GAME / f'art/missions/level0{level}/boxexpld.p3d']):
        cd = b['info']['composite']
        k = (b['index'], cd['name'] if cd else '')
        if k in seen: seen[k].append(b['file']); continue
        seen[k] = [b['file']]
        print(f"{b['file']}: Breakable index={b['index']} count={b['count']} '{cd['name'] if cd else '?'}'")
        if deep: print_deep(b['info'])
    for (i, n), fs in sorted(seen.items()): print(f"index {i:2d} {n:22s} в файлах: {' '.join(fs)}")

def main(a):
    level = 1
    if a and a[-1].isdigit(): level = int(a.pop())
    if a[:1] == ['--inventory']: return cmd_inventory(level)
    if a[:1] == ['--breakables']: return cmd_breakables(level)
    if a[:1] == ['--json']:
        rows = scan_level(level); br = breakables(level_files(level) + [ART / f'l0{level}_fx.p3d'])
        Path(a[1]).write_text(json.dumps(dict(entities=rows, breakables=br, atc=atc_table()), default=list, indent=1))
        return print('->', a[1])
    deep = '--deep' in a; a = [x for x in a if x != '--deep']
    if a[:1] == ['--file']: return cmd_states(a[2:], file=a[1])
    cmd_states(a or ['l1_crate', 'l1_vending', 'l1_phonestop', 'l1z6_powerbox', 'l1_shrubround'], level, deep)

if __name__ == '__main__':
    main(sys.argv[1:])
