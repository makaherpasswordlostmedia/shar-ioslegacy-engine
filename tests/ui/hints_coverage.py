#!/usr/bin/env python3
"""Гейт (Роб 17.10: «везде ли обновлены шрифты… accept и cancel старый шрифт»): на каждом экране всех пакетов, где есть подписи кнопок
(Accept/Back/Continue), они входят в группу панели типографики Роба — иначе идут шрифтом диска. Красный: UI_TYPO_HINTS_MENU_OLD=1 -> FAIL."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'tools')); sys.path.insert(0, os.path.join(ROOT, 'hit-and-run-web/tools')); os.chdir(ROOT)
import ui_export as U, ui_typo as T, menu_export as M
cov = set()
for g in T.GROUPS:
    if any(p in T.HINT_PAGES for p, _ in g.get('sel', [])): cov |= set(g.get('screens', ()))
pages = {sc: [pg for _, pg in v] for sc, v in U.SCREEN_PAGES.items()}
pages.update({sc: [pg for _, pg in v] for sc, v in M.PAGES.items()})
miss = sorted(sc for sc, pg in pages.items() if any(p in T.HINT_PAGES for p in pg) and sc not in cov)
print('экранов с подписями: %d, без группы панели: %s' % (sum(1 for pg in pages.values() if any(p in T.HINT_PAGES for p in pg)), miss or 'нет'))
print('PASS hints_coverage' if not miss else 'FAIL hints_coverage'); sys.exit(1 if miss else 0)
