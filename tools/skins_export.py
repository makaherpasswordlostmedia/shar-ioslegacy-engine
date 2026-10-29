#!/usr/bin/env python3
"""Гардероб Гомера (правка Роба 107, 30.09: «все скины уровня 1 загрузить»): костюмы уровня из данных диска.

  rewards.mfk  BindReward(имя, art\\chars\\<модель>.p3d, "skin", quest, уровень[, цена, "interior"]) — defaultskin и forsale
  l1i00/l1i01  ActionEvent-локаторы PurchaseSkin (школа int_ele_skin, Kwik-E-Mart int_kwik_skin) — где выбирают костюм
  skins2d      (до правки 119 — картинки костюмов; теперь на странице 3D-модель костюма, картинки не нужны)

Выход:
  build/wardrobe.shr   UIP1 — страница PhoneBooth.scr (та же вёрстка галереи: имя, картинка, стрелки, замок с ценой, Accept/Back)
  build/skins.txt      строки «skin имя файл_модели цена» и «spot x y z радиус» (координаты порта: z отражён)
L1: tools/homer_export.py --skin <модель> -> homer-<модель>.shr
L2–L7: tools/homer_export.py --level N --skin-index K -> l<N>/skin<K>.shr;
обычный костюм — l<N>/player.shr, скелет и клипы игрока своего уровня

  python tools/skins_export.py [--level 1] [--ui OUT.shr | --list OUT.txt]"""
import argparse, re, struct, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools')); sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))
import ui_export as U
import shop_export as SE   # правка 141: общая раскладка будки и гардероба (booth_layout)
import os
GAME = ROOT / 'hit-and-run-web/source/game'
SKINS2D = GAME / 'art/frontend/dynaload/images/skins2d'
SCREEN = 'wardrobe'
SPOT_R = 1.5   # м: △ у места выбора костюма (радиус триггера в данных у action-локатора не хранится — ПРАВИЛО ПОРТА)
WARD_RISE = 7   # №695 (Роб: «модель чуть выше, элементы по сетке»): центр модели на линии стрелок ◄ ► (141 - 7 = 134 + смещение модели ~6); WARDROBE_LAYOUT_OLD=1 — прежнее
SKIN_H = 170   # px картинки: skins2d 119×230 выше окна PreviewImage будки (cars2d 179×132) — цена на замке уходила под картинку;
               # до 170 — фигура в окне, «100 coins» под ней, как «LEVEL 1» у машин (ПРАВИЛО ПОРТА: страница будки, не оригинал)


def skins(level):
    """-> [(имя, модель, цена)] костюмов уровня по порядку rewards.mfk; обычный — цена 0"""
    txt = re.sub(r'//[^\n]*', '', (GAME / 'scripts/missions/rewards.mfk').read_text(errors='replace'))
    out = []
    for m in re.finditer(r'BindReward\s*\(([^)]*)\)', txt):
        a = [x.strip().strip('"') for x in m.group(1).split(',')]
        if len(a) >= 5 and a[2] == 'skin' and a[4].isdigit() and int(a[4]) == level:
            model = a[1].replace('\\', '/').split('/')[-1][:-4]
            out.append((a[0], model, int(a[5]) if a[3] == 'forsale' and len(a) > 5 else 0))
    return out


def spots(level):
    from p3d import read, walk, string
    out = []
    for f in sorted((GAME / 'art').glob(f'l{level}i*.p3d')):
        for c in walk(read(f)):
            if c.id != 0x3000005: continue
            name, p = string(c.data); kind, n = struct.unpack_from('<II', c.data, p)
            strs = [x.decode('latin1') for x in c.data[p + 8:p + 8 + 4 * n].split(b'\0') if x]
            if 'PurchaseSkin' not in strs: continue
            pos = struct.unpack_from('<3f', c.data, p + 8 + 4 * n)
            for t in c.children:
                if t.id == 0x3000006:
                    _, q = string(t.data); pos = struct.unpack_from('<16f', t.data, q + 16)[12:15]; break
            out.append((name, pos[0], pos[1], -pos[2]))
    return out


def model_file(model, level=1, index=0):
    # Codex-3 shop: playerLoad/homerWear read the current level directory.
    # --skin-index exports on that player's skeleton, including its own clips.
    # SKIN_CATALOG_OLD=1 reproduces the L1-only filenames for the red gate.
    if level > 1 and os.environ.get('SKIN_CATALOG_OLD') != '1':
        return 'player.shr' if index == 0 else f'skin{index}.shr'
    return 'homer.shr' if model == 'homer_m' else f'homer-{model}.shr'


def items(sk):
    bible = U._BIBLE or U.load_bible(U.LANG)
    names = [bible(n.upper()) or n for n, _, _ in sk]
    price = [('%d %s' % (p, bible('COINS') or 'coins')) if p else '' for _, _, p in sk]
    its, _ = U.build_items(SCREEN)
    out = []
    for it in its:
        nm, path = it['name'], it['path']
        if nm == 'PreviewNameDummy' or 'DamagedInfo' in path or 'VehicleStats' in path: continue   # у костюма нет звёзд и урона
        # правка Роба 119 (30.09): вместо картинки skins2d — 3D-модель Гомера в костюме, вращается (viewer/wardrobe_view.c); фон страницы —
        # отдельным тегом LOADING: движок рисует фон, поверх него Гомера, поверх — надписи, замок, стрелки (тег ALWAYS и прочие)
        if nm == 'PreviewImage': continue
        if nm == 'Spotlight' and os.environ.get('WARDROBE_BG_OLD') != '1': continue   # №695: голубое пятно по центру — вон; вместо него лучи из-под модели (viewer/wardrobe_view.c)
        if nm in ('BGColour', 'BGColourWideScreenL', 'BGColourWideScreenR', 'MiddleBar', 'Spotlight'): it['tag'] = 'LOADING'
        if 'Foreground/Locked' in path: it['tag'] = 'GAMBLE'
        if 'Foreground/Arrows' in path: it['tag'] = 'SKIP'
        if it['type'] == U.T_TEXT and nm == 'PreviewName':
            it.update(strings=names, field='ROW0', fmt='select', sel=0)
        elif it['type'] == U.T_TEXT and nm == 'Level' and 'Locked' in path:   # на замке — цена
            it.update(strings=price, field='ROW0', fmt='select', sel=0)
        elif it['type'] == U.T_TEXT and nm == 'Back' and it.get('strings'):
            it.update(strings=it['strings'][:1])
        out.append(it)
    return out


# №703 (Роб: «лучи очень лагают»): градиент страницы + 16 клиньев с альфой сведены в одну непрозрачную картинку 480x272 (tools/wardrobe_rays.py),
# отдельным слоем с тегом WASPS; прежний градиент (тег LOADING) остаётся в пакете — движок выбирает слой (viewer/wardrobe_view.c: файл raysold рядом
# с EBOOT / WARDROBE_RAYBAKE_OLD=1 — градиент и клинья как раньше). WARDROBE_RAYBAKE_OLD=1 при экспорте — пакет побайтно прежний (без слоя)
RAYBAKE = os.environ.get('WARDROBE_RAYBAKE_OLD') != '1'
RAYBAKE_KEY = 'wardrobe_rays'
# №761 (Роб 17.10, TEST32: «в магазине одежды пусть тоже крутятся на фоне лучи немножко медленно вокруг своей оси», как в будке №750): фон — один градиент
# (непрозрачная картинка 480x272, тот же слой WASPS), лучи — отдельный спрайт на прозрачном (своя страница текстур), движок крутит его drawSpin
# (WARD_SPIN_DEG °/с) вокруг центра лучей (№732: середина экрана, 12 клиньев). WARDROBE_RAYS_SPIN_OLD=1 — неподвижная запечённая картинка
WARD_SPIN = os.environ.get('WARDROBE_RAYS_SPIN_OLD') != '1'
WARD_SPIN_DEG, WARD_SPIN_TEX, WARD_SPIN_KEY = 9.0, 254, 'wardrobe_rays_spin'   # 254: страница 256² (shelf_pack: поля по 1 px)


def view_numbers():
    """те же числа, что строка «view» skins.txt (одна цифра после точки у x, y; рост целый)"""
    G = SE.booth_geometry('wardrobe')
    return tuple(float(v) for v in ('%.1f %.1f %d' % (G['gcx'], G['cy'] - (0 if os.environ.get('WARDROBE_LAYOUT_OLD') == '1' else WARD_RISE), G['ward_hpx'])).split())


def with_rays_bake(dl, assets):
    import numpy as np
    from PIL import Image
    import wardrobe_rays as WR
    bg = next(t for t in dl if t['name'] == 'BGColour' and t['type'] == U.T_RECT)
    top, bottom = bg['colors'][0], bg['colors'][2]
    if WARD_SPIN:   # №761: под лучами — только градиент
        img = np.clip(WR.gradient(top, bottom) + .5, 0, 255).astype(np.uint8)
    else:
        img, _ = WR.bake(top, bottom, view_numbers())
    key = assets.put(RAYBAKE_KEY, Image.fromarray(np.dstack([img, np.full(img.shape[:2], 255, np.uint8)]), 'RGBA'))
    it = dict(name='RaysBG', page=bg['page'], path=bg['path'], unit=bg.get('unit'), forced=None, tag='WASPS', type=U.T_IMG, field='NONE', fmt='none', menu=-1,
              color=[255, 255, 255, 255], anchor='C', bitmaps=[key], dst=list(bg['dst']))
    dl.insert(dl.index(bg) + 1, it)
    if WARD_SPIN:   # №761: лучи на прозрачном — как в будке (shop_export №750): белые клинья RAY_RGB с альфой, квадрат 2·RAY_R вокруг центра лучей
        if WR.RAYS732_OLD:
            vcx, vcy, vh = view_numbers(); cx, cy, nr = vcx, vcy + vh * WR.FOOT, WR.RAYS
        else:
            cx, cy, nr = WR.W / 2.0, WR.H / 2.0, WR.RAYS732
        S = WARD_SPIN_TEX; D = 2.0 * WR.RAY_R; k = D / S
        ys, xs = np.mgrid[0:S, 0:S]; px = (xs + .5) * k - D / 2; py = (ys + .5) * k - D / 2
        ang = np.mod(np.arctan2(py, px), 2 * np.pi / nr); r = np.hypot(px, py)
        al = np.where(ang < np.pi / nr, WR.RAY_A * WR.RAY_GAIN * np.clip(1.0 - r / WR.RAY_R, 0, 1), 0.0)
        rgba = np.zeros((S, S, 4), np.uint8); rgba[..., 0], rgba[..., 1], rgba[..., 2] = WR.RAY_RGB; rgba[..., 3] = np.clip(al + .5, 0, 255).astype(np.uint8)
        k2 = assets.put(WARD_SPIN_KEY, Image.fromarray(rgba, 'RGBA'))
        sp = dict(name='RaysSpin', page=bg['page'], path=bg['path'], unit=bg.get('unit'), forced=None, tag='WASPS', type=U.T_IMG, field='NONE', fmt='none', menu=-1,
                  color=[255, 255, 255, 255], anchor='C', bitmaps=[k2], dst=[cx - D / 2, cy - D / 2, D, D], spin=WARD_SPIN_DEG, pivot=(cx, cy))
        dl.insert(dl.index(it) + 1, sp)
    return dl


def ui_pack(sk, out):
    U.SCREEN_PAGES[SCREEN] = [('ingame.p3d', pg) for pg in U.project('ingame.p3d').screens['PhoneBooth.scr']]
    def build(sc, assets, fonts):
        dl, _ = U.adapt(items(sk), {}, 'psp', assets, fonts); dl = SE.booth_layout(dl, 'wardrobe', assets)   # правка 141
        return with_rays_bake(dl, assets) if RAYBAKE else dl
    grp = (lambda k: 'raysbg' if k == RAYBAKE_KEY else 'raysspin' if k == WARD_SPIN_KEY else 'ui') if RAYBAKE else (lambda k: 'ui')
    def post(screens):   # Роб 17.10: счёт монет гардероба — в правом верхнем углу, как в паузе и в будке (SE.coins_like_pause)
        if not SE.BOOTH_COIN_PAUSE: return
        co = next((x for x in screens[SCREEN] if x['type'] == U.T_NUM and x['name'] == 'NumCoins'), None)
        if co: SE.coins_like_pause(co)
    return U.pack(out, dict(screens=[SCREEN], build=build, tags={SCREEN: {'ALWAYS'}}, group=grp, radar=False, post=post,
                            groups=(('ui', 'raysbg', 'raysspin') if WARD_SPIN else ('ui', 'raysbg')) if RAYBAKE else ('ui',), layout='layout_wardrobe.json'))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--level', type=int, default=1)
    ap.add_argument('--ui'); ap.add_argument('--list')
    a = ap.parse_args(); sk = skins(a.level)
    if a.ui:
        r = ui_pack(sk, Path(a.ui)); print('wardrobe.shr: %d B, костюмы %s' % (r['size'], ', '.join(n for n, _, _ in sk)))
    if a.list:
        lines = ['skin %s %s %d' % (n, model_file(m, a.level, k), p) for k, (n, m, p) in enumerate(sk)] + ['spot %.2f %.2f %.2f %.1f' % (x, y, z, SPOT_R) for _, x, y, z in spots(a.level)]
        if os.environ.get('PHONE_LAYOUT_OLD') != '1':   # правка 141: место 3D-Гомера из раскладки (центр галереи, рост в доле полосы)
            G = SE.booth_geometry('wardrobe'); lines.append('view %.1f %.1f %d' % (G['gcx'], G['cy'] - (0 if os.environ.get('WARDROBE_LAYOUT_OLD') == '1' else WARD_RISE), G['ward_hpx']))
        Path(a.list).write_text('\n'.join(lines) + '\n'); print('\n'.join(lines))


if __name__ == '__main__':
    main()
