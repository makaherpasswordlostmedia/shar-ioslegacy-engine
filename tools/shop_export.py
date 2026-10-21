#!/usr/bin/env python3
"""Лавка продавца машин (пункт 6 ведущего 29.09): экран PurchaseRewards.scr оригинала -> пакеты порта.

  build/shop.shr          UIP1 (формат ui.shr; рисует viewer/ui.c uiScr*, открывается только на время лавки):
                          экран 0 purchase = страницы PurchaseRewards.scr из данных (ingame.p3d: Rewards.pag, Coins.pag,
                          Cancel.pag, Buy.pag, IrisCover.pag — последняя пуста), раскладка 16:9 — правила tools/ui_export.py
  build/reward-<k>.shr    FE1 (формат fe.shr; рисует viewer/frontend3d.c): сцена подиума rewardbg.p3d (шторы, колонны, пол) +
                          rewardfg.p3d (подиум, тень) + модель машины art/cars/<car>.p3d на подиуме; файл на каждую машину на
                          продажу уровня (BindReward «forsale», car), k — её номер по порядку (= ROW0; уровень 1: 0 Plow King,
                          1 Duff Truck, 2 Surveillance Van)

Данные (диск Роба, только чтение; hit-and-run-web/tools — MIT):
  scripts/missions/rewards.mfk  BindReward(имя, p3d, car|skin, quest, уровень, цена, продавец): машины на продажу уровня по
                                порядку файла — тот же порядок, что каталог рантайма (viewer/shop.c, пакет миссий)
  text bible (srr2.p3d)         имя машины — ключ имени прописными (PLOWK_V «Plow King»), COINS «coins», TO_PURCHASE,
                                VIEW_STATS / VIEW_MODEL «Show Stats» / «Hide Stats», PURCHASE, CANCEL
  rewardbg.p3d                  Pedestal_MasterController (121 кадр, 30 к/с): CAM_Pedestal_Camera облетает подиум по кругу
                                (радиус 8.19 м), STRN_group2 поворачивает сцену ровно на тот же угол (ключи 0/60/81/120,
                                сферическая интерполяция). Шторы стоят в кадре, крутится машина: оборот 121/30 = 4.03 с
                                (запись PS2 14:05–14:08: 90° ≈ 1.05 с). В осях сцены это: камера неподвижна (кадр 0), машина и
                                подиум (rewardfg — в мировых осях) поворачиваются на −угол group2 — одна дорожка FE1 (цикл)

Экран purchase (поля и метки; то же в viewer/shop_view.c):
  ROW0      номер машины среди машин на продажу уровня -> PreviewName (имя) и Price («150 coins»): варианты строк
  ROW1      ToggleView: 0 «Show Stats», 1 «Hide Stats»
  ROW4..7   звёзды Speed, Acceleration, Toughness, Stability («HANDLING») в полузвёздах 0..10 (SetCarAttributes × 2 — код);
            звезда k (0..4) — кадры [grey × (2k+1), half, full]: ui.c берёт кадр = значение поля и прижимает к последнему
  метки     GAMBLE — «to purchase» и цена (машина не куплена); STREETRACE — затемнение StatsOverlay и звёзды («Show Stats»);
            SKIP — стрелки ◄ ► (у продавца больше одной машины); COINS — счёт монет (Coins.pag)
  PreviewLightCover (чёрная шторка «свет выключен») в пакет не идёт: её прозрачность меняет код по времени (затемнение
  при входе/выходе, запись PS2), рисует viewer/shop_view.c тем же чёрным во весь экран
Правила порта (данных нет): свет машины на подиуме — то же правило, что у машины игрока в городе (tools/psp_export.py CAR_SUN,
CAR_AMB, CAR_DIF), низ машины на верху подиума (rewardfg pedgeo, y 0.119).

    python tools/shop_export.py [--level N] [--out-dir build]    # shop.shr + reward-<k>.shr (+ макет build/ui/shop_purchase.png)
    python tools/shop_export.py --check [--out-dir build]        # гейт: числа файлов = данным диска
Отрицательные контроли гейта (SHOP_PLANT): nlerp (поворот ключей group2 линейно, как FE.qsample — камера в осях сцены
«плывёт»), stars (звёзды без сдвига кадров), order (машины в обратном порядке)
"""
import argparse, math, os, re, struct, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import ui_export as U              # noqa: E402  Scrooby, раскладка 16:9, пакет UIP1
import frontend3d_export as FE     # noqa: E402  сцена Pure3D -> FE1 (текстуры, меши, свет, билборды)
import texq                        # noqa: E402
from p3d import read, string       # noqa: E402  (MIT)

GAME = ROOT / 'hit-and-run-web/source/game'
PLANT = os.environ.get('SHOP_PLANT', '')
SCREEN = 'purchase'
PED_TOP_NAME = 'pedgeoShape'       # rewardfg: подиум; машина ставится низом на его верх
TURN_ANIM, TURN_GROUP, CAM_ANIM = 'STRN_group2', 'group2', 'CAM_Pedestal_Camera'
STAR_ROWS = {'Spe_Stars': 4, 'Acc_Stars': 5, 'Tou_Stars': 6, 'Sta_Stars': 7}   # ROW4..7: скорость, разгон, прочность, управление
TAG_LOCKED, TAG_STATS, TAG_ARROWS = 'GAMBLE', 'STREETRACE', 'SKIP'
# правка Роба 470 (10.10): у повреждённой машины в будке — картинка повреждённой (cars2d/<имя>d.p3d). PHONE_DAMAGED_PIC_OLD=1 — как было (одна картинка)
PHONE_DAMAGED_PIC = os.environ.get('PHONE_DAMAGED_PIC_OLD') != '1'
TAG_SPOT = 'WASPS'   # №557: свечение под картинкой машины (Spotlight) — своя метка, движок прячет его под 3D-остовом (viewer/phone_view.c PV_T_SPOT)
TAG_PIC_OK, TAG_PIC_DMG = 'CARDS', 'PROXIMITY'   # метки HUD на экране будки свободны
# №697/№569 (Роб 17.10: «показывалась загоревшая машина, одна и та же на всех, в три четверти, как они все стоят»): у машины, разбитой целиком
# (100 %, ремонт за монеты), — родная картинка сгоревшего каркаса husk.png пакета ingame.p3d (119×88, одна на все машины), в размер силуэта этой машины.
# PHONE_HUSKPIC_OLD=1 — прежнее: картинка повреждённой машины cars2d/<машина>d.p3d
PHONE_HUSKPIC = os.environ.get('PHONE_HUSKPIC_OLD') != '1'
TAG_DAMAGE, PHONE_ROW_DMG = 'DAMAGE', 1   # будка: «Damaged: N %» (метка HUD DAMAGE на этом экране свободна), ROW1 = viewer/phone_view.c PV_ROW_DMG
# пункт ДОБИВКИ 26 (запись PS2 ps2_v105_booth_access): у закрытой машины подсказки Accept нет, только Back — Accept.pag под меткой
# ACTION (на экране будки свободна; viewer/phone_view.c PV_T_ACCEPT, menu_access.h boothShowAccept). PHONE_ACCEPT_OLD=1 — без метки
TAG_ACCEPT = None if os.environ.get('PHONE_ACCEPT_OLD') == '1' else 'ACTION'


# ---------------------------------------------------------------- каталог уровня
def forsale(level):
    """машины на продажу уровня по порядку rewards.mfk -> [(имя, цена, продавец)]"""
    txt = re.sub(r'//[^\n]*', '', (GAME / 'scripts/missions/rewards.mfk').read_text(errors='replace'))
    out = []
    for m in re.finditer(r'BindReward\s*\(([^)]*)\)', txt):
        a = [x.strip().strip('"') for x in m.group(1).split(',')]
        if len(a) >= 7 and a[2] == 'car' and a[3] == 'forsale' and int(a[4]) == level:
            out.append((a[0], int(a[5]), a[6]))
    return out[::-1] if PLANT == 'order' else out


# ---------------------------------------------------------------- экран purchase (UIP1)
def screen_pages():
    return [('ingame.p3d', pg) for pg in U.project('ingame.p3d').screens['PurchaseRewards.scr']]


def items_for(cars):
    bible = U._BIBLE or U.load_bible(U.LANG)
    names = [bible(c.upper()) or c for c, _, _ in cars]
    prices = ['%d %s' % (p, bible('COINS') or 'coins') for _, p, _ in cars]
    its, _ = U.build_items(SCREEN)
    out = []
    for it in its:
        nm, path = it['name'], it['path']
        if nm in ('PreviewLightCover', 'PreviewNameDummy'):
            continue                                              # шторка света — код; пустышка имени (прозрачная)
        if 'VehicleStats' in path:
            it['tag'] = TAG_STATS
        if 'Foreground/Locked' in path:
            it['tag'] = TAG_LOCKED
        if 'Foreground/Arrows' in path:
            it['tag'] = TAG_ARROWS
        if it['type'] == U.T_TEXT and nm == 'PreviewName':
            it.update(strings=names, field='ROW0', fmt='select', sel=0)
        elif it['type'] == U.T_TEXT and nm == 'Price':
            it.update(strings=prices, field='ROW0', fmt='select', sel=0)
        elif it['type'] == U.T_TEXT and nm == 'ToggleView':
            it.update(field='ROW1', fmt='select', sel=0)
        elif it['type'] == U.T_IMG and path.split('/')[-1] in STAR_ROWS:
            k = int(nm[-1]); g, h, f = it['frames'][:3]          # greystar, halfstar, carstar
            it['frames'] = [g, h, f] if PLANT == 'stars' else [g] * (2 * k + 1) + [h, f]
            it['field'] = 'ROW%d' % STAR_ROWS[path.split('/')[-1]]
        out.append(it)
    return out


def ui_pack(cars, out):
    U.SCREEN_PAGES[SCREEN] = screen_pages()

    def build(sc, assets, fonts):
        dl, _ = U.adapt(items_for(cars), {}, 'psp', assets, fonts)
        return dl
    spec = dict(screens=[SCREEN], build=build, tags={SCREEN: {'ALWAYS'}}, group=lambda k: 'ui', radar=False,
                groups=('ui',), layout='layout_shop.json')
    res = U.pack(out, spec)
    try:   # макет для глаза: первая машина, звёзды 3.5, «Show Stats», всё видно
        from PIL import Image
        dl = res['screens'][SCREEN]
        st = {'show': {'ALWAYS', 'COINS', TAG_LOCKED, TAG_STATS, TAG_ARROWS}, 'ROW0': 0, 'ROW1': 1, 'COINS': 151}
        for r in range(4, 8): st['ROW%d' % r] = 7
        img = U.render(dl, U.DST_W, U.DST_H, st, res['qbitmaps'], Image.new('RGBA', (U.DST_W, U.DST_H), (90, 20, 20, 255)), None, 0)
        U.OUTDIR.mkdir(parents=True, exist_ok=True); img.save(U.OUTDIR / 'shop_purchase.png')
    except Exception as e:   # макет необязателен
        print('  макет не нарисован:', e)
    return res


# ---------------------------------------------------------------- сцена подиума (FE1)
def slerp(a, b, u):
    d = float(np.dot(a, b))
    if d < 0: b, d = -b, -d
    if d > 0.9995: q = a + (b - a) * u
    else:
        th = math.acos(min(1., d)); q = (math.sin((1 - u) * th) * a + math.sin(u * th) * b) / math.sin(th)
    return q / np.linalg.norm(q)


def qkey(fr, v, f):
    """кватернион канала ROT на кадре f: между ключами — сферически (Pure3D), SHOP_PLANT=nlerp — линейно (FE.qsample)"""
    if PLANT == 'nlerp': return FE.qsample(fr, v, f)
    if len(fr) == 1 or f <= fr[0]: return v[0] / np.linalg.norm(v[0])
    if f >= fr[-1]: return v[-1] / np.linalg.norm(v[-1])
    i = int(np.searchsorted(fr, f, 'right')) - 1
    return slerp(np.array(v[i], np.float64), np.array(v[i + 1], np.float64), (f - fr[i]) / (fr[i + 1] - fr[i]))


def turntable(bg):
    """-> (кадров, к/с, [строчная 4x4 игры: поворот круга в осях сцены на кадре f], камера в осях сцены по кадрам (N, 12))"""
    A = FE.anims(bg)
    typ, nfr, fps, groups = A[TURN_ANIM]; ch = groups[TURN_GROUP]
    ctyp, cn, cfps, cg = A[CAM_ANIM]; cc = cg[CAM_ANIM]
    assert (nfr, fps) == (cn, cfps), (nfr, fps, cn, cfps)
    mats, cams = [], []
    for f in range(nfr):
        R = FE.row_from_qt(qkey(*ch['ROT'], f), np.zeros(3))[:3, :3]     # p_мир = p_сцена · R
        Ri = R.T                                                           # p_сцена = p_мир · R⁻¹
        M = np.eye(4); M[:3, :3] = Ri; mats.append(M)
        pos = FE.sample(*cc['TRAN'], f) @ Ri; look = FE.sample(*cc['LOOK'], f) @ Ri; up = FE.sample(*cc['UP'], f) @ Ri
        look = look / np.linalg.norm(look); up = up / np.linalg.norm(up)
        cams.append(np.r_[pos, look, up, FE.sample(*cc['FOV'], f)[0], FE.sample(*cc['NCLP'], f)[0], FE.sample(*cc['FCLP'], f)[0]])
    return nfr, fps, mats, np.array(cams)


def car_tris(car, place):
    """модель машины (конвертер hit-and-run-web, как машина игрока tools/psp_export.car_prims) -> треугольники FE (оси
    зеркальные), текстуры PIL. place — сдвиг (зеркальные оси). Свет — правило машины в городе (CAR_SUN/AMB/DIF)"""
    import json
    import psp_export as pe
    from convert import Converter, GAME as CGAME   # путь диска конвертера (без ссылки worktree)
    from PIL import Image
    cv = Converter(); nm = 'shop_car_%s_%d' % (car.lower(), os.getpid())   # номер процесса: параллельные экспорты не делят файл
    cv.export(CGAME / 'art' / 'cars' / f'{car}.p3d', nm, vehicle=True)
    meta = json.loads((pe.OUT / f'{nm}.json').read_text()); raw = (pe.OUT / f'{nm}.bin').read_bytes()
    for ext in ('json', 'bin'): (pe.OUT / f'{nm}.{ext}').unlink()
    tris, tex = [], {}
    for obj in meta['objects']:
        M = np.array(obj['matrix'], np.float64).reshape(4, 4)
        for prim in meta['meshes'].get(obj['mesh'], []):
            at = prim['attributes']
            g = lambda k, w: np.frombuffer(raw, '<f4', at[k][1], at[k][0]).reshape(-1, w).astype(np.float64)
            pos, uv = g('position', 3), g('uv', 2)
            idx = np.frombuffer(raw, '<u4', at['indices'][1], at['indices'][0]).astype(np.int64)
            P = (np.c_[pos, np.ones(len(pos))] @ M)[:, :3]
            if 'normal' in at: N = g('normal', 3) @ M[:3, :3]
            else:
                N = np.zeros_like(P); T = P[idx].reshape(-1, 3, 3); fn = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
                for k in range(3): np.add.at(N, idx.reshape(-1, 3)[:, k], fn)
            N = N / np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-9)
            k = np.clip(pe.CAR_AMB + pe.CAR_DIF * np.maximum(N @ pe.CAR_SUN, 0) + 0.08 * N[:, 1], 0, 1)
            C = np.c_[k, k, k, np.ones(len(k))]
            mat = meta['materials'].get(prim['shader'], {}); url = mat.get('textureUrl', '')
            fl = (FE.F_ATEST if mat.get('alpha') else 0) | (FE.F_BLEND if mat.get('translucent') or mat.get('blend') else 0)
            if (fl & FE.F_BLEND) and not (fl & FE.F_ATEST): fl |= FE.F_NOZW
            tname = ''
            if url:
                tname = 'car:' + url
                if tname not in tex: tex[tname] = Image.open(pe.ASSETS / url).convert('RGBA')
            T = idx.reshape(-1, 3)
            tris.append(dict(P=P[T] + place, UV=uv[T], C=C[T], tex=tname, flags=fl, node=0xffff, vis=0xffff, texTrack=0xffff,
                             shader=prim['shader']))
    return tris, tex


def reward_scene(car, out_path):
    texq.CAP, texq.CLUT4, texq.PRESWIZZLE, texq.SMALL_MIPS = 256, False, True, True   # закон 1: как уровень
    bg, fg = read(FE.PU / 'rewardbg.p3d'), read(FE.PU / 'rewardfg.p3d')
    sc = FE.Scene()
    for r in (bg, fg):
        FE.load_textures(sc, r)
        for k, v in FE.shaders_of(r).items(): sc.shaders.setdefault(k, v)
    lights = dict(dir=[], ambient=np.zeros(3), raw=[])                     # Pedestal_LightGroup: три направленных
    for c in bg.children:
        if c.id != 0x13000: continue
        n, p = string(c.data); ver, typ, colr = struct.unpack_from('<3I', c.data, p)
        d = next(np.frombuffer(s.data, '<f4', 3).astype(np.float64) for s in c.children if s.id == 0x13001)
        L = -d * [1, 1, -1]; L /= np.linalg.norm(L); lights['dir'].append((L, FE.argb(colr)[:3])); lights['raw'].append((n, L, colr))
    nfr, fps, mats, cams = turntable(bg)
    # сцена стоит (в своих осях): узел group2 без дорожки — анимацию STRN_group2 отдаём дорожке круга ниже
    orig = FE.anims
    FE.anims = lambda root: {k: v for k, v in orig(root).items() if k not in (TURN_ANIM, CAM_ANIM)}
    try:
        FE.scene_file(sc, 'rewardbg', bg, lights, (1, 0), None)
        n0 = len(sc.tris)
        FE.scene_file(sc, 'rewardfg', fg, lights, (1, 0), None)
    finally:
        FE.anims = orig
    # дорожки круга: подиум и машина (мир) в осях сцены — поворот R⁻¹(f). Таймлайн FE1 (часы — перелёты frontend3d.c, feFly):
    # кадры 0..120 — оборот с машиной, 121..241 — тот же оборот без неё (машина в точку); viewer/shop_view.c крутит нужный
    # отрезок по кругу. Прятать машину кодом (тёмная сцена до света, «уехала» после покупки) — только так, без правки frontend3d.c
    T = 2 * nfr
    rot = [FE.col(M)[:3, :4].astype('<f4').tobytes() for M in mats]
    tt = sc.add_track(FE.T_MAT, T, fps, FE.TR_TIMELINE, b''.join(rot[f % nfr] for f in range(T)))
    tc = sc.add_track(FE.T_MAT, T, fps, FE.TR_TIMELINE, b''.join(rot) + bytes(48 * nfr))
    ped = [t for t in sc.tris[n0:]]
    for t in ped: t['node'] = tt
    top = max(float(t['P'][:, :, 1].max()) for t in ped if t['shader'].startswith('carped'))
    ctris, ctex = car_tris(car, np.zeros(3))
    lo = float(min(t['P'][:, :, 1].min() for t in ctris))                 # низ модели в позе покоя
    place = np.array([0., top - lo - (0.5 if PLANT == 'lift' else 0.), 0.])
    for t in ctris: t['P'] = t['P'] + place; t['node'] = tc
    sc.tris += ctris
    for k, im in ctex.items(): sc.tex[k] = im; sc.tex_order.append(k)
    # камера: в осях сцены одна поза (кадр 0); сверка — все кадры облёта в пределах допуска (гейт --check)
    cam0 = cams[0]
    camrows = struct.pack('<12f', *(cam0[:3] * [1, 1, -1]), *(cam0[3:6] * [1, 1, -1]), *(cam0[6:9] * [1, 1, -1]), *cam0[9:12])
    view = FE.view_of(np.r_[cam0[:3] * [1, 1, -1], cam0[3:6] * [1, 1, -1], cam0[6:9] * [1, 1, -1], cam0[9:12]])
    VA = tuple(np.array([v]) for v in view)
    flights = [(0, 0, nfr - 1), (1, nfr, T - 1)]              # перелёт 0 — оборот с машиной, 1 — без неё (shop_view.c)
    return write_fe1(sc, out_path, camrows * T, fps, VA, T, nfr, flights), \
        dict(frames=nfr, fps=fps, cam_drift=cam_drift(cams), car_tris=sum(len(t['P']) for t in ctris), top=top, lift=float(place[1]))


def cam_drift(cams):
    """насколько камера в осях сцены уходит от кадра 0 за облёт: (м, градусы направления)"""
    dp = float(np.abs(cams[:, :3] - cams[0, :3]).max())
    ang = max(math.degrees(math.acos(float(np.clip(np.dot(c[3:6], cams[0, 3:6]), -1, 1)))) for c in cams)
    return dp, ang


def write_fe1(sc, out_path, camrows, fps, VA, nframes, menu, flights):
    """FE1 (шапка tools/frontend3d_export.py): без Гомера; камера — nframes одинаковых кадров, стартовый кадр menu;
    перелёты FLT1 [(номер, кадр от, кадр до)] — только «туда»"""
    used = {t['tex'] for t in sc.tris} | {b['tex'] for b in sc.bills}
    names = [n for n in sc.tex_order if n in used]
    missing = sorted(u for u in used if u and u not in sc.tex); assert not missing, missing
    tidx = {n: i for i, n in enumerate(names)}
    groups, src_total, added = {}, 0, 0
    for t in sc.tris:
        n = len(t['P']); src_total += n
        need = FE.need_split(t['P'], VA) if t['node'] == 0xffff else np.zeros(n, bool)
        for k in range(n):
            if need[k]:
                tri, a = FE.split_near(t['P'][k], t['UV'][k], t['C'][k], VA); added += a
            else: tri = [(t['P'][k], t['UV'][k], t['C'][k])]
            cen = t['P'][k].mean(0)
            cell = tuple(int(math.floor(x / FE.CELL)) for x in cen)
            key = (tidx.get(t['tex'], 0xffff), t['texTrack'], t['flags'], t['node'], t['vis']) + cell
            g = groups.setdefault(key, dict(P=[], UV=[], C=[], src=0)); g['src'] += 1
            for pp, u, c in tri: g['P'].append(pp); g['UV'].append(u); g['C'].append(c)
    blob = bytearray(128)

    def add(data, a=16):
        while len(blob) % a: blob.append(0)
        o = len(blob); blob.extend(data); return o
    trec = bytearray()
    for n in names:
        data, levels, pal, fmt = texq.build(sc.tex[n], 256, 'kmeans', False, True)
        w, h, nlev = struct.unpack_from('<HHH', data, 0)
        oc = add(data[16:16 + 1024]); body = data[16 + 1024:]
        offs, bufw = [], []; lw, lh, o = w, h, 0
        for l in range(nlev):
            rb = max(lw, 16); sz = rb * ((lh + 7) & ~7); sz += -sz % 16
            offs.append(o); bufw.append(rb); o += sz; lw, lh = max(1, lw // 2), max(1, lh // 2)
        assert o == len(body), (n, o, len(body))
        ob = add(body)
        offs = [ob + x for x in offs] + [0] * (8 - nlev); bufw = bufw + [0] * (8 - nlev)
        trec += struct.pack('<HHB3xI8I8HI', w, h, nlev, oc, *offs, *bufw, 0)
    offTex = add(bytes(trec))
    offNames = add(b''.join(n.encode('latin1')[-31:].ljust(32, b'\0') for n in names))
    tr_rec = bytearray()
    for typ, nf, tfps, fl, data in sc.tracks:
        o = add(data); tr_rec += struct.pack('<IIfII3I', typ, nf, tfps, fl, o, 0, 0, 0)
    offTrack = add(bytes(tr_rec))
    prec = bytearray()
    for key in sorted(groups):
        g = groups[key]; P = np.array(g['P']).reshape(-1, 3); UV = np.array(g['UV']).reshape(-1, 2); C = np.array(g['C']).reshape(-1, 4)
        lo, hi = P.min(0), P.max(0); origin = (lo + hi) / 2; scale = max(float((hi - lo).max() / 2), 1e-3) * 1.0001
        ov = add(FE.pack_verts(P, UV, C, origin, scale))
        tex, ttr, fl, node, vis = key[:5]
        prec += struct.pack('<6H2I4f6fI', tex, ttr, fl, node, vis, 0, len(P), ov, *origin, scale, *lo, *hi, g['src'])
    offPiece = add(bytes(prec))
    brec = bytearray()
    for b in sc.bills:
        c8 = np.clip(np.round(b['col'] * 255), 0, 255).astype(int)
        abgr = int(c8[0] | (c8[1] << 8) | (c8[2] << 16) | (c8[3] << 24))
        brec += struct.pack('<3H2B2fI12f12x', b['track'], tidx.get(b['tex'], 0xffff), b['flags'], b['mode'], b['glow'], b['w'], b['h'],
                            abgr, *b['m'].flatten())
    offBill = add(bytes(brec))
    offCam = add(camrows)
    lrec = bytearray(40)                                   # свет Гомера меню — не нужен (Гомера нет)
    offLights = add(bytes(lrec))
    frec = b''.join(struct.pack('<BBHHHHHf', it, 0, 0, a, b, 0, 0, 0.) for it, a, b in flights)
    offFlt = add(frec)
    while len(blob) % 16: blob.append(0)
    offHomer = len(blob)                                   # Гомера нет: пустой кусок в конце (frontend3d.c: homerOk = 0)
    blob.extend(struct.pack('<4sIII', b'FLT1', offFlt, len(flights), 0))
    hdr = struct.pack('<4s11I', b'FE1\0', 1, len(blob), len(names), offTex, len(groups), offPiece, len(sc.tracks), offTrack,
                      len(sc.bills), offBill, nframes)
    hdr += struct.pack('<IIfII12fIII', offCam, menu, fps, offHomer, 0, *np.eye(4)[:3].flatten(), offLights, src_total, offNames)
    hdr += bytes(128 - len(hdr))
    blob[:128] = hdr
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_bytes(bytes(blob))
    return dict(size=len(blob), tex=len(names), pieces=len(groups), tris=src_total, split=added, bills=len(sc.bills), tracks=len(sc.tracks))


# ---------------------------------------------------------------- гейт: файлы против данных
def read_uip1(path):
    """UIP1 -> (элементы экрана 0: dict type, tag, field, fmt, count, strings, flags), строки"""
    b = Path(path).read_bytes()
    h = struct.unpack_from('<4sI20I', b, 0)
    assert h[0] == b'UIP1', h[0]
    nitem, offItem, nscreen, offScreen, nstr, offStr = h[4], h[5], h[6], h[7], h[10], h[11]
    offs = struct.unpack_from('<%dI' % nstr, b, offStr)
    strs = [b[o:b.index(b'\0', o)].decode('latin-1') for o in offs]
    first, count, nmenu, tags = struct.unpack_from('<4I', b, offScreen)
    out = []
    for i in range(first, first + count):
        r = struct.unpack_from('<8B4h2I4B2H3fIf3I', b, offItem + 64 * i)
        ty, _, tag, field, fmt = r[:5]; sfirst, scount = r[18], r[19]
        out.append(dict(type=ty, tag=U.TAGS[tag], field=U.FIELDS[field], fmt=fmt, first=sfirst, count=scount,
                        strings=strs[sfirst:sfirst + scount] if ty == U.T_TEXT else [], rect=r[8:12]))
    return out


def read_fe1(path):
    b = Path(path).read_bytes()
    h = struct.unpack_from('<4s11I', b, 0); h2 = struct.unpack_from('<IIfII12fIII', b, 48)
    assert h[0] == b'FE1\0' and h[2] == len(b)
    ntr, offTr, nfr, offCam = h[7], h[8], h[11], h2[0]
    tracks = [struct.unpack_from('<IIfII3I', b, offTr + 32 * i) for i in range(ntr)]
    pieces = [struct.unpack_from('<6H2I4f6fI', b, h[6] + 64 * i) for i in range(h[5])]
    cams = np.frombuffer(b, '<f4', 12 * nfr, offCam).reshape(nfr, 12)
    flt = []
    if b[-16:-12] == b'FLT1':
        o, n = struct.unpack_from('<II', b, len(b) - 12)
        flt = [struct.unpack_from('<BBHHHHHf', b, o + 16 * i) for i in range(n)]
    return dict(b=b, tracks=tracks, pieces=pieces, frames=nfr, menu=h2[1], cams=cams, flights=flt, size=len(b))


def track_rows(f, t):
    """строки дорожки T_MAT: (кадров, 3, 4)"""
    return np.frombuffer(f['b'], '<f4', 12 * t[1], t[4]).reshape(t[1], 3, 4)


def check(out_dir, level):
    cars = forsale(level); bible = U.load_bible(U.LANG); bad = 0

    def res(name, ok, info):
        nonlocal bad
        print('CHECK %-12s %s  %s' % (name, 'OK  ' if ok else 'FAIL', info)); bad += not ok
    its = read_uip1(Path(out_dir) / 'shop.shr')
    txt = {tuple(t['strings']) for t in its if t['type'] == U.T_TEXT and t['field'] == 'ROW0'}
    true_n = tuple(bible(c.upper()) for c, _, _ in forsale_file_order(level))   # порядок файла rewards.mfk = каталог рантайма
    true_p = tuple('%d coins' % p for _, p, _ in forsale_file_order(level))
    res('names', true_n in txt, 'имена ROW0 %s (данные: %s)' % (sorted(txt), true_n))
    res('prices', true_p in txt, 'цены ROW0 (данные: %s)' % (true_p,))
    stars = [t for t in its if t['type'] == U.T_IMG and t['field'].startswith('ROW') and 4 <= int(t['field'][3:]) <= 7]
    per = {}
    for t in stars: per.setdefault(t['field'], []).append(t['count'])
    okst = len(stars) == 20 and all(sorted(v) == [3, 5, 7, 9, 11] for v in per.values())
    res('stars', okst, 'звёзд %d, кадров по строкам %s (нужно 3,5,7,9,11 — сдвиг на полузвезду)' % (len(stars), {k: sorted(v) for k, v in per.items()}))
    tags = {}
    for t in its: tags[t['tag']] = tags.get(t['tag'], 0) + 1
    res('tags', tags.get(TAG_LOCKED, 0) == 2 and tags.get(TAG_STATS, 0) == 25 and tags.get(TAG_ARROWS, 0) == 2 and tags.get('COINS', 0) >= 1,
        'метки %s (цена 2; затемнение 1 + звёзд 20 + подписей 4; стрелки 2; монеты)' % tags)
    # сцены
    bg = read(FE.PU / 'rewardbg.p3d'); nfr, fps, mats, cams = turntable(bg)
    dp, da = cam_drift(cams)
    res('camera', dp < 0.02 and da < 0.5, 'камера облёта в осях сцены: уход %.3f м, %.2f° за %d кадров (стоит на месте)' % (dp, da, nfr))
    for k, (c, _, _) in enumerate(forsale_file_order(level)):
        p = Path(out_dir) / ('reward-%d.shr' % k)
        if not p.exists():
            res('scene', False, '%s: нет файла' % p); continue
        f = read_fe1(p); T = 2 * nfr
        tls = [i for i, t in enumerate(f['tracks']) if t[0] == FE.T_MAT and t[3] == FE.TR_TIMELINE and t[1] == T and abs(t[2] - fps) < 1e-6]
        rows = {i: track_rows(f, f['tracks'][i]) for i in tls}
        car = [i for i in tls if np.abs(rows[i][nfr:]).max() == 0.]           # машина: во второй половине таймлайна её нет
        ped = [i for i in tls if i not in car]
        ok = len(car) == 1 and len(ped) == 1
        steps = np.zeros(1)
        if ok:
            R = rows[ped[0]]
            ang = [math.degrees(math.atan2(R[k, 0, 2], R[k, 0, 0])) for k in range(nfr)]   # оборот: шаг ровный (сферически)
            steps = np.degrees(np.abs(np.diff(np.unwrap(np.radians(ang)))))
            ok = float(steps.max() - steps.min()) < .5 and np.allclose(R[:nfr], R[nfr:]) and np.allclose(rows[car[0]][:nfr], R[:nfr])
        cam_same = bool(np.abs(f['cams'] - f['cams'][0]).max() < 1e-6) and f['frames'] == T
        fl = sorted((x[0], x[3], x[4]) for x in f['flights'])
        on = [pc for pc in f['pieces'] if car and pc[3] == car[0]]
        res('scene', ok and cam_same and f['menu'] == nfr and fl == [(0, 0, nfr - 1), (1, nfr, T - 1)] and len(on) > 3,
            '%s: %.0f КБ, таймлайн %d кадров @ %g, оборот шаг %.2f..%.2f°, кусков машины %d, старт без машины %s, перелёты %s'
            % (c, f['size'] / 1024, f['frames'], fps, steps.min(), steps.max(), len(on), f['menu'] == nfr, fl))
    print('shop check: %s' % ('PASS' if not bad else 'FAIL (%d)' % bad))
    return bad


def forsale_file_order(level):
    global PLANT
    keep = PLANT; PLANT = ''
    try: return forsale(level)
    finally: PLANT = keep


# ---------------------------------------------------------------- телефонная будка (правка Роба 94, 30.09)
# Экран PhoneBooth.scr оригинала (ingame.p3d: PhoneBooth.pag, Coins.pag, CarSelect.pag, Back.pag, Accept.pag): галерея машин —
# имя, звёзды, стрелки, замок «LEVEL n» у ещё не полученной, Accept / Back. Сцена машины — тот же подиум, что у лавки
# (reward_scene): build/pcar-<k>.shr, k — номер машины среди машин-наград уровня по порядку rewards.mfk (уровень 1: famil_v,
# cletu_v, elect_v, plowk_v, cDuff, cVan). Сведения о повреждении (DamagedInfo) — не рисуются (ПРАВИЛО ПОРТА)
PHONE = 'phone'


def phone_cars(level):
    """галерея будки (правка Роба 94/100): машины-награды уровня по порядку rewards.mfk, затем AddVehicleSelectInfo уровня
    (level.mfk: машины персонажей, у уровня 1 — snake_v, wiggu_v, cletu_v). Машина открывается на своём уровне (BindReward
    любого уровня) и потом видна во всех. -> [(имя, уровень открытия, [4 звезды в полузвёздах 0..10])]"""
    rtxt = re.sub(r'//[^\n]*', '', (GAME / 'scripts/missions/rewards.mfk').read_text(errors='replace'))
    unlock, stars = {}, {}
    for m in re.finditer(r'BindReward\s*\(([^)]*)\)', rtxt):
        a = [x.strip().strip('"') for x in m.group(1).split(',')]
        if len(a) >= 5 and a[2] == 'car' and a[4].isdigit(): unlock.setdefault(a[0].lower(), int(a[4]))
    for m in re.finditer(r'SetCarAttributes\s*\(([^)]*)\)', rtxt):
        a = [x.strip().strip('"') for x in m.group(1).split(',')]
        if len(a) >= 5: stars[a[0].lower()] = [int(round(float(v) * 2)) for v in a[1:5]]
    names = [c for c, _ in level_cars(level)]
    if os.environ.get('SHR_PHONE_ALL_OLD') != '1':   # правка 442/450, вариант Б (по умолчанию; SHR_PHONE_ALL_OLD=1 — вариант А): машины-награды всех уровней (первое вхождение имени), потом персонажи уровня
        names = []
        for L in range(1, 8):
            for c, _ in level_cars(L):
                if c.lower() not in [x.lower() for x in names]: names.append(c)
    ltxt = re.sub(r'//[^\n]*', '', (GAME / 'scripts/missions' / ('level%02d' % level) / 'level.mfk').read_text(errors='replace'))
    for m in re.finditer(r'AddVehicleSelectInfo\s*\(([^)]*)\)', ltxt):
        a = [x.strip().strip('"') for x in m.group(1).split(',')]
        if len(a) >= 2 and a[1] not in names: names.append(a[1])
    return [(c, unlock.get(c.lower(), level), stars.get(c.lower(), [0, 0, 0, 0])) for c in names]


def phone_reward_slot(name, level):
    """правка 442 (вариант Б): номер BindReward машины среди ВСЕХ BindReward уровня открытия (машины и костюмы, порядок rewards.mfk —
    ровно каталог пакета миссий, tools/missions/compile.py) и её квест. Нет в каталоге (машина персонажа) -> (-1, '')"""
    txt = re.sub(r'//[^\n]*', '', (GAME / 'scripts/missions/rewards.mfk').read_text(errors='replace'))
    i = 0
    for m in re.finditer(r'BindReward\s*\(([^)]*)\)', txt):
        a = [x.strip().strip('"') for x in m.group(1).split(',')]
        if len(a) < 5 or not a[4].isdigit() or int(a[4]) != level: continue
        if a[0].lower() == name.lower() and a[2] == 'car': return i, a[3]
        i += 1
    return -1, ''


def level_cars(level):
    """машины-награды уровня по порядку rewards.mfk -> [(имя, quest)]"""
    txt = re.sub(r'//[^\n]*', '', (GAME / 'scripts/missions/rewards.mfk').read_text(errors='replace'))
    out = []
    for m in re.finditer(r'BindReward\s*\(([^)]*)\)', txt):
        a = [x.strip().strip('"') for x in m.group(1).split(',')]
        if len(a) >= 5 and a[2] == 'car' and a[4].isdigit() and int(a[4]) == level:
            out.append((a[0], a[3]))
    return out


def phone_items(cars, level):
    bible = U._BIBLE or U.load_bible(U.LANG)
    names = [bible(c.upper()) or c for c, _, _ in cars]
    its, _ = U.build_items(PHONE)
    out = []
    for it in its:
        nm, path = it['name'], it['path']
        if nm == 'PreviewNameDummy' or 'RepairCostInfo' in path:   # «Cost to Fix» — в записи PS2 (37:54) его нет
            continue
        if 'DamagedInfo' in path:   # правка 104: «Damaged: 16 %» внизу слева — запись PS2 37:54; у машины, на которой игрок сейчас
            it['tag'] = TAG_DAMAGE   # (viewer/phone_view.c phoneViewSetCar), значение — ROW1 в процентах
            if it['type'] == U.T_TEXT and nm == 'VehicleDamaged_Value':
                it.update(field='ROW%d' % PHONE_ROW_DMG, fmt='pct', strings=['100%'])
            out.append(it); continue
        if nm == 'PreviewImage' and it['type'] == U.T_IMG:   # правка Роба 104: картинка машины — cars2d/<машина>.p3d диска
            it.update(frames=['pcar2d_%s.png' % c.lower() for c, _, _ in cars], field='ROW0')
            if PHONE_DAMAGED_PIC:   # правка 470: две картинки в одном месте — целая (метка CARDS) и повреждённая (PROXIMITY); какую — решает движок (phone_view.c)
                it['tag'] = TAG_PIC_OK
                dm = dict(it); dm.update(name='PreviewImageD', tag=TAG_PIC_DMG, frames=[('pcar2d_%sh.png' if PHONE_HUSKPIC else 'pcar2d_%sd.png') % c.lower() for c, _, _ in cars])
                out.append(it); out.append(dm); continue
            out.append(it); continue
        if 'VehicleStats' in path:
            it['tag'] = TAG_STATS
        if 'Foreground/Locked' in path:
            it['tag'] = TAG_LOCKED
        if 'Foreground/Arrows' in path:
            it['tag'] = TAG_ARROWS
        if 'Foreground/AcceptLabel' in path and TAG_ACCEPT:
            it['tag'] = TAG_ACCEPT
        if it['type'] == U.T_TEXT and nm == 'PreviewName':
            it.update(strings=names, field='ROW0', fmt='select', sel=0)
        elif it['type'] == U.T_TEXT and nm == 'Level' and 'Locked' in path:   # на замке — уровень, где машина открывается
            it.update(strings=['LEVEL %d' % lv for _, lv, _ in cars], field='ROW0', fmt='select', sel=0)
        elif it['type'] == U.T_TEXT and nm == 'Back' and it.get('strings'):
            it.update(strings=it['strings'][:1])
        elif it['type'] == U.T_IMG and path.split('/')[-1] in STAR_ROWS:
            k = int(nm[-1]); g, h, f = it['frames'][:3]
            it['frames'] = [g] * (2 * k + 1) + [h, f]
            it['field'] = 'ROW%d' % STAR_ROWS[path.split('/')[-1]]
        out.append(it)
    return out


CARS2D = GAME / 'art/frontend/dynaload/images/cars2d'

# ---------------------------------------------------------------- правка Роба 141: раскладка будки и гардероба
# Роб 01.10: «вёрстка, дивайдеры, странный низ — усреднить в одну строку, всё поместится, если не повторять оригинал точь-в-точь;
# отходить от оригинала только ради лучшего usability; пиксель-перфект под PSP». ПРАВИЛО ПОРТА (не данные диска): страница
# PhoneBooth.pag (запись PS2 37:54 — три полосы, Accept/Back стопкой) после U.adapt раскладывается по правилам ниже; координаты
# выводятся из размеров картинок диска и ширины строк, не из места. Решено терминалом за Роба (вкусовое — константами):
#   * будка — раскладка A: характеристика в одну строку «SPEED ★★★★☆» (подпись слева, 5 звёзд справа), колонка статов справа
#     шириной по самой длинной подписи, галерея — остальное слева;
#   * ровный фон: тёмная средняя полоса MiddleBar (её кромки и есть «дивайдеры») не рисуется — BOOTH_MIDBAR=1 вернёт;
#     BGColourWideScreenL/R целиком под BGColour (лишняя заливка каждый кадр) — убраны;
#   * машина 1:1 — родная картинка cars2d 179×132 без пересэмпла (BOOTH_CAR_K: доля родного, 0.65 ≈ запись PS2);
#   * низ — одна строка: слева «DAMAGED: 16%», справа «✕ ACCEPT  △ BACK», значки — ровно половина картинки диска (30 -> 15,
#     честный BOX 2×2), звёзды так же;
#   * строки (подписи, цена/уровень на замке, урон, кнопки) — грань pix8 (правка 126, пиксельный жирный 8×8, 1:1 без мыла):
#     дробная грань пакета Tt2001m×0.69 мылится (разведка 136), а пиксель-перфектной грани пакета до правки 136 нет.
#     Имя машины/костюма — грань пакета (заголовок; её резкость — правка 136). BOOTH_PIX8=0 — строки гранью пакета;
#   * гардероб — та же логика без статов и урона, галерея по центру экрана (240); место 3D-Гомера пишется строкой view в
#     skins.txt (viewer/wardrobe_view.c), рост — в той же доле средней полосы, что в прежней раскладке (128 px из 147).
#  PHONE_LAYOUT_OLD=1 — прежняя раскладка (отрицательный контроль гейта tests/ui/booth_layout.sh)
#  Правка Роба 464 (10.10: «интерфейс будки разбросан по краям — собрать под экран PSP: один масштаб, якоря, без растяжения»): две колонки с
#  общими осями — слева галерея (имя над машиной, «DAMAGED» под ней, по оси галереи), справа колонка статов (монеты над ней, «✕ ACCEPT △ BACK» под
#  ней, по оси колонки). Один масштаб (картинки и значки как раньше), ничего не растягивается; для будки (kind 'phone'). BOOTH_GATHER_OLD=1 — прежнее
#  (урон слева у поля, кнопки справа у поля, монеты в углу)
BOOTH_GATHER = os.environ.get('BOOTH_GATHER_OLD') != '1'
BOOTH_MIDBAR = os.environ.get('BOOTH_MIDBAR', '0') == '1'
BOOTH_PIX8 = os.environ.get('BOOTH_PIX8', '1') != '0'
PHONE_REPAIR_COST = 10 if os.environ.get('PHONE_REPAIR_COST_OLD') != '1' else 50   # = viewer/phone_view.c; оригинал: «Cost to Fix: 10 coins» (будка, машина 100 %, simpsons-hit-and-run.fandom.com, скриншот Роба 17.10); было 50 — правило порта
BOOTH_CAR_K = float(os.environ.get('BOOTH_CAR_K', '1.6' if os.environ.get('PHONE_LAYOUT2_OLD') != '1' else '1'))   # №557: картинка крупнее родной (ограничена колонкой)
# №684 (Роб, TEST27: «пропорции крайние, картинки машин немного меньше»): картинка машины заполняла всю среднюю полосу (137 из 272 px высоты = 50%), у PS2 спрайт ≈35% высоты
# (кадр build/twins/o4/v12_booth3 f00700: Family Sedan, корпус 123 px из 512; в долях экрана ≈0,69 от нашего размера). Правило порта: вся картинка (и каркас) × BOOTH_CAR_SCALE
# (0,85 — «немного»; до PS2 0,69 — решает глаз Роба; в панели Роба значения для картинки машины нет). BOOTH_CAR_SCALE_OLD=1 — прежний размер (1,0)
BOOTH_CAR_SCALE = float(os.environ.get('BOOTH_CAR_SCALE', '0.85')) if os.environ.get('BOOTH_CAR_SCALE_OLD') != '1' else 1.0   # гейт tests/ui/booth684_check.py
# №531/№533 (Роб 11.10): картинки машин будки — по видимому силуэту: центр по силуэту, холст один на все машины всех уровней (самый крупный силуэт, не выше родного 1:1), без дробного масштаба при K=1;
# звёзды характеристик — родной спрайт 30 px (было половина, 15 px), блок SPEED… сдвинут от правого края на BOOTH_STATS_PAD, монеты — на линии названия машины (№532). BOOTH_CAR_SIL_OLD=1 / BOOTH_STARS_OLD=1 / BOOTH_COINLINE_OLD=1 — прежнее
BOOTH_CAR_SIL = os.environ.get('BOOTH_CAR_SIL_OLD') != '1'
# №557 (Роб 11.10, будка): картинка машины и блок звёзд — пополам (картинка крупнее, звёзды 30 -> 24 px), ровные поля 12 px по периметру (имя, монеты, нижняя строка), REPAIR на 8 px под картинкой,
# повреждённая картинка — в размер целой машины, фон-градиент рисует движок без ступенек (viewer/phone_view.c phoneGrad). PHONE_LAYOUT2_OLD=1 — раскладка прежняя, PHONE_HUSK_OLD=1 — каркас прежнего размера,
# PHONE_GRAD_OLD=1 — градиент пакета (BGColour) как был (флаги экспорта и движка держать парой)
BOOTH_L2 = os.environ.get('PHONE_LAYOUT2_OLD') != '1'
BOOTH_HUSK = os.environ.get('PHONE_HUSK_OLD') != '1'
BOOTH_GRAD = os.environ.get('PHONE_GRAD_OLD') != '1'
BOOTH_M = 12            # px: поле по периметру (№557)
# Роб 17.10 (будка): свечение позади машины больше и размытее (было «слишком конкретное пятно»): × BOOTH_SPOT_K, размытие по Гауссу BOOTH_SPOT_BLUR px; BOOTH_SPOT_OLD=1 — как было
BOOTH_SPOT_K = 1.0 if os.environ.get('BOOTH_SPOT_OLD') == '1' else float(os.environ.get('BOOTH_SPOT_K', '1.6'))
BOOTH_SPOT_BLUR = float(os.environ.get('BOOTH_SPOT_BLUR', '6'))
# Роб 17.10: строка REPAIR — над DAMAGED, по её левому краю (блок из двух строк, как «Damaged / Cost to Fix» оригинала); счёт монет — по средней линии названия машины.
# BOOTH_INFO_OLD=1 — как было (REPAIR по центру под картинкой, монеты на месте пакета)
BOOTH_INFO = os.environ.get('BOOTH_INFO_OLD') != '1'
BOOTH_INFO_STEP = 12
# Роб 17.10 (вечер): счёт монет с монетой будки и гардероба — в правом верхнем углу, ровно где он в паузе (NumCoins паузы [440, 9, 26, 27], правый край 466,
# середина по высоте 22,5); цифры своей грани (панель). BOOTH_COIN_PAUSE_OLD=1 — на линии названия машины
BOOTH_COIN_PAUSE = os.environ.get('BOOTH_COIN_PAUSE_OLD') != '1'
PAUSE_COINS_BOX = (440, 9, 26, 27)
# Роб 17.10 (вечер): «строка скачет» — название машины капельку выше, монеты прилично ниже, одна средняя линия: замер кадра будки — середина букв
# названия y 50,5, цифр 19 → название −6, монеты +26 (обе ≈ 44,5). BOOTH_ROWMID_OLD=1 — монеты на месте паузы, название по панели
BOOTH_ROWMID = os.environ.get('BOOTH_ROWMID_OLD') != '1'
# Роб 17.10: «блок SPEED… со звёздами правее — слишком близко к стрелке; крайняя правая звезда — по центру монеты, что крутится сверху; всё, что в центре
# (машина, стрелки, статы) — капельку ниже». Центр монеты на кадре x 455 (3D-монета справа от цифр, правый край счёта 466). BOOTH_MIDBLOCK_OLD=1 — прежнее
BOOTH_MIDBLOCK = os.environ.get('BOOTH_MIDBLOCK_OLD') != '1'
BOOTH_COIN_CX, BOOTH_MID_DY = 455, 4
BOOTH_RAYS = os.environ.get('BOOTH_RAYS_OLD') != '1'   # Роб 17.10: лучи гардероба и в будке (центр за машиной); BOOTH_RAYS_OLD=1 — только градиент
BOOTH_RAYS_SPIN = os.environ.get('BOOTH_RAYS_SPIN_OLD') != '1'   # №750: лучи крутятся
BOOTH_RAYS_DEG, BOOTH_RAYS_TEX = 9.0, 254   # 254: страница 256² (у 256 с полями по 1 px — 512 шириной, +72 КБ); °/с (звёзды загрузки — 18, Роб: «немного крутиться»); сторона текстуры лучей, px
BOOTH_NAME_UP, BOOTH_COIN_DROP = 12, 20   # + Роб 17.10: «и название, и монеты капельку выше, пикселей на 6» — вся строка −6
def coins_like_pause(co):
    x, y, w, h = PAUSE_COINS_BOX; co['dst'] = [x + w - co['dst'][2], int(round(y + h / 2.0 - co['dst'][3] / 2.0)), co['dst'][2], co['dst'][3]]
BOOTH_COIN_DY = int(os.environ.get('BOOTH_COIN_DY', '0'))   # px: поправка «на глаз» середины цифр против заглавных названия
BOOTH_STAR = 15 if os.environ.get('BOOTH_STARS_OLD') == '1' else (24 if BOOTH_L2 else 30)
BOOTH_ARROW_K = 1.0 if os.environ.get('BOOTH_ARROWS_OLD') == '1' else 0.72   # №531: стрелки ◄ ► меньше (22 → 16 px), BOOTH_ARROWS_OLD=1 — прежние
BOOTH_STATS_PAD = 0 if os.environ.get('BOOTH_STARS_OLD') == '1' else 8
BOOTH_TOP = 36          # px: верхняя полоса (имя, монеты) 0..36
BOOTH_GAP = 4           # px: значок — подпись, подпись — число
BOOTH_GROUP_GAP = 16    # px: между группами «✕ ACCEPT» и «△ BACK»
BOOTH_COL_GAP = 8       # px: между галереей и колонкой статов, подписью и звёздами
BOOTH_ARROW_GAP = 16    # px: от края картинки до стрелки (будка при PHONE_LAYOUT2: 6, ближе — картинке больше места)
BOOTH_ROW_STEP = 26     # px: шаг строк статов (при звёздах 30 px — не меньше звезды + 4)
WARD_OLD_BAND, WARD_OLD_HPX = 147, 128   # прежняя раскладка: средняя полоса 46..193 и рост Гомера (viewer/wardrobe_view.c WV_HPX)


def half_box(img):
    """ровно половина картинки: среднее 2×2 в премультиплированном цвете (без Ланцоша — пиксель-перфект)"""
    from PIL import Image as _I
    a = np.asarray(img.convert('RGBA')).astype(np.float32) / 255
    h, w = a.shape[0] // 2 * 2, a.shape[1] // 2 * 2
    a = a[:h, :w]; pm = a.copy(); pm[..., :3] *= pm[..., 3:4]
    q = pm.reshape(h // 2, 2, w // 2, 2, 4).mean((1, 3))
    al = q[..., 3:4]; rgb = np.where(al > 1e-4, q[..., :3] / np.maximum(al, 1e-4), 0)
    return _I.fromarray((np.concatenate([np.clip(rgb, 0, 1), al], -1) * 255 + .5).astype(np.uint8), 'RGBA')


def booth_geometry(kind, label_w=0):
    """полосы и колонки экрана (kind 'phone' | 'wardrobe'); label_w — ширина самой длинной подписи стата, px"""
    M = BOOTH_M if (BOOTH_L2 and kind == 'phone') else None
    L, R = (M, U.DST_W - M) if M else (U.SAFE_X, U.DST_W - U.SAFE_X)
    icon = 15                                             # значок кнопки и звезда: половина 30 px диска
    row_y = U.DST_H - (M if M else U.SAFE_Y) - icon - (0 if M else 1)   # нижняя строка: значки 15 px, низ на поле M (№557) / на 1 px выше безопасного поля
    mid = (BOOTH_TOP, row_y - BOOTH_GAP)                  # средняя полоса
    if kind == 'phone':
        stats_x = R - BOOTH_STATS_PAD - 5 * BOOTH_STAR - BOOTH_COL_GAP - label_w
        col = (L, stats_x - BOOTH_COL_GAP)
    else:
        stats_x, col = None, (L, R)
    return dict(L=L, R=R, icon=icon, row_y=row_y, mid=mid, cy=(mid[0] + mid[1]) // 2, col=col, gcx=(col[0] + col[1]) / 2,
                stats_x=stats_x, ward_hpx=int(round(WARD_OLD_HPX * (mid[1] - mid[0]) / WARD_OLD_BAND)))


def _sil_bbox(img):
    a = np.asarray(img.convert('RGBA'))[..., 3]
    ys, xs = np.where(a > 16)
    if not len(xs):
        return (0, 0, img.width, img.height)
    return (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)


_SIL_ALL = []


def car_silhouettes():
    """силуэты картинок всех машин будок L1–L7: {машина: (ширина картинки, высота, bbox силуэта)}; общий холст — наибольший силуэт"""
    if _SIL_ALL:
        return _SIL_ALL[0]
    import load_export as LX
    out = {}
    for lv in range(1, 8):
        for c, _, _ in phone_cars(lv):
            f = CARS2D / (c.lower() + '.p3d')
            if c in out or not f.exists():
                continue
            for _, im in LX.sprite_images(f).items():
                out[c] = (im.width, im.height, _sil_bbox(im)); break
    _SIL_ALL.append(out); return out


def booth_layout(dl, kind, assets):
    """правка 141: раскладка после U.adapt (см. блок выше). -> новый список рисования; лишние картинки убираются из assets"""
    if os.environ.get('PHONE_LAYOUT_OLD') == '1':
        return dl
    def isimg(t, nm): return t['type'] == U.T_IMG and t['name'] == nm
    def istxt(t, nm): return t['type'] == U.T_TEXT and t['name'] == nm
    rows = [t for t in dl if t['type'] == U.T_TEXT and t['name'] in ('Speed', 'Acceleration', 'Toughness', 'Stability')]
    fc = U.FontCache('psp')

    def tw(t, s=None):                                     # ширина строки элемента t (первой, или s) его гранью, px
        s = (t.get('strings') or [''])[0] if s is None else s
        return U.pix8_width(s.upper()) if BOOTH_PIX8 else int(math.ceil(U.text_width(fc.get(t['font']), s)))
    lw = max((tw(t, s) for t in rows for s in t.get('strings') or ['']), default=0)
    G = booth_geometry(kind, lw); ic = G['icon']
    out = []

    def text_row(t, x, y, w, ha='left'):
        t['dst'] = [int(x), int(y), int(w), U.PIX8_LH if BOOTH_PIX8 else t['dst'][3]]
        t['halign'], t['valign'] = ha, 'top'
        if BOOTH_PIX8:
            t['pix8'] = True; t['strings'] = [s.upper() for s in t.get('strings') or []]

    def native(t, k=1.0):                                  # картинки кадров t в доле k родного размера (1 — как на диске)
        f0 = t['frames'][0]; iw, ih = assets.images[f0].size
        w, h = max(1, int(round(iw * k))), max(1, int(round(ih * k)))
        if k == 1.0: t['bitmaps'] = [assets.put('%s@%dx%d' % (f, w, h), assets.images[f].convert('RGBA')) for f in t['frames']]
        elif k == 0.5: t['bitmaps'] = [assets.put('%s@%dx%d_h' % (f, w, h), half_box(assets.images[f])) for f in t['frames']]
        else: t['bitmaps'] = [assets.scaled(f, w, h) for f in t['frames']]
        return w, h
    def silcar(t, limit_w, limit_h):                      # №531/№533: кадры по силуэту на общем холсте; -> (ширина, высота) холста
        sil = car_silhouettes()
        CW = max((b[2] - b[0] for _, _, b in sil.values()), default=1); CH = max((b[3] - b[1] for _, _, b in sil.values()), default=1)
        k1 = min(BOOTH_CAR_K, limit_w / CW, limit_h / CH)   # по самому крупному силуэту; выше родного не растёт
        k = k1 * BOOTH_CAR_SCALE                           # №684: × BOOTH_CAR_SCALE
        cw, ch = max(1, int(round(CW * k))), max(1, int(round(CH * k)))
        silcar.frame_w = max(1, int(round(CW * k1)))       # №684: ширина без уменьшения — по ней стоят стрелки ◄ ► (остаются на прежнем месте)
        from PIL import Image as _I
        bms = []
        for f in t['frames']:
            im = assets.images[f].convert('RGBA'); bb = _sil_bbox(im); crop = im.crop(bb)   # каркас центрируется по своему силуэту, как целая машина
            kk = k
            if BOOTH_HUSK and t.get('name') == 'PreviewImageD' and (f.endswith('d.png') or f.endswith('h.png')):   # №557: каркас — в размер целой машины (её силуэт по ширине), не мельче; в холст
                c = f[len('pcar2d_'):-len('d.png')]; whole = next((v[2] for n_, v in sil.items() if n_.lower() == c), None)
                if whole and crop.width:
                    kk = min(((whole[2] - whole[0]) * k) / crop.width, cw / crop.width, ch / crop.height)
            sw, sh = max(1, int(round(crop.width * kk))), max(1, int(round(crop.height * kk)))
            if (sw, sh) != crop.size: crop = crop.resize((sw, sh), _I.LANCZOS)
            canvas = _I.new('RGBA', (cw, ch), (0, 0, 0, 0)); canvas.paste(crop, ((cw - sw) // 2, (ch - sh) // 2))
            bms.append(assets.put('%s@sil%dx%d' % (f, cw, ch), canvas))
        t['bitmaps'] = bms
        return cw, ch
    def name_y(h):                                         # верх строки имени/монет: поле M (№557) или середина верхней полосы, как было
        return BOOTH_M if (BOOTH_L2 and kind == 'phone') else (BOOTH_TOP - h) // 2 + 2
    cy, gcx = G['cy'], G['gcx']
    agap = 6 if (BOOTH_L2 and kind == 'phone') else BOOTH_ARROW_GAP
    # картинка (машина) — в центре галереи; у гардероба её нет — место 3D-Гомера (строка view)
    car = next((t for t in dl if isimg(t, 'PreviewImage')), None)
    if car is not None:
        if BOOTH_CAR_SIL:
            colw = G['col'][1] - G['col'][0]; arrow_w = int(round(22 * BOOTH_ARROW_K))
            cw, ch = silcar(car, colw - 2 * (agap + arrow_w), G['mid'][1] - G['mid'][0] - 8)
        else:
            cw, ch = native(car, BOOTH_CAR_K)
        car['dst'] = [int(round(gcx - cw / 2)), int(round(cy - ch / 2)), cw, ch]
        half_w = (silcar.frame_w if BOOTH_CAR_SIL else cw) / 2   # №684: стрелки — по картинке до уменьшения
        cd = next((t for t in dl if isimg(t, 'PreviewImageD')), None)   # правка 470: повреждённая — в том же месте и размере
        if cd is not None:
            (silcar(cd, colw - 2 * (agap + arrow_w), G['mid'][1] - G['mid'][0] - 8) if BOOTH_CAR_SIL else native(cd, BOOTH_CAR_K)); cd['dst'] = list(car['dst'])
    else:
        half_w = G['ward_hpx'] * 0.45                      # полуширина места Гомера (руки в стороны) — для стрелок
    by = G['row_y']; ty = by + (ic - U.PIX8_GH) // 2 + 0   # верх рисунка pix8 по центру значков 15 px
    stars = {}
    for t in dl:
        nm = t['name']
        if t['type'] == U.T_RECT and (nm in ('BGColourWideScreenL', 'BGColourWideScreenR') or (nm == 'MiddleBar' and not BOOTH_MIDBAR) or (nm == 'BGColour' and BOOTH_GRAD and kind == 'phone')):   # BGColour — градиент рисует движок (phoneGrad, №557)
            continue                                       # не видны / «дивайдер» средней полосы
        if t['type'] == U.T_RECT and nm == 'MiddleBar':
            t['dst'] = [0, G['mid'][0], U.DST_W, G['mid'][1] - G['mid'][0]]
        elif nm in ('Spotlight', 'Overlay', 'Lock') and t['type'] == U.T_IMG:
            w, h = t['dst'][2], t['dst'][3]; t['dst'] = [int(round(gcx - w / 2)), int(round(cy - h / 2)), w, h]
            if nm == 'Spotlight' and BOOTH_HUSK and kind == 'phone': t['tag'] = TAG_SPOT
            if nm == 'Spotlight' and kind == 'phone' and BOOTH_SPOT_K != 1.0 and (t.get('frames') or [None])[0] in assets.images:   # Роб 17.10: свечение больше и мягче
                from PIL import ImageFilter as _F, Image
                w2, h2 = int(round(w * BOOTH_SPOT_K)), int(round(h * BOOTH_SPOT_K)); pad = int(BOOTH_SPOT_BLUR * 3)
                src = assets.images[t['frames'][0]].convert('RGBA').resize((w2, h2), Image.LANCZOS)
                big = Image.new('RGBA', (w2 + 2 * pad, h2 + 2 * pad), (0, 0, 0, 0)); big.paste(src, (pad, pad)); m0 = max(1, big.getchannel('A').getextrema()[1]); big = big.filter(_F.GaussianBlur(BOOTH_SPOT_BLUR))
                m1 = max(1, big.getchannel('A').getextrema()[1]); big.putalpha(big.getchannel('A').point(lambda v: min(255, int(v * m0 / m1 + .5))))   # яркость в центре — как у прежнего пятна
                t['bitmaps'] = [assets.put('spot_soft@%dx%d' % big.size, big)]; t['dst'] = [int(round(gcx - big.width / 2)), int(round(cy - big.height / 2)), big.width, big.height]
        elif istxt(t, 'Level'):                            # на замке: уровень открытия машины / цена костюма — под замком
            lock = next(x for x in dl if isimg(x, 'Lock'))
            ly = int(round(cy - lock['dst'][3] / 2)) + lock['dst'][3] + BOOTH_GAP
            text_row(t, G['col'][0], ly, G['col'][1] - G['col'][0], 'centre')
        elif nm in ('LeftArrow', 'RightArrow') and t['type'] == U.T_IMG:
            w, h = t['dst'][2], t['dst'][3]
            if BOOTH_ARROW_K != 1.0:
                w, h = max(1, int(round(w * BOOTH_ARROW_K))), max(1, int(round(h * BOOTH_ARROW_K)))
                if t.get('frames') and t.get('bitmaps'): t['bitmaps'] = [assets.scaled(f, w, h) for f in t['frames']]
                else: t['bitmaps'] = [assets.scaled(t['image'], w, h)] if t.get('image') else t.get('bitmaps')
            x = gcx - half_w - agap - w if nm == 'LeftArrow' else gcx + half_w + agap
            t['dst'] = [int(round(x)), int(round(cy - h / 2)), w, h]
        elif istxt(t, 'PreviewName'):                     # по центру галереи, рамка симметрична и не заходит на монеты
            coins = next((x for x in dl if x['type'] == U.T_NUM and x['name'] == 'NumCoins'), None)
            hw = min(gcx - G['col'][0], G['col'][1] - gcx, (coins['dst'][0] - BOOTH_COL_GAP - gcx) if coins else 1e9)
            h = t['dst'][3]; t['dst'] = [int(round(gcx - hw)), name_y(h), int(round(2 * hw)), h]
            t['halign'] = 'centre'
        elif t['type'] == U.T_NUM and nm == 'NumCoins':   # монеты: по центру верхней полосы, у правого поля
            h = t['dst'][3]; t['dst'] = [t['dst'][0], name_y(h), t['dst'][2], h]
            if os.environ.get('BOOTH_COINLINE_OLD') != '1':   # №532: середина строки монет — на середине строки названия машины (PreviewName 15 px: (36 - 15) // 2 + 2)
                name_mid = name_y(15) + 15 / 2.0; t['dst'][1] = int(round(name_mid - h / 2.0))
            if BOOTH_GATHER and kind == 'phone' and G['stats_x'] is not None:   # правка 464: над колонкой статов, по её оси
                t['dst'][0] = int(round((G['stats_x'] + G['R']) / 2 - t['dst'][2] / 2))
        elif t['type'] == U.T_IMG and nm[:4] in ('Spe_', 'Acc_', 'Tou_', 'Sta_'):
            native(t, BOOTH_STAR / 30.0); stars.setdefault(nm[:4], []).append(t)
        elif t['type'] == U.T_IMG and nm in ('Accept', 'Back'):
            native(t, 0.5)
        out.append(t)
    # статы: 4 строки «ПОДПИСЬ ★★★★★» по центру средней полосы
    if kind == 'phone':
        order = [('Speed', 'Spe_'), ('Acceleration', 'Acc_'), ('Toughness', 'Tou_'), ('Stability', 'Sta_')]
        sw_ = BOOTH_STAR; step = max(BOOTH_ROW_STEP, sw_ + 4)
        y0 = cy - (3 * step + sw_) // 2
        for i, (lab, pre) in enumerate(order):
            y = y0 + i * step
            t = next(x for x in out if istxt(x, lab))
            text_row(t, G['stats_x'], y + (sw_ - U.PIX8_GH + 1) // 2, lw)
            for s in stars.get(pre, []):
                k = int(s['name'][-1]); s['dst'] = [G['R'] - BOOTH_STATS_PAD - (5 - k) * sw_, y, sw_, sw_]
    # нижняя строка: слева урон, справа «✕ ACCEPT  △ BACK»
    acc_i = next(x for x in out if isimg(x, 'Accept')); acc_t = next(x for x in out if istxt(x, 'Accept'))
    bck_i = next(x for x in out if isimg(x, 'Back')); bck_t = next(x for x in out if istxt(x, 'Back'))
    wa, wb = tw(acc_t), tw(bck_t)
    gather = BOOTH_GATHER and kind == 'phone' and G['stats_x'] is not None
    if gather:   # правка 464: «✕ ACCEPT  △ BACK» — по оси колонки статов
        wg = ic + BOOTH_GAP + wa + BOOTH_GROUP_GAP + ic + BOOTH_GAP + wb
        x = int(round((G['stats_x'] + G['R']) / 2 - wg / 2))
        acc_i['dst'] = [x, by, ic, ic]; x += ic + BOOTH_GAP; text_row(acc_t, x, ty, wa); x += wa + BOOTH_GROUP_GAP
        bck_i['dst'] = [x, by, ic, ic]; x += ic + BOOTH_GAP; text_row(bck_t, x, ty, wb)
    else:
        x = G['R'] - wb; text_row(bck_t, x, ty, wb)
        x -= BOOTH_GAP + ic; bck_i['dst'] = [x, by, ic, ic]
        x -= BOOTH_GROUP_GAP + wa; text_row(acc_t, x, ty, wa)
        x -= BOOTH_GAP + ic; acc_i['dst'] = [x, by, ic, ic]
    dm = next((x for x in out if istxt(x, 'VehicleDamaged')), None); dv = next((x for x in out if istxt(x, 'VehicleDamaged_Value')), None)
    if dm is not None:
        wd = tw(dm); wv = tw(dv, '100%') + 2 if dv is not None else 0
        x0 = int(round(gcx - (wd + (BOOTH_GAP + wv if dv is not None else 0)) / 2)) if gather else G['L']   # правка 464: по оси галереи
        text_row(dm, x0, ty, wd)
        if dv is not None: text_row(dv, x0 + wd + BOOTH_GAP, ty, wv)
    # №535 (Роб 11.10): «REPAIR: 50 COINS» — пакетная строка со своей группой панели (phone_repair), по умолчанию Bart 16bit; две копии на одном месте: хватает монет (жёлтая, метка COUNTDOWN)
    # и не хватает (красная, ITEMS_COMPLETE) — какую показать, решает viewer/phone_view.c. PHONE_REPAIR_TEXT_OLD=1 — как было (строка кодом, шрифт пакета 0)
    if kind == 'phone' and car is not None and dm is not None and os.environ.get('PHONE_REPAIR_TEXT_OLD') != '1':
        cx0, cw0 = G['col'][0], G['col'][1] - G['col'][0]
        for nm_, tag_, col_ in (('RepairOk', 'COUNTDOWN', [255, 255, 64, 255]), ('RepairNo', 'ITEMS_COMPLETE', [255, 64, 64, 255])):
            r = dict(dm); r.update(name=nm_, tag=tag_, color=col_, font='bart_16bit@1', pix8=False, nopix8=True, subset=True, strings=['REPAIR: %d COINS' % PHONE_REPAIR_COST],
                                   field='NONE', fmt='none', halign='centre', valign='top', dst=[int(cx0), car['dst'][1] + car['dst'][3] + (8 if BOOTH_L2 else 4), int(cw0), 10])
            lab = next((x for x in out if x['type'] == U.T_TEXT and x.get('tag') == TAG_DAMAGE and x.get('name') == 'VehicleDamaged'), None)
            if BOOTH_INFO and lab is not None:   # над DAMAGED, тем же левым краем, шаг строки 12 px
                r.update(halign='left', dst=[lab['dst'][0], lab['dst'][1] - BOOTH_INFO_STEP, int(cw0), 10])
            out.append(r)
    # картинки, на которые больше никто не ссылается (прежние размеры), — вон из пакета
    used = set()
    for t in out:
        used.update(t.get('bitmaps') or [])
        if t.get('prefix'): used.add(t['prefix'])
        for g in (t.get('glyphs') or {}).values(): used.add(g[0])
        for b, _ in t.get('slots') or []: used.add(b)
    for k in [k for k in assets.bitmaps if k not in used]: del assets.bitmaps[k]
    return out


# №809 (Роб 18.10: «в будке снизу картинки нашей сломанной машины битые шакалы, как шум наложен»): у картинок машин диска (cars2d, husk.png) вокруг силуэта
# сотни почти прозрачных точек (альфа 1..47: у husk.png 738 из 3380) — после масштаба и палитры CLUT8 они видны как шум. Такие точки — полностью прозрачные
# (мягкая тень под машиной на экране будки и так своя — Spotlight). PHONE_PIC_CLEAN_OLD=1 — картинки как на диске
PHONE_PIC_CLEAN = os.environ.get('PHONE_PIC_CLEAN_OLD') != '1'
def _pic_clean(im):
    if not PHONE_PIC_CLEAN: return im
    from PIL import Image as _I
    a = np.asarray(im.convert('RGBA')).copy(); a[a[..., 3] < 48] = 0
    return _I.fromarray(a, 'RGBA')
def phone_pack(cars, level, out):
    U.SCREEN_PAGES[PHONE] = [('ingame.p3d', pg) for pg in U.project('ingame.p3d').screens['PhoneBooth.scr']]
    import load_export as LX   # картинки машин будки (правка 104): спрайт Scrooby из cars2d/<машина>.p3d, 179×132
    imgs = U.project('ingame.p3d').images   # общий словарь картинок проекта (all_images собирает из него)
    for c, _, _ in cars:
        f = CARS2D / (c.lower() + '.p3d')
        if f.exists():
            for nm_, im in LX.sprite_images(f).items(): imgs['pcar2d_%s.png' % c.lower()] = _pic_clean(im); break
        if PHONE_HUSKPIC and 'husk.png' in imgs: imgs['pcar2d_%sh.png' % c.lower()] = _pic_clean(imgs['husk.png'])   # №697: сгоревший каркас — один на все машины
        fd = CARS2D / (c.lower() + 'd.p3d')   # правка 470: картинка повреждённой машины (диск: <имя>d.p3d, 42 файла), нет — целая
        got = False
        if fd.exists() and PHONE_DAMAGED_PIC:
            for nm_, im in LX.sprite_images(fd).items(): imgs['pcar2d_%sd.png' % c.lower()] = _pic_clean(im); got = True; break
        if not got and ('pcar2d_%s.png' % c.lower()) in imgs:
            # №533: у машины нет своей картинки каркаса — общий каркас (famil_v), а не целая машина (у Malibu Stacy подставлялась мелкая); PHONE_HUSK_OLD=1 — прежнее
            hk = CARS2D / 'famil_vd.p3d'
            if os.environ.get('PHONE_HUSK_OLD') != '1' and PHONE_DAMAGED_PIC and hk.exists():
                for nm_, im in LX.sprite_images(hk).items(): imgs['pcar2d_%sd.png' % c.lower()] = _pic_clean(im); break
            else:
                imgs['pcar2d_%sd.png' % c.lower()] = imgs['pcar2d_%s.png' % c.lower()]

    phone_assets = []
    def build(sc, assets, fonts):
        phone_assets[:] = [assets]   # для post (лучи будки)
        dl, _ = U.adapt(phone_items(cars, level), {}, 'psp', assets, fonts)
        return booth_layout(dl, 'phone', assets)
    def post(screens):   # после панели Роба: счёт монет — серединой на середину строки названия машины
        if not BOOTH_INFO: return
        dl = screens[PHONE]; nm = next((x for x in dl if x['type'] == U.T_TEXT and x['name'] == 'PreviewName'), None)
        co = next((x for x in dl if x['type'] == U.T_NUM and x['name'] == 'NumCoins'), None)
        if nm and co:
            if BOOTH_COIN_PAUSE:   # Роб 17.10: счёт монет справа вверху (место паузы), по высоте — одна средняя линия с названием машины
                coins_like_pause(co)
                if BOOTH_ROWMID: co['dst'][1] += BOOTH_COIN_DROP; nm['dst'][1] -= BOOTH_NAME_UP
        if BOOTH_RAYS:   # Роб 17.10: лучи как в гардеробе (№703/№732), центр — за машиной; одна непрозрачная картинка во весь экран под всем
            import numpy as np
            from PIL import Image
            import wardrobe_rays as WR
            car = next((x for x in dl if x['type'] == U.T_IMG and x.get('tag') == 'CARDS'), None)
            if car is not None:
                cx = car['dst'][0] + car['dst'][2] / 2.0; cy = car['dst'][1] + car['dst'][3] / 2.0 + (BOOTH_MID_DY if BOOTH_MIDBLOCK else 0)
                if BOOTH_RAYS_SPIN:   # №750 (Роб, видео IMG_7282 3:52–4:03): лучи медленно крутятся вокруг своей оси, как звёзды загрузки (drawSpin, правка 336):
                    # только лучи на прозрачном (белые клинья RAY_RGB с альфой как в гардеробе), квадрат 2·RAY_R вокруг центра за машиной, градиент под ними
                    # рисует движок (phoneGrad). Один повёрнутый спрайт за кадр. BOOTH_RAYS_SPIN_OLD=1 — неподвижная запечённая картинка (59db61e7)
                    S = BOOTH_RAYS_TEX; D = 2.0 * WR.RAY_R; k = D / S
                    ys, xs = np.mgrid[0:S, 0:S]; px = (xs + .5) * k - D / 2; py = (ys + .5) * k - D / 2
                    ang = np.mod(np.arctan2(py, px), 2 * np.pi / WR.RAYS732); r = np.hypot(px, py)
                    inw = ang < np.pi / WR.RAYS732; w0 = np.clip(1.0 - r / WR.RAY_R, 0, 1)
                    al = np.where(inw, WR.RAY_A * WR.RAY_GAIN * w0, 0.0)
                    rgba = np.zeros((S, S, 4), np.uint8); rgba[..., 0], rgba[..., 1], rgba[..., 2] = WR.RAY_RGB; rgba[..., 3] = np.clip(al + .5, 0, 255).astype(np.uint8)
                    key = phone_assets[0].put('booth_rays', Image.fromarray(rgba, 'RGBA'))
                    dl.insert(0, dict(name='RaysSpin', page=car.get('page'), path=car.get('path'), unit=None, forced=None, tag='ALWAYS', type=U.T_IMG, field='NONE', fmt='none',
                                      menu=-1, color=[255, 255, 255, 255], anchor='C', bitmaps=[key], dst=[cx - D / 2, cy - D / 2, D, D], spin=BOOTH_RAYS_DEG, pivot=(cx, cy)))
                else:
                    img = WR.bake_at((90, 99, 180), (37, 43, 67), cx, cy)   # цвета градиента будки (viewer/phone_view.c phoneGrad)
                    key = phone_assets[0].put('booth_rays', Image.fromarray(np.dstack([img, np.full(img.shape[:2], 255, np.uint8)]), 'RGBA'))
                    dl.insert(0, dict(name='RaysBG', page=car.get('page'), path=car.get('path'), unit=None, forced=None, tag='ALWAYS', type=U.T_IMG, field='NONE', fmt='none',
                                      menu=-1, color=[255, 255, 255, 255], anchor='C', bitmaps=[key], dst=[0, 0, 480, 272]))
        if BOOTH_MIDBLOCK:   # Роб 17.10: блок статов правее (крайняя звезда — под центром монеты), весь центр капельку ниже
            stars = [x for x in dl if x['type'] == U.T_IMG and x.get('tag') == 'STREETRACE']
            dx = int(round(BOOTH_COIN_CX - max(x['dst'][0] + x['dst'][2] / 2.0 for x in stars))) if stars else 0
            for x in dl:
                if x.get('tag') == 'STREETRACE': x['dst'][0] += dx
                if x.get('tag') in ('STREETRACE', 'CARDS', 'PROXIMITY', 'GAMBLE', 'SKIP', 'WASPS') or x['name'] == 'Spotlight': x['dst'][1] += BOOTH_MID_DY
            else: mid = nm['dst'][1] + nm['dst'][3] / 2.0; co['dst'][1] = int(round(mid - co['dst'][3] / 2.0)) + BOOTH_COIN_DY
        lab = next((x for x in dl if x['type'] == U.T_TEXT and x['name'] == 'VehicleDamaged'), None)   # REPAIR — над DAMAGED тем же левым краем (после панели)
        if lab:
            for x in dl:
                if x['type'] == U.T_TEXT and x['name'] in ('RepairOk', 'RepairNo'):
                    x['halign'] = 'left'; x['dst'] = [lab['dst'][0], lab['dst'][1] - BOOTH_INFO_STEP, x['dst'][2], x['dst'][3]]
    # лучи будки — своя страница и своя палитра (как raysbg гардероба): на общей странице с картинками машин у чёрного седана (cSedan) нижние
    # строки картинки брали чужие пиксели — пёстрая полоска под машиной (тур 17.10 21:10). BOOTH_RAYS_OLD=1 — без лучей
    spec = dict(screens=[PHONE], build=build, tags={PHONE: {'ALWAYS'}}, group=(lambda k: 'raysbg' if k == 'booth_rays' else 'ui') if BOOTH_RAYS else (lambda k: 'ui'),
                radar=False, post=post, groups=('ui', 'raysbg') if BOOTH_RAYS else ('ui',), layout='layout_phone.json')
    return U.pack(out, spec)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--level', type=int, default=U.LEVEL); ap.add_argument('--out-dir', default=str(ROOT / 'build'))
    ap.add_argument('--check', action='store_true'); ap.add_argument('--ui-only', action='store_true')
    ap.add_argument('--car', help='только сцена этой машины (без shop.shr)')
    ap.add_argument('--scene', type=int, help='только сцена машины номер K (без shop.shr)')
    ap.add_argument('--out', help='один файл (tools/ship_rules.txt {out}): с --ui-only — shop.shr, с --scene K — reward-K.shr')
    ap.add_argument('--phone-ui', action='store_true', help='экран телефонной будки -> --out (phone.shr)')
    ap.add_argument('--phone-list', action='store_true', help='список галереи будки -> --out (phonecars.txt)')
    ap.add_argument('--phone-scene', type=int, help='сцена машины будки номер K -> --out (pcar-K.shr)')
    a = ap.parse_args()
    if a.check: sys.exit(1 if check(a.out_dir, a.level) else 0)
    if a.phone_list:   # список галереи для движка (viewer/phone_view.c): «имя уровень_открытия 4 звезды» по строке
        o = Path(a.out) if a.out else Path(a.out_dir) / 'phonecars.txt'
        if os.environ.get('SHR_PHONE_ALL_OLD') != '1':   # правка 442, вариант Б: + номер BindReward в каталоге уровня открытия и квест (viewer/phone_view.c ownedOther)
            rows = [(c, lv, st, *phone_reward_slot(c, lv)) for c, lv, st in phone_cars(a.level)]
            o.write_text(''.join('%s %d %s %d %s\n' % (c, lv, ' '.join(str(x) for x in st), ix, q) if ix >= 0 else
                                 '%s %d %s\n' % (c, lv, ' '.join(str(x) for x in st)) for c, lv, st, ix, q in rows))
        else:
            o.write_text(''.join('%s %d %s\n' % (c, lv, ' '.join(str(x) for x in st)) for c, lv, st in phone_cars(a.level)))
        print('phonecars.txt:', ', '.join(c for c, _, _ in phone_cars(a.level))); return
    if a.phone_ui or a.phone_scene is not None:
        pc = phone_cars(a.level); o = Path(a.out) if a.out else Path(a.out_dir) / ('phone.shr' if a.phone_ui else 'pcar-%d.shr' % a.phone_scene)
        if a.phone_ui:
            r = phone_pack(pc, a.level, o); print('phone.shr: %d B, машины %s' % (r['size'], ', '.join(c for c, _, _ in pc)))
        else:
            c = pc[a.phone_scene][0]; st, info = reward_scene(c, o); print('pcar-%d.shr (%s): %.0f КБ' % (a.phone_scene, c, st['size'] / 1024))
        return
    cars = forsale(a.level)
    out = Path(a.out_dir); out.mkdir(parents=True, exist_ok=True)
    one = a.car or a.scene is not None
    if a.out and not (a.ui_only or a.scene is not None): ap.error('--out только с --ui-only или --scene K')
    if not one:
        res = ui_pack(cars, Path(a.out) if a.out else out / 'shop.shr')
        print('shop.shr: %d B, машины %s' % (res['size'], ', '.join('%s %d (%s)' % c for c in cars)))
    if a.ui_only: return
    for k, (c, price, seller) in enumerate(cars):
        if (a.car and c != a.car) or (a.scene is not None and k != a.scene): continue
        s, info = reward_scene(c, Path(a.out) if a.out else out / ('reward-%d.shr' % k))
        print('reward-%d.shr (%s): %.0f КБ, текстур %d, кусков %d, треугольников %d (+%d у камеры), билбордов %d; круг %d кадров @ %g, '
              'машина %d треуг., низ на %.3f (подиум %.3f); камера облёта в осях сцены уходит на %.3f м / %.2f°'
              % (k, c, s['size'] / 1024, s['tex'], s['pieces'], s['tris'], s['split'], s['bills'], info['frames'], info['fps'],
                 info['car_tris'], info['lift'], info['top'], *info['cam_drift']))


if __name__ == '__main__':
    main()
