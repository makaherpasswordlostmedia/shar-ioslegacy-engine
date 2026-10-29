#!/usr/bin/env python3
"""Правка Роба 312 (04.10.2026): твик-панель типографики — локальная страница build/ТИПОГРАФИКА_ПАНЕЛЬ/index.html + img/.

Экран PSP 480×272 пиксель в пиксель: фон — снимки безголового эмулятора (кадр игры без текста «b», без интерфейса «c», целиком «a»
для сверки; flag uitypo, viewer/ui.c), текст поверх рисует страница теми же гранями, что игра (порт tools/ui_export.py FontCache,
грань pix8 viewer/ui_layout.h, перенос uiWrap, раскладка строки viewer/ui.c textGlyphs/fitW/objTextStart). Группы строк и правила
переноса настроек в игру — tools/ui_typo.py (страница несёт его GROUPS; кнопка «Сохранить» отдаёт build/ui_typo.json).

    python tools/typo_panel.py --shots <папка снимков scen.py> [--out build/ТИПОГРАФИКА_ПАНЕЛЬ]
    python tools/typo_panel.py --fontref FILE   # эталон граней для гейта tests/ui/typo_fonts.mjs (порт FontCache побайтно)

Снимки: сценарии tests/ui/typo_scenes/*.txt (scen.py имя typo_<сцена>), кадры <сцена>_a/_b/_c.png. Нет снимка — сцена на тёмном
фоне из картинок пакета (лавка: Барни в эмуляторе не открывает экран покупки — фон без 3D-подиума)."""
import base64
import hashlib
import io
import json
import math
import os
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ui_export as U  # noqa: E402
import ui_typo as UT  # noqa: E402

ROOT = U.ROOT
PAGE_TEMPLATE = Path(__file__).resolve().parent / 'typo_panel_page.html'
OBJICON_EXT = 1000
TAGS = U.TAGS


def failure_examples(data):
    """Original failure strings, as previews; typography JSON changes no game text."""
    import importlib.util
    import re
    source = (ROOT / 'viewer/ui_layout.h').read_text()
    words = re.search(r'static const char \*const list\[\] = \{([^}]+)', source)
    data['short_words'] = re.findall(r'"([A-Z]+)"', words.group(1)) if words else []
    spec = importlib.util.spec_from_file_location('typo_mission_texts', ROOT / 'tools/missions/compile.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    get = module.bible()
    names = [('TIME_OUT', 'Время'), ('PLAYER_OUT_OF_VEHICLE', 'Вне машины'),
             ('VEHICLE_DAMAGE', 'Урон'), ('POSITION', 'Позиция'), ('RACE', 'Гонка'),
             ('FOLLOW_DISTANCE', 'Дистанция'), ('HIT_N_RUN', 'Арест')]
    variants = []
    for suffix, title in names:
        key = 'MISSION_FAILED_' + suffix
        reason = get(key)
        if not reason:
            raise ValueError('missing original failure text: ' + key)
        hints = [(i, get(key + '_HINT%d' % i)) for i in range(8)]
        hints = [(i, hint) for i, hint in hints if hint]
        for i, hint in hints or [(0, '')]:
            variants.append(dict(id=key + '_HINT%d' % i, title=title + ' · подсказка %d' % (i + 1),
                                 text={'MSN_FAIL': reason.replace('\\', '\n'), 'MSN_HINT': hint.replace('\\', '\n')}))
    generic = get('MISSION_FAILED')
    if not generic:
        raise ValueError('missing original generic failure text')
    variants.append(dict(id='MISSION_FAILED', title='Общий провал', text={'MSN_FAIL': generic, 'MSN_HINT': ''}))
    for scene in data['scenes']:
        if scene['id'] == 'over':
            scene['examples'] = variants
    return data

# ---------------------------------------------------------------- сцены
# show — метки экрана, видимые в кадре; sel — выбранная строка меню; dim — приглушённые строки; hid — скрытые строки (правка 137:
# RESET CAR у игрока не виден; служебный запуск эмулятора его показывает — hid_ref пустой для сверки с кадром); text — строки, которые
# в игре ставит код (поле -> текст); fields — значения полей; obj — значок задания ('ext' — аватар извне, None — без значка)
# теги и поля экранов бонус-игры — как tools/bonus/screens_export.py (CUR_TAGS, TRACK_TAGS, DEMO)
MINI_CUR = ['TIMER', 'PARTIME', 'LAP', 'POSITION', 'DAMAGE', 'PROXIMITY', 'CARDS']
MINI_TRACKS = ['COINS', 'WASPS', 'COLLECTIBLES', 'ITEMS_COMPLETE', 'STAGE_COMPLETE', 'MISSION_COMPLETE', 'MISSION_FAILED']
MINI_CHAR = {'ROW2': 1, 'ROW5': 27, 'ROW6': 5, 'ROW7': 0}
SCENES = [
    dict(id='bootload', title='Экран запуска · Копирайт и LOADING', pack='boot', screen='bootload', shot='typo_boot/bootload', base='typo_boot/tvframe', show={'ALWAYS'}),
    dict(id='title', title='Первый экран · Press START', pack='boot', screen='splash', shot='typo_title/title', show={'ALWAYS', 'PRESS_START'}),
    dict(id='bonus', title='Итоги бонус-игры', pack='mini', screen='msbase', shot='typo_bonus_accepted/summary', show={'ALWAYS'}, bonus_rows=True),
    dict(id='talk', title='Пузырь задания · Talk to Marge', pack='ui', screen='hud', shot='typo_talk/talk',
         show={'ALWAYS', 'RADAR', 'HNR_METER', 'OBJECTIVE'}, obj='ext', icon='char/marage.p3d',
         text={'OBJECTIVE': 'TALK TO MARGE'}),
    dict(id='action', title='Подпись △ · телефонная будка', pack='ui', screen='hud', shot='typo_action/action', base='typo_talk/talk_c',
         show={'ALWAYS', 'RADAR', 'HNR_METER', 'OBJECTIVE', 'ACTION'}, obj='ext', icon='char/marage.p3d',
         text={'OBJECTIVE': 'TALK TO MARGE', 'ACTION_TEXT': 'Use Telephone Booth'}),
    dict(id='boom', title='Пузырь без значка · машина взорвана', pack='ui', screen='hud', shot='typo_boom/boom',
         show={'ALWAYS', 'RADAR', 'HNR_METER', 'OBJECTIVE'}, obj=None, edge_icon='char/marage.p3d',
         text={'OBJECTIVE': 'VEHICLE DESTROYED! FIND A WRENCH, OR GO TO A PHONEBOOTH, TO REPAIR YOUR VEHICLE.'}),   # в кадре игры подписи △ нет (Marge далеко)
    dict(id='busted', title='Штраф полиции · BUSTED!', pack='ui', screen='hud', shot='typo_police/busted',
         show={'ALWAYS', 'RADAR', 'HNR_METER', 'HNR_TICKET'}, edge_icon='char/marage.p3d', fields={'HNR_TEXT': 1}, text={'ACTION_TEXT': 'Talk To Marge'}),
    dict(id='hitrun', title='Погоня · Hit & Run!', pack='ui', screen='hud', shot='typo_police/hitrun',
         show={'ALWAYS', 'RADAR', 'HNR_METER', 'HNR_TICKET'}, edge_icon='char/marage.p3d', fields={'HNR_TEXT': 0}, text={'ACTION_TEXT': 'Talk To Marge'}),
    dict(id='race', title='HUD гонки · круги и место', pack='ui', screen='hud', shot='typo_race/race',
         show={'ALWAYS', 'RADAR', 'HNR_METER', 'LAP', 'POSITION'}, fields={'LAP': 1, 'LAPS': 3, 'POSITION': 4, 'RACERS': 4}),
    dict(id='tut', title='Подсказка Барта', pack='ui', screen='tutorial', shot='typo_tut/tut', show={'ALWAYS', 'STREETRACE'}, tut=2),   # STREETRACE = UI_T_TUT_CONTINUE: Continue виден, когда реплика кончилась (hints_tut)
    dict(id='lbox', title='Разговор · кнопки внизу', pack='ui', screen='letterbox', shot='typo_brief/lbox_none', base='typo_brief/lbox_c',
         show={'ALWAYS', 'STREETRACE'}),
    dict(id='brief', title='Карточка миссии', pack='ui', screen='missionload', shot='typo_brief/brief', base='typo_brief/brief_c',
         show={'ALWAYS', 'PRESS_START'},
         text={'MSN_TITLE': 'THE COLA CAPER', 'MSN_INFO': 'GO TO THE KWIK-E-MART AND PURCHASE SOME ICE CREAM AND COLA.'}),
    dict(id='pause', title='Меню паузы', pack='ui', screen='pause', shot='typo_pause/pause', show={'ALWAYS', 'COINS'},
         sel=0, dim={'SaveGame', 'MissionSelect'}, hid={'ResetCar'}, hid_ref={'ResetCar'}, fields={'COINS': 0}, text={'PLACE': 'L1 K9-7'}),   # №598: код клетки — элемент PlaceCode пакета (UI_PLACE_CODE=1); №565: меню паузы игрока без RESET CAR (viewer/main_levels.h pauseRowsSvc: скрыт, строки ниже поднимаются); кадр снят режимом игрока (flag player)
    dict(id='ls', title='Пауза · LEVEL PROGRESS', pack='ui', screen='levelstats', shot='typo_pause/ls_none', base='typo_pause/pause_c', show={'ALWAYS', 'SKIP'},
         fields={'STAT_MODE': 0}, stats={'StoryMissions': (0, 8), 'BonusMissions': (0, 1), 'StreetRaces': (0, 3), 'Cards': (0, 7),
                                         'Clothing': (1, 4), 'Vehicles': (1, 6), 'Wasps': (0, 20), 'Gags': (0, 15)}, pct=3),
    dict(id='menu', title='Главное меню', pack='ui', screen='main', shot='typo_menusave/menu', show={'ALWAYS', 'SKIP'}, sel=4),
    dict(id='save', title='Сохранение · выбор слота', pack='psave', screen='pslots', shot='typo_menusave/save', show={'ALWAYS'},
         sel=0, rows={k: '< EMPTY SLOT >' for k in range(4)}),
    # без снимка этого момента: кадр игры без интерфейса (base) + картинки пакета; текст тот же
    dict(id='stage', title='Надпись этапа · TASK COMPLETE', pack='ui', screen='hud', shot='typo_stage/stage', base='typo_talk/talk_c',
         show={'ALWAYS', 'STAGE_COMPLETE'}),
    # Правка Роба 500 (10.10, «все основные экраны»): конец миссии, загрузка уровня газетой, меню и пауза бонус-игры — в панели не было
    dict(id='mdone', title='Конец миссии · MISSION COMPLETE!', pack='ui', screen='hud', shot='typo_mdone/mdone', base='typo_talk/talk_c',
         show={'ALWAYS', 'MISSION_COMPLETE'}, text={'MSN_DONE': 'MISSION COMPLETE!'}),
    dict(id='load', title='Загрузка уровня · газета и LOADING', pack='load', screen='loading', shot='typo_load/load', show={'ALWAYS', 'LOADING'}),
    # меню бонус-игры — составные экраны (tools/bonus/screens_export.py mock): выбор персонажа и машины (mmchar) + подписи кнопок (mmhints); выбор трассы (mmtrack) поверх
    # персонажей. Страница раньше показывала mmtrack/mmhints по отдельности — пустой экран с одной подписью (аудит 10.10, сцена 21)
    dict(id='bchar', title='Бонус-игра · выбор персонажа и машины', pack='mini', screen='mmchar', shot='typo_bonus_menu/chars',
         show={'ALWAYS', MINI_CUR[2]}, fields=MINI_CHAR,
         extra_scenes=[dict(id='bchar_h', title='h', pack='mini', screen='mmhints', show={'ALWAYS'})]),
    dict(id='btrack', title='Бонус-игра · выбор трассы и кругов', pack='mini', screen='mmtrack', shot='typo_bonus_menu/track',
         show={'ALWAYS', MINI_CUR[0]} | set(MINI_TRACKS), fields=dict(ROW9=3, ROW10=0),
         under=[dict(screen='mmchar', show={'ALWAYS', MINI_CUR[2]}, fields=MINI_CHAR)],
         extra_scenes=[dict(id='btrack_h', title='h', pack='mini', screen='mmhints', show={'ALWAYS'})]),
    dict(id='bhints', title='Бонус-игра · подписи кнопок (поверх выбора трассы)', pack='mini', screen='mmhints', shot='typo_bonus_menu/hints', show={'ALWAYS'},
         under=[dict(screen='mmchar', show={'ALWAYS', MINI_CUR[2]}, fields=MINI_CHAR),
                dict(screen='mmtrack', show={'ALWAYS', MINI_CUR[0]} | set(MINI_TRACKS), fields=dict(ROW9=3, ROW10=0))],
         extra_scenes=[dict(id='bhints_t', title='t', pack='mini', screen='mmtrack', show={'ALWAYS', MINI_CUR[0]} | set(MINI_TRACKS), fields=dict(ROW9=3, ROW10=0))]),
    dict(id='bpause', title='Бонус-игра · пауза', pack='mini', screen='minipause', shot='typo_bonus_menu/pause', show={'ALWAYS'}, sel=0),
    dict(id='cards', title='Колода собрана · открыто новое', pack='ui', screen='hud', shot='typo_rewards/cards', base='typo_talk/talk_c',
         show={'ALWAYS', 'ITEMS_COMPLETE'}),
    dict(id='dropped', title='Потерян предмет', pack='ui', screen='hud', shot='typo_dropped/dropped', base='typo_talk/talk_c',
         show={'ALWAYS', 'ITEM_DROPPED'}),
    dict(id='over', title='Провал миссии', pack='ui', screen='missionover', shot='typo_over/over', base='typo_boom/boom_c', show={'ALWAYS'}, sel=0,
         text={'MSN_FAIL': 'You destroyed your vehicle.', 'MSN_HINT': 'Hint : Avoid hitting large objects (buildings, trees and vehicles).'}),
    dict(id='msg', title='Окно сообщения', pack='ui', screen='message', shot='typo_windows/msg_none', base='typo_windows/msg_c', show={'ALWAYS'},
         text={'MSGBOX': "Congratulations! You've unlocked Cletus' Pickup Truck. Go to a phone booth to use it."}),
    # правка 348: MISSION SELECT паузы (pextra.shr) — DEV SAVE, уровень 1, выбрана последняя (текущая) миссия; значки и полоса выбора
    # группы ms_rows рисует страница (едут со строкой при шаге), остальное — картинки пакета на кадре паузы без интерфейса
    dict(id='msel', title='Пауза · MISSION SELECT', pack='pextra', screen='missionselect', shot='typo_extra/msel', base='typo_pause/pause_c',
         show={'ALWAYS'}, sel=6, fields=dict({'MS%d' % k: 2 for k in range(6)}, MS6=1, MS_LEVEL=0)),
    # №597: открытая карточка уровня 7 (карточка 6) — Scrooby-страница pextra.shr, кадр паузы без интерфейса; QR рисует движок поверх (метка на панели)
    dict(id='vcard', title='Пауза · VIEW CARDS · открытая карточка', pack='pextra', screen='viewcards', shot='typo_extra/vcard', base='typo_pause/pause_c',
         show={'ALWAYS', 'STREETRACE'}, sel=6),
    dict(id='saveq', title='Сохранение · вопрос', pack='psave', screen='pprompt', shot='typo_windows/saveq', base='typo_menusave/save_c', show={'ALWAYS'},
         sel=0, fields={'ROW11': 9}),
    dict(id='shop', title='Лавка · покупка машины', pack='shop', screen='purchase', shot='typo_rewards/shop',
         show={'ALWAYS', 'GAMBLE', 'STREETRACE', 'SKIP'}, fields={'ROW0': 3, 'ROW1': 1, 'ROW4': 3, 'ROW5': 1, 'ROW6': 10, 'ROW7': 3}),
    dict(id='phone', title='Телефонная будка', pack='phone', screen='phone', shot='typo_booth/phone',
         show={'ALWAYS', 'DAMAGE', 'STREETRACE', 'ITEMS_COMPLETE'}, fields={'ROW0': 0, 'ROW1': 100, 'ROW4': 3, 'ROW5': 3, 'ROW6': 5, 'ROW7': 7}),
]


# ---------------------------------------------------------------- пакеты (те же функции, что выпуск)
def ui_pack(tmp):
    def build(sc, assets, fonts):
        items, icons = U.build_items(sc)
        assets.images.update(U.EXTRA_IMAGES)   # №613: синтетическая плашка карточки (brief_plate.png) — до раскладки
        dl = U.adapt(items, icons, 'psp', assets, fonts)[0]
        return U.msgbox_fit(dl) if sc == 'message' else dl
    spec = dict(screens=U.SCREENS, build=build, tags=U.DEFAULT_TAGS, layout='layout_typo_panel.json')
    return U.pack(tmp / 'ui.shr', spec)


def packs(tmp):
    out = {'ui': ui_pack(tmp)}
    import save_export as SV
    out['psave'] = SV.export('psave', tmp / 'psave.shr', mocks=False)
    import shop_export as SH
    out['shop'] = SH.ui_pack(SH.forsale(U.LEVEL), tmp / 'shop.shr')
    out['phone'] = SH.phone_pack(SH.phone_cars(U.LEVEL), U.LEVEL, tmp / 'phone.shr')
    import menu_export as ME   # правка 348: экраны паузы pextra.shr (MISSION SELECT)
    out['pextra'] = ME.export('pextra', tmp / 'pextra.shr', mocks=False)
    import load_export as LO
    out['boot'] = LO.export('boot', tmp / 'boot.shr', mocks=False)
    out['load'] = LO.export('load', tmp / 'load.shr', mocks=False)
    import importlib.util
    spec = importlib.util.spec_from_file_location('typo_bonus_screens', ROOT / 'tools/bonus/screens_export.py')
    MG = importlib.util.module_from_spec(spec); spec.loader.exec_module(MG)
    out['mini'] = MG.export(tmp / 'mini.shr', mocks=False)
    return out


# ---------------------------------------------------------------- грани диска (для порта FontCache на странице)
def b64(a):
    return base64.b64encode(bytes(a)).decode('ascii')


def font_sources():
    out = {}
    for name, f in U.all_fonts().items():
        a = np.asarray(f['image'].convert('RGBA'))[..., 3]
        gl = [[c, g['x'], g['y'], g['w'], g['h'], g['adv'], g['left']] for c, g in sorted(f['glyphs'].items())]
        out[name] = dict(w=int(a.shape[1]), h=int(a.shape[0]), height=f['height'], baseline=f['baseline'],
                         gscale=U.glyph_scale(f, 'psp'), alpha=b64(a.astype(np.uint8).reshape(-1)), glyphs=gl)
        if f.get('pixel'):   # №547: пиксельные грани из шрифтов диска (pixel_fonts.derived): родной размер, кратные только целые
            out[name]['pixel'] = 1; out[name]['gscale'] = 1.0
            import pixel_fonts as _PF
            if name in _PF.KERN and _PF.kern_of(name): out[name]['kern'] = list(_PF.kern_of(name))
    import typo_panel_pixfonts as PF   # 11.10: два пиксельных шрифта Lauke (CC BY 3.0) — только панель, по сетке без сглаживания
    for name, spec in PF.FONTS.items():
        out[name] = PF.build_font(PF.FONT_DIR / spec['file'])
    return out


def pix8_cells():
    """ячейки pix8 как в viewer/ui_layout.h (жирный, ручные буквы, знаки кнопок): строки, левый столбец рисунка, ширина, шаг"""
    import re
    msx = bytes(int(v, 16) for v in re.findall(r'0x([0-9a-fA-F]{2})', (ROOT / 'viewer/bootmsx.h').read_text().split('{', 1)[1]))
    fix = {m[0]: [int(x, 16) for x in m[1].split(',')] for m in re.findall(r"\{'(.)', \{([^}]*)\}\}", (ROOT / 'viewer/ui_layout.h').read_text())}
    btn = [[0x00, 0x42, 0x24, 0x18, 0x18, 0x24, 0x42, 0x00], [0x00, 0x3c, 0x42, 0x42, 0x42, 0x42, 0x3c, 0x00],
           [0x00, 0x18, 0x18, 0x24, 0x24, 0x42, 0x7e, 0x00], [0x00, 0x7e, 0x42, 0x42, 0x42, 0x42, 0x7e, 0x00]]
    cells = []
    for c in range(99):
        if c >= 95:
            rows = btn[c - 95]
        else:
            ch = chr(c + 32)
            rows = fix[ch] if ch in fix else [((r | ((r >> 1) & ~(r << 1))) & 0xff) for r in msx[(c + 32) * 8:(c + 32) * 8 + 8]]
        m = 0
        for r in rows: m |= r
        if c >= 95: l, w = 0, 8
        elif not m: l, w = 0, 2
        else:
            a = next(x for x in range(8) if m & (0x80 >> x)); b = next(x for x in range(7, -1, -1) if m & (0x80 >> x)); l, w = a, b - a + 1
        adv = 9 if c >= 95 else w + 1
        cells.append([rows, l, w, adv])
    cmap = {}
    for code in range(256):
        if code in (0xa3, 0xbf): k = 95
        elif code in (0xae, 0xb5): k = 96
        elif code == ord('@'): k = 97
        elif code in (0xa7, 0xa9): k = 98
        elif 32 <= code <= 126: k = code - 32
        else: continue
        cmap[code] = k
    return dict(cells=cells, map=cmap)


def fontref(path):
    """эталон для гейта порта: грани -> строка, ячейки букв (уровни альфы 0..15 как в атласе T4), шаг, отступ"""
    fc = U.FontCache('psp'); faces = ['boulder_24', 'boulder_24*1.35+1', 'boulder_24*2.3', 'boulder_16*1.26', 'boulder_16*1.5', 'boulder_16@1',
                                      'boulder_16@1+1^2', 'Tt2001m__14', 'Tt2001m__14*1.06', 'Tt2001m__14*1.4', 'swz721n_10@1', 'boulder_16*1.07',
                                      'boulder_24*1.2+-1', 'Tt2001m__14*1.3', 'swz721mi_12*1.1', 'boulder_16', 'boulder_24*0.85^-1', 'pix8_8@1', 'pix8_8*1.5625+1^2', 'pix8_8*2.0']
    out = {}
    for face in faces:
        f = fc.get(face); gl = {}
        for code, g in f['glyphs'].items():
            if code > 255: continue
            bm = g['bm']
            lev = None if bm is None else np.round(bm * 15).astype(np.uint8)
            gl[code] = [g['w'], g['left'], int(g['adv']), None if lev is None else [int(lev.shape[0]), b64(lev.reshape(-1))]]
        out[face] = dict(lh=f['lh'], gh=f.get('gh', 0), glyphs=gl)
    Path(path).write_text(json.dumps(out))
    print('fontref ->', path, len(out), 'граней')


# ---------------------------------------------------------------- строки сцены
def shown(t, sc, scene, ref=False):
    show = scene.get('show', set())
    if t['tag'] != 'ALWAYS' and t['tag'] not in show:
        return False
    if t.get('selonly') and t.get('menu', -1) != scene.get('sel', -1):
        return False
    hid = scene.get('hid_ref' if ref else 'hid', scene.get('hid', set())) or set()
    if t['name'] in hid:
        return False
    if t.get('field') in ('SPEED', 'SPEED_UNIT'):
        return False
    return True


def text_of(t, scene):
    """строка, которую рисует движок (viewer/ui.c drawScreen T_TEXT)"""
    f, ss = t.get('field', 'NONE'), t.get('strings') or ['']
    sel = t.get('sel', 0) or 0
    ss = ss[sel:] or ['']
    fv = dict(scene.get('fields') or {})
    if f in (scene.get('text') or {}):
        return scene['text'][f]
    if t.get('menu', -1) >= 0 and scene.get('rows') and t['menu'] in scene['rows'] and t['type'] == U.T_TEXT:
        return scene['rows'][t['menu']]
    if f == 'NONE':
        return ss[0]
    fm = t.get('fmt', 'none')
    if f.startswith('STAT_') and f != 'STAT_MODE':
        if f == 'STAT_PCT':
            return '%d%%' % scene.get('pct', 0)
        key = t['name'].replace('_Unlocked', '')
        d, n = (scene.get('stats') or {}).get(key, (0, 0))
        return '%d/%d' % (d, n)
    if fm == 'ordinal':
        p = fv.get(f, 1); return ss[(p - 1) if 1 <= p <= 3 else 3] if len(ss) > 3 else ss[0]
    if fm == 'int':
        return '%d' % fv.get(f, 0)
    if fm == 'pct':
        return '%d%%' % fv.get(f, 0)
    if fm == 'select' or f.startswith('ROW'):
        k = fv.get(f, 0) % max(1, len(ss)); return ss[k]
    return ss[0]


def num_text(t, scene):
    f = t.get('field', 'NONE'); fv = scene.get('fields') or {}
    if f == 'NONE':
        return t.get('text', '')
    if f == 'MSN_DONE':   # вспышка конца миссии: строку ставит код (msnDoneText), сцена несёт её в text
        return (scene.get('text') or {}).get('MSN_DONE', 'MISSION COMPLETE!')
    if f == 'LAP':
        return '%d/%d' % (fv.get('LAP', 1), fv.get('LAPS', 3))
    if f == 'POSITION':   # viewer/ui_anim.h uiPosText: «4 /4» (место, соперники); без числа соперников — только место
        pos, racers = fv.get('POSITION', 1), fv.get('RACERS', 0)
        return ('? /%d' % racers if racers > 0 else '?') if pos < 0 else ('%d /%d' % (pos, racers) if racers > 0 else '%d' % pos)
    if f == 'CARDS':
        return '%d/%d' % (fv.get('CARDS', 0), fv.get('CARDS_TOTAL', 7))
    if f == 'TIMER' or f == 'PARTIME':
        s = int(fv.get(f, 0)) // 1000; return '%d:%02d' % (s // 60, s % 60)
    return '%d' % fv.get(f, 0)


def rgba(c):
    return [int(v) for v in c]


def group_of(sc, t, var=None):
    for g in UT.GROUPS:
        if UT.matches(g, sc, t, var):
            return g['id']
    return None


def carry_of(sc, t):
    """правка 348: группа, с чьей строкой едет элемент (ui_typo rowcarry: значок и полоса выбора строки MISSION SELECT), None — нет"""
    for g in UT.GROUPS:
        if UT._carried(g, sc, t):
            return g['id']
    return None


# ---------------------------------------------------------------- картинки
class Imgs:
    def __init__(self, out):
        self.dir = out / 'img'; self.dir.mkdir(parents=True, exist_ok=True); self.seen = {}
        # №596 (закон Роба 15.10): пересборка панели НЕ уносит картинки из img/ (13.10 так пропали фоны 29 экранов: прежний код переносил все PNG в резерв, а писал только пересобранные сцены).
        # Имена картинок по хэшу содержимого, поэтому повторная запись безвредна; лишние файлы остаются. Проверка ссылок страницы: tests/ui/typo_img_check.py

    def put(self, im, hint='l'):
        buf = io.BytesIO(); im.save(buf, 'PNG', optimize=True); data = buf.getvalue()
        h = hashlib.sha1(data).hexdigest()[:10]
        if h not in self.seen:
            name = '%s_%s.png' % (hint, h); (self.dir / name).write_bytes(data); self.seen[h] = name
        return 'img/' + self.seen[h]


def item_layer(t, bitmaps, state, sel):
    """один элемент списка рисования, как его рисует tools/ui_export.py render (картинки пакета после квантования) -> (картинка, x, y)"""
    t2 = dict(t); t2['tag'] = 'ALWAYS'
    im = U.render([t2], U.DST_W, U.DST_H, state, bitmaps, Image.new('RGBA', (U.DST_W, U.DST_H), (0, 0, 0, 0)), None, sel)
    bb = im.getchannel('A').getbbox()
    if not bb:
        return None
    return im.crop(bb), bb[0], bb[1]


def msnicon(rel, ext):
    """значок задания (msnicons) ровно размера рамки аватара, как tools/msnart_export.py: ui_export.resample -> RGBA, видимый правый край"""
    from p3d import read
    root = read(U.WEB / 'source/game/art/frontend/dynaload/images/msnicons' / rel)
    for c in root.children:
        if c.id == 0x19005:
            _, im = U.decode_sprite_image(c)
            w, h = int(ext[0]), int(ext[1])
            r = U.resample(im, w, h)
            a = np.asarray(r)[..., 3]
            vis = 0
            for x in range(w - 1, -1, -1):
                if (a[:, x] >= 32).any(): vis = x + 1; break
            cols = np.where((a >= 32).any(axis=0))[0]
            return r, w, h, vis, (int(cols[0]) if len(cols) else 0)
    return None


NUM_GK = {'hud_nums': [round(0.6 + 0.05 * i, 2) for i in range(21)], 'hud_mdone': [round(1.0 + 0.1 * i, 2) for i in range(14)], 'tut_text': [round(0.3 + 0.05 * i, 2) for i in range(14)]}


def tint(im, col):
    """картинка буквы x цвет вершины (GE: GU_TFX_MODULATE), как viewer/ui.c drawNum"""
    if list(col) == [255, 255, 255, 255]:
        return im
    a = np.asarray(im.convert('RGBA')).astype(np.float32) * np.array(col, np.float32) / 255
    return Image.fromarray(np.clip(a + .5, 0, 255).astype(np.uint8), 'RGBA')


def num_sets(gid, t, chars_needed, imgs, col, qbm=None):
    """картинки букв спрайтового шрифта для масштабов NUM_GK (выбор панели); масштаб по умолчанию — из пакета (квантованные)"""
    sets = {}
    gk0 = t.get('glyph_k', 1.0)
    ks = sorted(set(NUM_GK.get(gid, []) + [gk0]))
    for gk in ks:
        a = U.Assets(); it = dict(t, glyph_k=gk)
        glyphs, pre = U.num_glyphs(it, U.S, a)
        tab = {}
        for ch, g in glyphs.items():
            if ch.upper() not in chars_needed and ch not in chars_needed:
                continue
            key, gw, gh, xoff, adv = g
            src = qbm[key] if (qbm is not None and abs(gk - gk0) < 1e-9 and key in qbm) else a.bitmaps.get(key)
            tab[ch] = [imgs.put(tint(src, col), 'g') if key else None, gw, gh, xoff, adv]
        pinfo = None
        if pre:
            pim = qbm[pre] if (qbm is not None and abs(gk - gk0) < 1e-9 and pre in qbm) else a.bitmaps[pre]
            pinfo = [imgs.put(pim, 'g'), pim.width, pim.height]
        sets['%.2f' % gk] = dict(glyphs=tab, prefix=pinfo)
    return sets, gk0


def scene_data(scene, res, imgs, shots):
    have_shot = bool(scene.get('shot') and shots and (shots / (scene['shot'] + '_b.png')).exists())
    nocmp = os.environ.get('TYPO_PANEL_NOCOMPARE') == '1'
    if nocmp and have_shot and (shots / (scene['shot'] + '_c.png')).exists():
        # Правка 500: снимки старше текущей игры несут СТАРЫЙ интерфейс (пузырь, радар, значки на прежних местах) в кадре «b». Берём только 3D без интерфейса («c»), картинки
        # интерфейса собирает пакет текущей раскладки (как у сцен без снимка): тексты и рамки сходятся с игрой
        scene = dict(scene, base=scene['shot'] + '_c'); have_shot = False; stale3d = True
    else:
        stale3d = False
    sc = scene['screen']; dl = res['screens'][sc]; bm = res['qbitmaps']
    state = {'show': set(scene.get('show', set()))}
    state.update(scene.get('fields') or {})
    sel = scene.get('sel', -1)
    items, statics, texts, nums, fitlist = [], [], [], [], []
    obj = None
    for i, t in enumerate(dl):
        ty = t['type']
        fitlist.append([ty, t['tag'], t['name']] + [int(v) for v in t.get('dst', [0, 0, 0, 0])])
        if ty == U.T_TEXT:
            if not shown(t, sc, scene) and not shown(t, sc, scene, ref=True):
                continue
            col = rgba(t.get('color', [255, 255, 255, 255]))
            menu = t.get('menu', -1)
            if menu >= 0 and t['name'] in (scene.get('dim') or set()):
                col = [160, 160, 160, 128]                  # viewer/ui.c DIM_ABGR
            elif menu >= 0 and menu == sel:
                col = [255, 230, 20, 255]                   # SEL_ABGR
            sh = None
            if t.get('sh'):
                sdx, sdy, scol = t['sh']; sh = [int(sdx), int(sdy), rgba(scol)]
            texts.append(dict(i=i, name=t['name'], page=t['page'], group=group_of(sc, t, 'avatar' if scene.get('obj') == 'ext' else 'plain'), font=t['font'], pix8=UT.engine_pix8(sc, t), pix8Default=bool(t.get('pix8_default')),
                              dst=[int(t['dst'][0]) - (3 if (t.get('fmt') == 'ordinal' and sc == 'hud' and os.environ.get('ORDINAL_OLD') != '1') else 0)] + [int(v) for v in t['dst'][1:]], ha=U.HALIGN.get(t.get('halign', 'left'), 0), va=U.VALIGN.get(t.get('valign', 'top'), 0),   # №545: игра рисует окончание места на ORDINAL_DX=3 px левее пакета (ui.c)
                              wrap=bool(t.get('wrap')), field=t.get('field', 'NONE'), tag=t['tag'], menu=menu, color=col, sh=sh,
                              text=text_of(t, scene), vis=shown(t, sc, scene), vis_ref=shown(t, sc, scene, ref=True),
                              hid=t['name'] in (scene.get('hid') or set()),
                              strings=list(t.get('strings') or [])))
        elif ty == U.T_NUM:
            if not shown(t, sc, scene) and not (sc == 'tutorial' and t['name'] == 'TutorialMessage'):
                continue
            gid = group_of(sc, t, 'avatar' if scene.get('obj') == 'ext' else 'plain')
            if sc == 'tutorial' and t['name'] == 'TutorialMessage':
                txt = U.tutorial_texts()[scene.get('tut', 0)]
            else:
                txt = num_text(t, scene)
            need = set(txt.upper()) | set(txt)
            sets, gk0 = num_sets(gid, t, need, imgs, rgba(t.get('color', [255, 255, 255, 255])), bm)
            nums.append(dict(i=i, name=t['name'], page=t['page'], group=gid, dst=[int(v) for v in t['dst']], ha=U.HALIGN.get(t.get('halign', 'left'), 0),
                             va=U.VALIGN.get(t.get('valign', 'top'), 0), color=rgba(t.get('color', [255, 255, 255, 255])), text=txt,
                             gk0=gk0, sets=sets, tut=(sc == 'tutorial' and t['name'] == 'TutorialMessage'), field=t.get('field', 'NONE')))
        else:
            if ty == U.T_SLOT and t.get('field') == 'OBJICON':   # значок задания (аватар извне): рамка для начала текста (objTextStart)
                obj = dict(slot=[int(v) for v in t['dst']], ext=[int(v) for v in t.get('extframe', t['dst'])], tag=t['tag'])
            if not shown(t, sc, scene):
                continue
            gid = group_of(sc, t, 'avatar' if scene.get('obj') == 'ext' else 'plain'); cg = carry_of(sc, t) if gid is None else None
            if cg is not None:
                gid = cg
            if t.get('home'):                   # №623: значок дома вне миссии — рисует игра, в сценах панели с кружком задания его нет
                continue
            if ty == U.T_RECT and not t.get('fill') and os.environ.get('TYPO_FLAT_OLD') != '1':   # №574 2b-3: плоские плашки (заливка цветом: фон рамки, строки таблицы, нить) — слои: выбор, сдвиг, масштаб, ширина, высота
                dx_, dy_, dw_, dh_ = [int(v) for v in t['dst']]
                cs = t.get('colors')
                statics.append(dict(i=i, name=t['name'], page=t['page'], tag=t['tag'], alphaTop=0, group=None, dst=[dx_, dy_, dw_, dh_], img=None, at=[dx_, dy_], src=None, hs=False, frame=0,
                                    srcframe=None, carry=False, flat=rgba(t.get('color', [255, 255, 255, 255])), grad=[rgba(cs[0]), rgba(cs[2])] if cs else None))
                continue
            action_img = sc == 'hud' and t['tag'] == 'ACTION' and ty == U.T_IMG
            movable = gid is not None or action_img or ty == U.T_IMG   # №574 2b: все картинки экрана (рамки, плашки, значки, баннеры) — отдельные объекты: выбор, сдвиг, масштаб
            if not movable:
                continue
            lay = item_layer(t, bm, state, sel)
            if lay is None:
                continue
            im, x, y = lay
            k = 0
            fld = t.get('field', 'NONE')
            if ty == U.T_IMG and fld != 'NONE':
                k = int(state.get(fld, 0)); k = max(0, min(k, len(t.get('bitmaps') or [1]) - 1))
            src = None
            if ty == U.T_IMG and t.get('frames'):
                fk = t['frames'][min(k, len(t['frames']) - 1)]
                aimgs = dict(U.all_images())
                if fk not in aimgs:
                    import load_export as LD
                    aimgs.update(LD.Loader().img)
                src = imgs.put(aimgs[fk].convert('RGBA'), 's') if fk in aimgs else None
                if src is None and t.get('bitmaps'):   # картинки других пакетов (экран загрузки, будка, лавка, бонус): исходника нет в общем наборе — масштаб по готовой картинке пакета (без него масштаб превращался в сдвиг; panelsync 508e2d21)
                    src = imgs.put(bm[t['bitmaps'][min(k, len(t['bitmaps']) - 1)]].convert('RGBA'), 's')
            alpha_top = 0
            if action_img and t.get('bitmaps'):
                box = bm[t['bitmaps'][0]].getchannel('A').point(lambda a: 255 if a >= 32 else 0).getbbox()
                alpha_top = box[1] if box else 0
            statics.append(dict(i=i, name=t['name'], page=t['page'], tag=t['tag'], alphaTop=alpha_top, group=gid, dst=[int(v) for v in t['dst']], img=imgs.put(im, 'st'),
                                at=[x, y], src=src, hs=bool((t.get('bitmaps') or [''])[0].endswith('_hs')), frame=k,
                                srcframe=(t.get('frames') or [None])[k] if t.get('frames') else None,
                                carry=(cg is not None and not have_shot) or sc == 'bootload'))   # рисует страница, если реального фона с этим элементом нет
    if obj is not None:
        obj['icon'] = scene.get('obj')
        # Runtime retains oiPix even when OBJECTIVE/its icon is hidden
        edge_icon = scene.get('edge_icon') or scene.get('icon')
        if edge_icon:
            r = msnicon(edge_icon, obj['ext'][2:])
            if r:
                im, w, h, vis, left = r; obj.update(oiW=w, oiH=h, oiVisR=vis, oiVisL=left)
    d = dict(id=scene['id'], title=scene['title'], screen=sc, pack=scene['pack'], texts=texts, nums=nums, statics=statics, fit=fitlist,
             obj=obj, sel=sel, tut=scene.get('tut'), show=sorted(scene.get('show', set())), shot=scene.get('shot'))
    # фоны
    shot = scene.get('shot')
    if have_shot:
        # Правка 500: --no-compare (TYPO_PANEL_NOCOMPARE=1) — снимки старше текущей игры: кадры «целиком» (a, a2) несут СТАРЫЙ текст интерфейса и сбили бы
        # сверку «Кадр игры»; берём только фон без текста (b) и без интерфейса (c). Гейт typo_panel_check тогда пропускает такие сцены (нет bg_a)
        for k in (('b', 'c') if os.environ.get('TYPO_PANEL_NOCOMPARE') == '1' else ('a', 'b', 'c', 'a2')):   # a2 — тот же кадр целиком на 0,2 с позже: где он не равен «a», мир двигался (гейт)
            f = shots / (shot + '_%s.png' % k)
            d['bg_' + k] = imgs.put(Image.open(f).convert('RGB'), 'bg_' + scene['id']) if f.exists() else None
        d.setdefault('bg_a', None); d.setdefault('bg_a2', None)
        d['bg_note'] = ('кадр игры из безголового эмулятора без текста (%s, снимок 04.10; текст интерфейса рисует страница по текущим данным)' % shot
                        if os.environ.get('TYPO_PANEL_NOCOMPARE') == '1' else 'снимок безголового эмулятора (%s)' % shot)
    else:   # без снимка: картинки пакета на кадре игры без интерфейса (base) или на тёмном поле (как макет экспортёра)
        bshot = scene.get('base')
        if bshot and shots and (shots / (bshot + '.png')).exists():
            base = Image.open(shots / (bshot + '.png')).convert('RGBA')
        else:
            base = Image.new('RGBA', (U.DST_W, U.DST_H), (24, 24, 26, 255)); bshot = None
        for u in scene.get('under', ()):   # нижние экраны составной сцены: их картинки — в фон (бонус-игра: выбор трассы поверх персонажей)
            ud = res['screens'][u['screen']]; ust = {'show': set(u.get('show', set()))}; ust.update(u.get('fields') or {})
            base = U.render([t for t in ud if t['type'] not in (U.T_TEXT, U.T_NUM)], U.DST_W, U.DST_H, ust, bm, base, None, -1).convert('RGBA')
        st2 = dict(state); notext = [t for t in dl if t['type'] not in (U.T_TEXT, U.T_NUM) and carry_of(sc, t) is None]   # 348: rowcarry — страница
        im = U.render(notext, U.DST_W, U.DST_H, st2, bm, base, None, sel)
        d['bg_b'] = imgs.put(im.convert('RGB'), 'bg_' + scene['id'])
        d['bg_c'] = imgs.put(base.convert('RGB'), 'bg_' + scene['id'])
        d['bg_a'] = None
        fa = shots / (scene['shot'] + '_a.png') if shots and scene.get('shot') else None   # есть только кадр «a» (экраны бонус-игры, загрузка): для сверки «панель против кадра игры»
        if fa is not None and fa.exists():
            d['bg_a'] = imgs.put(Image.open(fa).convert('RGB'), 'bg_' + scene['id'])
            fa2 = shots / (scene['shot'] + '_a2.png'); d['bg_a2'] = imgs.put(Image.open(fa2).convert('RGB'), 'bg_' + scene['id']) if fa2.exists() else None
        d['bg_note'] = ('3D из снимка 04.10 без интерфейса (%s), интерфейс собран из текущих пакетов игры' % bshot) if stale3d else \
            ('кадр игры без интерфейса (%s) + картинки пакета; этот момент в эмуляторе не снят' % bshot) if bshot else \
            'снимка этого экрана нет: картинки пакета на тёмном поле (3D-фона у экрана нет или он не снят)'
    return d


def group_defaults(scenes):
    """значения групп «как в игре»: грань, строка, заглавная — по первой строке группы"""
    fc = U.FontCache('psp'); out = {}
    for s in scenes:
        for t in s['texts']:
            g = t['group']
            if not g or g in out:
                continue
            gr = UT.GROUP[g]
            if gr['kind'] == 'pix8':
                out[g] = dict(font='pix8', face0=t['font'])
            else:
                out[g] = dict(face=t['font'])
            if gr.get('pitch'):
                ys = sorted({x['dst'][1] for x in s['texts'] if x['group'] == g})
                out[g]['pitch'] = int(round((ys[-1] - ys[0]) / (len(ys) - 1))) if len(ys) > 1 else 0
        for n in s['nums']:
            if n['group'] and n['group'] not in out:
                out[n['group']] = dict(gk=n['gk0'])
        for st in s['statics']:
            if st['group'] and st['group'] not in out:
                out[st['group']] = dict(k=1.0)
    # A move group may overlap a font/number group; first-match group_of
    # must not make its controls or initial JSON disappear
    for g in UT.GROUPS:
        if g['kind'] == 'move' and any(t['name'] not in g.get('exclude', ()) and s['screen'] in g['screens'] and
                                      any(t['page'] == pg and UT._name_ok(nm, t['name']) for pg, nm in g['sel']) for s in scenes
                                      for t in s['texts'] + s['nums'] + s['statics']):
            out.setdefault(g['id'], {})
    return out


def proposal():
    """правки 310/311 (Роб: «немного крупнее» = несколько px; размеры — заглавная H, px PSP): BUSTED! 10 -> 13 и квитанция x1,25 (310);
    места с заглавной 7 px, которые Роб ещё не подгонял, — до 9 px (311), тонкий Tt2001m — гранью диска 1:1 (пиксель в пиксель, без мыла:
    правка 136). Меню сохранения уже +2 px помощником правки 309 (652d98a) — здесь не трогается. Не тронуто и то, что Роб решил сам:
    пузырь «Talk to Marge» (156: «шрифт хорош»), подписи кнопок (233: «мельче»), пункты меню (201), Continue и название карточки (299),
    подпись под △ (272)"""
    return {
        'hud_busted': dict(face='boulder_24*1.25'),         # заглавная 10 -> 13 px, строка 16 -> 20 (правка 310)
        'st_ticket': dict(k=1.25),                          # квитанция 42x57 -> 52x71 px: «50» на ней читается
        'shop_stats': dict(face='Tt2001m__14@1'),           # SPEED, ACCELERATION…: 7 -> 9 px, 1:1
        'shop_buttons': dict(face='Tt2001m__14@1'),         # Purchase / Cancel / Show Stats: 7 -> 9 px, 1:1
        'tut_disable': dict(face='Tt2001m__14@1'),          # Disable Tutorials: 7 -> 9 px, 1:1
        'hud_unlock': dict(face='boulder_16*1.4'),          # New bonus game track unlocked!: 7 -> 9 px
        'msgbox': dict(lead=1),                             # окно сообщения в 3–4 строки: шаг 10 -> 11 px (буквы 8×8 те же)
    }


def taste():
    """«Предложение вкуса 11.10» (поверх ТЕКУЩИХ значений Роба, кнопка в панели; значения в файлах не меняются, пока он не сохранит). Единая шкала по ролям вместо случайных множителей:
    заголовки экранов — заглавная Boulder 18 px; названия карточки и пункты меню/списков — 14 px; ответы, подписи и малые плашки — 11 px; текст — Bart 8 px (как выбрал Роб); подписи гонки —
    Swiss курсив 10 px. Все лица — пиксельные из tools/pixel_fonts.py (целый размер заглавной). Подписи кнопок и угловые элементы: ручные dx/dy сняты, ставят общие правила (555: центр значка,
    углы HINT_ALIGN). None — убрать ключ"""
    # шрифты НЕ предлагаем (Роб 12.10: «больше шрифты не трогаем без моего слова»): только снятие ручных сдвигов кнопок, ставят общие правила
    return {
        'hints_main': dict(dx=None, dy=None), 'hints_message': dict(dx=None, dy=None), 'hints_tut': dict(dx=None, dy=None), 'brief_btn': dict(dx=None, dy=None), 'lb_buttons': dict(dx=None, dy=None),
    }


def build(out, shots, shot_prefix='typo_'):
    tmp = out / '_pack'; tmp.mkdir(parents=True, exist_ok=True)
    initial = UT.load() or {'version': 1, 'groups': {}}
    # №382: исходная раскладка + один мост JSON; иначе dx/dy/k применяются дважды
    old_typo = os.environ.get('UI_TYPO')
    os.environ['UI_TYPO'] = '0'
    try:
        res = packs(tmp)
    finally:
        if old_typo is None: os.environ.pop('UI_TYPO', None)
        else: os.environ['UI_TYPO'] = old_typo
    imgs = Imgs(out)
    specs = []
    for scene in SCENES:
        scene = dict(scene)
        for key in ('shot', 'base'):
            if scene.get(key) and scene[key].startswith('typo_'):
                scene[key] = shot_prefix + scene[key][5:]
        specs.append(scene)
    scenes = []
    for spec in specs:
        d = scene_data(spec, res[spec['pack']], imgs, shots)
        for sub in spec.get('extra_scenes', ()):   # тексты и картинки соседних экранов составной сцены (группы те же, что на их экранах)
            ex = scene_data(sub, res[sub['pack']], imgs, shots)
            for key in ('texts', 'nums', 'statics', 'fit'): d[key].extend(ex[key])
        if spec.get('bonus_rows'):
            import re
            rows = {}
            logfile = shots / 'typo_bonus_accepted/smoke.txt' if shots else None
            if logfile and logfile.exists():
                for match in re.finditer(r'BONUS ev=sumrow k=(\d+) racer=(\d+) chr=(\d+) wins=(\S+) pts=(\S+) total=(\S+) best=(\S+) king=(\d+),(\d+)', logfile.read_text()):
                    k, racer, character, wins, points, total, best, kt, kl = match.groups()
                    rows[int(k)] = dict(fields={'ROW0': int(character), 'ROW1': int(racer)},
                                        text={'ROW2': wins, 'ROW3': points, 'ROW4': total, 'ROW5': best},
                                        show={'ALWAYS'} | ({'SKIP'} if int(kt) else set()) | ({'STREETRACE'} if int(kl) else set()))
            for k in range(4):
                row = dict(spec, screen='msrow%d' % k,
                           fields={'ROW0': (k + 2) % 5, 'ROW1': k},
                           text={'ROW2': str(3 - k), 'ROW3': str(12 - k * 3), 'ROW4': '2:34.50', 'ROW5': '0:50.20'})
                row.update(rows.get(k, {}))
                extra = scene_data(row, res['mini'], imgs, shots)
                for key in ('texts', 'nums', 'statics', 'fit'): d[key].extend(extra[key])
        scenes.append(d)
    # Preserve the generated UIP1 inputs as provenance for frame comparisons.
    # Project cleanup is reversible; a rebuild must not unlink its evidence.
    backup=ROOT/'_backups'/('typo-panel-packs-'+time.strftime('%Y%m%d-%H%M%S')+'-'+str(time.time_ns()))
    backup.mkdir(parents=True)
    manifest=[dict(name=p.name,size=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in tmp.iterdir() if p.is_file()]
    tmp.rename(backup/'packs')
    (backup/'manifest.json').write_text(json.dumps(dict(source=str(tmp),files=manifest),indent=2)+'\n')
    data = dict(built=time.strftime('%Y-%m-%d %H:%M'), S=U.S, FONT_MIN_PX=U.FONT_MIN_PX, fonts=font_sources(), pix8=pix8_cells(),
                groups=UT.GROUPS, defaults=group_defaults(scenes), scenes=scenes, proposal=proposal(), initial=initial, native_pix=bool(U.NATIVE_PIX_ON), native_thin=list(U.NATIVE_THIN), taste=taste(),
                hint_pages=list(UT.HINT_PAGES), tags=TAGS)
    failure_examples(data)
    page = PAGE_TEMPLATE.read_text().replace('/*@@DATA@@*/', 'window.TYPO = ' + json.dumps(data, ensure_ascii=False, separators=(',', ':'),
                                                                                        default=list) + ';')
    (out / 'index.html').write_text(page)
    try:
        if os.environ.get('NATIVE_PIX_ON') == '1': import native_compare as _NC; _NC.page(out)   # №566: страница сравнения граней только при NATIVE_PIX_ON=1
    except Exception as e:
        print('сравнение граней не собрано:', e)
    print('панель ->', out / 'index.html', '%.0f КБ' % ((out / 'index.html').stat().st_size / 1024), 'картинок', len(imgs.seen))


def add_flats(out):
    """№574 2b-3: плоские плашки (T_RECT с заливкой не на весь экран) — слои сцен: добавить их в statics уже собранной страницы (flat/grad, без картинок); снимки и остальное не трогаются.
    Повторный запуск заменяет прежние плашки"""
    html = (out / 'index.html').read_text(); k = html.index('window.TYPO = ') + len('window.TYPO = ')
    data = json.loads(html[k:html.index(';\n</script>', k)])
    tmp = Path(tempfile.mkdtemp(prefix='typo_flats_')); old_typo = os.environ.get('UI_TYPO'); os.environ['UI_TYPO'] = '0'
    try:
        res = packs(tmp)
    finally:
        if old_typo is None: os.environ.pop('UI_TYPO', None)
        else: os.environ['UI_TYPO'] = old_typo
    imgs = Imgs(out); n = 0
    for spec in SCENES:
        sc = next((x for x in data['scenes'] if x['id'] == spec['id']), None)
        if sc is None: continue
        subs = [spec] + list(spec.get('extra_scenes', ()))
        if spec.get('bonus_rows'): subs += [dict(spec, screen='msrow%d' % k, pack='mini', fields={'ROW0': (k + 2) % 5, 'ROW1': k}, text={'ROW2': str(3 - k), 'ROW3': str(12 - k * 3), 'ROW4': '2:34.50', 'ROW5': '0:50.20'}) for k in range(4)]
        sc['statics'] = [q for q in sc['statics'] if not q.get('flat')]
        for sub in subs:
            ex = scene_data(sub, res[sub.get('pack', spec['pack'])], imgs, None)
            for q in ex['statics']:
                if q.get('flat'): sc['statics'].append(q); n += 1
    data['initial'] = UT.load() or data['initial']
    (out / 'index.html').write_text(PAGE_TEMPLATE.read_text().replace('/*@@DATA@@*/', 'window.TYPO = ' + json.dumps(data, ensure_ascii=False, separators=(',', ':'), default=list) + ';'))
    print('плоских плашек добавлено', n)


def page_only(out):
    """только страница (шаблон tools/typo_panel_page.html) на данных уже собранной панели — без пересборки пакетов"""
    html = (out / 'index.html').read_text(); k = html.index('window.TYPO = ') + len('window.TYPO = ')
    data = failure_examples(json.loads(html[k:html.index(';\n</script>', k)]))
    data['initial'] = UT.load() or data['initial']   # №596: настройки Роба из build/ui_typo.json (после его сохранений и правок выравнивания)
    (out / 'index.html').write_text(PAGE_TEMPLATE.read_text().replace('/*@@DATA@@*/', 'window.TYPO = ' + json.dumps(data, ensure_ascii=False, separators=(',', ':')) + ';'))
    (out / 'typo_audit.js').write_bytes((Path(__file__).resolve().parent / 'typo_audit.js').read_bytes())   # №596: аудит выравнивания в браузере (Playwright)
    print('страница ->', out / 'index.html')


def regroup_page(out):
    """после добавления групп пузыря (ui_typo.py hud_bubble_avatar/plain, st_bubble_avatar/plain, №528): на данных уже собранной панели элементы пузыря в сценах получают группу своего варианта
    (сцена с аватаркой — avatar, остальные — plain), новые группы добавляются в список; всё остальное не трогается, снимков не нужно"""
    html = (out / 'index.html').read_text(); k = html.index('window.TYPO = ') + len('window.TYPO = ')
    data = json.loads(html[k:html.index(';\n</script>', k)])
    new = {g['id']: g for g in UT.GROUPS if g.get('variant')}
    have = {g['id'] for g in data['groups']}
    for sc in data['scenes']:
        var = 'avatar' if sc['id'] in {x['id'] for x in SCENES if x.get('obj') == 'ext'} else 'plain'   # в данных страницы поля obj нет — по описанию сцены
        for key, ty in (('texts', U.T_TEXT), ('statics', U.T_IMG)):
            for it in sc.get(key, ()):
                if it.get('group') in ('hud_bubble', 'st_bubble') or str(it.get('group', '')).endswith(('_avatar', '_plain')):
                    g = group_of(sc['screen'], dict(type=ty, name=it['name'], page=it.get('page')), var)
                    if g in new: it['group'] = g
    for gid, g in new.items():
        if gid not in have:
            data['groups'].append(json.loads(json.dumps(g, default=list)))
    for gid, g in new.items():   # «как в игре» у варианта — те же, что были у прежней общей группы
        if g.get('inherit') in data['defaults']: data['defaults'][gid] = dict(data['defaults'][g['inherit']])
    (out / 'index.html').write_text(PAGE_TEMPLATE.read_text().replace('/*@@DATA@@*/', 'window.TYPO = ' + json.dumps(data, ensure_ascii=False, separators=(',', ':'), default=list) + ';'))
    print('страница (группы пузыря) ->', out / 'index.html')


def rebuild_scene(out, shots, sid, shot_prefix='typo_'):
    """одна сцена панели заново (раскладка пакета + снимки игры) в уже собранной странице; остальные сцены и снимки не трогаются. Нужна, когда изменилась раскладка одного экрана (будка, 11.10)"""
    spec = dict(next(x for x in SCENES if x['id'] == sid))
    for key in ('shot', 'base'):
        if spec.get(key) and spec[key].startswith('typo_'): spec[key] = shot_prefix + spec[key][5:]
    tmp = out / '_pack1'; tmp.mkdir(parents=True, exist_ok=True)
    old_typo = os.environ.get('UI_TYPO'); os.environ['UI_TYPO'] = '0'
    try:
        import shop_export as SH
        U.project('frontend.p3d')
        if spec['pack'] == 'phone':
            res = {'phone': SH.phone_pack(SH.phone_cars(U.LEVEL), U.LEVEL, tmp / 'phone.shr')}
        elif spec['pack'] == 'ui':   # №598: пакет ui.shr с элементом PlaceCode (кадры — EBOOT с полем PLACE)
            os.environ['UI_PLACE_CODE'] = '1'
            res = {'ui': ui_pack(tmp)}
        elif spec['pack'] == 'boot':
            import load_export as LD
            res = {'boot': LD.export('boot', tmp / 'boot.shr', mocks=False)}
        else:
            res = None
    finally:
        if old_typo is None: os.environ.pop('UI_TYPO', None)
        else: os.environ['UI_TYPO'] = old_typo
    imgs = Imgs(out)
    d = scene_data(spec, res[spec['pack']], imgs, shots)
    html = (out / 'index.html').read_text(); k = html.index('window.TYPO = ') + len('window.TYPO = ')
    data = json.loads(html[k:html.index(';\n</script>', k)])
    if any(sc['id'] == sid for sc in data['scenes']):
        data['scenes'] = [d if sc['id'] == sid else sc for sc in data['scenes']]
    else:
        data['scenes'].insert(0, d)
    have = {g['id'] for g in data['groups']}
    for g in UT.GROUPS:
        if g['id'] not in have: data['groups'].append(json.loads(json.dumps(g, default=list)))
    defs = group_defaults([d])
    for gid, v in defs.items(): data['defaults'].setdefault(gid, v)
    (out / 'index.html').write_text(PAGE_TEMPLATE.read_text().replace('/*@@DATA@@*/', 'window.TYPO = ' + json.dumps(data, ensure_ascii=False, separators=(',', ':'), default=list) + ';'))
    print('сцена', sid, '->', out / 'index.html')


def import_scene(out, src, sid, after=None):
    """№597: сцена, собранная в другой копии панели (другой уровень или кадр), переносится в эту страницу: сцена, её группы и умолчания, картинки копируются (ничего не стирается)"""
    import shutil
    src = Path(src)
    def read(d):
        html = (d / 'index.html').read_text(); k = html.index('window.TYPO = ') + len('window.TYPO = ')
        return json.loads(html[k:html.index(';\n</script>', k)])
    other = read(src); data = read(out)
    sc = next(x for x in other['scenes'] if x['id'] == sid)
    import re
    for name in set(re.findall(r'img/[A-Za-z0-9_.\-]+\.png', json.dumps(sc))):
        if not (out / name).exists(): shutil.copy2(src / name, out / name)
    if any(x['id'] == sid for x in data['scenes']):
        data['scenes'] = [sc if x['id'] == sid else x for x in data['scenes']]
    else:
        i = next((k + 1 for k, x in enumerate(data['scenes']) if x['id'] == after), len(data['scenes'])); data['scenes'].insert(i, sc)
    have = {g['id'] for g in data['groups']}
    for g in UT.GROUPS:
        if g['id'] not in have: data['groups'].append(json.loads(json.dumps(g, default=list)))
    for gid, v in other['defaults'].items(): data['defaults'].setdefault(gid, v)
    data['initial'] = UT.load() or data['initial']
    (out / 'index.html').write_text(PAGE_TEMPLATE.read_text().replace('/*@@DATA@@*/', 'window.TYPO = ' + json.dumps(data, ensure_ascii=False, separators=(',', ':'), default=list) + ';'))
    print('сцена', sid, 'перенесена из', src)


def regroup_scene(out, sid):
    """после новой группы (hints_vcards, №596): элементы одной сцены получают группу по её правилам, остальные сцены и снимки не трогаются"""
    html = (out / 'index.html').read_text(); k = html.index('window.TYPO = ') + len('window.TYPO = ')
    data = json.loads(html[k:html.index(';\n</script>', k)])
    for sc in data['scenes']:
        if sc['id'] != sid: continue
        for key, ty in (('texts', U.T_TEXT), ('statics', U.T_IMG)):
            for it in sc.get(key, ()):
                if it.get('group'): continue
                g = group_of(sc['screen'], dict(type=ty, name=it['name'], page=it.get('page')), None)
                if g: it['group'] = g
        for it in sc.get('texts', ()):
            if it['name'] == 'BriefLoading': it['group'] = 'brief_loading'   # №632: своя группа
    have = {g['id'] for g in data['groups']}
    for g in UT.GROUPS:
        if g['id'] not in have: data['groups'].append(json.loads(json.dumps(g, default=list)))
    for gid, v in group_defaults([x for x in data['scenes'] if x['id'] == sid]).items(): data['defaults'].setdefault(gid, v)
    data['initial'] = UT.load() or data['initial']
    (out / 'index.html').write_text(PAGE_TEMPLATE.read_text().replace('/*@@DATA@@*/', 'window.TYPO = ' + json.dumps(data, ensure_ascii=False, separators=(',', ':'), default=list) + ';'))
    print('сцена', sid, 'перегруппирована')


def refresh_shots(out, shots):
    """Refresh screenshots and dynamic strings without re-exporting unchanged UI packs."""
    html = (out / 'index.html').read_text(); k = html.index('window.TYPO = ') + 14
    data = json.loads(html[k:html.index(';\n</script>', k)])
    specs = {s['id']: s for s in SCENES}
    pairs_path = shots / 'typography_pairs.json'
    pairs = json.loads(pairs_path.read_text()) if pairs_path.exists() else {}
    for scene in data['scenes']:
        spec = specs[scene['id']]
        if scene['id'] in ('busted', 'hitrun'):
            for text in scene['texts']:
                if text['tag'] == 'ACTION': text['vis'] = text['vis_ref'] = False
        if scene['id'] == 'save':
            stamp = time.localtime((shots / (spec['shot'] + '_a.png')).stat().st_mtime)
            spec['rows'][3] = 'DEV SAVE  LEVEL 1  %02d/%02d' % (stamp.tm_mday, stamp.tm_mon)
        scene['shot'] = spec['shot']
        # Independent runs of the same dialogue checkpoint keep camera timing paired.
        if scene['id'] in pairs.get('independent_pairs', []): scene.pop('bg_a2', None)
        for text in scene['texts']:
            if scene['id'] == 'menu' and text['menu'] == spec.get('sel'):
                text['color'] = [255, 230, 20, 255]
            if text['name'] in spec.get('hid', set()): text['vis'] = False
            if text['name'] in spec.get('hid_ref', spec.get('hid', set())): text['vis_ref'] = False
            if text['field'] in spec.get('text', {}):
                text['text'] = spec['text'][text['field']]
            if text['menu'] >= 0 and text['menu'] in spec.get('rows', {}):
                text['text'] = spec['rows'][text['menu']]
        for suffix in ('a', 'b', 'c', 'a2'):
            source = shots / (spec['shot'] + '_' + suffix + '.png')
            if not source.exists(): continue
            buffer = io.BytesIO(); Image.open(source).convert('RGB').save(buffer, 'PNG', optimize=True)
            raw = buffer.getvalue()
            name = 'bg_' + scene['id'] + '_' + hashlib.sha1(raw).hexdigest()[:10] + '.png'
            (out / 'img' / name).write_bytes(raw)
            if suffix != 'a2' or scene['id'] not in pairs.get('independent_pairs', []): scene['bg_' + suffix] = 'img/' + name
        scene['bg_note'] = 'снимок безголового эмулятора (%s)' % spec['shot']
    failure_examples(data)
    (out / 'index.html').write_text(PAGE_TEMPLATE.read_text().replace('/*@@DATA@@*/', 'window.TYPO = ' + json.dumps(data, ensure_ascii=False, separators=(',', ':')) + ';'))


if __name__ == '__main__':
    a = sys.argv[1:]
    if '--fontref' in a:
        fontref(a[a.index('--fontref') + 1]); sys.exit(0)
    out = Path(a[a.index('--out') + 1]) if '--out' in a else ROOT / 'build' / 'ТИПОГРАФИКА_ПАНЕЛЬ'
    shots = Path(a[a.index('--shots') + 1]) if '--shots' in a else ROOT / 'build' / 'twins' / 'scen' / 'full'
    if '--refresh-shots' in a:
        refresh_shots(out, shots); sys.exit(0)
    if '--regroup' in a:
        regroup_page(out); sys.exit(0)
    if '--scene' in a:
        rebuild_scene(out, shots, a[a.index('--scene') + 1], a[a.index('--shot-prefix') + 1] if '--shot-prefix' in a else 'typo_'); sys.exit(0)
    if '--regroup-scene' in a:
        regroup_scene(out, a[a.index('--regroup-scene') + 1]); sys.exit(0)
    if '--import-scene' in a:
        i = a.index('--import-scene'); import_scene(out, a[i + 1], a[i + 2], a[i + 3] if len(a) > i + 3 and not a[i + 3].startswith('--') else None); sys.exit(0)
    if '--add-flats' in a:
        add_flats(out); sys.exit(0)
    if '--page-only' in a:
        page_only(out); sys.exit(0)
    U.project('frontend.p3d')
    build(out, shots, a[a.index('--shot-prefix') + 1] if '--shot-prefix' in a else 'typo_')
