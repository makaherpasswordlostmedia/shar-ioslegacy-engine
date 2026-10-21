#!/usr/bin/env python3
"""Сверка прогона tests/ui/options_extra_scenario.txt: VIEW CREDITS (ViewCredits.scr) и VIEW MOVIES (ViewMovies.scr) в OPTIONS.
  options_extra_check.py RUN_DIR   -> первая строка итог, код 0 = OK
  · в OPTIONS включены строки VIEW CREDITS и VIEW MOVIES (пакет menu.shr с экранами 2, 3)
  · титры: 32 блока CREDITS_00..31 библии (все строки), музыка «credits» (событие Credits композиции), первая строка в начале —
    у нижнего края по данным Scrooby (ViewCredits.pag: y 0, высота 15 -> PSP y (480-15)·272/480), по центру экрана; за 4 с
    между снимками титры уехали вверх на CREDITS_SPEED·4 (±25 %); △ — назад
  · ролики: открыты видимые (moviesseen 3 -> GAME INTRODUCTION, LEVEL 1 INTRODUCTION, если файлы есть), прочие серые; X на
    GAME INTRODUCTION — ролик intro показан (кадры > 0), START — пропуск, назад в список
  · снимки есть"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))

run = Path(sys.argv[1]); log = (run / 'smoke.txt').read_text(errors='replace').splitlines() if (run / 'smoke.txt').exists() else []
kv = lambda l: dict(p.split('=', 1) for p in l.split()[1:] if '=' in p)
bad, info = [], []
S = 272 / 480; SPEED = 35 * S   # viewer/main.c CREDITS_SPEED

rows = [kv(l) for l in log if l.startswith('OPTROWS ')]
if not rows or int(rows[0].get('credits', -1)) < 0 or int(rows[0].get('movies', -1)) < 0:
    bad.append(f'в OPTIONS нет строк VIEW CREDITS / VIEW MOVIES: {rows[:1]}')
cr = [(l.split()[1], kv(l)) for l in log if l.startswith('CREDITS ')]
on = [d for e, d in cr if e == 'on']
if not on or on[0].get('music') != 'credits': bad.append(f'титры без музыки Credits: {on[:1]}')
st = [d for e, d in cr if e == 'start']
import ui_export as U
B = U.load_bible('E'); want_lines = sum((B('CREDITS_%02d' % i) or '').count('\\') + 1 for i in range(32))
if not st: bad.append('титры не открылись')
else:
    d = st[0]; top = int(d['top']); x0, x1 = map(int, d['x'].split(','))
    if d.get('blocks') != '32' or int(d.get('lines', 0)) != want_lines:
        bad.append(f"титров {d.get('blocks')} блоков / {d.get('lines')} строк != 32 / {want_lines} (CREDITS_00..31 библии)")
    y0 = min((480 - 15) * S, 272 - U.SAFE_Y - 15 * S)   # R3 + R4 (низ не ближе SAFE_Y к краю экрана)
    if abs(top - y0) > 1.5: bad.append(f'первая строка на y {top} != низ экрана по Scrooby {y0:.1f}')
    if abs((x0 + x1) / 2 - 240) > 3: bad.append(f'титры не по центру: {x0}..{x1}')
    info.append(f"титры: 32 блока, {d.get('lines')} строк, старт y {top}, x {x0}..{x1}")
a = next((d for e, d in cr if e == 'cred_a'), None); b = next((d for e, d in cr if e == 'cred_b'), None)
if not a or not b: bad.append('нет строк CREDITS на снимках cred_a / cred_b')
else:
    ds = float(b['scroll']) - float(a['scroll']); dt = float(b['t']) - float(a['t'])
    if not (0.75 * SPEED * 4 <= ds <= 1.25 * SPEED * 4): bad.append(f'за 4 с титры сдвинулись на {ds:.1f} px, ждали {SPEED * 4:.1f}')
    if not int(b['top']) <= int(a['top']) and int(b['first']) <= int(a['first']): bad.append('титры не едут вверх')
    info.append(f"сдвиг за 4 с: {ds:.1f} px (скорость {SPEED:.1f} px/с), первый блок на экране {a['first']} -> {b['first']}")
if not any(e == 'back' for e, d in cr): bad.append('△ не вернул из титров')

mo = [kv(l) for l in log if l.startswith('MOVIES open')]
if not mo: bad.append('VIEW MOVIES не открылся')
else:
    av = int(mo[0]['avail'], 16)
    if not av & 1 or av & ~3: bad.append(f'открытые ролики 0x{av:x}: ждали GAME INTRODUCTION (+ LEVEL 1 INTRODUCTION), прочие серые')
    info.append(f'VIEW MOVIES: открыты 0x{av:x}')
pl = [kv(l) for l in log if l.startswith('MOVIES play')]
fm = [kv(l) for l in log if l.startswith('MSNFMV ') and kv(l).get('name') == 'intro']
if not pl or pl[0].get('name') != 'intro': bad.append(f'X не запустил GAME INTRODUCTION: {pl[:1]}')
if not fm or int(fm[0].get('frames', 0)) <= 0 or fm[0].get('skipped') != '1': bad.append(f'ролик intro не показан или START не пропустил: {fm[:1]}')
if not any(l.startswith('OPT pack=menu scr=-1') for l in log): bad.append('△ △ не вернул в главное меню')
for s in ('cred_a', 'cred_b', 'movies_list', 'movie_play', 'movies_back'):
    if not (run / f'{s}.png').exists(): bad.append(f'нет снимка {s}')
print('options extra: ' + ('PASS' if not bad else 'FAIL — ' + '; '.join(bad)))
for x in info: print('  ' + x)
sys.exit(1 if bad else 0)
