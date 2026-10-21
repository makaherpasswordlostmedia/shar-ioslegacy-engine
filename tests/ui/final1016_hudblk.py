#!/usr/bin/env python3
"""Гейт hudBlk (блок времени и места, viewer/ui.c hudBlkUpdate): после паузы в вызовах (смена уровня, меню, пауза) первый кадр сразу в нужном месте, без
доезда ~0,2 с из старого положения; плавный ход при непрерывной работе сохранён. Функция берётся из ui.c как есть (между «#ifndef HUD_BLK_RESET_OLD» и концом
hudBlkUpdate), собирается на Маке. КРАСНЫЙ: -DHUD_BLK_RESET_OLD=1 (прежнее). python3 tests/ui/final1016_hudblk.py [--old] -> 0 = PASS"""
import re, subprocess, sys, tempfile, os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
src = (ROOT / 'viewer/ui.c').read_text()
a = src.index('static float hudBlkV, hudBlkClk')
b = src.index('static float hudBlkUpdate'); e = src.index('\n}\n', b) + 3
chunk = src[a:e]
prog = '#include <stdio.h>\n#define HUD_CORNER_X 20\nstatic float uiClk;\n' + chunk + r'''
int main(void) {
  for (int i = 0; i < 60; i++) { uiClk += 1.f / 60; hudBlkUpdate(1, 1.f, 0); }          // кружок поднят: блок правее (1.0)
  uiClk += 2.0f;                                                                       // пауза в вызовах: смена уровня
  float first = hudBlkUpdate(0, 0.f, 0);                                               // на новом уровне кружка нет: блок сразу в углу (0.0)
  hudBlkInit = 0; hudBlkClk = -1.f; for (int i = 0; i < 60; i++) { uiClk += 1.f / 60; hudBlkUpdate(1, 1.f, 0); }
  float v[7]; for (int i = 0; i < 7; i++) { uiClk += 1.f / 60; v[i] = hudBlkUpdate(0, 0.f, 0); }   // непрерывно: плавно за ~0,35 с
  printf("first=%.3f smooth6=%.3f smooth7=%.3f\n", first, v[5], v[6]);
  int bad = 0;
  if (first > 0.01f) { printf("FAIL после паузы блок доезжает из старого положения (first=%.3f)\n", first); bad = 1; }
  if (!(v[5] > .05f && v[5] < .95f)) { printf("FAIL непрерывный ход не плавный (%.3f на 6-м кадре)\n", v[5]); bad = 1; }
  if (!bad) printf("OK\n");
  return bad;
}
'''
with tempfile.TemporaryDirectory() as d:
    c = Path(d) / 't.c'; c.write_text(prog)
    defs = ['-DHUD_BLK_RESET_OLD=1'] if '--old' in sys.argv else []
    subprocess.run(['cc', '-std=c11', '-O1', '-Wno-unused-function'] + defs + [str(c), '-o', str(Path(d) / 't')], check=True)
    r = subprocess.run([str(Path(d) / 't')], capture_output=True, text=True)
print(r.stdout.strip()); sys.exit(r.returncode)
