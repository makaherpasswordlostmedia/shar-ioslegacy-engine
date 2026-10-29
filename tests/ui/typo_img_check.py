#!/usr/bin/env python3
"""Закон Роба 15.10: после любой сборки панели все картинки, на которые ссылается страница, на месте (и при заданном порте отдаются 200).
  python3 tests/ui/typo_img_check.py [папка панели] [порт]   -> 0 = PASS; красный контроль: --plant (убрать одну картинку из копии списка)"""
import re, sys, urllib.request
from pathlib import Path
a = [x for x in sys.argv[1:] if not x.startswith('--')]
panel = Path(a[0]) if a else Path(__file__).resolve().parents[2] / 'build' / 'ТИПОГРАФИКА_ПАНЕЛЬ'
refs = sorted(set(re.findall(r'img/[A-Za-z0-9_.\-]+\.png', (panel / 'index.html').read_text())))
if '--plant' in sys.argv: (panel / refs[0]).exists() and refs.append('img/__нет_такой__.png')
bad = [r for r in refs if not (panel / r).exists()]
if len(a) > 1:
    for r in refs:
        try: c = urllib.request.urlopen('http://127.0.0.1:%s/%s' % (a[1], r)).status
        except Exception as e: c = str(e)
        if c != 200: bad.append((r, c))
print('ссылок', len(refs), 'нет', len(bad), bad[:3]); sys.exit(1 if bad else 0)
