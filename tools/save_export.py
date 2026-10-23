#!/usr/bin/env python3
"""Экраны сохранения оригинала (Scrooby, диск Роба) -> два пакета UIP1 того же формата, что menu.shr (рисует viewer/ui.c uiScr*,
логику ведёт viewer/savemenu.c; грузятся только на время показа):

  fsave.shr   главное меню → LOAD GAME (над 3D-гостиной, в рамке ТВ):
              0 slots   frontend.p3d LoadGame.scr: TVFrame + BigBoard + SelectMemoryDevice + GameSlots + Back + Accept
              1 prompt  Prompt3D.scr:  TVFrame + MessageBox + GenericPrompt + Prompt (YES / NO) + Accept3
              2 notice  то же, один ответ Continue (сообщение с подтверждением: «Load Successful», ошибка)
              3 message Message3D.scr: TVFrame + MessageBox + Message (идёт чтение / запись)
              4 strings строки библии для кода (не рисуется): см. STRINGS
  psave.shr   пауза → SAVE GAME (над остановленным городом):
              0 slots   ingame.p3d SaveGame.scr: PauseBgd + BigBoard + SelectMemoryDevice + GameSlots + Back + Accept
              1 prompt  Prompt.scr:  PauseBgd + MessageBox + GenericPrompt + Prompt + Accept3
              2 notice  то же, один ответ Continue
              3 message Message.scr: MessageBox + Message
              4 strings

Строки меню: слоты Slot0..Slot3 (Foreground/Menu GameSlots.pag, сверху вниз; Slot4..7 лежат в скрытом слое Unused — у оригинала
слотов 4), ответы Response0/1 (Prompt.pag). Текст сообщения (Message GenericPrompt.pag / Message.pag) — поле ROW11 с вариантами
MSGS (номер варианта ставит код: savemenu.c SVM_*), подпись слота код подменяет строкой слота (uiScrRowText).
Правила порта (в данных нет / другая платформа; сверить с эталоном PS2):
  - у PSP одно устройство (Memory Stick): группа «Select another memory card (PS2)» и значок △ не выводятся, строка устройства
    CurrentMemoryDevice (у PS2 её пишет код: «memory card (PS2) slot 1») = «Memory Stick»
  - в текстах (PS2) слова «memory card (PS2) [in MEMORY CARD slot $]» заменены на «Memory Stick»; «$» в номере слота ставит код
  - FullMessage (нет места на карте PS2) не выводится: ошибку записи показывает сообщение ERROR_HW_FAILURE_SAVING_(PS2)
  - значок ошибки ErrorIcon (MessageBox.pag) виден только у сообщений об ошибке: тег MISSION_FAILED (показывает код)
    python tools/save_export.py                    # оба пакета -> build/fsave.shr, build/psave.shr + макеты build/ui/save_*.png
    python tools/save_export.py --pack psave --out X
Читает только диск (hit-and-run-web/source/game) и hit-and-run-web/tools (MIT) через ui_export.py.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ui_export as U  # noqa: E402

SCREENS = ['slots', 'prompt', 'notice', 'message', 'strings']
PACKS = {'fsave': ['f' + s for s in SCREENS], 'psave': ['p' + s for s in SCREENS]}
FE, IG = 'frontend.p3d', 'ingame.p3d'
BG = ('ingamel%d.p3d' % U.LEVEL, 'PauseBgd.pag')
PAGES = {
    'fslots': [(FE, 'TVFrame.pag'), (FE, 'BigBoard.pag'), (FE, 'SelectMemoryDevice.pag'), (FE, 'GameSlots.pag'), (FE, 'Back.pag'),
               (FE, 'Accept.pag')],
    'fprompt': [(FE, 'TVFrame.pag'), (FE, 'MessageBox.pag'), (FE, 'GenericPrompt.pag'), (FE, 'Prompt.pag'), (FE, 'Accept3.pag')],
    'fmessage': [(FE, 'TVFrame.pag'), (FE, 'MessageBox.pag'), (FE, 'Message.pag')],
    'pslots': [BG, (IG, 'BigBoard.pag'), (IG, 'SelectMemoryDevice.pag'), (IG, 'GameSlots.pag'), (IG, 'Back.pag'), (IG, 'Accept.pag')],
    'pprompt': [BG, (IG, 'MessageBox.pag'), (IG, 'GenericPrompt.pag'), (IG, 'Prompt.pag'), (IG, 'Accept3.pag')],
    'pmessage': [(IG, 'MessageBox.pag'), (IG, 'Message.pag')],
}
PAGES['fnotice'] = PAGES['fprompt']; PAGES['pnotice'] = PAGES['pprompt']
PAGES['fstrings'] = [(FE, 'GameSlots.pag')]; PAGES['pstrings'] = [(IG, 'GameSlots.pag')]
SLOTS = 4
# тексты сообщений (поле ROW11: варианты для макетов; на PSP код берёт строку с экрана strings и подставляет номер слота).
# Порядок = viewer/savemenu.c enum SVM_MSG_* (сверяет tests/savegame/host.sh)
MSGS = ['MSG_SAVE_CONFIRM_OVERWRITE_(PS2)', 'MSG_SAVE_CONFIRM_(PS2)', 'MSG_SAVING_GAME_(PS2)', 'MSG_SAVE_SUCCESSFUL',
        'ERROR_HW_FAILURE_SAVING_(PS2)', 'MSG_LOAD_CONFIRM_(PS2)', 'MSG_LOADING_GAME_(PS2)', 'MSG_LOAD_SUCCESSFUL',
        'ERROR_DATA_CORRUPT_LOADING_(PS2)', 'MSG_CONFIRM_SAVE_BEFORE_QUIT', 'MSG_DELETING_(PS2)', 'MSG_DELETE_CORRUPT_FAIL_(PS2)',
        'MSG_LOAD_CARD_EMPTY_(PS2)']
# строки для кода (экран strings, строка k = STRINGS[k]); ключ или ('#', хеш) — строка библии, ключ которой не известен
DAMAGED_HASH = 527255                                   # «< Damaged Save >»
STRINGS = ['EMPTY_SLOT', ('#', DAMAGED_HASH)] + ['LEVEL_%d' % i for i in range(1, 8)] + MSGS   # = savemenu.c enum SVS_*
ROW_MSG = 11
MSG_TAG_ERROR = 'MISSION_FAILED'
TAGS = {sc: {'ALWAYS'} for p in PACKS.values() for sc in p}
DEVICE = 'Memory Stick'
# правка 309 (Роб 04.10, голосом: «доработал бы там размер шрифта» — меню сохранения): текст крупнее на 2 px — заглавная H 7 -> 9 px.
# Строки слотов и ответы (boulder_16 — грань оригинала, пересэмпл R7 как и прежде) x SAVE_FONT_K; строки «Save to: / Memory Stick»
# и сообщения — Tt2001m 1:1 (пиксельная грань диска, заглавная 9, прежде дробная 0,69). Места и рамки — оригинала (R1, один масштаб):
# строка boulder_16*1.35 — 15 px при шаге слотов 17. Подсказки кнопок (Accept / Back) — общей гранью HINT_FACE, как в паузе
# (правка 233; общий размер текста — правка 311). Правило порта. SAVE_FONT_OLD=1 — прежние грани (красный tests/ui/save_font.py)
SAVE_FONT_OLD = bool(os.environ.get('SAVE_FONT_OLD'))
SAVE_FONT_K = float(os.environ.get('SAVE_FONT_K', '1.35'))
SAVE_INFO_FACE = os.environ.get('SAVE_INFO_FACE', 'Tt2001m__14@1')


def save_face(it):
    """грань текста меню сохранения после правки 309 (подсказки кнопок — общие)"""
    f = it['font']
    if SAVE_FONT_OLD or it['page'] in U.HINT_PAGES:
        return f
    if f.split('*')[0].split('@')[0].split('+')[0] == 'Tt2001m__14':
        return SAVE_INFO_FACE
    return U.face_mul(f, SAVE_FONT_K)


def psp_text(s):
    """тексты PS2 про карту памяти -> PSP (правило порта, см. заголовок)"""
    for a in ('memory card (PS2) in MEMORY CARD slot $', 'Memory card (PS2) in MEMORY CARD slot $', 'memory card (PS2)',
              'Memory card (PS2)'):
        s = s.replace(a, DEVICE)
    return s


def bible_hash(h):
    """строка английской библии по её хешу (ключ не известен): тот же разбор, что ui_export.load_bible"""
    import struct
    from p3d import read, walk, string
    root = read(U.SCROOBY / 'resource/txtbible/srr2.p3d')
    for c in walk(root):
        if c.id != 0x1800E:
            continue
        _, p = string(c.data)
        if c.data[p:p + 1] != U.LANG.encode():
            continue
        n, mod, size = struct.unpack_from('<III', c.data, p + 1); p += 13
        hs = struct.unpack_from('<%dI' % n, c.data, p); offs = struct.unpack_from('<%dI' % n, c.data, p + 4 * n)
        buf = c.data[p + 8 * n:]
        for hh, o in zip(hs, offs):
            if hh == h:
                return buf[o:].decode('utf-16-le', errors='replace').split('\0')[0]
    raise SystemExit('нет строки библии с хешем %d' % h)


TEXT_FALLBACK = {'MSG_DELETING_(PS2)': 'Deleting...'}


def text(key):
    v = bible_hash(key[1]) if isinstance(key, tuple) else U._BIBLE(key)
    if v is None and key in TEXT_FALLBACK: v = TEXT_FALLBACK[key]   # №880: в библии NTSC нет MSG_DELETING_(PS2)
    if v is None:
        raise SystemExit('нет строки библии %s' % (key,))
    return psp_text(v)


def items(sc):
    its, _ = U.build_items(sc)
    kind = sc[1:]
    out = []
    if kind == 'strings':                                               # не рисуется: строки для кода, по строке меню
        proto = next(it for it in its if it['type'] == U.T_TEXT and it['name'] == 'Slot0')
        for k, key in enumerate(STRINGS):
            out.append(dict(proto, name='Str%d' % k, strings=[text(key)], menu=k, sel=0))
        return out
    slots = sorted((it for it in its if it['page'] == 'GameSlots.pag' and it['type'] == U.T_TEXT and it['name'].startswith('Slot')),
                   key=lambda t: t['rect'][1])
    assert kind != 'slots' or len(slots) == SLOTS, [t['name'] for t in slots]
    resp = sorted((it for it in its if it['page'] == 'Prompt.pag' and it['type'] == U.T_TEXT), key=lambda t: t['rect'][1])
    for it in its:
        nm, pg = it['name'], it['page']
        if pg == 'SelectMemoryDevice.pag':
            if 'SelectMemoryDevice' in it['path'].split('/') or nm == 'AuxX':   # «Select another memory card» — у PSP одно устройство
                continue
            if nm == 'LoadSave':                                        # «Load from:» / «Save to:»
                it = dict(it, strings=[text('LOAD_GAME_FROM' if sc[0] == 'f' else 'SAVE_GAME_TO')], sel=0)
            elif nm == 'CurrentMemoryDevice':
                it = dict(it, strings=[DEVICE], sel=0)
        if pg == 'GameSlots.pag':
            if nm == 'FullMessage':
                continue
            k = next((i for i, s in enumerate(slots) if s is it), -1)
            if k >= 0:
                it = dict(it, menu=k, sel=0)
        if pg == 'Prompt.pag':
            if it['type'] != U.T_TEXT:
                continue
            r = next(i for i, s in enumerate(resp) if s is it)
            want = (['YES', 'NO'] if kind == 'prompt' else ['CONTINUE'])
            if r >= len(want):
                continue
            it = dict(it, strings=[text(want[r])], menu=r, sel=0)
        if pg in ('GenericPrompt.pag', 'Message.pag') and it['type'] == U.T_TEXT and nm == 'Message':
            it = dict(it, strings=[text(k) for k in MSGS], field='ROW%d' % ROW_MSG, fmt='select', sel=0, wrap=True)
        if pg == 'MessageBox.pag' and nm == 'ErrorIcon':
            it = dict(it, tag=MSG_TAG_ERROR)
        out.append(it)
    return out


def build(sc, assets, fonts):
    its = [dict(it, font=save_face(it)) if it['type'] == U.T_TEXT else it for it in items(sc)]   # правка 309
    dl, _ = U.adapt(its, {}, 'psp', assets, fonts)
    return dl


def group_of(key):
    return 'tv' if key.split('@')[0].startswith('tvframe') else 'ui'


def export(name, out=None, mocks=True):
    for sc in PACKS[name]:
        U.SCREEN_PAGES[sc] = PAGES[sc]
    spec = dict(screens=PACKS[name], build=build, tags=TAGS, group=group_of, radar=False, groups=('tv', 'ui'),
                layout='layout_%s.json' % name)
    res = U.pack(out or (U.ROOT / 'build' / ('%s.shr' % name)), spec)
    print('%s.shr: %d B (%.1f KB), экраны %s' % (name, res['size'], res['size'] / 1024, ', '.join(PACKS[name])))
    if mocks:
        from PIL import Image
        U.OUTDIR.mkdir(parents=True, exist_ok=True)
        demo = {'slots': 0, 'prompt': 0, 'notice': 3, 'message': 2}
        for sc in PACKS[name]:
            kind = sc[1:]
            if kind == 'strings':
                continue
            st = {'show': TAGS[sc] | ({MSG_TAG_ERROR} if kind == 'notice' else set()), 'ROW%d' % ROW_MSG: demo[kind]}
            bg = (40, 44, 90, 255) if name == 'fsave' else (0, 0, 0, 255)
            img = U.render(res['screens'][sc], U.DST_W, U.DST_H, st, res['qbitmaps'], Image.new('RGBA', (U.DST_W, U.DST_H), bg), None, 0)
            p = U.OUTDIR / ('save_%s.png' % sc); img.save(p)
            print('  макет', p.relative_to(U.ROOT))
    return res


if __name__ == '__main__':
    argv = sys.argv[1:]
    out = pk = None
    if '--out' in argv:
        i = argv.index('--out'); out = argv[i + 1]; del argv[i:i + 2]
    if '--pack' in argv:
        i = argv.index('--pack'); pk = argv[i + 1]; del argv[i:i + 2]
    if '--strings' in argv:                                            # для сверки с savemenu.c (tests/savegame/host.sh)
        print('\n'.join(k if isinstance(k, str) else '#%d' % k[1] for k in STRINGS)); sys.exit(0)
    U.project(FE)                                                      # библия (U._BIBLE) загружается с первым проектом
    for n in ([pk] if pk else list(PACKS)):
        export(n, out if pk else None, mocks=not out)
