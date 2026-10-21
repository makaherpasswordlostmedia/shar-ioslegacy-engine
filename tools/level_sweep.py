"""Прогон уровней 1..7 через конвейер экспорта SHR7 — только в черновую папку, build/level.shr не трогается.

Экспорт идёт кодом tools/psp_export.py (импорт как модуль, файл не меняется), но с подменами:
  * временные файлы конвертера — с префиксом st_lvN_ (а не psp_), чтобы не пересечься с основным экспортом;
  * старт уровня берётся из локатора level{N}_carstart (скрипт leveli.mfk -> InitLevelPlayerVehicle);
  * по пути собираем статистику: небо (имена объектов), треугольники по сценам, повторы между сценами,
    текстуры (исходные размеры/число цветов), цвета вершин (яркость — видно ночь/закат).
Потом файл разбирается: размер, резидентная память, клетки стриминга, треугольники, текстуры,
бюджет треугольников в кадре (логика tools/budget.py), по желанию PVS (tools/pvs --samples 5).

  python tools/level_sweep.py --level 3            -> один уровень (для параллельного запуска)
  python tools/level_sweep.py --level 3 --pvs      -> + PVS 5x5 на черновой копии
  python tools/level_sweep.py --level 1 --tex texq -> текстуры через tools/texq.load_tex (сравнение памяти)
  python tools/level_sweep.py --summary            -> таблицы markdown по готовым JSON (для docs/levels.md)
  python tools/level_sweep.py --info 2             -> только старт/интерьеры/файлы уровня, без экспорта
Папка результатов: $SWEEP_DIR или scratchpad/streams/levels (levelN.shr, levelN.log, levelN.json)."""
import sys, os, io, json, time, struct, re, traceback, importlib.util, hashlib, subprocess, argparse, contextlib
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = Path('/private/tmp/claude-501/-Users-robertvagin-Downloads-shar-psp/'
                   '3f2ce002-62fd-4bf8-9553-98f95067c719/scratchpad/streams/levels')
PREFIX = 'st_lv{N}_'   # временные файлы конвертера (N — номер уровня)
INTERIOR_NAMES = {0: 'SpringfieldElementary', 1: 'KwikEMart', 2: 'SimpsonsHouse', 3: 'DMV', 4: 'Moes',
                  5: 'AndroidsDungeon', 6: 'Observatory', 7: 'BartRoom'}   # как в hit-and-run-web/tools/campaign.py
# движок (viewer/main.c) — те же числа, что и там
LOAD_DIST, DROP_DIST = 150.0, 200.0
PIECE_STRUCT, CELL_STRUCT = 108, 72          # sizeof(Piece), sizeof(Cell) в main.c


def sweep_dir():
    d = Path(os.environ.get('SWEEP_DIR', DEFAULT_DIR)); d.mkdir(parents=True, exist_ok=True); return d


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


# ---------------------------------------------------------------------------------------------------------------
# сведения об уровне без экспорта: старт, интерьеры, прочие файлы
def level_files(level):
    sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))
    from convert import GAME
    art = GAME / 'art'
    scenes = [f'l{level}_terra'] + sorted(p.stem for p in art.glob(f'l{level}r*.p3d')) + sorted(p.stem for p in art.glob(f'l{level}z*.p3d'))
    other = sorted(p.stem for p in art.glob(f'l{level}*.p3d') if p.stem not in scenes)
    return GAME, scenes, other


def find_spawn(level):
    """Старт уровня: InitLevelPlayerVehicle(car, locator) в leveli.mfk -> локатор (тип 3, с курсом) в
    art/missions/level0N/level.p3d (запасной вариант — любой p3d уровня).
    Курс для движка (вперёд = (sin h, cos h), как камера и budget.py): h = pi - угол_из_файла = heading_web + pi.
    Проверено гонками: машина на старте sr1/sr2/sr3 уровня 1 смотрит на первую точку маршрута с этим h
    (ошибка 2°/30°/57° — дорога изгибается), а с курсом hit-and-run-web (-угол) — назад (178°/150°/123°)."""
    sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))
    from campaign import parse, locators, GAME
    init = parse((GAME / f'scripts/missions/level0{level}/leveli.mfk').read_text())
    call = next((c['args'] for c in init if c['op'] == 'InitLevelPlayerVehicle'), None)
    if not call: return dict(error='InitLevelPlayerVehicle not found')
    car, name = str(call[0]), str(call[1])
    order = [GAME / f'art/missions/level0{level}/level.p3d', GAME / f'art/l{level}_terra.p3d',
             *sorted((GAME / 'art').glob(f'l{level}[rz]*.p3d')), *sorted((GAME / f'art/missions/level0{level}').glob('*.p3d'))]
    hits = []
    for p in order:
        if not p.exists(): continue
        for l in locators(p):
            if l['name'].lower() == name.lower(): hits.append(l)
        if hits: break
    if not hits: return dict(car=car, locator=name, error='locator not found')
    l = hits[0]; h = (float(l.get('heading', 0.0)) + np.pi) % (2 * np.pi)   # campaign.locators даёт -угол
    tele = re.findall(r'AddTeleportDest\("([^"]+)",\s*([\d.-]+),\s*([\d.-]+),\s*([\d.-]+)',
                      (GAME / f'scripts/missions/level0{level}/level.mfk').read_text())
    return dict(car=car, locator=name, source=l['source'], pos=[round(v, 3) for v in l['position']], heading=round(h, 4),
                teleports=[(n, float(x), float(y), -float(z)) for n, x, y, z in tele])


def describe_p3d(path):
    """Лёгкий разбор p3d без записи файлов: меши, треугольники, текстуры, коллизия, локаторы, габарит."""
    sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))
    from p3d import read, walk, string
    from convert import geometry
    root = read(path); tris = 0; lo = np.full(3, 1e9); hi = np.full(3, -1e9); meshes = tex = coll = locs = 0; names = []
    for c in walk(root):
        if c.id == 0x10000: meshes += 1
        elif c.id == 0x19000: tex += 1
        elif c.id == 0x3f00003: coll += 1
        elif c.id == 0x3000005:
            locs += 1; names.append(string(c.data)[0])
        elif c.id == 0x10002:
            try:
                _, parts = geometry(c)
            except Exception:
                continue
            for part in parts:
                tris += len(part['indices']) // 3; P = part['position']
                if len(P): lo = np.minimum(lo, P.min(0)); hi = np.maximum(hi, P.max(0))
    return dict(file=path.name, kb=path.stat().st_size // 1024, meshes=meshes, tris=tris, textures=tex, collision_chunks=coll,
                locators=locs, locator_names=names[:12],
                bbox=[round(float(v), 1) for v in (*lo, *hi)] if tris else None)


def level_info(level):
    GAME, scenes, other = level_files(level)
    info = dict(level=level, scenes=scenes, other_files=other, spawn=find_spawn(level), interiors=[], extras=[])
    for stem in other:
        d = describe_p3d(GAME / 'art' / f'{stem}.p3d')
        m = re.fullmatch(r'l[1-7]i(\d+)', stem)
        if m:
            d['interior'] = INTERIOR_NAMES.get(int(m.group(1)), '?'); info['interiors'].append(d)
        else: info['extras'].append(d)
    for stem in scenes:
        if stem.endswith('_dam') or re.fullmatch(rf'l{level}r\d+[a-z]', stem):
            info['extras'].append(dict(describe_p3d(GAME / 'art' / f'{stem}.p3d'), note='exported as a scene'))
    return info


# ---------------------------------------------------------------------------------------------------------------
# небо уровней 2..7
def sky_patch(root, st=None):
    """Небо любого уровня — составной объект (CompositeDrawable 0x4512, обычно 'horizon1') внутри «мировой сферы»
    (чанк 0x3f0000b в l{N}_terra.p3d: скелет, анимация облаков, меши неба). В l1_terra его вдобавок ставит граф сцены
    (0x120100 -> 0x120107 'horizon1'), и convert.export его видит; в l2..l7_terra графа сцены НЕТ -> неба в экспорте нет.
    Лечение: если графа сцены нет, дописываем в корень минимальный граф с одним рисуемым 'horizon1' -> convert.export
    ставит части составного объекта по позе скелета, объект называется 'horizon1' и попадает в небо (is_sky)."""
    from p3d import Chunk
    if any(c.id == 0x120100 for c in root.children): return root
    for ws in (c for c in root.children if c.id == 0x3f0000b):
        comp = next((x for x in ws.children if x.id == 0x4512), None)
        if comp is None: continue
        n = comp.data[0]; name = comp.data[1:1 + n]                 # p3d-строка: длина + байты (с нулями)
        ps = bytes([n]) + name
        root.children.append(Chunk(0x120100, b'', [Chunk(0x120107, ps + ps, [])]))
        if st is not None: st.skyfix = name.rstrip(b'\0').decode('latin1')
    return root


# ---------------------------------------------------------------------------------------------------------------
# экспорт с подменами
class Stats:
    def __init__(self):
        self.scene = None; self.sky = {}; self.scene_tris = {}; self.scene_keys = {}; self.textures = {}
        self.vcol = [0.0, 0.0]; self.sky_rgb = []; self.lit_materials = set(); self.errors = []
        self.texuse = {}   # № текстуры -> [(площади треугольников в мире м², площади в UV, машина?)]
        self.cache = None; self.skyfix = None


def run_export(level, out, texmode=None, skyfix=True):
    pe = load_module('st_lv_psp_export', ROOT / 'tools/psp_export.py')
    src_md5 = hashlib.md5((ROOT / 'tools/psp_export.py').read_bytes()).hexdigest()[:12]
    st = Stats(); base_out = pe.OUT; BaseConv = pe.Converter
    PREFIX = f"st_lv{level}{texmode or ''}_"   # свой префикс на уровень и вариант: можно гнать параллельно (машина у всех «car»)

    class Out:   # OUT / 'psp_x.json' -> OUT / 'st_lvN_x.json'; всё остальное (текстуры) — как есть
        def __truediv__(self, name):
            name = str(name)
            if name.startswith('psp_'): name = PREFIX + name[4:]
            return base_out / name

    import convert as cv
    orig_read = cv.read

    class Conv(BaseConv):
        def export(self, path, outname, *a, **k):
            if outname.startswith('psp_'): outname = PREFIX + outname[4:]
            st.scene = outname[len(PREFIX):]
            if skyfix: cv.read = lambda p: sky_patch(orig_read(p), st)
            try: return super().export(path, outname, *a, **k)
            finally: cv.read = orig_read

    orig_is_sky, orig_pack, orig_load_tex = pe.is_sky, pe.pack_prims, pe.load_tex
    if texmode == 'texq':
        orig_load_tex = load_module('st_lv_texq', ROOT / 'tools/texq.py').load_tex

    def is_sky(obj):
        r = orig_is_sky(obj)
        if r: st.sky.setdefault(st.scene, set()).add(obj['name'])
        return r

    def load_tex(url, cache, blob, **kw):   # kw: blend (texq — копия вырезки для полупрозрачного материала)
        if url and url not in cache and url not in st.textures:
            from PIL import Image
            im = Image.open(base_out / url).convert('RGBA'); a = np.asarray(im).reshape(-1, 4)
            st.textures[url] = dict(w=im.size[0], h=im.size[1], colors=int(len(np.unique(a.view('<u4'))))) if len(a) else dict(w=0, h=0, colors=0)
        return orig_load_tex(url, cache, blob, **kw)

    def pack_prims(meta, raw, conv_cache, blob, want=lambda o: True):
        res = orig_pack(meta, raw, conv_cache, blob, want); st.cache = conv_cache
        for k, m in meta['materials'].items():
            if m.get('lit'): st.lit_materials.add((st.scene, k))
        sky = want is is_sky
        for t, fl, P, UV, C in res:
            n = len(P) // 3
            if sky:
                c = np.stack([(C >> s) & 0xFF for s in (0, 8, 16)], 1).astype(np.float64)
                st.sky_rgb.append((c.reshape(-1, 3, 3).mean(1), P.reshape(-1, 3, 3).mean(1), t, UV.reshape(-1, 3, 2).mean(1)))
                continue
            if t >= 0:
                T = P.reshape(-1, 3, 3).astype(np.float64); U = UV.reshape(-1, 3, 2).astype(np.float64)
                wa = np.linalg.norm(np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]), axis=1) / 2
                e1, e2 = U[:, 1] - U[:, 0], U[:, 2] - U[:, 0]; ua = np.abs(e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]) / 2
                st.texuse.setdefault(t, []).append((wa, ua, st.scene == 'car'))
            if st.scene == 'car': continue
            st.scene_tris[st.scene] = st.scene_tris.get(st.scene, 0) + n
            q = np.round(P.reshape(-1, 3, 3).mean(1) * 50).astype(np.int64)   # центр треугольника с точностью 2 см
            st.scene_keys.setdefault(st.scene, []).append(q[:, 0] * 1000003 * 1000003 + q[:, 1] * 1000003 + q[:, 2])
            lum = ((C & 0xFF) * .299 + ((C >> 8) & 0xFF) * .587 + ((C >> 16) & 0xFF) * .114)
            st.vcol[0] += float(lum.sum()); st.vcol[1] += len(C)
        return res

    pe.OUT = Out(); pe.Converter = Conv; pe.is_sky = is_sky; pe.pack_prims = pack_prims; pe.load_tex = load_tex
    sp = find_spawn(level)
    if 'pos' in sp: pe.SPAWN[level] = (tuple(sp['pos']), sp['heading'])
    t0 = time.time(); err = None
    try:
        pe.main(level, str(out))
    except Exception:
        err = traceback.format_exc()
    finally:   # временные файлы конвертера — только свои
        for f in base_out.glob(PREFIX + '*'): f.unlink()
    return st, err, time.time() - t0, src_md5


# ---------------------------------------------------------------------------------------------------------------
# разбор готового SHR7
def parse_shr(path):
    d = Path(path).read_bytes()
    assert d[:4] == b'SHR7', 'not SHR7'
    ntex, npc = struct.unpack_from('<II', d, 4)
    bb = struct.unpack_from('<6f', d, 12); spawn = struct.unpack_from('<4f', d, 36); lift, = struct.unpack_from('<f', d, 52)
    hox, hoz, cell = struct.unpack_from('<3f', d, 56); W, H = struct.unpack_from('<II', d, 68)
    toff, = struct.unpack_from('<I', d, 76); ncell, coff, pvsoff, coloff = struct.unpack_from('<IIII', d, 80)
    p = 104 + W * H * 8; p += -p % 16; hm_end = p; p += W * H * 4; p += -p % 16; wall_end = p   # заголовок 104 Б (@96 propOff, @100 carOff)
    tex = []
    for _ in range(ntex):
        w, h, lv = struct.unpack_from('<HHH', d, p); fmt, pre = d[p + 6], d[p + 7]; q = p + 16 + 1024; sw = 0; lw, lh = w, h
        bpp = 4 if fmt == 4 else 8   # байт 6 = 4: CLUT4, байт 7 = 1: уже в swizzle (tools/texq.py), иначе как сейчас
        for _ in range(lv):
            rows = (lh + 7) & ~7 if pre else lh
            rb = max(16, (lw * bpp + 7) // 8) if pre else lw * bpp // 8   # правило строки движка (main.c texRowBytes)
            q += rb * rows; q += -q % 16; sw += 0 if pre else lw * bpp // 8 * ((lh + 7) & ~7); lw >>= 1; lh = max(1, lh >> 1)
        tex.append(dict(w=w, h=h, levels=lv, bytes=q - p, swz=sw, fmt=fmt)); p = q; p += -p % 16
    recs = [struct.unpack_from('<6fiIIII3ffIII', d, toff + 80 * i) for i in range(npc)]
    cells = [struct.unpack_from('<6fIIIII', d, coff + 48 * i) for i in range(ncell)]
    pvs = None
    if pvsoff and d[pvsoff:pvsoff + 4] == b'PVS1':
        pw, ph, pool = struct.unpack_from('<III', d, pvsoff + 16)
        ent = np.frombuffer(d, '<u4', pw * ph * 2, pvsoff + 32).reshape(-1, 2)
        has = ent[:, 1] != 0xFFFFFFFF
        pvs = dict(W=pw, H=ph, pool=pool, bytes=pw * ph * 8 + pool * 2, cells_with_data=int(has.sum()),
                   mean_list=float(ent[has, 1].mean()) if has.any() else 0.0, max_list=int(ent[has, 1].max()) if has.any() else 0)
    col = None
    if coloff and d[coloff:coloff + 4] == b'COL1':
        cW, cH, ntri, nbox, ncyl, nseg, nref = struct.unpack_from('<7I', d, coloff + 16)
        n = 48 + ntri * 48 + nbox * 64 + ncyl * 48 + nseg * 32 + (cW * cH + 1) * 4 + nref * 4; n += -n % 16
        col = dict(tris=ntri, boxes=nbox, cyls=ncyl, fences=nseg, refs=nref, bytes=n)
    hm = np.frombuffer(d, '<i2', W * H * 4, 104).reshape(H, W, 4)
    return dict(size=len(d), ntex=ntex, npc=npc, bbox=bb, spawn=spawn, lift=lift, hox=hox, hoz=hoz, cell=cell, W=W, H=H,
                hm=hm, hm_bytes=hm_end - 104, wall_bytes=wall_end - hm_end, tex=tex, tex_bytes=toff - wall_end,
                recs=recs, cells=cells, ncell=ncell, resident_block=coff + 48 * ncell, pvs=pvs, col=col, wall_off=hm_end)


def ground_at(S, x, z):
    gx, gz = int((x - S['hox']) / S['cell']), int((z - S['hoz']) / S['cell'])
    if not (0 <= gx < S['W'] and 0 <= gz < S['H']): return None
    h = S['hm'][gz, gx]; h = h[h != -32768]
    return (h * .01).tolist()


def streaming(S, step=8):
    """Рабочий набор клеток города вокруг точки: грузится до LOAD_DIST+r, выгружается после DROP_DIST+r.
    -> пик загруженного (при подъезде) и пик удерживаемого (гистерезис, худший случай), байты."""
    C = [c for c in S['cells'] if c[8] == 0]
    if not C: return dict(load_peak=0, hold_peak=0)
    bb = np.array([c[:6] for c in C]); size = np.array([c[10] for c in C], np.float64)
    cen = (bb[:, :3] + bb[:, 3:]) / 2; rad = .5 * np.linalg.norm(bb[:, 3:] - bb[:, :3], axis=1)
    hm = S['hm']; lp = hp = 0; at = None
    for gz in range(0, S['H'], step):
        for gx in range(0, S['W'], step):
            hs = hm[gz, gx]; hs = hs[hs != -32768]
            if not len(hs): continue
            e = np.array([S['hox'] + (gx + .5) * S['cell'], hs.min() * .01, S['hoz'] + (gz + .5) * S['cell']])
            dist = np.linalg.norm(cen - e, axis=1)
            l = size[dist < LOAD_DIST + rad].sum(); h = size[dist < DROP_DIST + rad].sum()
            if l > lp: lp, at = l, e
            hp = max(hp, h)
    return dict(load_peak=int(lp), hold_peak=int(hp), load_peak_at=[round(float(v)) for v in at] if at is not None else None)


def analyze(path):
    S = parse_shr(path)
    R = S['recs']; city = [r for r in R if r[10] == 0]; car = [r for r in R if r[10] == 1]; sky = [r for r in R if r[10] == 2]
    csz = np.array([c[10] for c in S['cells'] if c[8] == 0], np.float64)
    other = sum(c[10] for c in S['cells'] if c[8] != 0)
    swz = sum(t['swz'] for t in S['tex'])
    tx = S['tex']; sizes = {}
    for t in tx: k = f"{t['w']}x{t['h']}"; sizes[k] = sizes.get(k, 0) + 1
    res = dict(file_mb=S['size'] / 2**20, heightmap_kb=S['hm_bytes'] / 1024, walls_kb=S['wall_bytes'] / 1024,
               tex_count=S['ntex'], tex_mb=S['tex_bytes'] / 2**20, tex_swizzle_copy_mb=swz / 2**20,
               tex_sizes=dict(sorted(sizes.items(), key=lambda kv: -kv[1])[:8]),
               tables_kb=(80 * S['npc'] + 48 * S['ncell']) / 1024, engine_structs_kb=(PIECE_STRUCT * S['npc'] + 4 * S['npc'] + CELL_STRUCT * S['ncell']) / 1024,
               resident_block_mb=S['resident_block'] / 2**20, pieces=S['npc'], cells=len(csz),
               cell_kb_mean=float(csz.mean() / 1024) if len(csz) else 0, cell_kb_max=float(csz.max() / 1024) if len(csz) else 0,
               cell_kb_p95=float(np.percentile(csz, 95) / 1024) if len(csz) else 0, city_mb=float(csz.sum() / 2**20),
               car_sky_cells_kb=other / 1024,
               tris_near=sum(r[9] for r in city) // 3, tris_far=sum(r[16] for r in city) // 3,
               tris_car=sum(r[9] for r in car) // 3, tris_sky=sum(r[9] for r in sky) // 3,
               grid=f"{S['W']}x{S['H']}", bbox=[round(v, 1) for v in S['bbox']], spawn=[round(v, 3) for v in S['spawn']], lift=S['lift'],
               pvs=S['pvs'], col=S['col'])
    st = streaming(S); res['stream'] = st
    res['resident_total_mb'] = (S['resident_block'] + swz + PIECE_STRUCT * S['npc'] + 4 * S['npc'] + CELL_STRUCT * S['ncell']
                                + other + (S['pvs']['bytes'] if S['pvs'] else 0) + (S['col']['bytes'] if S['col'] else 0)) / 2**20
    res['peak_total_mb'] = res['resident_total_mb'] + st['hold_peak'] / 2**20
    sp = S['spawn']; g = ground_at(S, sp[0], sp[2]); res['spawn_ground'] = g
    # стены вокруг старта: свободный путь по курсу и против него (проверка курса)
    wl = np.frombuffer(Path(path).read_bytes(), '<i2', S['W'] * S['H'] * 2, S['wall_off']).reshape(S['H'], S['W'], 2)
    def free(h):
        for k in range(1, 200):
            x, z = sp[0] + np.sin(h) * k * .5, sp[2] + np.cos(h) * k * .5
            gx, gz = int((x - S['hox']) / S['cell']), int((z - S['hoz']) / S['cell'])
            if not (0 <= gx < S['W'] and 0 <= gz < S['H']): return k * .5
            lo, hi = wl[gz, gx] * .01
            if lo <= hi and hi > sp[1] + .45 and lo < sp[1] + 1.6: return k * .5
        return 100.0
    res['spawn_free_m'] = {f'{a:.2f}': free(a) for a in (sp[3], sp[3] + np.pi, sp[3] + np.pi / 2, sp[3] - np.pi / 2)}
    # бюджет треугольников в кадре — логика tools/budget.py (без PVS -> верхняя оценка)
    try:
        bud = load_module('st_lv_budget', ROOT / 'tools/budget.py')
        s = bud.simulate(bud.load(path)); t = s[:, 0]; i = int(t.argmax())
        res['budget'] = dict(points=len(s), median=float(np.median(t)), p90=float(np.percentile(t, 90)), p99=float(np.percentile(t, 99)),
                             max=float(t.max()), pieces_median=float(np.median(s[:, 1])), pieces_max=float(s[:, 1].max()),
                             worst=[round(float(s[i, 2])), round(float(s[i, 3])), round(float(s[i, 4]), 2)])
    except Exception as e:
        res['budget'] = dict(error=repr(e))
    if S['pvs']:
        try: res['budget_pvs'] = budget_pvs(path, S)
        except Exception as e: res['budget_pvs'] = dict(error=repr(e))
    return res


def budget_pvs(path, S, draw=115., lod=50., cone=(0.60, 0.80), step=6, cam_back=7.5, cam_up=3.2):
    """Как tools/budget.py simulate, но видимые куски города берутся из списка PVS клетки глаза (как cullCity в main.c)."""
    d = Path(path).read_bytes(); off, = struct.unpack_from('<I', d, 88)
    ox, oz, cell = struct.unpack_from('<3f', d, off + 4); pw, ph, pool = struct.unpack_from('<III', d, off + 16)
    ent = np.frombuffer(d, '<u4', pw * ph * 2, off + 32).reshape(-1, 2); P = np.frombuffer(d, '<u2', pool, off + 32 + pw * ph * 8)
    R = S['recs']; bb = np.array([r[:6] for r in R]); c = (bb[:, :3] + bb[:, 3:]) / 2
    rad = .5 * np.linalg.norm(bb[:, 3:] - bb[:, :3], axis=1); city = np.array([r[10] == 0 for r in R])
    ni = np.array([r[9] for r in R]) // 3; nf = np.array([r[16] for r in R]) // 3
    hm = S['hm']; res = []; nodata = 0
    for gz in range(0, S['H'], step):
        for gx in range(0, S['W'], step):
            hs = hm[gz, gx]; hs = hs[hs != -32768]
            if not len(hs): continue
            y = hs.min() * .01; x = S['hox'] + (gx + .5) * S['cell']; z = S['hoz'] + (gz + .5) * S['cell']
            for h in np.arange(0, 2 * np.pi, np.pi / 4):
                e = np.array([x - np.sin(h) * cam_back, y + cam_up, z - np.cos(h) * cam_back])
                f = np.array([x, y + 1.4, z]) - e; f /= np.linalg.norm(f)
                qx, qz = int(np.floor((e[0] - ox) / cell)), int(np.floor((e[2] - oz) / cell))
                cand = city.copy()
                if 0 <= qx < pw and 0 <= qz < ph and ent[qz * pw + qx, 1] != 0xFFFFFFFF:
                    s0, n = ent[qz * pw + qx]; cand = np.zeros(len(R), bool); cand[P[s0:s0 + n]] = True; cand &= city
                else: nodata += 1
                idx = np.where(cand)[0]; dv = c[idx] - e; dist = np.linalg.norm(dv, axis=1)
                fw = dv @ f; side = np.sqrt(np.maximum(0, dist ** 2 - fw ** 2))
                vis = (dist - rad[idx] <= draw) & ~(side * cone[0] - fw * cone[1] > rad[idx])
                far = dist - rad[idx] > lod
                res.append((np.where(far, nf[idx], ni[idx])[vis].sum(), vis.sum(), x, z, h))
    s = np.array(res); t = s[:, 0]; i = int(t.argmax())
    return dict(points=len(s), no_pvs_data=nodata, median=float(np.median(t)), p90=float(np.percentile(t, 90)),
                p99=float(np.percentile(t, 99)), max=float(t.max()), pieces_median=float(np.median(s[:, 1])), pieces_max=float(s[:, 1].max()),
                worst=[round(float(s[i, 2])), round(float(s[i, 3])), round(float(s[i, 4]), 2)])


def sky_color_stats(C, P):
    """C (N,3) цвета треугольников неба (вершина * текстура), P (N,3) их центры в мире ->
    цвет у горизонта (пояс 0..12°, 64 сектора азимута): дальний слой (купол-задник, он за всем: кандидат в цвет
    тумана/фона) и ближний слой (холмы/город), средний цвет зенита (верхние 10%)."""
    sc = (P.min(0) + P.max(0)) / 2
    r = np.hypot(P[:, 0] - sc[0], P[:, 2] - sc[2]); el = np.degrees(np.arctan2(P[:, 1], r))
    az = ((np.arctan2(P[:, 0] - sc[0], P[:, 2] - sc[2]) + np.pi) / (2 * np.pi) * 64).astype(int) % 64
    band = (el >= 0) & (el <= 12); far, near = [], []
    for b in range(64):
        m = np.where(band & (az == b))[0]
        if len(m): far.append(C[m[r[m].argmax()]]); near.append(C[m[r[m].argmin()]])
    hx = lambda v: '#%02x%02x%02x' % tuple(int(round(x)) for x in v)
    return dict(backdrop_horizon=hx(np.mean(far, 0)) if far else None, front_horizon=hx(np.mean(near, 0)) if near else None,
                zenith=hx(C[el >= np.percentile(el, 90)].mean(0)), sectors=len(far), tris=len(C),
                elevation_range=[round(float(el.min()), 1), round(float(el.max()), 1)])


def modulate(prims_rgb, url):
    """[(цвет вершин (N,3), центры (N,3), № текстуры, UV центров (N,2))] -> цвета с текстурой (как GU_TFX_MODULATE), центры"""
    from PIL import Image
    tc = {}; C = []
    for c, cen, t, uv in prims_rgb:
        if t >= 0 and t in url:
            if t not in tc: tc[t] = np.asarray(Image.open(ROOT / 'hit-and-run-web/public/assets' / url[t]).convert('RGB'), np.float64)
            a = tc[t]; H, W = a.shape[:2]
            c = c * a[np.floor(uv[:, 1] * H).astype(int) % H, np.floor(uv[:, 0] * W).astype(int) % W] / 255
        C.append(c)
    return np.concatenate(C), np.concatenate([p for _, p, _, _ in prims_rgb])


def sky_summary(st):
    """Имена объектов неба + цвета (sky_color_stats). Сейчас в движке один цвет на все уровни: SKY 0xffe0b070."""
    names = {k: sorted(v) for k, v in st.sky.items()}
    if not st.sky_rgb: return dict(objects=names, skyfix=st.skyfix)
    C, P = modulate(st.sky_rgb, {i: u.split('#')[0] for u, i in (st.cache or {}).items()})
    return dict(objects=names, skyfix=st.skyfix, **sky_color_stats(C, P))


def texuse_summary(st):
    """По каждой текстуре: сколько м² она покрывает в мире и плотность UV (единиц UV на метр, взвешенно по площади).
    Тексели на метр = плотность * размер текстуры -> сравнить с тем, сколько пикселей экрана даёт метр вблизи."""
    if not st.cache: return {}
    url = {i: u.split('#')[0] for u, i in st.cache.items()}; out = {}
    for t, parts in st.texuse.items():
        wa = np.concatenate([p[0] for p in parts]); ua = np.concatenate([p[1] for p in parts])
        ok = (wa > 1e-6) & (ua > 1e-12)
        if not ok.any(): continue
        dens = np.sqrt(ua[ok] / wa[ok]); w = wa[ok]; o = np.argsort(dens); cw = np.cumsum(w[o]) / w.sum()
        out[url[t]] = dict(area=float(wa.sum()), tris=int(len(wa)), car=any(p[2] for p in parts),
                           uv_per_m_p50=float(dens[o][np.searchsorted(cw, .5)]), uv_per_m_p90=float(dens[o][min(np.searchsorted(cw, .9), len(o) - 1)]),
                           uv_span=float(np.sqrt(ua.sum())))
    return out


def dup_summary(st):
    keys = {s: np.unique(np.concatenate(v)) for s, v in st.scene_keys.items() if v}
    out = []; ss = sorted(keys)
    for i, a in enumerate(ss):
        for b in ss[i + 1:]:
            n = len(np.intersect1d(keys[a], keys[b], assume_unique=True))
            if n > 50: out.append(dict(a=a, b=b, shared=int(n), share_a=round(n / len(keys[a]), 3), share_b=round(n / len(keys[b]), 3)))
    return out


def run_level(level, pvs=False, texmode=None, skyfix=True):
    d = sweep_dir(); tag = f'level{level}' + (f'_{texmode}' if texmode else '')
    out = d / f'{tag}.shr'; log = d / f'{tag}.log'
    info = level_info(level)
    buf = io.StringIO()

    class Tee(io.TextIOBase):
        def write(self, s): sys.__stdout__.write(s); buf.write(s); return len(s)
        def flush(self): sys.__stdout__.flush()
    with contextlib.redirect_stdout(Tee()):
        st, err, secs, md5 = run_export(level, out, texmode, skyfix)
    log.write_text(buf.getvalue() + ('\n' + err if err else ''))
    res = dict(level=level, texmode=texmode, skyfix=skyfix, exporter_md5=md5, export_sec=round(secs), error=err, info=info,
               sky=sky_summary(st), scene_tris=st.scene_tris, duplicates=dup_summary(st),
               vertex_luma=st.vcol[0] / max(st.vcol[1], 1), lit_materials=len(st.lit_materials),
               textures_src=dict(n=len(st.textures),
                                 over_128=sum(1 for t in st.textures.values() if max(t['w'], t['h']) > 128),
                                 le16_colors=sum(1 for t in st.textures.values() if t['colors'] <= 16),
                                 le256_colors=sum(1 for t in st.textures.values() if t['colors'] <= 256),
                                 max_side=max((max(t['w'], t['h']) for t in st.textures.values()), default=0)),
               texuse=texuse_summary(st), texsrc=st.textures,
               log_tail=[l for l in buf.getvalue().splitlines() if re.search(r'небо|градиент|коллизия|COL1|skip|ошибк|MB,', l)][-25:])
    dump = lambda: (d / f'{tag}.json').write_text(json.dumps(res, indent=1, default=lambda o: o.tolist() if hasattr(o, 'tolist') else str(o)))
    dump()   # сначала — то, что собрано при экспорте (разбор файла можно повторить: --reanalyze N)
    if not err and out.exists():
        if pvs:
            t0 = time.time()
            if not (ROOT / 'tools/pvs').exists(): res['pvs_run'] = 'tools/pvs missing'
            else:
                pvs_copy = d / f'{tag}_pvs.shr'
                r = subprocess.run([str(ROOT / 'tools/pvs'), str(out), str(pvs_copy), '--samples', '5'], capture_output=True, text=True)
                res['pvs_run'] = dict(sec=round(time.time() - t0), rc=r.returncode, tail=(r.stdout + r.stderr).strip().splitlines()[-4:])
                if r.returncode == 0: out = pvs_copy
        res['file'] = str(out)
        res.update(analyze(out))
    dump()
    print(f'== level {level}: {"FAILED" if err else "ok"} in {secs:.0f} s -> {d / (tag + ".json")}')
    return res


def sky_colors(level):
    """Быстро (без экспорта уровня): небо из l{N}_terra (с sky_patch) -> цвета для тумана/фона (sky_color_stats)."""
    pe = load_module('st_lv_psp_export_sky', ROOT / 'tools/psp_export.py')
    import convert as cv
    orig = cv.read; conv = pe.Converter(); name = f'st_lvsky{level}_terra'
    cv.read = lambda q: sky_patch(orig(q))
    try: conv.export(pe.GAME / 'art' / f'l{level}_terra.p3d', name)
    finally: cv.read = orig
    try:
        meta = json.loads((pe.OUT / f'{name}.json').read_text()); raw = (pe.OUT / f'{name}.bin').read_bytes()
        cache, blob = {}, []
        prims = pe.pack_prims(meta, raw, cache, blob, pe.is_sky)
    finally:
        for ext in ('json', 'bin'): (pe.OUT / f'{name}.{ext}').unlink(missing_ok=True)
    rgb = []
    for t, fl, Pp, UV, Cc in prims:
        c = np.stack([(Cc >> k) & 0xFF for k in (0, 8, 16)], 1).astype(np.float64).reshape(-1, 3, 3).mean(1)
        rgb.append((c, Pp.reshape(-1, 3, 3).mean(1), t, UV.reshape(-1, 3, 2).mean(1)))
    C, P = modulate(rgb, {i: u.split('#')[0] for u, i in cache.items()})
    return dict(level=level, **sky_color_stats(C, P))


def reanalyze(level):
    f = sweep_dir() / f'level{level}.json'; res = json.loads(f.read_text())
    out = Path(res.get('file') or sweep_dir() / f'level{level}.shr')
    res['file'] = str(out); res.update(analyze(out))
    f.write_text(json.dumps(res, indent=1, default=lambda o: o.tolist() if hasattr(o, 'tolist') else str(o)))
    print('reanalyzed', f)


# ---------------------------------------------------------------------------------------------------------------
def summary():
    d = sweep_dir(); rows = []
    for lv in range(1, 8):
        f = d / f'level{lv}.json'
        if f.exists(): rows.append(json.loads(f.read_text()))
    if not rows: print('no results in', d); return
    k = lambda r, *p: (lambda v: v)(eval('r' + ''.join(f'[{x!r}]' for x in p))) if r.get(p[0]) is not None else None
    print('| | ' + ' | '.join(f"L{r['level']}" for r in rows) + ' |'); print('|---' * (len(rows) + 1) + '|')
    def row(name, f):
        vals = []
        for r in rows:
            try: vals.append(f(r))
            except Exception: vals.append('—')
        print(f'| {name} | ' + ' | '.join(vals) + ' |')
    row('export', lambda r: 'FAIL' if r['error'] else f"ok, {r['export_sec']} s")
    row('file (with PVS), MB', lambda r: f"{r['file_mb']:.1f}")
    row('resident block (hm+walls+tex+tables), MB', lambda r: f"{r['resident_block_mb']:.2f}")
    row('  heightmap + walls, MB', lambda r: f"{(r['heightmap_kb'] + r['walls_kb']) / 1024:.2f}")
    row('  textures (file), MB', lambda r: f"{r['tex_mb']:.2f}")
    row('  + swizzled copy at load, MB', lambda r: f"{r['tex_swizzle_copy_mb']:.2f}")
    row('  piece+cell tables, KB', lambda r: f"{r['tables_kb']:.0f}")
    row('PVS section, MB', lambda r: f"{r['pvs']['bytes'] / 2**20:.2f}" if r['pvs'] else 'n/a')
    row('COL1 section, MB', lambda r: f"{r['col']['bytes'] / 2**20:.2f}" if r['col'] else 'n/a')
    row('resident total (engine today), MB', lambda r: f"{r['resident_total_mb']:.1f}")
    row('streamed city cells: peak loaded / held, MB', lambda r: f"{r['stream']['load_peak'] / 2**20:.1f} / {r['stream']['hold_peak'] / 2**20:.1f}")
    row('peak level RAM (resident + held cells), MB', lambda r: f"{r['peak_total_mb']:.1f}")
    row('city cells: count, mean / p95 / max KB', lambda r: f"{r['cells']}, {r['cell_kb_mean']:.0f} / {r['cell_kb_p95']:.0f} / {r['cell_kb_max']:.0f}")
    row('pieces', lambda r: f"{r['pieces']}")
    row('triangles near / far', lambda r: f"{r['tris_near'] / 1e3:.0f}k / {r['tris_far'] / 1e3:.0f}k")
    row('sky tris / car tris', lambda r: f"{r['tris_sky']} / {r['tris_car']}")
    row('textures: count', lambda r: f"{r['tex_count']}")
    row('budget tris/frame (no PVS) median / p99 / max', lambda r: f"{r['budget']['median'] / 1e3:.1f}k / {r['budget']['p99'] / 1e3:.1f}k / {r['budget']['max'] / 1e3:.1f}k")
    row('budget with PVS median / p99 / max', lambda r: f"{r['budget_pvs']['median'] / 1e3:.1f}k / {r['budget_pvs']['p99'] / 1e3:.1f}k / {r['budget_pvs']['max'] / 1e3:.1f}k")
    row('PVS 5x5: time, mean / max list', lambda r: f"{r['pvs_run']['sec']} s, {r['pvs']['mean_list']:.0f} / {r['pvs']['max_list']}" if r.get('pvs') else '—')
    row('spawn (locator)', lambda r: '{:.1f}, {:.1f}, {:.1f} h {:.2f}'.format(*r['spawn']))
    row('player car (leveli.mfk)', lambda r: r['info']['spawn']['car'])
    row('vertex luma (0-255)', lambda r: f"{r['vertex_luma']:.0f}")
    row('sky objects', lambda r: ', '.join(sorted({n for v in r['sky']['objects'].values() for n in v})) + (' (added)' if r['sky'].get('skyfix') else ''))
    row('sky at horizon: backdrop / front, zenith', lambda r: f"{r['sky']['backdrop_horizon']} / {r['sky']['front_horizon']}, {r['sky']['zenith']}")


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='SHR7 sweep over levels 1..7 (scratch only)')
    ap.add_argument('--level', type=int, action='append')
    ap.add_argument('--pvs', action='store_true', help='run tools/pvs --samples 5 on the scratch copy')
    ap.add_argument('--tex', choices=['texq'], help='texture path: tools/texq.load_tex instead of psp_export.load_tex')
    ap.add_argument('--stock-sky', action='store_true', help='do not add the sky of levels 2-7 (exporter as is)')
    ap.add_argument('--summary', action='store_true')
    ap.add_argument('--info', type=int)
    ap.add_argument('--sky', type=int, action='append', help='quick sky colours of level N (fog/clear colour candidates)')
    ap.add_argument('--reanalyze', type=int, action='append', help='re-run the file analysis on an existing levelN.shr/json')
    a = ap.parse_args()
    if a.info: print(json.dumps(level_info(a.info), indent=1, default=str))
    for lv in a.sky or []: print(sky_colors(lv))
    for lv in a.level or []: run_level(lv, a.pvs, a.tex, not a.stock_sky)
    for lv in a.reanalyze or []: reanalyze(lv)
    if a.summary: summary()
