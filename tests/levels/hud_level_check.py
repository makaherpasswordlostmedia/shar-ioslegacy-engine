#!/usr/bin/env python3
"""Гейт «интерфейс уровня» (29.09): пакет HUD уровня N (UIP1: ui.shr у уровня 1, build/levels/l<N>/ui.shr у 2–7, собирается
`LEVEL=N tools/ui_export.py`) несёт СВОИ данные уровня:
  радар   текстура радарной карты (из resource/pure3d/l<N>hudmap.p3d) ложится на дороги уровня: середины и концы отрезков
          дорог ботов (tools/cartest/roads.py из l<N>_terra, те же координаты, что level.shr) попадают на дорожные тексели
          карты (±1 тексель) — не меньше RADAR_MIN; чужая карта (карта уровня 1 на уровне 3) даёт мало попаданий
  пауза   фон паузы — страница PauseBgd.pag из ingamel<N>.p3d: слой Background с элементом Overlay (прямоугольник на весь
          экран, цвет из данных). Overlay на диске одинаков на всех 7 уровнях, но слой ВИДИМ только у 1–3 (у ночных 4–7 флаг
          видимости слоя 0 — затемнения паузы нет; эталон PS2 не сверен). Проверка: видим — первый элемент паузы = Overlay
          с цветом данных; скрыт — полноэкранного Overlay нет. Своё у ingamel<N> ещё — страница Level<N>.pag: карточки
          уровня и ссылка на l<N>hudmap (тот же радар)
  hud_level_check.py --level N [N ...] [--ui P] [--roads P]   PASS / FAIL
  hud_level_check.py --level 3 --ui build/levels/l1/ui.shr     красный: карта уровня 1 на уровне 3
  hud_level_check.py --level 4 --ui build/levels/l1/ui.shr     красный: пакет уровня 1 на уровне 4 (та же карта города,
                                                               но затемнение паузы уровня 1)
  hud_level_check.py --level N --plant-pause OUT               красный: пакет уровня N с перекрашенным Overlay паузы"""
import argparse, struct, sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))
from p3d import read, walk, string   # noqa: E402

GAME = ROOT / 'hit-and-run-web/source/game'
SCROOBY = GAME / 'art/frontend/scrooby'
RADAR_MIN = 0.85          # доля точек дорог на дорожных текселях своей карты (замер 29.09: 0.93–0.99 у своих, < 0.5 у чужих)
T_RECT = 0
SCREENS = ['hud', 'pause', 'main', 'missionload', 'missionover', 'letterbox']   # порядок tools/ui_export.py SCREENS


def uip(path):
    b = Path(path).read_bytes()
    assert b[:4] == b'UIP1', path
    h = struct.unpack_from('<19I', b, 4)
    map_tex, x0, z0, mpp = struct.unpack_from('<i3f', b, 4 + 19 * 4)
    ntex, off_tex, nitem, off_item, nscr, off_scr = h[1:7]
    tex = [struct.unpack_from('<4H6I', b, off_tex + 32 * i) for i in range(ntex)]
    items = [struct.unpack_from('<8B4h2I4B2H3fIf3I', b, off_item + 64 * i) for i in range(nitem)]
    scr = [struct.unpack_from('<4I', b, off_scr + 16 * i) for i in range(nscr)]
    return dict(b=b, tex=tex, items=items, screens=scr, map_tex=map_tex, x0=x0, z0=z0, mpp=mpp)


def radar_mask(U):
    """-> bool[h, w]: тексели дорог радарной карты (альфа CLUT > 0)"""
    psm, _, w, h, po, co, nclut, bufw, rows, _ = U['tex'][U['map_tex']]
    assert psm == 4, psm
    wb = w // 2
    sw = np.frombuffer(U['b'], np.uint8, wb * h, po).reshape(h // 8, wb // 16, 8, 16)
    lin = sw.transpose(0, 2, 1, 3).reshape(h, wb)                  # обратное swizzle ui_export (блоки 16 Б x 8 строк)
    idx = np.empty((h, w), np.uint8); idx[:, 0::2] = lin & 15; idx[:, 1::2] = lin >> 4
    clut = np.frombuffer(U['b'], np.uint8, 4 * nclut, co).reshape(nclut, 4)
    return clut[idx][..., 3] > 0


def radar_score(U, roads):
    m = radar_mask(U)
    m = m | np.roll(m, 1, 0) | np.roll(m, -1, 0) | np.roll(m, 1, 1) | np.roll(m, -1, 1)
    r = np.frombuffer(Path(roads).read_bytes(), '<f4').reshape(-1, 7)
    pts = np.concatenate([r[:, 0:3], r[:, 3:6], (r[:, 0:3] + r[:, 3:6]) / 2])
    u = np.floor((pts[:, 0] - U['x0']) / U['mpp']).astype(int); v = np.floor((pts[:, 2] - U['z0']) / U['mpp']).astype(int)
    h, w = m.shape
    inside = (u >= 0) & (v >= 0) & (u < w) & (v < h)
    hit = np.zeros(len(pts), bool); hit[inside] = m[v[inside], u[inside]]
    return float(hit.mean()), len(pts)


def overlay_want(lv):
    """-> цвет ABGR Overlay страницы PauseBgd.pag ingamel<N>.p3d или None, если его слой скрыт
    (0x18003 слой: имя, u32 версия, u32 видимость, …; 0x18009 Overlay: 4 цвета вершин ARGB в конце)"""
    for page in walk(read(SCROOBY / f'ingamel{lv}.p3d')):
        if page.id != 0x18002 or string(page.data)[0] != 'PauseBgd.pag': continue
        for layer in page.children:
            nm, p = string(layer.data); ver, vis = struct.unpack_from('<II', layer.data, p)
            for c in layer.children:
                if c.id == 0x18009 and string(c.data)[0] == 'Overlay':
                    argb = struct.unpack_from('<4I', c.data, len(c.data) - 16)
                    assert len(set(argb)) == 1, 'Overlay: цвета вершин разные'
                    a, r, g, b_ = argb[0] >> 24, argb[0] >> 16 & 255, argb[0] >> 8 & 255, argb[0] & 255
                    return ((a << 24) | (b_ << 16) | (g << 8) | r) if vis else None
    raise ValueError(f'ingamel{lv}.p3d: нет Overlay в PauseBgd.pag')


def pause_bg(U):
    first, n, _, _ = U['screens'][SCREENS.index('pause')]
    it = U['items'][first]
    return dict(type=it[0], dst=it[8:12], col=it[12])


def atlas_rgba(U, ti, u, v, w, h):
    """прямоугольник страницы T8 пакета UIP1 -> RGBA (обратное swizzle, CLUT 256)"""
    psm, _, tw, th, po, co, nclut, bufw, rows, _ = U['tex'][ti]
    assert psm == 5, psm
    sw = np.frombuffer(U['b'], np.uint8, tw * rows, po).reshape(rows // 8, tw // 16, 8, 16)
    idx = sw.transpose(0, 2, 1, 3).reshape(rows, tw)
    clut = np.frombuffer(U['b'], np.uint8, 4 * nclut, co).reshape(nclut, 4)
    return clut[idx[v:v + h, u:u + w]]


def small_gray(rgba, size=(16, 12)):
    from PIL import Image
    a = np.asarray(Image.fromarray(np.ascontiguousarray(rgba), 'RGBA').convert('L').resize(size, Image.BILINEAR), np.float32)
    a -= a.mean(); n = np.linalg.norm(a)
    return a / n if n else a


def news_check(lv, load_shr):
    """газета экрана загрузки: у элемента с полем LEVEL в load.shr кадр N-1 (viewer/main.c LEVEL_IDX) похож на
    dynaload/images/loading/loading<N>.p3d больше, чем на газету любого другого уровня"""
    sys.path.insert(0, str(ROOT / 'tools'))
    import ui_export as UE, load_export as LE
    U = uip(load_shr); fld = UE.FIELDS.index('LEVEL')
    it = next((i for i in U['items'] if i[3] == fld and i[0] == UE.T_IMG), None)
    if it is None: return [f'{load_shr}: нет газеты уровня (элемент с полем LEVEL)']
    sfirst, scount = it[18], it[19]
    off_slot = struct.unpack_from('<19I', U['b'], 4)[16]
    frames = [struct.unpack_from('<7Hh', U['b'], off_slot + 16 * (sfirst + k))[:5] for k in range(scount)]
    if len(frames) < 7: return [f'газет в load.shr {len(frames)} из 7']
    src = [small_gray(np.asarray(LE.sprite_images(LE.GAME / f'dynaload/images/loading/loading{m}.p3d')[f'loading{m}.png']))
           for m in range(1, 8)]
    got = small_gray(atlas_rgba(U, *frames[lv - 1]))
    corr = [float((got * s).sum()) for s in src]
    best = int(np.argmax(corr)) + 1
    print(f'уровень {lv}: газета загрузки — кадр {lv - 1} load.shr ближе всего к loading{best}.p3d '
          f'(сходство {corr[best - 1]:.2f}, у своей {corr[lv - 1]:.2f})')
    return [] if best == lv else [f'уровень {lv}: кадр газеты {lv - 1} похож на loading{best}, не на loading{lv}']


def default_ui(lv):
    return next(p for p in ([ROOT / 'build/ui.shr'] if lv == 1 else []) + [ROOT / f'build/levels/l{lv}/ui.shr', ROOT / f'build/ui_l{lv}.shr'] if p.exists())


def default_roads(lv):
    return next(p for p in (ROOT / f'build/sandbox/roads-l{lv}.bin', ROOT / f'build/levels/l{lv}/roads-l{lv}.bin') if p.exists())


def check(lv, ui=None, roads=None):
    bad = []
    ui = ui or default_ui(lv); roads = roads or default_roads(lv)
    U = uip(ui)
    if U['map_tex'] < 0: return [f'уровень {lv}: в {ui} нет радарной карты']
    s, n = radar_score(U, roads)
    print(f'уровень {lv}: радар {Path(ui).relative_to(ROOT) if Path(ui).is_relative_to(ROOT) else ui}: точек дорог на карте {s:.3f} из {n} (порог {RADAR_MIN}); '
          f'карта x0 {U["x0"]:.1f} z0 {U["z0"]:.1f} {U["mpp"]:.2f} м/тексель')
    if s < RADAR_MIN: bad.append(f'уровень {lv}: радарная карта не ложится на дороги уровня ({s:.3f} < {RADAR_MIN})')
    want = overlay_want(lv); got = pause_bg(U)
    full = got['type'] == T_RECT and tuple(got['dst']) == (0, 0, 480, 272)
    ok = (full and got['col'] == want) if want is not None else not full
    print(f'уровень {lv}: фон паузы — первый элемент {got["dst"]} цвет {got["col"]:08x}; ingamel{lv}: ' +
          (f'Overlay {want:08x}' if want is not None else 'слой Background скрыт — затемнения нет'))
    if not ok: bad.append(f'уровень {lv}: фон паузы не как PauseBgd.pag ingamel{lv} ({got})')
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--level', type=int, nargs='+', required=True)
    ap.add_argument('--ui'); ap.add_argument('--roads'); ap.add_argument('--plant-pause')
    ap.add_argument('--load', help='load.shr (газеты загрузки; по умолчанию build/load.shr, если есть)')
    ap.add_argument('--plant-news', help='красный: load.shr с переставленными газетами 1 и 3 -> OUT')
    a = ap.parse_args()
    bad = []
    load = a.load or (ROOT / 'build/load.shr' if (ROOT / 'build/load.shr').exists() else None)
    if a.plant_news and load:   # газеты уровней 1 и 3 поменяны местами: кадр N-1 уже не газета уровня N
        U = uip(load); sys.path.insert(0, str(ROOT / 'tools')); import ui_export as UE
        it = next(i for i in U['items'] if i[3] == UE.FIELDS.index('LEVEL') and i[0] == UE.T_IMG)
        off_slot = struct.unpack_from('<19I', U['b'], 4)[16]; o0, o2 = off_slot + 16 * it[18], off_slot + 16 * (it[18] + 2)
        b = bytearray(U['b']); b[o0:o0 + 16], b[o2:o2 + 16] = U['b'][o2:o2 + 16], U['b'][o0:o0 + 16]
        Path(a.plant_news).write_bytes(bytes(b)); load = a.plant_news
    for lv in a.level:
        ui = a.ui
        if a.plant_pause:   # тот же пакет уровня, у Overlay паузы другой цвет (фон паузы не из ingamel<N>)
            U = uip(default_ui(lv)); first = U['screens'][SCREENS.index('pause')][0]
            off_item = struct.unpack_from('<19I', U['b'], 4)[4]
            b = bytearray(U['b']); struct.pack_into('<I', b, off_item + 64 * first + 16, 0xff3040c0)
            Path(a.plant_pause).write_bytes(bytes(b)); ui = a.plant_pause
        bad += check(lv, ui, a.roads)
        if load: bad += news_check(lv, load)
    for x in bad: print('ПРОВАЛ:', x)
    print('FAIL' if bad else 'PASS')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
