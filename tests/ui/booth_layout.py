#!/usr/bin/env python3
"""Гейт правки Роба 141 (будка и гардероб: вёрстка, дивайдеры, «странный низ» — в одну строку, пиксель-перфект под PSP).
Читает готовые пакеты UIP1 (что увидит движок, а не раскладку экспортёра) и skins.txt, проверяет:
  1. низ — одна строка: значки и подписи Accept/Back и урон по одной средней линии (разброс ≤ 2 px), полоса ≤ 28 px;
  2. ничего не выходит за безопасное поле [8,472]×[6,266] и ничто не налезает на соседа (кроме слоя замка поверх картинки);
  3. строки (подписи статов, урон, кнопки, уровень/цена на замке) — грань pix8 (бит 3 res[0]); звёзды и значки кнопок —
     ровно 1 или 1/2 картинки диска; у будки каждая строка стата — подпись и 5 звёзд на одной линии;
  4. нет тёмной средней полосы-разделителя (прямоугольник во всю ширину, но не во весь экран);
  5. картинка машины — родной размер cars2d (× BOOTH_CAR_K); гардероб — центр галереи (имя, стрелки, место Гомера view) = 240±1.
  python tests/ui/booth_layout.py PHONE.shr WARDROBE.shr SKINS.txt  -> PASS/FAIL, код 0/1"""
import os, struct, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools')); sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))
import ui_export as U   # noqa: E402
import shop_export as SHOPX   # noqa: E402
import ui_typo as _UT   # noqa: E402
TYPO = _UT.load() is not None

SAFE = (U.SAFE_X, U.SAFE_Y, U.DST_W - U.SAFE_X, U.DST_H - U.SAFE_Y)


def items(path):
    b = Path(path).read_bytes(); assert b[:4] == b'UIP1', path
    h = struct.unpack_from('<4sI20I', b, 0)
    nitem, offItem, nscreen, offScreen, nstr, offStr = h[4], h[5], h[6], h[7], h[10], h[11]
    offs = struct.unpack_from('<%dI' % nstr, b, offStr)
    strs = [b[o:b.index(b'\0', o)].decode('latin-1') for o in offs]
    first, count, _, _ = struct.unpack_from('<4I', b, offScreen)
    out = []
    for i in range(first, first + count):
        r = struct.unpack_from('<8B4h2I4B2H3fIf3I', b, offItem + 64 * i)
        out.append(dict(type=r[0], tag=U.TAGS[r[2]], field=U.FIELDS[r[3]], ha=r[5], va=r[6], x=r[8], y=r[9], w=r[10], h=r[11],
                        strings=strs[r[18]:r[18] + r[19]] if r[0] == U.T_TEXT else [], pix8=bool(r[25] & 8)))
    return out


def ink(t):
    """видимый прямоугольник: картинка — рамка; pix8 — рисунок самой широкой строки по выравниванию; прочий текст — рамка"""
    if t['type'] == U.T_TEXT and t['pix8']:
        lw = max(U.pix8_width(s) for s in t['strings'] or [''])
        x0 = t['x'] if t['ha'] == 0 else (t['x'] + t['w'] - lw if t['ha'] == 2 else t['x'] + (t['w'] - lw) // 2)
        return (x0, t['y'], x0 + lw - 1, t['y'] + 7)            # шаг последнего знака: 1 пустой столбец; заглавные 7 строк
    return (t['x'], t['y'], t['x'] + t['w'], t['y'] + t['h'])


def cy(r): return (r[1] + r[3]) / 2
def hit(a, b): return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def check(kind, its, bad, skins=None):
    fg = [t for t in its if t['type'] != U.T_RECT]
    car = next((t for t in its if t['type'] == U.T_IMG and t['field'] == 'ROW0'), None)
    # №470/№557: картинка разбитой машины и каркас — слоями на месте картинки машины (теги PROXIMITY, CARDS), это не наложение
    carl = [t for t in its if car and t['type'] == U.T_IMG and t['field'] == 'ROW0' and (t['x'], t['y'], t['w'], t['h']) == (car['x'], car['y'], car['w'], car['h'])]
    # значки кнопок низа: ALWAYS, у будки Accept.pag под меткой ACTION (пункт ДОБИВКИ 26, tools/shop_export.py TAG_ACCEPT: у закрытой
    # машины Accept скрыт, как на PS2 ps2_v105_booth_access) — раскладку значка Accept проверяем так же, как раньше
    small = [t for t in its if t['type'] == U.T_IMG and t['tag'] in ('ALWAYS', 'ACTION') and t['field'] == 'NONE' and t['w'] <= 32]
    glow = [t for t in its if t['type'] == U.T_IMG and t['tag'] in ('ALWAYS', 'LOADING') and t['field'] == 'NONE' and t['w'] > 32]
    # 4. дивайдер
    for t in its:
        if t['type'] == U.T_RECT and t['w'] >= U.DST_W and 0 < t['h'] < U.DST_H - 2 * U.SAFE_Y:
            bad.append(f'{kind}: тёмная полоса-разделитель во всю ширину y {t["y"]}..{t["y"] + t["h"]}')
    # 3. строки pix8
    rows = [t for t in its if t['type'] == U.T_TEXT and (t['tag'] in ('STREETRACE', 'DAMAGE', 'GAMBLE') or
                                                        any(s.upper() in ('ACCEPT', 'BACK') for s in t['strings']))]
    # 17.10: с типографикой Роба (build/ui_typo.json, docs/typography/README.md) шрифт строк задаёт его панель (bart_16bit и др.), а не pix8;
    # совпадение «панель = игра» проверяет tests/ui/b708_top_gate.py. pix8 обязателен только без панели (UI_TYPO=0)
    for t in rows:
        if not t['pix8'] and not TYPO: bad.append(f'{kind}: строка {t["strings"][:1]} не гранью pix8 (дробная грань пакета мылится)')
    stars = [t for t in its if t['type'] == U.T_IMG and t['tag'] == 'STREETRACE']
    star = SHOPX.BOOTH_STAR                                   # №557 (Роб 11.10): звёзды будки 24 px (30 — родные, BOOTH_LAYOUT2_OLD; 15 — BOOTH_STARS_OLD)
    for t in stars + small:
        if (t['w'], t['h']) not in ((30, 30), (15, 15), (star, star)): bad.append(f'{kind}: значок {t["w"]}×{t["h"]} — не 1, не 1/2 картинки диска 30×30 и не {star} (№557)')
    # 1. нижняя строка
    btn = [t for t in its if t['type'] == U.T_TEXT and any(s.upper() in ('ACCEPT', 'BACK') for s in t['strings'])]
    low = btn + small + [t for t in its if t['tag'] == 'DAMAGE']
    if len(btn) != 2 or len(small) != 2: bad.append(f'{kind}: кнопок {len(btn)} подписи / {len(small)} значка, ждали 2/2')
    elif low:
        cs = [cy(ink(t)) for t in low]
        rs = [ink(t) for t in low]
        if max(cs) - min(cs) > 2 and not TYPO: bad.append(f'{kind}: низ не одной строкой — средние линии {sorted(set(cs))}')   # с панелью Роба строки ставит панель (hints_phone, phone_damage)
        if max(r[3] for r in rs) - min(r[1] for r in rs) > 28: bad.append(f'{kind}: нижняя полоса {min(r[1] for r in rs)}..{max(r[3] for r in rs)} > 28 px')
    # 2. поле и наложения
    layer = [t for t in fg if t['tag'] == 'GAMBLE'] + glow + carl
    # №703: WASPS — запечённый фон лучей гардероба во весь экран и подсветка под замком будки: подложка под всем по замыслу
    wasps = [t for t in fg if t['tag'] == 'WASPS']; fg = [t for t in fg if t['tag'] != 'WASPS']
    for t in fg:
        r = ink(t)
        if r[0] < SAFE[0] or r[1] < SAFE[1] or r[2] > SAFE[2] or r[3] > SAFE[3]:
            bad.append(f'{kind}: {t["strings"][:1] or (t["type"], t["tag"])} за краем {r}')
    for i, a in enumerate(fg):
        for b2 in fg[i + 1:]:
            if a in layer and b2 in layer: continue
            # шрифт панели Роба: рамка строки шире букв (ink() считает буквы только у pix8) — их места сверяет b708_top_gate / панель
            if TYPO and any(t['type'] == U.T_TEXT and not t['pix8'] for t in (a, b2)): continue
            if hit(ink(a), ink(b2)):
                bad.append(f'{kind}: налезают {a["strings"][:1] or (a["type"], a["tag"], a["field"])} {ink(a)} и '
                           f'{b2["strings"][:1] or (b2["type"], b2["tag"], b2["field"])} {ink(b2)}')
    if car:
        for t in fg:
            if t['tag'] == 'GAMBLE' and not (car['x'] <= ink(t)[0] and ink(t)[2] <= car['x'] + car['w'] and car['y'] <= ink(t)[1] and ink(t)[3] <= car['y'] + car['h']):
                bad.append(f'{kind}: слой замка вне картинки {ink(t)}')
    if kind == 'phone':
        for f in ('ROW4', 'ROW5', 'ROW6', 'ROW7'):
            st = [t for t in stars if t['field'] == f]
            if len(st) != 5: bad.append(f'phone: {f} звёзд {len(st)}'); continue
            if len({t['y'] for t in st}) != 1: bad.append(f'phone: звёзды {f} не в одну строку')
        labs = sorted([t for t in its if t['type'] == U.T_TEXT and t['tag'] == 'STREETRACE'], key=lambda t: t['y'])
        rows_y = sorted({t['y'] for t in stars})
        if len(labs) != 4 or len(rows_y) != 4: bad.append(f'phone: подписей статов {len(labs)}, строк звёзд {len(rows_y)}')
        else:
            for t, y in zip(labs, rows_y):
                if abs(cy(ink(t)) - (y + 7.5)) > 2 and not TYPO: bad.append(f'phone: подпись {t["strings"][:1]} не на линии своих звёзд (y {y})')
        if car is None: bad.append('phone: нет картинки машины')
        else:
            import load_export as LX, shop_export as SE
            iw, ih = next(iter(LX.sprite_images(SE.CARS2D / 'famil_v.p3d').values())).size
            k = float(os.environ.get('BOOTH_CAR_K', '1'))
            if SHOPX.BOOTH_CAR_SIL:   # №531/№533: общий холст по силуэтам всех машин (не родные 179×132); размер — гейт tests/ui/booth684_check.py
                sil = SHOPX.car_silhouettes(); CW = max(b_[2] - b_[0] for _, _, b_ in sil.values()); CH = max(b_[3] - b_[1] for _, _, b_ in sil.values())
                if abs(car['w'] / car['h'] - CW / CH) > 0.03: bad.append(f'phone: машина {car["w"]}×{car["h"]} — не пропорции холста силуэтов {CW}×{CH}')
            elif (car['w'], car['h']) != (int(round(iw * k)), int(round(ih * k))):
                bad.append(f'phone: машина {car["w"]}×{car["h"]}, родная {iw}×{ih} × {k}')
    else:
        name = next(t for t in its if t['type'] == U.T_TEXT and t['field'] == 'ROW0' and t['tag'] == 'ALWAYS')
        arr = [t for t in its if t['tag'] == 'SKIP']
        cxs = {'имя': name['x'] + name['w'] / 2}
        if len(arr) == 2: cxs['стрелки'] = (min(t['x'] for t in arr) + max(t['x'] + t['w'] for t in arr)) / 2
        view = [l.split() for l in Path(skins).read_text().splitlines() if l.startswith('view ')] if skins else []
        if view: cxs['Гомер (view)'] = float(view[0][1])
        else: bad.append('wardrobe: в skins.txt нет строки view (место Гомера по константам 189.5)')
        for k_, v in cxs.items():
            if abs(v - U.DST_W / 2) > 1: bad.append(f'wardrobe: {k_} — центр {v}, не 240')


def main():
    phone, ward, skins = sys.argv[1:4]
    bad = []
    pi, wi = items(phone), items(ward)
    check('phone', pi, bad); check('wardrobe', wi, bad, skins)
    for b in bad[:int(os.environ.get("BL_SHOW", "12"))]: print('FAIL:', b)
    if bad: print(f'RESULT FAIL {len(bad)}'); sys.exit(1)
    print(f'RESULT PASS будка {len(pi)} элементов, гардероб {len(wi)}'); sys.exit(0)


if __name__ == '__main__':
    main()
