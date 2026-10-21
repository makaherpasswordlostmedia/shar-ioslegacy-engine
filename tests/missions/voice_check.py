#!/usr/bin/env python3
"""Сверка голоса разговоров и музыки миссий по журналу (строки VOICE / MUSIC из viewer/msn_audio.c).
   voice_check.py ЖУРНАЛ [--emu]   -> код 0 = зелёный
Журнал — вывод бота (строки "A\\t...", tests/missions/voice_gate.sh) или smoke.txt эмулятора (--emu, tests/missions/emu_m0.sh).
Что обязано быть (данные диска: scripts/missions/level01/m0sdi.mfk SetDialogueInfo("homer","marge","icecream"),
m0i.mfk SetDialogueInfo("homer","apu","congrats"), композиция sound/music/l1_music.rms: M0_win -> поток M0_End_Pos):
  * разговор icecream: реплики 1/2 (Мардж, mrg) и 2/2 (Гомер, hom) — «start» и «end» каждой, по порядку, без «нет голоса»;
  * длина каждой реплики > 0.5 с (реплика реально звучала, а не пропущена);
  * бот (не --emu): разговор congrats с Апу 3/3 и событие музыки M0_win -> дорожка (миссия пройдена);
  * ни одной строки «VOICE none» (реплика без голоса)."""
import re, sys

path = sys.argv[1]; emu = '--emu' in sys.argv
lines = [l.split('\t', 1)[1] if l.startswith('A\t') else l for l in open(path, encoding='utf-8', errors='replace').read().splitlines()]
v = [l for l in lines if l.startswith(('VOICE', 'MUSIC'))]
for l in v: print('  ', l)
bad = []
none = [l for l in v if l.startswith('VOICE none')]
if none: bad.append(f'{len(none)} реплик без голоса')

def conv(name, n, who):
    starts = [re.match(r'VOICE start (\S+) (\d+)/(\d+) (\S+) track=(\S+) dur=([\d.]+)', l) for l in v if l.startswith(f'VOICE start {name} ')]
    ends = [l for l in v if l.startswith(f'VOICE end {name} ')]
    got = [(int(m.group(2)), m.group(4), float(m.group(6))) for m in starts if m]
    if [g[0] for g in got] != list(range(1, n + 1)): bad.append(f'{name}: реплики {[g[0] for g in got]}, ждали 1..{n}'); return
    if [g[1] for g in got] != who: bad.append(f'{name}: кто говорит {[g[1] for g in got]}, ждали {who}')
    if any(g[2] < .5 for g in got): bad.append(f'{name}: реплика короче 0.5 с')
    if len(ends) < n: bad.append(f'{name}: закончилось {len(ends)} реплик из {n}')

conv('icecream', 2, ['mrg', 'hom'])
if not emu:
    conv('congrats', 3, ['hom', 'apu', 'hom'])
    if not any(re.match(r'MUSIC event M0_win -> \S+', l) and 'нет' not in l for l in v): bad.append('нет музыки победы M0_win')
print('ИТОГ:', 'зелёный' if not bad else 'КРАСНЫЙ: ' + '; '.join(bad))
sys.exit(1 if bad else 0)
