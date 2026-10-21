#!/usr/bin/env python3
"""Сверка прогона tools/options_scenario.txt (строки OPT из smoke.txt, viewer/main.c optLog):
  · главное меню: экран options (pack=menu scr=0), SOUND открывает sound (scr=1); на sound музыка 1000→800, эффекты 1000→900
    (◄ = −100), значения строк ползунков совпадают с настройками (rows = vol)
  · пауза: pmenu scr=0 → SETTINGS (scr=2), радар 1→0, выключенные строки помечены x, курсор ни разу не стоял на x
  · есть снимки сценария
  · звуки (29.09): на экранах OPTIONS / SOUND главного меню — scroll на ↓ и на смене ползунка, accept на пункте, back на △
    (строки UISFX, голос выдан h>0); «flag uisfx0» (звуки молчат) — красный
Первая строка вывода — итог; код 0 = OK."""
import sys
from pathlib import Path


def kv(parts):
    return dict(p.split('=', 1) for p in parts if '=' in p)


def main():
    out = Path(sys.argv[1])
    log = (out / 'smoke.txt').read_text().splitlines() if (out / 'smoke.txt').exists() else []
    opt = [kv(l.split()[1:]) for l in log if l.startswith('OPT ')]
    fails = []
    if not any(l.startswith('END') for l in log): fails.append('нет END: упал / завис')
    menu = [d for d in opt if d['pack'] == 'menu']; pm = [d for d in opt if d['pack'] == 'pmenu']
    snd = [d for d in menu if d['scr'] == '1']
    if not any(d['scr'] == '0' for d in menu): fails.append('экран OPTIONS главного меню не открылся')
    if not snd: fails.append('SOUND главного меню не открылся')
    else:
        v = snd[-1]['vol'].split(',')
        if v[0] != '800' or v[1] != '900': fails.append(f'громкость после ◄◄ / ↓◄: музыка {v[0]} (ждём 800), эффекты {v[1]} (ждём 900)')
        for d in snd:
            rows = [r.rstrip('x') for r in d['rows'].split(',')]
            if sorted(rows[:4]) != sorted(d['vol'].split(',')): fails.append(f"ползунки {d['rows']} ≠ настройкам {d['vol']} (t {d['t']})"); break
    st = [d for d in pm if d['scr'] == '2']
    if not st: fails.append('SETTINGS паузы не открылся')
    elif st[-1]['radar'] != '0': fails.append(f"радар после ◄: {st[-1]['radar']} (ждём 0 = Off)")
    for d in opt:
        if d['scr'] in ('-1',) or 'rows' not in d: continue
        rows = d['rows'].split(','); s = int(d['sel'])
        if 0 <= s < len(rows) and rows[s].endswith('x'): fails.append(f"курсор на выключенной строке {s}: {d['pack']} scr {d['scr']} (t {d['t']})"); break
    go = next((i for i, l in enumerate(log) if l.startswith('MENUGO ')), len(log))   # только главное меню (до запуска игры)
    sfx = [kv(l.split()[1:]) for l in log[:go] if l.startswith('UISFX ')]
    got = {n: sum(1 for d in sfx if d['name'] == n and int(d['h']) > 0) for n in ('scroll', 'accept', 'back')}
    need = {'scroll': 4, 'accept': 2, 'back': 2}   # сценарий: в SOUND ◄◄ ↓ ◄ (4), × OPTIONS и × SOUND (2), △ △ (2)
    short = [f'{n} {got[n]} < {k}' for n, k in need.items() if got[n] < k]
    if short: fails.append('звуки меню OPTIONS: ' + ', '.join(short))
    scn = (out / 'scenario.txt').read_text().splitlines() if (out / 'scenario.txt').exists() else []
    miss = [l.split()[1] for l in scn if l.startswith('shot ') and not (out / (l.split()[1] + '.png')).exists()]
    if miss: fails.append('нет снимков: ' + ', '.join(miss))
    if fails:
        print('options: FAIL — ' + '; '.join(fails)); return 1
    print(f"options: PASS — меню OPTIONS/SOUND: музыка {snd[-1]['vol']}; пауза SETTINGS: радар {st[-1]['radar']}; строк OPT {len(opt)}; "
          f"звуки scroll {got['scroll']}, accept {got['accept']}, back {got['back']}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
