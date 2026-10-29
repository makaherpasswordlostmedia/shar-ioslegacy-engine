"""Регионы уровня и что из них рисовать с места игрока (правка Роба 95/83/84, место L1 F11-2 у заправки) -> секция REG1.

Что это было. Город уровня на диске — 13 файлов-регионов (уровень 1: l1r1…l1r7 дороги, l1z1…l1z7 районы). Оригинал
никогда не держит их все: локаторы ZoneEvent (вид 5) в l1_terra.p3d — ящики-триггеры поперёк дорог со строкой «выгрузить:
загрузить;» (формат строки — donut, Level::DynaLoadData: ';' загрузка, ':' выгрузка, '@'/'$' интерьеры), телепорты
AddTeleportDest и SetDynaLoadData миссий держат 3–4 региона. Художники этим пользуются: в регионе лежат грубые «декорации
издали» соседних районов, которые видны, пока сам район выгружен. У заправки (L1 F10-7/F11-2, движок −183 283 / −150 317)
это l1r1 (дорога у дома Симпсонов и Kwik-E-Mart): холм с дорогой (L147_r1_gensd_471Shape_019/_032, трава grassc и асфальт
rd1_norm на высоте 7–27 м), дома с красными крышами (_002 grn_a, _033 red_roof_shingles, _017 fence_cedar) и стена
фоновых деревьев (_041 treeline_oak, до 37 м) — без коллизии, поверх настоящей заправки l1r3 и особняка Бёрнса l1z4.
Оригинал у заправки l1r1 не грузит ни в одном состоянии (l1r1 никогда не бывает вместе с l1r3 и l1z4), порт рисовал всё
сразу: холм, через который едешь, мерцание кроны с холмом, «купол деревьев» вместо особняка с крыши.

Правило (одно для всех уровней, без координат мест):
  состояния — множества регионов, которые оригинал держит вместе: загрузки полных триггеров ZoneEvent, телепорты,
     SetDynaLoadData миссий; частичные триггеры замыкают их: S -> (S − выгрузки) ∪ загрузки;
  дом клетки 20 м (сетка PVS, tools/pvs.c) — регионы, чья земля коллизии (Intersect) есть в клетке ± REG_MARGIN: стоять на
     земле выгруженного региона нельзя, значит в оригинале он загружен;
  маска клетки — объединение состояний, где есть регион дома; клетки без земли — маска ближайшей клетки с землёй;
  «декорация издали»: два региона, которые вместе не грузятся, а рисунок их пересекается (не меньше CONF_MIN клеток 4 м) —
     в клетке остаётся тот, чья своя земля ближе (у заправки — l1r3 и l1z4, у дома Симпсонов — l1r1);
  движок (viewer/main.c regEye) и PVS (tools/pvs.c) не рисуют и не считают заслоняющими куски регионов вне маски клетки
     глаза; опора по видимой земле (psp_export.col_visible_ground, 11.3) не берёт треугольники вне маски их клетки;
     слои-наклейки (mark_layers) не ищутся между регионами, которые вместе не грузятся.

Формат секции (little endian), в самом конце файла до PVS1 (tools/pvs дописывает PVS1 сразу за ней):
  'REG1' u32 version=1, nreg, W, H; f32 ox, oz, cell                                   32 Б
  char name[nreg][16]                                                                 имена регионов (без .p3d)
  u16 mask[W*H]                                                                       бит r — регион r рисуется с этой клетки
  выравнивание до 16 и хвост 16 Б: 'REGF', u32 смещение REG1 от начала файла, u32 размер секции с хвостом, u32 version
Кусок города знает регион: Rec.pad[0] = номер региона + 1 (0 — без региона, рисуется всегда: объекты AnimCollision и т. п.).
Старые level.shr (без хвоста REGF) читаются как раньше — рисуется всё.
  python tools/regions_export.py [уровень] [x z ...]  — состояния, пары «декорация издали», маски в точках (без сборки уровня)"""
import math, re, struct, sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))
from p3d import read, walk, string   # MIT, разбор Pure3D
GAME = ROOT / 'hit-and-run-web/source/game'

REG_CELL = 20.0     # клетка маски = клетка PVS (tools/pvs.c PCELL), сетка от угла карты высот − REG_PAD
REG_PAD = 10.0      # tools/pvs.c PMARGIN
REG_MARGIN = 10.0   # дом клетки — земля коллизии в клетке ± 10 м (камера за спиной игрока, граница района)
FINE = 4.0          # мелкая сетка покрытия (м)
CONF_MIN = 10       # клеток FINE пересечения рисунка (≈160 м²) — пара регионов «декорация издали»
MAX_REG = 16        # маска u16
VERSION = 2   # правка 181 (02.10): + ворота подгрузки и наборы мест (блок GAT1 за маской); движок читает и версию 1
GATE_REC = 68  # f32 c[3], half[3], ax[9] (строки — оси объёма в осях порта), u16 загрузить, u16 выгрузить, u32 0
STATE_REC = 12 # f32 x, z (порт), u16 маска регионов, u16 0


def level_regions(level):
    art = GAME / 'art'
    return sorted(p.stem.lower() for p in art.glob(f'l{level}r*.p3d')) + sorted(p.stem.lower() for p in art.glob(f'l{level}z*.p3d'))


def parse_dyna(s):
    """строка ZoneEvent/телепорта -> (загрузки, выгрузки): имена файлов без .p3d; ';' загрузка, ':' выгрузка, '@'/'$' — интерьеры"""
    load, unload, prev = [], [], 0
    for i, ch in enumerate(s):
        if ch in ';:@$':
            f = s[prev:i].strip().lower().replace('\\', '/').split('/')[-1]
            if f.endswith('.p3d'): f = f[:-4]
            prev = i + 1
            if f and ch == ';': load.append(f)
            elif f and ch == ':': unload.append(f)
    return load, unload


def dyna_sources(level):
    """-> [(откуда, имя, загрузки, выгрузки, полный)]: ZoneEvent-локаторы файлов уровня, AddTeleportDest, SetDynaLoadData миссий"""
    regs = set(level_regions(level)); out = []
    for path in sorted((GAME / 'art').glob(f'l{level}*.p3d')):
        for c in walk(read(path)):
            if c.id != 0x3000005: continue
            name, p = string(c.data); kind, ln = struct.unpack_from('<II', c.data, p)
            if kind != 5: continue
            ld, ul = parse_dyna(c.data[p + 8: p + 8 + ln * 4].split(b'\0')[0].decode('latin1'))
            ld, ul = [f for f in ld if f in regs], [f for f in ul if f in regs]
            if ld or ul: out.append((path.stem, name, set(ld), set(ul), set(ld) | set(ul) >= regs))
    sd = GAME / f'scripts/missions/level{level:02d}'
    for f in sorted(sd.glob('*.mfk')) if sd.exists() else []:
        txt = re.sub(r'//[^\n]*', '', f.read_text(errors='replace'))
        for m in re.finditer(r'AddTeleportDest\(\s*"([^"]*)"\s*,[^,]*,[^,]*,[^,]*,\s*"([^"]*)"', txt):
            ld, ul = parse_dyna(m.group(2)); ld = [x for x in ld if x in regs]
            if ld: out.append((f.name, 'tp:' + m.group(1), set(ld), set(), True))
        for m in re.finditer(r'SetDynaLoadData\(\s*"([^"]*)"', txt):
            ld, ul = parse_dyna(m.group(1)); ld = [x for x in ld if x in regs]
            if ld and not ul: out.append((f.name, 'msn', set(ld), set(), True))
    return out


def dyna_states(level, regions=None):
    """-> (список масок состояний — замыкание полных состояний частичными триггерами, источники)"""
    regions = regions or level_regions(level); RI = {r: i for i, r in enumerate(regions)}
    bit = lambda s: sum(1 << RI[r] for r in s if r in RI)
    src = dyna_sources(level)
    st = {bit(ld) for _, _, ld, ul, full in src if full and ld}
    part = [(bit(ld), bit(ul)) for _, _, ld, ul, full in src if not full]
    todo = list(st)
    while todo and len(st) < 4096:
        S = todo.pop()
        for ld, ul in part:
            N = (S & ~ul) | ld
            if N and N not in st: st.add(N); todo.append(N)
    return sorted(st), src


def cover(tris, ox, oz, W, H, cell=FINE):
    """треугольники (n,3,3) -> маска клеток (H, W): клетка покрыта, если в ней есть точка треугольника (шаг выборки <= cell/2)"""
    m = np.zeros((H, W), bool)
    P = np.asarray(tris, np.float64).reshape(-1, 3, 3)
    if not len(P): return m
    ext = np.max([np.hypot(P[:, (i + 1) % 3, 0] - P[:, i, 0], P[:, (i + 1) % 3, 2] - P[:, i, 2]) for i in range(3)], 0)
    ns = np.clip(np.ceil(ext / (cell * .5)).astype(int), 1, 400)
    for n in np.unique(ns):
        S = P[ns == n][:, :, [0, 2]]; us = np.arange(n + 1) / n
        uu, vv = np.meshgrid(us, us); k = uu + vv <= 1 + 1e-9; uu, vv = uu[k], vv[k]
        for k0 in range(0, len(uu), 64):
            u = uu[k0:k0 + 64][None, :, None]; v = vv[k0:k0 + 64][None, :, None]
            Q = (S[:, None, 0] * (1 - u - v) + S[:, None, 1] * u + S[:, None, 2] * v).reshape(-1, 2)
            ix = np.floor((Q[:, 0] - ox) / cell).astype(np.int64); iz = np.floor((Q[:, 1] - oz) / cell).astype(np.int64)
            ok = (ix >= 0) & (ix < W) & (iz >= 0) & (iz < H)
            m[iz[ok], ix[ok]] = True
    return m


def cheb_steps(m):
    """клеток (Чебышёв) до ближайшей True; где True нет вовсе — 1e9"""
    if not m.any(): return np.full(m.shape, 10 ** 9, np.int64)
    d = np.full(m.shape, 10 ** 9, np.int64); cur = m.copy(); d[cur] = 0; step = 0
    while True:
        step += 1
        nb = cur.copy(); nb[1:] |= cur[:-1]; nb[:-1] |= cur[1:]
        nb2 = nb.copy(); nb2[:, 1:] |= nb[:, :-1]; nb2[:, :-1] |= nb[:, 1:]
        new = nb2 & ~cur
        if not new.any(): return d
        d[new] = step; cur = nb2


class Regions:
    """col: {регион: треугольники коллизии Intersect (n,3,3)}, vis: {регион: рисуемые треугольники}; lo, W, H, cell — карта
    высот уровня (как в заголовке SHR7): сетка маски совпадает с сеткой PVS tools/pvs.c"""
    def __init__(self, level, col, vis, lo, W, H, cell):
        self.level = level; self.names = level_regions(level); nR = len(self.names)
        self.ok = 0 < nR <= MAX_REG
        self.ox, self.oz = float(lo[0]) - REG_PAD, float(lo[2]) - REG_PAD
        self.W = int(math.ceil((W * cell + 2 * REG_PAD) / REG_CELL)); self.H = int(math.ceil((H * cell + 2 * REG_PAD) / REG_CELL))
        self.states, self.src = dyna_states(level, self.names)
        co = np.zeros((nR, nR), bool)
        for S in self.states:
            ix = [r for r in range(nR) if S >> r & 1]
            for a in ix: co[a, ix] = True
        self.co = co
        k = int(round(REG_CELL / FINE)); FW, FH = self.W * k, self.H * k
        C = np.stack([cover(col.get(r, np.zeros((0, 3, 3))), self.ox, self.oz, FW, FH) for r in self.names])
        V = np.stack([cover(vis.get(r, np.zeros((0, 3, 3))), self.ox, self.oz, FW, FH) for r in self.names])
        self.conf = []
        for a in range(nR):
            for b in range(a + 1, nR):
                if co[a, b]: continue
                ov = int((V[a] & V[b]).sum())
                if ov >= CONF_MIN: self.conf.append((a, b, ov, int((V[a] & C[b]).sum()), int((V[b] & C[a]).sum())))
        dist = np.stack([cheb_steps(C[r]) for r in range(nR)])   # шагов FINE до своей земли
        m = int(round(REG_MARGIN / FINE))
        home = np.zeros((self.H, self.W), np.int64); mask = np.zeros((self.H, self.W), np.int64)
        for gz in range(self.H):
            for gx in range(self.W):
                sub = C[:, max(0, gz * k - m):(gz + 1) * k + m, max(0, gx * k - m):(gx + 1) * k + m]
                h = 0
                for r in range(nR):
                    if sub[r].any(): h |= 1 << r
                home[gz, gx] = h
                if not h: continue
                u = 0
                for S in self.states:
                    if S & h: u |= S
                u |= h
                cz, cx = min(gz * k + k // 2, FH - 1), min(gx * k + k // 2, FW - 1)
                for a, b, _, _, _ in self.conf:
                    if u >> a & 1 and u >> b & 1:
                        da, db = dist[a, cz, cx], dist[b, cz, cx]
                        u &= ~(1 << (a if (da, a) > (db, b) else b))
                mask[gz, gx] = u
        empty = mask == 0; self.filled = int(empty.sum())
        have = ~empty
        while (~have).any():   # клетки без земли — маска ближайшей клетки с землёй (по 4 соседям, детерминированно)
            prev = have.copy(); grew = False
            for dz, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                src_ = np.zeros_like(prev); val = np.zeros_like(mask)
                zs, xs = slice(max(0, dz), self.H + min(0, dz)), slice(max(0, dx), self.W + min(0, dx))
                zt, xt = slice(max(0, -dz), self.H + min(0, -dz)), slice(max(0, -dx), self.W + min(0, -dx))
                src_[zs, xs] = prev[zt, xt]; val[zs, xs] = mask[zt, xt]
                take = src_ & ~have
                if take.any(): mask[take] = val[take]; have |= take; grew = True
            if not grew: mask[~have] = (1 << nR) - 1; break
        self.home, self.mask = home, mask
        self.all = (1 << nR) - 1

    def index(self, name):
        return self.names.index(name.lower()) if name and name.lower() in self.names else -1

    def mask_at(self, x, z):
        """-> маски клеток для массивов x, z (вне сетки — все регионы)"""
        x = np.asarray(x, np.float64); z = np.asarray(z, np.float64)
        gx = np.floor((x - self.ox) / REG_CELL).astype(np.int64); gz = np.floor((z - self.oz) / REG_CELL).astype(np.int64)
        ok = (gx >= 0) & (gx < self.W) & (gz >= 0) & (gz < self.H)
        out = np.full(x.shape, self.all, np.int64)
        out[ok] = self.mask[gz[ok], gx[ok]]
        return out

    def allowed(self, x, z, reg):
        """треугольник региона reg (номер, −1 — без региона) в точке x, z рисуется с этой клетки?"""
        reg = np.asarray(reg, np.int64)
        return (reg < 0) | ((self.mask_at(x, z) >> np.maximum(reg, 0)) & 1).astype(bool)

    def never(self):
        """матрица «никогда не грузятся вместе» (для слоёв-наклеек)"""
        return ~self.co

    def gates(self):
        """правка 181: ворота подгрузки оригинала — объёмы ZoneEvent-локаторов (вид 5) с масками «загрузить»/«выгрузить» регионов;
        у локатора с несколькими объёмами — запись на каждый объём. [PS2] сверено ездой бота: 22 из 22 чтений файлов зон — при въезде
        в их ворота (tools/twins/loadmap.py, knowledge/facts/ps2-streaming-gates.yaml)"""
        import sound_export as SE
        RI = {r: i for i, r in enumerate(self.names)}
        bit = lambda fs: sum(1 << RI[f] for f in fs if f in RI)
        out = []
        for f, nm, kind, d, p, vols in SE.locators(self.level):
            if kind != 5: continue
            cmd = d.split(b'\0')[0].decode('latin1')
            if '@' in cmd: continue   # двери помещений (дом, Kwik-E-Mart, школа): у порта вход — своя логика комнат по △ (правило порта)
            ld, ul = parse_dyna(cmd)
            L, U = bit(ld), bit(ul)
            if not (L or U): continue
            for v in vols:
                out.append((nm, [float(x) for x in v['t']], [float(h) for h in v['half']], [float(x) for row in v['R'] for x in row], L, U))
        return out

    def places(self):
        """наборы регионов по местам: AddTeleportDest (как в level.mfk: место и файлы) -> [(x, z порта, маска)]"""
        RI = {r: i for i, r in enumerate(self.names)}
        sd = GAME / f'scripts/missions/level{self.level:02d}'; out = []
        for f in sorted(sd.glob('*.mfk')) if sd.exists() else []:
            txt = re.sub(r'//[^\n]*', '', f.read_text(errors='replace'))
            for m in re.finditer(r'AddTeleportDest\(\s*"[^"]*"\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*"([^"]*)"', txt):
                ld, _ = parse_dyna(m.group(4)); mask = sum(1 << RI[x] for x in ld if x in RI)
                if mask: out.append((float(m.group(1)), -float(m.group(3)), mask))
        return out

    def gat1(self):
        """блок 'GAT1' u32 ворот, u32 мест, 4 Б; ворота по GATE_REC, места по STATE_REC; кратно 16 (его же читает сверка
        tests/zonegate)"""
        G, P = self.gates(), self.places()
        b = bytearray(b'GAT1' + struct.pack('<2I', len(G), len(P)) + b'\0' * 4)
        for nm, c, half, ax, L, U in G: b += struct.pack('<3f3f9fHHI', *c, *half, *ax, L, U, 0)
        for x, z, mask in P: b += struct.pack('<2fHH', x, z, mask, 0)
        b += b'\0' * (-len(b) % 16)
        return bytes(b)

    def section(self, at):
        """байты секции REG1 с хвостом REGF; at — смещение секции от начала файла (кратно 16)"""
        nR = len(self.names)
        b = bytearray(b'REG1' + struct.pack('<4I3f', VERSION, nR, self.W, self.H, self.ox, self.oz, REG_CELL))
        for n in self.names: b += n.encode('latin1')[:15].ljust(16, b'\0')
        b += self.mask.astype('<u2').tobytes()
        b += b'\0' * (-len(b) % 16)
        if VERSION >= 2: b += self.gat1()   # правка 181: ворота и места
        b += b'REGF' + struct.pack('<3I', at, len(b) + 16, VERSION)
        return bytes(b)

    def report(self):
        nm = self.names
        lines = [f'регионы (правка 95): {len(nm)} файлов, состояний оригинала {len(self.states)} '
                 f'(источников: ZoneEvent {sum(1 for s in self.src if not s[1].startswith(("tp:", "msn")))}, '
                 f'телепортов {sum(1 for s in self.src if s[1].startswith("tp:"))}, миссий {sum(1 for s in self.src if s[1] == "msn")}); '
                 f'сетка {self.W}x{self.H} по {REG_CELL:g} м, клеток без земли (маска соседа) {self.filled}']
        for a, b, ov, ab, ba in self.conf:
            lines.append(f'  декорация издали: {nm[a]} и {nm[b]} вместе не грузятся, рисунок пересекается на {ov * FINE * FINE:,.0f} м² '
                         f'(рисунок {nm[a]} над землёй {nm[b]} {ab * FINE * FINE:,.0f} м², наоборот {ba * FINE * FINE:,.0f} м²)')
        return lines

    def describe(self, x, z):
        g = int(self.mask_at([x], [z])[0])
        gx = int(math.floor((x - self.ox) / REG_CELL)); gz = int(math.floor((z - self.oz) / REG_CELL))
        h = int(self.home[gz, gx]) if 0 <= gx < self.W and 0 <= gz < self.H else 0
        return [n for r, n in enumerate(self.names) if h >> r & 1], [n for r, n in enumerate(self.names) if g >> r & 1]


def read_section(buf, base_end=None):
    """level.shr (bytes) -> dict(names, W, H, ox, oz, cell, mask (H, W) u16) или None. Хвост REGF — перед PVS1 (или в конце файла)"""
    if base_end is None:
        pvs = struct.unpack_from('<I', buf, 88)[0] if len(buf) >= 104 else 0
        base_end = pvs if pvs else len(buf)
    if base_end < 48 or buf[base_end - 16:base_end - 12] != b'REGF': return None
    at, size, ver = struct.unpack_from('<3I', buf, base_end - 12)
    if at + 32 > len(buf) or buf[at:at + 4] != b'REG1': return None
    ver, nR, W, H = struct.unpack_from('<4I', buf, at + 4); ox, oz, cell = struct.unpack_from('<3f', buf, at + 20)
    names = [buf[at + 32 + 16 * i: at + 48 + 16 * i].split(b'\0')[0].decode('latin1') for i in range(nR)]
    m = np.frombuffer(buf, '<u2', W * H, at + 32 + 16 * nR).reshape(H, W)
    return dict(names=names, W=W, H=H, ox=ox, oz=oz, cell=cell, mask=m, at=at, size=size)


if __name__ == '__main__':
    level = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    st, src = dyna_states(level)
    names = level_regions(level)
    print(f'уровень {level}: регионы {names}')
    for f, n, ld, ul, full in src:
        print(f'  {f:14} {n[:28]:28} {"полный " if full else "частичный"} загрузка {sorted(ld)} выгрузка {sorted(ul)}')
    print(f'состояний (замыкание): {len(st)}')
    co = np.zeros((len(names),) * 2, bool)
    for S in st:
        ix = [r for r in range(len(names)) if S >> r & 1]
        for a in ix: co[a, ix] = True
    for a in range(len(names)):
        nv = [names[b] for b in range(len(names)) if not co[a, b]]
        if nv: print(f'  {names[a]:7} никогда вместе с {nv}')
