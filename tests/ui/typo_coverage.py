#!/usr/bin/env python3
"""Гейт (Роб 17.10 вечер: «везде ли обновлены шрифты… прошурши, проверь везде»): каждая надпись каждого экрана пакетов ui_export / menu_export входит
в группу панели типографики Роба (иначе идёт гранью диска — «старый шрифт»). Исключения — надписи, которых игра не показывает (SKIP_OK, с причиной).
Красный: VC_TITLE_OLD=1 или UI_TYPO_HINTS_MENU_OLD=1 -> FAIL."""
import os, sys
from fnmatch import fnmatch
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'tools')); sys.path.insert(0, os.path.join(ROOT, 'hit-and-run-web/tools')); os.chdir(ROOT)
import ui_export as U, ui_typo as T, menu_export as M
SKIP_OK = {   # не рисуются в порте
    ('hud', 'Hud.pag', 'Speed'): 'спидометр выключен в порте', ('hud', 'Hud.pag', 'SpeedUnit0'): 'спидометр выключен в порте',
    ('pause', 'PauseFgd.pag', 'PressStartResumePlay'): 'подсказка PS2 «нажми START» снята', ('pausemsn', 'PauseFgd.pag', 'PressStartResumePlay'): 'то же',
    **{('missionload', 'MissionLoad.pag', n): 'поля гонки на ставку (метка GAMBLE карточки движок не включает — в порте не выводятся; пропуск возможности, Робу 17.10)' for n in
       ('Payout', 'Payout_Value', 'VehicleOdds', 'VehicleOdds_Value', 'BestTime', 'BestTime_Value', 'TimeToBeat', 'TimeToBeat_Value', 'EntryFee', 'EntryFee_Value')},
}
def covered(sc, page, name):
    for g in T.GROUPS:
        if sc not in g.get('screens', ()): continue
        sels = list(g.get('sel', [])) + [s for pt in (g.get('parts') or []) for s in pt.get('sel', [])]
        if any(fnmatch(page, p) and fnmatch(name, n) for p, n in sels): return True
    return False
miss = []
for sc in list(U.SCREEN_PAGES.keys()):
    try: its, _ = U.build_items(sc)
    except Exception: continue
    for it in its:
        if it['type'] == U.T_TEXT and not covered(sc, it['page'], it['name']) and (sc, it['page'], it['name']) not in SKIP_OK:
            miss.append('%s: %s/%s' % (sc, it['page'], it['name']))
# экраны menu_export: подписи кнопок (их строки строит menu_export, не build_items)
cov = {s for g in T.GROUPS if any(p in T.HINT_PAGES for p, _ in g.get('sel', [])) for s in g.get('screens', ())}
miss += ['%s: подписи кнопок' % sc for sc, v in M.PAGES.items() if any(pg in T.HINT_PAGES for _, pg in v) and sc not in cov]
print('надписей вне панели: %d%s' % (len(miss), (' — ' + '; '.join(miss[:12])) if miss else ''))
print('PASS typo_coverage' if not miss else 'FAIL typo_coverage'); sys.exit(1 if miss else 0)
