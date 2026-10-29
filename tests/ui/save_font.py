#!/usr/bin/env python3
"""Гейт правки Роба 309 (04.10, голосом: «доработал бы там размер шрифта» — меню сохранения) — хост, Мак, CPU, без эмулятора.

  python3 tests/ui/save_font.py            -> первая строка итог, код 0 = PASS (зелёный + красный пойман)
  python3 tests/ui/save_font.py --one      -> только проверка текущих граней (для красного: SAVE_FONT_OLD=1 обязан упасть)

Читает экраны меню сохранения так, как их собирает tools/save_export.py (build -> грани текста, перерисованные для PSP):
  · строки слотов, ответы YES/NO/Continue, «Save to: / Memory Stick», сообщения — заглавная H на SAVE_CAP_STEP px крупнее прежней
    (7 -> 9 px: «немного крупнее» — шаг числом, не «до краёв»);
  · строка не выше шага слотов (17 px PSP): соседние строки не наезжают;
  · самая длинная строка слота («LEVEL 7   31/12  23:59», «< Damaged Save >») — внутри рамки BigBoard;
  · строки Tt2001m (Save to / Memory Stick / сообщения) — грань 1:1 (пиксельная, без дробного пересэмпла);
  · подписи кнопок (Accept / Back) — общая грань HINT_FACE, как в паузе (правка 233; общий размер — правка 311).
Красный: SAVE_FONT_OLD=1 (прежние грани) — заглавная 7 px, проверка обязана упасть."""
import os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SAVE_CAP_OLD, SAVE_CAP_STEP = 7, 2


def check():
    sys.path.insert(0, str(ROOT / 'tools'))
    import save_export as SE, ui_export as U
    U.project(SE.FE)
    for n in SE.PACKS:
        for sc in SE.PACKS[n]: U.SCREEN_PAGES[sc] = SE.PAGES[sc]
    fc = U.FontCache('psp'); fails, notes = [], []
    for sc in ('pslots', 'pprompt', 'pnotice', 'pmessage', 'fslots', 'fprompt', 'fnotice', 'fmessage'):
        its = [it for it in SE.items(sc) if it['type'] == U.T_TEXT]
        pitch = None
        slots = sorted((it for it in its if it['name'].startswith('Slot')), key=lambda t: t['rect'][1])
        if len(slots) > 1: pitch = (slots[1]['rect'][1] - slots[0]['rect'][1]) * U.S
        board = None
        if sc[1:] == 'slots':
            fr = [it for it in SE.items(sc) if it['page'] == 'BigBoard.pag' and it['name'] in ('Frame_Left', 'Frame_Right')]
            if len(fr) == 2:
                xs = sorted(it['rect'][0] for it in fr); board = (xs[0] * U.S, (xs[1] + fr[0]['rect'][2]) * U.S)
        for it in its:
            f = SE.save_face(it); g = fc.get(f); cap = U.cap_px(f); nm = '%s/%s' % (sc, it['name'])
            if it['page'] in U.HINT_PAGES:
                if f != it['font']: fails.append('%s: подпись кнопки не общей гранью (%s)' % (nm, f))
                continue
            if cap < SAVE_CAP_OLD + SAVE_CAP_STEP: fails.append('%s: заглавная %d px (нужно %d)' % (nm, cap, SAVE_CAP_OLD + SAVE_CAP_STEP))
            if cap > SAVE_CAP_OLD + SAVE_CAP_STEP + 1: fails.append('%s: заглавная %d px — крупнее шага (+%d)' % (nm, cap, SAVE_CAP_STEP))
            if it['name'].startswith('Slot') and pitch and g['lh'] > pitch + .5:
                fails.append('%s: строка %d px выше шага слотов %.1f' % (nm, g['lh'], pitch))
            if it['name'].startswith('Slot') and board:
                w = max(U.face_width(f, [s]) for s in ('LEVEL 7   31/12  23:59', '< Damaged Save >', '< EMPTY SLOT >'))
                cx = (it['rect'][0] + it['rect'][2] / 2) * U.S
                if cx - w / 2 < board[0] or cx + w / 2 > board[1]:
                    fails.append('%s: строка %d px шире рамки (%.0f..%.0f)' % (nm, w, *board))
            if f.startswith('Tt2001m') and abs(g['scale'] - round(g['scale'])) > 1e-6:
                fails.append('%s: грань %s дробная (масштаб %.3f), нужна 1:1' % (nm, f, g['scale']))
            if sc == 'pslots' and it['name'] in ('Slot0', 'LoadSave'): notes.append('%s %s заглавная %d px' % (it['name'], f, cap))
    return fails, notes


if __name__ == '__main__':
    if '--one' in sys.argv:
        f, n = check(); print(('FAIL — ' + '; '.join(f[:6])) if f else ('OK — ' + '; '.join(n))); sys.exit(1 if f else 0)
    f, n = check()
    r = subprocess.run([sys.executable, __file__, '--one'], env=dict(os.environ, SAVE_FONT_OLD='1'), capture_output=True, text=True)
    red = r.returncode != 0
    print(('PASS' if not f and red else 'FAIL') + ': зелёный %s; красный SAVE_FONT_OLD=1 %s' %
          ('OK — ' + '; '.join(n) if not f else 'FAIL — ' + '; '.join(f[:6]),
           'пойман — ' + r.stdout.strip()[:160] if red else 'НЕ ПОЙМАН — ' + r.stdout.strip()[:160]))
    sys.exit(0 if not f and red else 1)
