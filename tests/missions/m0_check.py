#!/usr/bin/env python3
"""Сверка хода m0 по smoke.txt EBOOT (строки MSN ... из viewer/msn_view.c): tests/missions/emu_m0.sh.
   m0_check.py SMOKE_TXT RC_СМОУКА -> код 0 = этапы m0 шли по порядку и засчитаны настоящими условиями, смоук OK."""
import re, sys

log = open(sys.argv[1], encoding='utf-8', errors='replace').read().splitlines()
rc = int(sys.argv[2]) if len(sys.argv) > 2 else 0
ms = [l for l in log if l.startswith('MSN')]
stages = [m.groups() for m in (re.match(r'MSN stage (\S+) obj=(\S+)', l) for l in ms) if m]
done = [l.split()[2] for l in ms if l.startswith('MSN done ')]
# родной порядок m0 (scripts/missions/level01/m0sdi.mfk + m0i.mfk): вступление m0sd, основная часть m0
want = [('m0.0.0', 'talkto'), ('m0.0.1', 'dialogue'), ('m0.1.0', 'getin'), ('m0.1.1', 'goto'), ('m0.1.2', 'interior'),
        ('m0.1.3', 'talkto'), ('m0.1.4', 'dialogue'), ('m0.1.5', 'goto')]
print('этапы:', ' -> '.join(f'{s}:{o}' for s, o in stages) or '-')
print('засчитаны:', ' '.join(done) or '-')
for l in ms:
    if l.startswith(('MSNSTART', 'MSNMEM', 'MSNNPC', 'MSN npc marge', 'MSN npc apu', 'MSN dialogue', 'MSNGO', 'MSN complete', 'MSN flash', 'MSN briefing')):
        print('  ', l)
n = 0
while n < len(stages) and n < len(want) and stages[n] == want[n]: n += 1
room = any(l.startswith('MSNGO room') for l in ms)
complete = any(l.startswith('MSN complete m0') for l in ms)
brief = any(l.startswith('MSN briefing m0') and 'bitmap=mis01_00' in l for l in ms) and any(l.startswith('MSN briefing-continue') for l in ms)
if not brief: print('нет брифинга m0 (MissionLoad с картинкой mis01_00 и продолжением по X)')
base = n >= 5 and brief and all(d in done for d in ('0.0', '0.1', '1.0', '1.1')) and any('MSNNPC load marge' in l for l in ms)
# голос и музыка (пакет озвучки миссий, viewer/msn_audio.c): реплики Мардж и Гомера звучат по порядку, конец разговора —
# конец последней реплики; после вступления m1 — музыка миссии M1_start (композиция l1_music.rms -> collection02_pickup)
va =[l for l in log if l.startswith(('VOICE', 'MUSIC'))]
for l in va: print('  ', l)
vs = lambda c, k, n: any(l.startswith(f'VOICE {k} {c} {n}') for l in va)
voice = vs('icecream', 'start', '1/2 mrg') and vs('icecream', 'end', '1/2') and vs('icecream', 'start', '2/2 hom') and vs('icecream', 'end', '2/2') \
        and not any(l.startswith('VOICE none') for l in va)
music = any(re.match(r'MUSIC event M1_start -> collection02', l) for l in va)
print('голос разговора с Мардж (icecream 1/2 mrg, 2/2 hom):', 'есть' if voice else 'НЕТ')
print('музыка миссии M1_start после вступления m1:', 'есть' if music else 'НЕТ')
base = base and voice and music
if complete: print('m0 пройдена целиком')
elif base and room: print('m0 до двери Kwik-E-Mart: пройдено; дальше «не покрыто» — комнаты не подключены (крючок mvSetInterior)')
elif base: print('m0 до двери пройдено, но сценарий не дошёл до конца')
else: print(f'ход m0 сломан: совпало {n} этапов из {len(want)}')
print(f'смоук (FPS/кадры/память): {"OK" if rc == 0 else "ПРОВАЛ"}')
sys.exit(0 if base and rc == 0 else 1)
