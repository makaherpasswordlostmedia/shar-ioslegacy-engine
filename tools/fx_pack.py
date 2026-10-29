"""Родные частицы SHAR для PSP: build/fx.shr (формат FXP1), читает viewer/fx.c.

python tools/fx_pack.py [--level N] [--out build/fx.shr] [--png DIR]

Берёт системы частиц уровня N (tools/fx_export.default_files: l0N_fx, зоны lNr*/lNz*, lN_terra, missgen, wrench, cards, boxexpld),
обломки (BreakableObject, несколько фабрик + биллборды взрыва), фоновые системы (пар, факелы, шины) с мировыми
позициями, плюс «кодовые» эффекты (искры spark4, пыль/сколы cloud) и текстуры блеска (scratch2, glowsolid, glow64,
bluestarglow, glow2, halo). Текстуры — родные индексы и палитры P3DI без переквантования (T4/T8 + CLUT 8888).
Координаты зеркалятся по z, как у level.shr (tools/psp_export.py): off.z -> -z, кватернион (w,x,y,z) -> (w,-x,-y,z).

Формат FXP1 (little-endian, все смещения от начала файла, всё выровнено на 16):
  Header 64 B : 'FXP1', u32 ver=1, nTex, nSys, nEmit, nKey, nBB, nAmb, nBrk, offTex, offSys, offEmit, offKey, offBB,
                offAmb, offBrk
  FxTex  32 B : u16 w, h, bufw; u8 psm (4|8), u8 swz; u32 offPix, offClut (CLUT 8888 ABGR, 16 или 256 записей);
                char name[16] (обрезано до 15)
  FxSys  56 B : char name[32]; u16 firstEmit, nEmit, nFrames; u8 oneShot, maxInst; f32 fps; i16 instType, brkType;
                u16 firstBB, nBB; u32 pad
  FxEmit 468 B: EMIT_FMT (u16 tex; u8 cols, rows, nFr, texMode, blend, angleMode, gen, flags (1 COOL, 2 ALOL), pad2; f32 texRate, angle,
                aspect, genW, genH, spreadH, spreadV; u16 key[NP][2]; u32 ol[NOL] (ABGR: COOL, альфа=ALOL);
                f32 olSize[NOL], olSpeed[NOL], olSpin[NOL], olWeight[NOL])
                единицы как в данных: RAT шт/кадр, LIF кадры, SPD м/кадр (рантайм ×FX_VEL), GRA·WGT м/кадр², SPI рад/кадр
  FxKey   8 B : u16 frame, u16 pad, f32 value  (линейно между ключами)
  FxBB   32 B : u16 tex; u8 blend, mode (0 лежит по ROT, 1 к камере); f32 dist; f32 rot[4] (w,x,y,z); u16 nFrames, pad;
                u32 offLut -> nFrames × (f32 w, f32 h, u32 ABGR)
  FxAmb  16 B : u16 sys, u16 pad, f32 x, y, z
  FxBrk  16 B : i16 type, u16 nSys, u16 sys[4], u16 firstBB, nBB
"""
import sys, struct, json, hashlib, argparse, math
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools')); sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))
import numpy as np
from p3d import read, walk, string
import fx_export as fe

G = fe.G
def level_files(level=1): return [f for f in fe.default_files(level) if not f.startswith('art/cars/') and 'frontend' not in f]
FILES = level_files(1)
PARAMS = ['RAT', 'SPD', 'SPDV', 'LIF', 'LIFV', 'SIZ', 'SIZV', 'SPI', 'SPIV', 'WGT', 'WGTV', 'GRA', 'DRA', 'ALP', 'ALPV',
          'CLRR', 'CLRG', 'CLRB', 'CLRV', 'NUM', 'TX', 'TY', 'TZ', 'QW', 'QX', 'QY', 'QZ']
NP, NOL = len(PARAMS), 16
DEFAULTS = {'RAT': 0, 'DRA': 1, 'ALP': 255, 'CLRR': 255, 'CLRG': 255, 'CLRB': 255, 'WGT': 1, 'NUM': 0, 'QW': 1}
EMIT_FMT = '<H8B2x7f' + f'{NP * 2}H' + f'{NOL}I' + f'{NOL * 4}f'
EMIT_SIZE = struct.calcsize(EMIT_FMT)
EXTRA_TEX = ['scratch2.bmp', 'scratch2_sm.bmp', 'glowsolid.bmp', 'glow64.bmp', 'bluestarglow.bmp', 'glow2.bmp',
             'halo.bmp', 'spark4.bmp', 'cloud.tga', 'scratch2_blue.bmp', 'scratch2_red.bmp', 'glow_star.bmp']
BLEND = {'alpha': 0, 'none': 0, 'add': 1, 'subtract': 2}
# правка Роба 249: текстура следов шин — шейдер skid_m (art/l0N_fx.p3d, 16×16, альфа 0,81–0,89), её берёт viewer/skid.c по имени.
# У оригинала по поверхности (SLES_518.97 0x205218): трава (1) skidg.bmp, грунт (7) skidd.bmp, иначе skid.bmp; у порта типов поверхности
# в COL1 нет — только дорога. Слово Роба 03.10: только уровень 1 (пакеты уровней 2–7 не меняются)
SKID_TEX = {1: ['skid.bmp']}

# ---------- текстуры: индексы + палитра как есть ----------
def p3di(c):
    img = next(v for v in c.children if v.id == 0x19001)
    raw = next(v for v in img.children if v.id == 0x19002).data[4:]
    if raw[:4] == b'\x89PNG':   # часть текстур на диске лежит индексным PNG — берём его индексы и палитру как есть
        import io
        from PIL import Image
        im = Image.open(io.BytesIO(raw))
        if im.mode != 'P': im = im.convert('RGBA').quantize(256)
        idx = np.array(im, np.uint8); h, w = idx.shape
        pr = im.getpalette() or [0] * 768; npal = len(pr) // 3
        pal = np.zeros((256, 4), np.uint8); pal[:npal, :3] = np.array(pr, np.uint8).reshape(-1, 3); pal[:, 3] = 255
        tr = im.info.get('transparency')
        if isinstance(tr, (bytes, bytearray)): pal[:len(tr), 3] = np.frombuffer(tr, np.uint8)
        elif isinstance(tr, int): pal[tr, 3] = 0
        if idx.max() < 16: return w, h, 4, idx, pal[:16]
        return w, h, 8, idx, pal
    assert raw[:4] == b'P3DI', raw[:4]
    fmt, w, h, bpp, psz, pxs = struct.unpack_from('<6I', raw, 4)
    pal = np.frombuffer(raw[28:28 + psz], np.uint8).reshape(-1, 4).copy()
    pal[:, 3] = np.minimum(pal[:, 3].astype(np.uint16) * 255 // 128, 255)
    px = np.frombuffer(raw[28 + psz:28 + psz + pxs], np.uint8)
    if bpp == 8:
        o = np.arange(256); o = (o & ~24) | ((o & 8) << 1) | ((o & 16) >> 1)
        pal = pal[o]; idx = px[:w * h].reshape(h, w)
    elif bpp == 4:
        idx = np.stack([px & 15, px >> 4], 1).flatten()[:w * h].reshape(h, w)
        pal = pal[:16]
    else:
        raise ValueError(f'bpp {bpp}')
    return w, h, bpp, idx.astype(np.uint8), pal

class TexBank:
    def __init__(self):
        self.files = {}; self.list = []; self.key = {}
    def file_tex(self, rel):
        if rel not in self.files:
            m = {}
            for c in walk(read(G / rel)):
                if c.id == 0x19000:
                    n = string(c.data, 0)[0]
                    try: m.setdefault(n.lower(), []).append(p3di(c))
                    except Exception as e: print('tex skip', rel, n, e)
            self.files[rel] = m
        return self.files[rel]
    def get(self, name, rel_order, w=None, h=None):
        for rel in rel_order:
            for t in self.file_tex(rel).get(name.lower(), []):
                if w and (t[0], t[1]) != (w, h): continue
                return self.add(name, t)
        return None
    def add(self, name, t):
        w, h, bpp, idx, pal = t
        k = hashlib.md5(idx.tobytes() + pal.tobytes() + bytes([bpp])).hexdigest()
        if k not in self.key:
            self.key[k] = len(self.list); self.list.append((name, t))
        return self.key[k]

def swizzle(buf, wbytes, h):
    """Swizzle PSP: блоки 16 байт × 8 строк."""
    out = bytearray(len(buf)); o = 0
    for by in range(0, h, 8):
        for bx in range(0, wbytes, 16):
            for r in range(8):
                s = (by + r) * wbytes + bx; out[o:o + 16] = buf[s:s + 16]; o += 16
    return bytes(out)

def tex_blob(t):
    w, h, bpp, idx, pal = t
    if bpp == 4:
        bufw = max(w, 32); a = np.zeros((h, bufw), np.uint8); a[:, :w] = idx
        pix = (a[:, 0::2] | (a[:, 1::2] << 4)).astype(np.uint8).tobytes(); wb = bufw // 2
    else:
        bufw = max(w, 16); a = np.zeros((h, bufw), np.uint8); a[:, :w] = idx; pix = a.tobytes(); wb = bufw
    swz = 1 if (wb % 16 == 0 and h % 8 == 0) else 0
    if swz: pix = swizzle(pix, wb, h)
    clut = pal.astype(np.uint8).tobytes()   # RGBA байты = ABGR u32 на PSP
    return bufw, swz, pix, clut

# ---------- кривые ----------
def keys_of(v, comp=None):
    """Значение канала -> список (кадр, float). comp: индекс компоненты вектора / кватерниона."""
    if isinstance(v, dict):
        out = []
        for f, x in v['keys']:
            if comp is not None:
                if 'mapping' in v:   # 1DOF: меняется компонента mapping; 2DOF: mapping постоянная, две другие по порядку
                    full = list(v['const'])
                    if len(x) == 1: full[v['mapping']] = x[0]
                    else:
                        free = [i for i in range(3) if i != v['mapping']]; full[free[0]], full[free[1]] = x
                    x = full[comp]
                else: x = x[comp]
            out.append((int(f), float(x)))
        return out
    if comp is not None: v = v[comp]
    return [(0, float(v))]

def colour_keys(v, shift):
    def c(s): return int(s[1:], 16)
    if isinstance(v, dict): return [(int(f), float((c(x) >> shift) & 255)) for f, x in v['keys']]
    return [(0, float((c(v) >> shift) & 255))]

def sample(keys, u):
    if not keys: return None
    if u <= keys[0][0]: return keys[0][1]
    for (f0, a), (f1, b) in zip(keys, keys[1:]):
        if u <= f1: return a + (b - a) * (u - f0) / max(1e-9, f1 - f0)
    return keys[-1][1]

def ol_lut(v, nol, default, colour_shift=None):
    if v is None: return [default] * NOL
    ks = colour_keys(v, colour_shift) if colour_shift is not None else keys_of(v)
    return [sample(ks, i * (nol - 1) / (NOL - 1)) for i in range(NOL)]

# ---------- упаковка ----------
def emitter_rec(e, sysd, tex_id, keys):
    em, ol, gen = e.get('emit', {}), e.get('overLife', {}), e.get('gen', {})
    ch = {}
    for p in ('RAT', 'SPD', 'SPDV', 'LIF', 'LIFV', 'SIZ', 'SIZV', 'SPI', 'SPIV', 'WGT', 'WGTV', 'GRA', 'DRA', 'ALP', 'ALPV',
              'CLRV', 'NUM'):
        if p in em: ch[p] = keys_of(em[p])
    if 'CLR' in em:
        ch['CLRR'], ch['CLRG'], ch['CLRB'] = (colour_keys(em['CLR'], s) for s in (16, 8, 0))
    if 'TRA' in em:
        ch['TX'], ch['TY'], ch['TZ'] = (keys_of(em['TRA'], i) for i in range(3))
        ch['TZ'] = [(f, -x) for f, x in ch['TZ']]
    if 'ROT' in em:
        q = [keys_of(em['ROT'], i) for i in range(4)]
        ch['QW'], ch['QX'], ch['QY'], ch['QZ'] = q[0], [(f, -x) for f, x in q[1]], [(f, -x) for f, x in q[2]], q[3]
    kidx = []
    for p in PARAMS:
        ks = ch.get(p) or [(0, float(DEFAULTS.get(p, 0)))]
        if p == 'NUM' and not ch.get(p): ks = [(0, float(e['maxParticles']))]
        kidx += [len(keys), len(ks)]; keys += ks
    nol = sysd['numOLFrames'] or 100
    alol = ol_lut(ol.get('ALOL'), nol, 255.)
    if 'COOL' in ol:
        rr, gg, bb = (ol_lut(ol['COOL'], nol, 255., s) for s in (16, 8, 0))
    else: rr = gg = bb = [255.] * NOL
    olc = [(int(round(min(255, max(0, a)))) << 24) | (int(round(b)) << 16) | (int(round(g)) << 8) | int(round(r))
           for r, g, b, a in zip(rr, gg, bb, alol)]
    luts = [ol_lut(ol.get(k), nol, 1.) for k in ('SZOL', 'SPOL', 'SNOL', 'WEOL')]
    ti = e.get('texInfo') or {}
    cols, rows = ti.get('frameGrid', [1, 1]); fw, fh = ti.get('frameSize', [1, 1])
    nfr = max(1, min(e['numTexFrames'] or 1, cols * rows))
    tm = {'NONE': 0, 'RAND': 1, 'LIN': 2}.get(e['texAnimMode'], 0)
    am = {'SPEC': 0, 'RAND': 1, 'MOAL': 2}.get(e['angleMode'], 0)
    gm = {'PNT': 0, 'PLN': 1, 'SPHR': 2}.get(e['generator'], 0)
    g1 = sample(keys_of(gen['WDT']), 0) if 'WDT' in gen else (sample(keys_of(gen['RAD']), 0) if 'RAD' in gen else 0.)
    g2 = sample(keys_of(gen['HGT']), 0) if 'HGT' in gen else g1
    sh = sample(keys_of(gen['HOSP']), 0) if 'HOSP' in gen else 0.
    sv = sample(keys_of(gen['VESP']), 0) if 'VESP' in gen else 0.
    flags = (1 if 'COOL' in ol else 0) | (2 if 'ALOL' in ol else 0)
    return struct.pack(EMIT_FMT, tex_id, cols, rows, nfr, tm, BLEND.get(e['blend'], 0), am, gm, flags,
                       float(e['texFrameRate'] or 0), float(e['angle']), fh / max(1, fw), g1, g2, sh, sv,
                       *kidx, *olc, *[x for l in luts for x in l])

def is_oneshot(s):
    for e in s['emitters']:
        r = e.get('emit', {}).get('RAT', 0)
        if not isinstance(r, dict):
            if r > 0: return 0
        elif r['keys'][-1][1] > 0: return 0
    return 1

def code_systems():
    """Эффекты, которые в оригинале рисует exe (параметров в данных нет) — по предложению docs/fx_spec.md."""
    def e(name, tex, blend, am, life, lifev, size, sizev, cool, alol, grav, szol=(1., 1.), aspect_tex=None):
        return {'name': name, 'shader': '', 'angleMode': am, 'angle': 0., 'texAnimMode': 'NONE', 'numTexFrames': 1,
                'texFrameRate': 0, 'texture': tex, 'blend': blend, 'generator': 'PNT', 'maxParticles': 60,
                'texInfo': aspect_tex,
                'emit': {'LIF': life, 'LIFV': lifev, 'SIZ': size, 'SIZV': sizev, 'GRA': grav, 'WGT': 0.0108889,
                         'DRA': 0.97, 'SPD': 0.2, 'NUM': 60},
                'overLife': {'COOL': {'keys': [[i * 99 // (len(cool) - 1), c] for i, c in enumerate(cool)], 'interp': 1},
                             'ALOL': {'keys': [[i * 99 // (len(alol) - 1), a] for i, a in enumerate(alol)], 'interp': 1},
                             'SZOL': {'keys': [[0, szol[0]], [99, szol[1]]], 'interp': 1}}}
    spark = e('spark', 'spark4.bmp', 'add', 'MOAL', 10, 2.3, 0.35, 0.08,
              ['#ffffffff', '#ffffe0a0', '#ffc06020', '#ff000000'], [255, 255], -1.0,
              aspect_tex={'frameGrid': [1, 1], 'frameSize': [64, 9]})   # 0.35 × 0.05 м
    paint = e('paint', 'cloud.tga', 'alpha', 'RAND', 18, 3, 0.08, 0.03, ['#ffffffff', '#ffffffff'], [255, 255, 0], -1.0)
    dust = e('dust', 'cloud.tga', 'alpha', 'RAND', 30, 6, 0.6, 0.2, ['#ff9a9080', '#ff9a9080'], [0, 90, 40, 0], 0.,
             szol=(0.6, 2.2))
    return [{'name': 'code_' + x['name'], 'fps': 30., 'numAnimFrames': 30, 'numOLFrames': 100, 'maxInstances': 1,
             'context': {'kind': 'code'}, 'file': 'art/missions/generic/missgen.p3d', 'emitters': [x], 'users': []}
            for x in (spark, paint, dust)]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=str(ROOT / 'build/fx.shr')); ap.add_argument('--png')
    ap.add_argument('--level', type=int, default=1, help='уровень: файлы систем частиц tools/fx_export.default_files(N)')
    a = ap.parse_args()
    global FILES
    FILES = level_files(a.level)
    systems, breakables = [], []
    for rel in FILES:
        s, b, _ = fe.parse_file(rel); systems += s; breakables += b
    systems += code_systems()
    bank = TexBank()
    # уникальные системы: одинаковое имя и одинаковое содержимое = одна
    uniq, sig_of = [], {}
    for s in systems:
        sig = hashlib.md5(json.dumps([s['name'], s['emitters'], s['numAnimFrames']], sort_keys=True, default=str)
                          .encode()).hexdigest()
        if sig in sig_of:
            u = uniq[sig_of[sig]]
            if s['context'].get('kind') == 'inst': u['context'] = s['context']
            u['users'] += s['users']; continue
        sig_of[sig] = len(uniq); uniq.append(dict(s, users=list(s['users'])))
    order_files = lambda rel: [rel] + [f for f in FILES if f != rel]
    emits, keys, sysrecs, sys_index = [], [], [], {}
    for si, s in enumerate(uniq):
        first = len(emits)
        for e in s['emitters']:
            ti = e.get('texInfo') or {}
            tid = bank.get(e['texture'] or '', order_files(s['file']), ti.get('w'), ti.get('h')) if e.get('texture') else None
            if tid is None and e.get('texture'): tid = bank.get(e['texture'], order_files(s['file']))
            if tid is None: print('нет текстуры', s['name'], e['name'], e.get('texture')); tid = 0
            emits.append(emitter_rec(e, s, tid, keys))
        ctx = s['context']
        sysrecs.append(dict(name=s['name'], first=first, n=len(s['emitters']), nFrames=max(1, s['numAnimFrames']),
                            oneShot=is_oneshot(s), maxInst=s.get('maxInstances') or 1, fps=s['fps'] or 30.,
                            inst=ctx['type'] if ctx.get('kind') == 'inst' else -1, brk=-1, bbFirst=0, bbN=0))
        sys_index.setdefault((s['name'], s['file']), si); sys_index.setdefault(s['name'], si)
    # обломки: по номеру типа — один набор (из первого файла)
    bbs, bblut, brks, seen_brk = [], bytearray(), [], set()
    for br in breakables:
        if br['type'] in seen_brk or not br['factories']: continue
        seen_brk.add(br['type'])
        ids = [sys_index.get((f, br['file']), sys_index.get(f)) for f in br['factories']]
        ids = [i for i in ids if i is not None][:4]
        for i in ids: sysrecs[i]['brk'] = br['type']
        bfirst = len(bbs)
        anims = {x['name']: x for x in br['anims']}
        for g in br['billboards']:
            an = anims.get('BQG_' + g['name']); q = g['quads'][0]
            nfr = int(an['numFrames']) if an else 1; ch = an['channels'] if an else {}
            kw = keys_of(ch['WDT']) if 'WDT' in ch else [(0, q['w'])]
            kh = keys_of(ch['HGT']) if 'HGT' in ch else [(0, q['h'])]
            kc = [colour_keys(ch['CLR'], s) if 'CLR' in ch else [(0, float((int(q['colour'][1:], 16) >> s) & 255))]
                  for s in (24, 16, 8, 0)]
            rot = ch.get('ROT', q.get('rot', [1, 0, 0, 0]))
            rot = rot if not isinstance(rot, dict) else rot['keys'][0][1]
            rot = [rot[0], -rot[1], -rot[2], rot[3]]
            tid = bank.get(g['texture'], order_files(br['file']))
            off = len(bblut)
            for f in range(nfr):
                A, R, Gc, B = (int(round(sample(k, f))) for k in kc)
                bblut += struct.pack('<2fI', sample(kw, f), sample(kh, f), (A << 24) | (B << 16) | (Gc << 8) | R)
            bbs.append((tid or 0, BLEND.get(g['blend'], 1), 0 if q['mode'] == 'NOAX' else 1, float(q['distance']),
                        rot, nfr, off))
        if ids:
            sysrecs[ids[0]]['bbFirst'], sysrecs[ids[0]]['bbN'] = bfirst, len(bbs) - bfirst
        brks.append((br['type'], ids, bfirst, len(bbs) - bfirst))
    # фон уровня: мировые позиции (z зеркалим)
    ambs = []
    for si, s in enumerate(uniq):
        for u in s['users']:
            if u['container'] in ('3f0000c', '3f00008') and u.get('pos'):
                x, y, z = u['pos']; ambs.append((si, x, y, -z))
    ambs = list(dict.fromkeys(ambs))
    for n in EXTRA_TEX + SKID_TEX.get(a.level, []): bank.get(n, ['art/missions/generic/missgen.p3d', 'art/wrench.p3d', 'art/cards.p3d', FILES[0]])   # FILES[0] — l0N_fx уровня
    # --- запись ---
    texrecs, texdata = [], bytearray()
    blobs = [tex_blob(t) for _, t in bank.list]
    HDR = 64
    off = HDR
    def al(x): return (x + 15) & ~15
    offTex = off; off = al(off + 32 * len(blobs))
    offSys = off; off = al(off + 56 * len(sysrecs))
    offEmit = off; off = al(off + EMIT_SIZE * len(emits))
    offKey = off; off = al(off + 8 * len(keys))
    offBB = off; off = al(off + 32 * len(bbs))
    offLut = off; off = al(off + len(bblut))
    offAmb = off; off = al(off + 16 * len(ambs))
    offBrk = off; off = al(off + 16 * len(brks))
    body = bytearray(off)
    for i, ((name, t), (bufw, swz, pix, clut)) in enumerate(zip(bank.list, blobs)):
        op = off; body += pix; body += bytes(al(len(body)) - len(body))
        oc = len(body); body += clut; body += bytes(al(len(body)) - len(body)); off = len(body)
        struct.pack_into('<3H2B2I16s', body, offTex + 32 * i, t[0], t[1], bufw, t[2], swz, op, oc, name.encode()[:15])
    for i, r in enumerate(sysrecs):
        struct.pack_into('<32s3H2Bf2h2HI', body, offSys + 56 * i, r['name'].encode()[:31], r['first'], r['n'],
                         r['nFrames'], r['oneShot'], min(255, r['maxInst']), r['fps'], r['inst'], r['brk'],
                         r['bbFirst'], r['bbN'], 0)
    for i, e in enumerate(emits): body[offEmit + EMIT_SIZE * i: offEmit + EMIT_SIZE * (i + 1)] = e
    for i, (f, v) in enumerate(keys): struct.pack_into('<2Hf', body, offKey + 8 * i, min(65535, f), 0, v)
    for i, (tid, bl, mode, dist, rot, nfr, lo) in enumerate(bbs):
        struct.pack_into('<H2Bf4f2HI', body, offBB + 32 * i, tid, bl, mode, dist, *rot, nfr, 0, offLut + lo)
    body[offLut:offLut + len(bblut)] = bblut
    for i, (si, x, y, z) in enumerate(ambs): struct.pack_into('<2H3f', body, offAmb + 16 * i, si, 0, x, y, z)
    for i, (t, ids, bf, bn) in enumerate(brks):
        ids4 = (ids + [0xFFFF] * 4)[:4]
        struct.pack_into('<hH4H2H', body, offBrk + 16 * i, t, len(ids), *ids4, bf, bn)
    struct.pack_into('<4s15I', body, 0, b'FXP1', 1, len(blobs), len(sysrecs), len(emits), len(keys), len(bbs),
                     len(ambs), len(brks), offTex, offSys, offEmit, offKey, offBB, offAmb, offBrk)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True); Path(a.out).write_bytes(body)
    texb = sum(len(p) + len(c) for _, _, p, c in blobs)
    print(f'{a.out}: {len(body) // 1024} КБ — {len(sysrecs)} систем, {len(emits)} эмиттеров ({EMIT_SIZE} Б), '
          f'{len(keys)} ключей, {len(blobs)} текстур ({texb // 1024} КБ), {len(bbs)} биллбордов, {len(ambs)} фоновых, '
          f'{len(brks)} обломков')
    if a.png:
        from PIL import Image
        d = Path(a.png); d.mkdir(parents=True, exist_ok=True)
        for i, (name, (w, h, bpp, idx, pal)) in enumerate(bank.list):
            Image.fromarray(pal[idx], 'RGBA').save(d / f'{i:02d}_{Path(name).stem}_{w}x{h}.png')
    json.dump({'systems': [dict(id=i, name=r['name'], inst=r['inst'], brk=r['brk'], oneShot=r['oneShot'])
                           for i, r in enumerate(sysrecs)],
               'textures': [n for n, _ in bank.list]},
              open(Path(a.out).with_suffix('.json'), 'w'), indent=0, ensure_ascii=False)

if __name__ == '__main__':
    main()
