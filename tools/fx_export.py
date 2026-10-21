"""Разбор родных систем частиц SHAR (Pure3D ParticleSystemFactory 0x15800 и контейнеры) -> build/fx_dump.json.

python tools/fx_export.py [--level N]          -> уровень N, по умолчанию 1 (l0N_fx, missgen, wrench, cards, машины, зоны lN*) + таблица
python tools/fx_export.py --all                -> все p3d диска
python tools/fx_export.py art/l01_fx.p3d ...   -> только эти файлы (пути от G = hit-and-run-web/source/game)
    --out FILE    куда писать JSON (по умолчанию build/fx_dump.json)
    --png DIR     дополнительно сохранить используемые текстуры частиц в PNG (только локально, не коммитить)
    --quiet       без таблицы

Формат (разобран по данным, опора: Pure3D/src/Pure3D/Chunks, donut/dev/Chunks.md; все поля little-endian):
  0x15800 ParticleSystemFactory: u32 ver, str name, f32 frameRate, u32 numAnimFrames, u32 numOLFrames,
          u16 cycleAnim, u16 enableSorting, u32 numEmitters; дети 0x1580B (u32 ver, u32 maxInstances), 0x15806 x N
  0x15806 SpriteEmitter: u32 ver, str name, str shader, 4cc angleMode (SPEC|RAND|MOAL), f32 angle,
          4cc texAnimMode (NONE|RAND|LIN), u32 numTexFrames, u32 texFrameRate; ребёнок 0x15805
  0x15805 BaseEmitter: u32 ver, str name, 4cc particleType (SPRT), 4cc generator (PNT|PLN|SPHR), u32 zTest,
          u32 zWrite, u32 fog, u32 maxParticles, u32 infiniteLife, f32 rotCohesion, f32 transCohesion;
          дети 0x15808 ParticleAnimation (по жизни частицы), 0x15809 EmitterAnimation (по времени системы),
          0x1580A GeneratorAnimation; каждая = u32 ver + 0x121000 Animation (ver, str name, 4cc type, f32 numFrames,
          f32 frameRate, u32 cyclic) -> 0x121002 -> 0x121001 (ver, str, u32 id, u32 nch) -> каналы
  каналы: u32 ver, 4cc param, u32 n, u16 frames[n], values[n]  (0x121100 f32, 0x121104 vec3, 0x121105 quat wxyz,
          0x121109 цвет u32 ARGB, 0x12110E i32); 0x121102/3 = ver, param, u16 mapping, vec3 const, n, frames, f32/vec2;
          ребёнок 0x121110: u32 ver, u32 interpolate (1 = линейно, 0 = ступенька)
  0x15801 ParticleSystem: u32 ver, str name, str factory
  0x3001001 InstParticleSystem: u32 type (номер системы, который вызывает код), u32 maxInstances + текстуры/шейдеры/фабрика
  0x3001000 BreakableObject: u32 type (номер обломка), u32 maxInstances + фабрика, скелет, анимация, BillboardQuadGroup
  0x3F0000C Anim (ambient): CompositeDrawable ссылается на фабрику -> положение из скелета (world)
"""
import sys, json, struct, math, argparse
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))
from p3d import read, walk, string

G = ROOT / 'hit-and-run-web/source/game'
def level_gags(level=1):
    """В5: сцены гэгов уровня (GagBegin в level.mfk, закомментированные — нет): их системы частиц (огонь барбекю, брызги
    колонки, искры плавильни…) играют окна EFX сцен из пакета collect-l1.shr (viewer/main.c collFrame -> fxBurst)."""
    import re
    out = []
    for line in (G / f'scripts/missions/level0{level}/level.mfk').read_text(errors='replace').splitlines():
        m = re.match(r'\s*GagBegin\("([^"]+)"\)', line)
        if m and f'art/nis/gags/{m.group(1)}' not in out and (G / 'art/nis/gags' / m.group(1)).exists(): out.append(f'art/nis/gags/{m.group(1)}')
    return out
def mission_effect_files(level):
    """Перепись миссий 04.10 (docs/МИССИИ_ПОЛНОТА_2026-10-04.md): файлы эффектов подбора миссий уровня. SetCollectibleEffect("<имя>")
    в скриптах уровня -> тот файл из их LoadP3DFile (art/missions/...), где лежит составной рисунок <имя>: L5 m1 и L6 m4 грузят
    level01/boxexpld (bonestorm_explosion — пыль crateDUST), L3 m6 — carfish, L6 m6 — lsrexpld. Раньше брался только
    level0N/boxexpld своего уровня (есть лишь у 1): системы частиц этих эффектов не попадали в fx.shr. Уровень 1 — тот же список"""
    import re
    d = G / f'scripts/missions/level0{level}'
    out = [x for x in [f'art/missions/level0{level}/boxexpld.p3d'] if (G / x).exists()]
    if not d.exists(): return out
    eff, loads = set(), []
    for f in sorted(d.glob('*.mfk')):
        if f.name.lower().startswith(('demo', 'e3', 'd1', 'leveli-d', 'level-d', 'ss')): continue   # не грузятся уровнем
        for line in f.read_text(errors='replace').splitlines():
            line = line.split('//')[0]
            m = re.search(r'SetCollectibleEffect\s*\(\s*"([^"]+)"', line)
            if m: eff.add(m.group(1).lower())
            m = re.search(r'LoadP3DFile\s*\(\s*"([^"]+)"', line)
            if m and m.group(1).replace('\\', '/').lower() not in loads: loads.append(m.group(1).replace('\\', '/').lower())
    for p in loads:
        if p in out or not p.startswith('art/missions/') or not (G / p).exists(): continue
        if {string(c.data)[0].lower() for c in read(G / p).children if c.id == 0x4512} & eff: out.append(p)
    return out
def default_files(level=1):
    """Файлы систем частиц уровня N: эффекты уровня l0N_fx, общие (missgen, wrench, cards), город l<N>_terra, взрыв ящика
    миссий level0N/boxexpld (если он есть у уровня; на диске — только у 1), искры Scrooby, районы и зоны l<N>r*/z*, машины,
    сцены гэгов level.mfk. Уровень 1 — прежний список DEFAULT до строки."""
    return [f'art/l0{level}_fx.p3d', 'art/missions/generic/missgen.p3d', 'art/wrench.p3d', 'art/cards.p3d', f'art/l{level}_terra.p3d'] + \
           mission_effect_files(level) + \
           ['art/frontend/scrooby/resource/pure3d/sparkles.p3d'] + \
           sorted(str(p.relative_to(G)) for p in (G / 'art').glob(f'l{level}[rz]*.p3d')) + \
           sorted(str(p.relative_to(G)) for p in (G / 'art/cars').glob('*.p3d')) + level_gags(level)
DEFAULT = default_files(1)
PARTICLE_SLOTS_MFK = 'scripts/missions/level0{level}/leveli.mfk'

u32 = lambda b, p: struct.unpack_from('<I', b, p)[0]
f32 = lambda b, p: struct.unpack_from('<f', b, p)[0]
cc = lambda b, p: b[p:p + 4].rstrip(b'\0').decode('latin1')
r6 = lambda x: round(x, 6)

def argb(c): return '#%02x%02x%02x%02x' % ((c >> 24) & 255, (c >> 16) & 255, (c >> 8) & 255, c & 255)

# ---------- каналы анимации ----------
def channel(c):
    b = c.data; param = cc(b, 4); interp = None
    for k in c.children:
        if k.id == 0x121110: interp = u32(k.data, 4)
    if len(b) < 12: return param, {'kind': 'empty', 'frames': [], 'values': [], 'interp': interp}
    if c.id in (0x121102, 0x121103):     # Vector1DOF / Vector2DOF: mapping + константы
        mapping = struct.unpack_from('<H', b, 8)[0]; const = struct.unpack_from('<3f', b, 10); p = 22
        n = u32(b, p); p += 4; frames = list(struct.unpack_from(f'<{n}H', b, p)); p += 2 * n
        dim = 1 if c.id == 0x121102 else 2
        vals = [list(struct.unpack_from(f'<{dim}f', b, p + 4 * dim * i)) for i in range(n)]
        vals = [[r6(x) for x in v] for v in vals]
        return param, {'kind': f'vec{dim}dof', 'mapping': mapping, 'const': [r6(x) for x in const],
                       'frames': frames, 'values': vals, 'interp': interp}
    if c.id == 0x121108:                 # BoolChannel: u16 начальное состояние, u32 n, u16 кадры переключения
        start = struct.unpack_from('<H', b, 8)[0]; n = u32(b, 10)
        return param, {'kind': 'bool', 'frames': list(struct.unpack_from(f'<{n}H', b, 14)),
                       'values': [bool(start ^ (i & 1)) for i in range(1, n + 1)], 'start': start, 'interp': 0}
    n = u32(b, 8); p = 12; frames = list(struct.unpack_from(f'<{n}H', b, p)); p += 2 * n
    if c.id == 0x121100: kind, vals = 'f', [r6(x) for x in struct.unpack_from(f'<{n}f', b, p)]
    elif c.id == 0x121101: kind, vals = 'vec2', [[r6(x) for x in struct.unpack_from('<2f', b, p + 8 * i)] for i in range(n)]
    elif c.id == 0x121104: kind, vals = 'vec3', [[r6(x) for x in struct.unpack_from('<3f', b, p + 12 * i)] for i in range(n)]
    elif c.id == 0x121105: kind, vals = 'quat', [[r6(x) for x in struct.unpack_from('<4f', b, p + 16 * i)] for i in range(n)]
    elif c.id == 0x121111:
        kind, vals = 'cquat', [[r6(x / 32767) for x in struct.unpack_from('<4h', b, p + 8 * i)] for i in range(n)]
    elif c.id == 0x121109: kind, vals = 'argb', [argb(x) for x in struct.unpack_from(f'<{n}I', b, p)]
    elif c.id == 0x12110E: kind, vals = 'i', list(struct.unpack_from(f'<{n}i', b, p))
    else: kind, vals = f'raw_{c.id:x}', b[p:].hex()
    return param, {'kind': kind, 'frames': frames, 'values': vals, 'interp': interp}

def compact(ch):
    """Один ключ -> просто значение; иначе {'keys': [[кадр, значение], ...], 'interp': ...}."""
    if isinstance(ch['values'], list) and len(ch['values']) == 1 and ch['kind'] not in ('vec1dof', 'vec2dof'):
        return ch['values'][0]
    out = {'keys': [[f, v] for f, v in zip(ch['frames'], ch['values'])], 'interp': ch['interp']}
    if 'const' in ch: out.update(mapping=ch['mapping'], const=ch['const'])
    return out

def animation(c):
    """0x15808/9/A -> (meta, {param: value})."""
    a = next((k for k in c.children if k.id == 0x121000), None)
    if a is None: return None, {}
    return anim_header(a), anim_channels(a)

def anim_header(a):
    b = a.data; name, p = string(b, 4)
    return {'name': name, 'type': cc(b, p), 'numFrames': r6(f32(b, p + 4)), 'fps': r6(f32(b, p + 8)),
            'cyclic': u32(b, p + 12)}

def anim_channels(a):
    out = {}
    for k in walk(a):
        if 0x121100 <= k.id <= 0x121111 and k.id != 0x121110:
            param, ch = channel(k); out[param] = compact(ch)
    return out

# ---------- текстуры и шейдеры ----------
def texture(c):
    b = c.data; name, p = string(b, 0)
    t = dict(zip(('ver', 'w', 'h', 'bpp', 'alphaDepth', 'mips', 'texType', 'usage', 'priority'),
                 struct.unpack_from('<9I', b, p)))
    return name, {'w': t['w'], 'h': t['h'], 'bpp': t['bpp'], 'alphaDepth': t['alphaDepth'], 'mips': t['mips']}

BLEND = {0: 'none', 1: 'alpha', 2: 'add', 3: 'subtract', 4: 'modulate', 5: 'modulate2', 6: 'additive_modulate'}

def shader(c):
    name, _ = string(c.data, 0); s = {}
    for k in c.children:
        key = cc(k.data, 0)
        if k.id == 0x11002: s[key] = string(k.data, 4)[0]
        elif k.id == 0x11003: s[key] = u32(k.data, 4)
        elif k.id == 0x11004: s[key] = r6(f32(k.data, 4))
        elif k.id == 0x11005: s[key] = argb(u32(k.data, 4))
    return name, s

# ---------- фабрика частиц ----------
def emitter(c, shaders, textures):
    b = c.data; name, p = string(b, 4); sh, p = string(b, p)
    e = {'name': name, 'shader': sh, 'angleMode': cc(b, p), 'angle': r6(f32(b, p + 4)),
         'texAnimMode': cc(b, p + 8), 'numTexFrames': u32(b, p + 12), 'texFrameRate': u32(b, p + 16)}
    s = shaders.get(sh, {})
    tex = s.get('TEX'); e['texture'] = tex
    e['blend'] = BLEND.get(s.get('BLMD', 0), s.get('BLMD')); e['shaderParams'] = s
    if tex in textures:
        t = textures[tex]; n = max(1, e['numTexFrames'])
        cols = max(1, min(n, t['w'] // max(1, t['h']))) if t['w'] >= t['h'] else 1
        rows = (n + cols - 1) // cols
        e['texInfo'] = dict(t, frameGrid=[cols, rows], frameSize=[t['w'] // cols, t['h'] // rows])
    base = next(k for k in c.children if k.id == 0x15805)
    bb = base.data; _, q = string(bb, 4)
    e.update(particleType=cc(bb, q), generator=cc(bb, q + 4), zTest=u32(bb, q + 8), zWrite=u32(bb, q + 12),
             fog=u32(bb, q + 16), maxParticles=u32(bb, q + 20), infiniteLife=u32(bb, q + 24),
             rotCohesion=r6(f32(bb, q + 28)), transCohesion=r6(f32(bb, q + 32)))
    for k in base.children:
        meta, ch = animation(k)
        key = {0x15808: 'overLife', 0x15809: 'emit', 0x1580A: 'gen'}.get(k.id)
        if key: e[key] = ch; e[key + 'Anim'] = meta
    return e

def factory(c, shaders, textures):
    b = c.data; name, p = string(b, 4)
    f = {'name': name, 'fps': r6(f32(b, p)), 'numAnimFrames': u32(b, p + 4), 'numOLFrames': u32(b, p + 8),
         'cycleAnim': struct.unpack_from('<H', b, p + 12)[0], 'enableSorting': struct.unpack_from('<H', b, p + 14)[0],
         'numEmitters': u32(b, p + 16), 'maxInstances': None, 'emitters': []}
    for k in c.children:
        if k.id == 0x1580B: f['maxInstances'] = u32(k.data, 4)
        elif k.id == 0x15806: f['emitters'].append(emitter(k, shaders, textures))
    f['duration_s'] = r6(f['numAnimFrames'] / f['fps']) if f['fps'] else None
    return f

# ---------- биллборды (вспышки взрыва и т.п.) ----------
def quad_group(c):
    b = c.data; name, p = string(b, 4); sh, p = string(b, p)
    g = {'name': name, 'shader': sh, 'zTest': u32(b, p), 'zWrite': u32(b, p + 4), 'fog': u32(b, p + 8), 'quads': []}
    for k in c.children:
        if k.id != 0x17001: continue
        q = k.data; qn, r = string(q, 4)
        tr = struct.unpack_from('<3f', q, r + 4); col = u32(q, r + 16); w, h, dist = struct.unpack_from('<3f', q, r + 52)
        quad = {'name': qn, 'mode': cc(q, r), 'pos': [r6(x) for x in tr], 'colour': argb(col),
                'w': r6(w), 'h': r6(h), 'distance': r6(dist)}
        for d in k.children:
            if d.id == 0x17003:
                rot = struct.unpack_from('<4f', d.data, 4); quad['cutOff'] = cc(d.data, 20)
                quad['rot'] = [r6(x) for x in rot]
            if d.id == 0x17004: quad['perspective'] = u32(d.data, 4)
        g['quads'].append(quad)
    return g

def skeleton_world(sk, joint):
    """Мировая позиция сустава joint (цепочка родителей, строки-векторы Pure3D: M = local * parent)."""
    js = []
    for k in sk.children:
        if k.id != 0x4501: continue
        b = k.data; _, p = string(b, 0); parent = u32(b, p)
        m = struct.unpack_from('<16f', b, p + 24); js.append((parent, m))
    if not js: return None
    def mul(a, b_): return [sum(a[r * 4 + i] * b_[i * 4 + c] for i in range(4)) for r in range(4) for c in range(4)]
    j = min(joint, len(js) - 1); m = list(js[j][1]); seen = 0
    while j != js[j][0] and seen < 64 and j > 0:
        j = js[j][0]; m = mul(m, list(js[j][1])); seen += 1
    return [r6(m[12]), r6(m[13]), r6(m[14])]

# ---------- ATC ----------
def atc_table():
    r = read(G / 'art/atc/atc.p3d')
    c = next(k for k in walk(r) if k.id == 0x3000602)
    b = c.data; n = u32(b, 0); p = 4; rows = []
    for i in range(n):
        snd, p = string(b, p); part, p = string(b, p); brk, p = string(b, p)
        a, m, e = struct.unpack_from('<3f', b, p); p += 12
        rows.append({'row': i, 'sound': snd, 'particle': part, 'breakable': brk,
                     'f0': r6(a), 'mass': r6(m), 'f2': r6(e)})
    return rows

def particle_slots(level=1):
    out = {}
    f = G / PARTICLE_SLOTS_MFK.format(level=level)
    if not f.exists(): return out
    for line in f.read_text('latin1').splitlines():
        s = line.strip()
        if s.startswith('SetParticleTexture'):
            a = s[s.index('(') + 1:s.index(')')].split(',')
            out[int(a[0])] = {'texture': a[1].strip().strip('"'), 'comment': s.split('//', 1)[1].strip() if '//' in s else ''}
    return out

# ---------- файл ----------
def parse_file(rel):
    r = read(G / rel); textures, shaders = {}, {}
    for c in walk(r):
        if c.id == 0x19000: n, t = texture(c); textures[n] = t
        elif c.id == 0x11000: n, s = shader(c); shaders[n] = s
    systems, breakables, placements = [], [], []
    skels = {string(c.data, 0)[0]: c for c in walk(r) if c.id == 0x4500}
    bbs = {}
    for c in walk(r):
        if c.id == 0x17002:
            g = quad_group(c); sh = shaders.get(g['shader'], {}); bbs[g['name']] = g
            g['texture'] = sh.get('TEX'); g['blend'] = BLEND.get(sh.get('BLMD', 0), sh.get('BLMD'))
    def bb_refs(c):   # биллборды, на которые ссылается CompositeDrawable внутри c (сами 0x17002 могут лежать в корне файла)
        names = [string(k.data, 0)[0] for k in walk(c) if k.id in (0x4516, 0x4518)]
        return [bbs[n] for n in dict.fromkeys(names) if n in bbs]

    def local(c):   # текстуры/шейдеры контейнера перекрывают файловые (одно имя smoke3.bmp бывает 32 и 64 px)
        t, sh = dict(textures), dict(shaders)
        for k in walk(c):
            if k.id == 0x19000: n, v = texture(k); t[n] = v
            elif k.id == 0x11000: n, v = shader(k); sh[n] = v
        return t, sh
    scope = [(textures, shaders)]

    def rec(c, ctx):
        if c.id in (0x3001001, 0x3001000): scope.append(local(c))
        if c.id == 0x3001001:
            ctx = {'kind': 'inst', 'type': u32(c.data, 0), 'maxInstances': u32(c.data, 4)}
        elif c.id == 0x3001000:
            ctx = {'kind': 'breakable', 'type': u32(c.data, 0), 'maxInstances': u32(c.data, 4)}
            br = dict(ctx, file=rel, factories=[], billboards=[], anims=[])
            for k in c.children:
                if k.id == 0x15800: br['factories'].append(string(k.data, 4)[0])
                elif k.id == 0x121000: br['anims'].append(dict(anim_header(k), channels=anim_channels(k)))
                elif k.id == 0x20000: br['animObject'] = string(k.data, 4)[0]
            br['billboards'] = bb_refs(c)
            sk = next((k for k in c.children if k.id == 0x4500), None)
            if sk is not None: br['skeleton'] = string(sk.data, 0)[0]
            breakables.append(br)
        if c.id == 0x15800:
            f = factory(c, scope[-1][1], scope[-1][0]); f['file'] = rel; f['context'] = ctx or {'kind': 'standalone'}
            systems.append(f); return
        for k in c.children: rec(k, ctx)
        if c.id in (0x3001001, 0x3001000): scope.pop()
    SKIP = {0x15800, 0x15801, 0x19000, 0x11000, 0x3001001, 0x3001000, 0x4500, 0x10000, 0x7000}
    for c in r.children:
        rec(c, None)
        if c.id in SKIP: continue
        # кто использует систему: Anim 0x3F0000C (фон: пар, огонь), AnimDynaPhys 0x3F0000E (пропы со стейт-машиной) и т.п.
        ent = string(c.data, 0)[0] if c.data[:1] and 0 < c.data[0] < 64 else ''
        atc = next(((u32(k.data, 0), u32(k.data, 4), string(k.data, 8)[0]) for k in walk(c) if k.id == 0x3000600), None)
        for k in walk(c):
            if k.id != 0x4512: continue
            skn2 = string(k.data, string(k.data, 0)[1])[0]   # CompositeDrawable: name, skeleton
            sk = skels.get(skn2) or next((x for x in walk(c) if x.id == 0x4500 and string(x.data, 0)[0] == skn2), None)
            for pr in walk(k):
                if pr.id != 0x4518: continue
                pn, q = string(pr.data, 0); joint = u32(pr.data, q + 4)
                u = {'container': f'{c.id:x}', 'entity': ent, 'joint': joint, 'system': pn, 'file': rel,
                     'pos': skeleton_world(sk, joint) if sk is not None else None}
                if atc: u.update(propClass=atc[0], physProp=atc[1], sound=atc[2])
                states = []
                for st in walk(c):
                    if st.id != 0x8020001: continue
                    stn = string(st.data, 0)[0]; vis = None; fc = None
                    for d in st.children:
                        if d.id == 0x8020002 and string(d.data, 0)[0] == pn: vis = u32(d.data, string(d.data, 0)[1])
                        if d.id == 0x8020003 and string(d.data, 0)[0] == 'EFX_' + pn:
                            q2 = string(d.data, 0)[1]
                            cyc, ncyc, hold = struct.unpack_from('<3I', d.data, q2)
                            mn, mx, spd = struct.unpack_from('<3f', d.data, q2 + 12)
                            fc = {'cyclic': cyc, 'numCycles': ncyc, 'hold': hold, 'min': r6(mn), 'max': r6(mx), 'speed': r6(spd)}
                    if vis is not None or fc: states.append({'state': stn, 'visible': vis, 'efx': fc})
                if states: u['states'] = states
                bb = bb_refs(c)
                if bb: u['billboards'] = bb
                placements.append(u)
    names = {x['name'] for x in systems}
    placements = [p for p in placements if p['system'] in names]
    for x in systems:
        x['users'] = [p for p in placements if p['system'] == x['name']]
    return systems, breakables, textures

def tex_index(names):
    """Где лежит каждая нужная текстура (первый файл по порядку) — для глобальных слотов частиц."""
    want = {n.lower() for n in names}; found = {}
    order = [G / 'art/missions/generic/missgen.p3d', G / 'art/l01_fx.p3d', G / 'art/cars/common.p3d',
             G / 'art/wrench.p3d', G / 'art/cards.p3d', G / 'art/frontend/scrooby/resource/pure3d/sparkles.p3d']
    order += sorted((G / 'art').rglob('*.p3d'))
    for f in order:
        if not want - set(found): break
        try: r = read(f)
        except Exception: continue
        for c in walk(r):
            if c.id == 0x19000:
                n, t = texture(c)
                if n.lower() in want and n.lower() not in found:
                    found[n.lower()] = dict(t, name=n, file=str(f.relative_to(G)))
    return found

def dump_png(rel_files, names, outdir):
    from textures import decode_image
    outdir = Path(outdir); outdir.mkdir(parents=True, exist_ok=True); done = set()
    for rel in rel_files:
        r = read(G / rel)
        for c in walk(r):
            if c.id != 0x19000: continue
            n = string(c.data, 0)[0]
            if n not in names: continue
            img = next(v for v in c.children if v.id == 0x19001)
            raw = next(v for v in img.children if v.id == 0x19002).data[4:]
            q = string(img.data, 0)[1]; w, h = u32(img.data, q + 4), u32(img.data, q + 8)
            key = (n, w, h)
            if key in done: continue
            out = outdir / (Path(n).stem + '.png')
            if any(d[0] == n for d in done): out = outdir / f'{Path(n).stem}_{w}x{h}.png'
            try: decode_image(raw).save(out); done.add(key)
            except Exception as e: print('png', n, e)
    return done

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('files', nargs='*'); ap.add_argument('--all', action='store_true')
    ap.add_argument('--out', default=str(ROOT / 'build/fx_dump.json')); ap.add_argument('--png')
    ap.add_argument('--quiet', action='store_true'); ap.add_argument('--level', type=int, default=1)
    a = ap.parse_args()
    files = a.files or (sorted(str(p.relative_to(G)) for p in (G / 'art').rglob('*.p3d')) if a.all else default_files(a.level))
    systems, breakables = [], []; used = set()
    for rel in files:
        try: s, b, _ = parse_file(rel)
        except Exception as e: print('skip', rel, e); continue
        systems += s; breakables += b
    for s in systems:
        for e in s['emitters']:
            if e.get('texture'): used.add(e['texture'])
    # текстура может лежать в другом файле (BurstShape берёт scratch2.bmp из missgen.p3d)
    miss = {e['texture'] for x in systems for e in x['emitters'] if e.get('texture') and 'texInfo' not in e}
    gidx = tex_index(miss) if miss else {}
    for x in systems:
        for e in x['emitters']:
            t = gidx.get((e.get('texture') or '').lower())
            if t and 'texInfo' not in e:
                n = max(1, e['numTexFrames']); cols = max(1, min(n, t['w'] // max(1, t['h']))) if t['w'] >= t['h'] else 1
                rows = (n + cols - 1) // cols
                e['texInfo'] = dict(t, frameGrid=[cols, rows], frameSize=[t['w'] // cols, t['h'] // rows])
    slots = particle_slots(a.level)
    idx = tex_index([v['texture'] for v in slots.values()])
    for k, v in slots.items(): v['where'] = idx.get(v['texture'].lower())
    atc = atc_table()
    out = {'source': 'SHAR PS2 PAL disc, parsed by tools/fx_export.py', 'files': files,
           'units': {'emitter.LIF': 'frames @ factory.fps (particle life)', 'emitter.RAT': 'particles per frame',
                     'overLife keys': 'frame 0..numOLFrames-1 = normalized particle age 0..1',
                     'emitter/generator keys': 'frame of system timeline 0..numAnimFrames',
                     'ALP/ALOL': '0..255', 'angles': 'radians (RDVA degrees)'},
           'particleSlots': slots, 'atc': atc, 'breakables': breakables, 'systems': systems}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, indent=1))
    if a.png: print('png:', len(dump_png(files, used | {v['texture'] for v in slots.values()}, a.png)))
    if a.quiet: return
    print(f'{len(systems)} систем, {sum(len(s["emitters"]) for s in systems)} эмиттеров, {len(breakables)} обломков -> {a.out}')
    print(f'{"файл":22} {"ctx":10} {"система":26} {"эмиттер":22} {"текстура":14} {"blend":5} {"gen":4} {"max":>4} {"rate":>6} {"life":>6} {"spd":>6} {"grav":>7} {"size":>5}')
    for s in systems:
        ctx = s['context']; cs = ctx['kind'][:5] + (f":{ctx['type']}" if 'type' in ctx else '')
        for e in s['emitters']:
            em = e.get('emit', {})
            def v(k):
                x = em.get(k); return x if not isinstance(x, dict) else max(kv[1] for kv in x['keys'])
            print(f'{Path(s["file"]).name[:22]:22} {cs:10} {s["name"][:26]:26} {e["name"][:22]:22} {str(e["texture"])[:14]:14} '
                  f'{str(e["blend"])[:5]:5} {e["generator"]:4} {e["maxParticles"]:4} {v("RAT") or 0:6.2f} {v("LIF") or 0:6.1f} '
                  f'{v("SPD") or 0:6.3f} {v("GRA") or 0:7.4f} {v("SIZ") or 0:5.2f}')

if __name__ == '__main__':
    main()
