#!/usr/bin/env python3
"""№896: сценарий-бот меню (Mission Select и соседние экраны) — случайная последовательность действий по seed, как «прыжки между уровнями и миссиями в любом порядке».
  python3 tests/menu896/gen.py SEED [N_ACTIONS] [--fail N] > scenario.txt
Действия: S — миссия того же уровня (↑/↓ по строкам, ✕); L — другой уровень (◄ ► по кругу 1..3 раза, ✕); C — открыл MISSION SELECT и вышел △ / START;
O — OPTIONS паузы (PICTURE ✕, △, △, START). После каждого перехода — пауза под загрузку и снимок. Пузыри сообщений (tests/menu896/bubbles.txt) — на старте,
после каждой смены уровня и в конце. --fail N — «flag msopenfail N» перед первым Mission Select (красный контроль: пакет не открывается, запасной список).
Проверка по строкам лога и снимкам: tests/menu896/check.py"""
import os, random, sys
args = [a for a in sys.argv[1:] if not a.startswith('--')]
fail = int(sys.argv[sys.argv.index('--fail') + 1]) if '--fail' in sys.argv else 0
if fail: args.remove(str(fail))
seed = int(args[0]); n = int(args[1]) if len(args) > 1 else 8
rnd = random.Random(seed)
BUB = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bubbles.txt')).read().splitlines()
def bubbles(tag): return [l.replace('BB_', tag + '_') for l in BUB]
out = ['# №896 бот меню, seed %d' % seed, 'flag menu', 'flag lvset %d' % rnd.choice([2, 3, 4, 5, 6, 7]), 'wait 1.5', 'press cross', 'wait 70', 'flag uimsndone 15', 'wait 1']
out += bubbles('s0')
if fail: out.append('flag msopenfail %d' % fail)
OPEN = ['press start', 'wait 1', 'press down', 'wait 0.4', 'press cross', 'wait 1']   # пауза -> MISSION SELECT (строка 2 паузы)
acts = []
for i in range(n):
    a = rnd.choices('SLCO', [5, 3, 2, 2])[0]
    acts.append(a)
    out.append('# действие %d: %s' % (i, a))
    if a == 'S':
        out += OPEN
        for _ in range(rnd.randint(0, 3)): out += ['press %s' % rnd.choice(['up', 'down']), 'wait 0.3']
        out += ['shot a%d_ms' % i, 'press cross', 'wait 12']
    elif a == 'L':
        out += OPEN
        for _ in range(rnd.randint(1, 3)): out += ['press %s' % rnd.choice(['left', 'right']), 'wait 0.5']
        out += ['shot a%d_ms' % i, 'press cross', 'wait 45', 'flag uimsndone 15', 'wait 1'] + bubbles('a%d' % i)
    elif a == 'C':
        out += OPEN + ['shot a%d_ms' % i, 'press %s' % rnd.choice(['triangle', 'start']), 'wait 0.8', 'press start', 'wait 1']
    else:
        out += ['press start', 'wait 1'] + ['press down', 'wait 0.3'] * 4 + ['press cross', 'wait 1.2', 'press cross', 'wait 1', 'shot a%d_opt' % i,
                'press triangle', 'wait 0.8', 'press triangle', 'wait 0.8', 'press start', 'wait 1']
out += ['wait 1'] + bubbles('s1') + ['end']
sys.stdout.write('\n'.join(out) + '\n')
sys.stderr.write('ACTIONS %s\n' % ''.join(acts))
