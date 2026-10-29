#!/usr/bin/env python3
"""Правка Роба 293: читает smoke.txt прогона с настоящим перелётом меню (строки FEFR … sw=строка,опоздала,ждали,guard; FEFLY … late= waited=
old=; FECAP …) и проверяет правило «смена буфера опоздала → ждать следующий обратный ход» (viewer/main.c swapBuf).
  python3 tests/fe_guard/swap_read.py smoke.txt [--expect-late] [--glow] [--quiet]
Зелёный (код 0): у перелёта NEW GAME (item=4 mode=0) есть счётчики смены, и каждая опоздавшая смена дождалась обратного хода
(waited == late; у строк FEFR со сменой по правилу, guard 1, — «,1,1,1»); с --expect-late ещё и опоздания были (имитация swaplate дошла до перелёта).
Красный (код 1): счётчиков нет (прежний движок), или опоздавшие смены не ждали (flag swapold 1 — прежнее поведение).
--glow (вместо проверки смены): подсветка пункта после ухода камеры из главного вида гаснет 0,1–0,3 с (у оригинала 0,16 с):
по строкам FEFR перелёта — время (сумма dt) кадров с home=0 и прежним числом подсветок (bills как у кадра меню); прежнее
(flag feglowcut 1) — 0 с, красный."""
import re, sys

def kv(line):
    return dict(re.findall(r'(\w+)=([^\s]+)', line))

def glow(L):
    fr = [kv(l) for l in L if l.startswith('FEFR ')]
    i0 = max((i for i, f in enumerate(fr) if f.get('home') == '1' and float(f.get('tl', 0)) < 300), default=-1)   # последний кадр меню перелёта
    if i0 < 0: print('КРАСНЫЙ: нет строк FEFR перелёта'); return 1
    nb = fr[i0].get('bills'); dur = 0.; n = 0
    for f in fr[i0 + 1:]:
        if f.get('home') != '0' or f.get('bills') != nb: break
        dur += float(f.get('dt', 0)) / 1000.; n += 1
    nxt = fr[i0 + 1 + n].get('bills') if i0 + 1 + n < len(fr) else '?'
    print(f'подсветка пункта после ухода из главного вида: {n} кадров, {dur:.3f} с (подсветок в меню {nb}, потом {nxt}); у оригинала 0,16 с')
    ok = 0.1 <= dur <= 0.3
    print('ЗЕЛЁНЫЙ' if ok else f'КРАСНЫЙ: подсветка пропала за {dur:.3f} с (ждём 0,1–0,3 с)')
    return 0 if ok else 1


def main():
    path = sys.argv[1]; expect = '--expect-late' in sys.argv
    L = open(path, errors='replace').read().splitlines()
    if '--glow' in sys.argv: return glow(L)
    fly = [kv(l) for l in L if l.startswith('FEFLY ') and 'item=4' in l and 'mode=0' in l]
    fr = [l for l in L if l.startswith('FEFR ')]
    cap = [l for l in L if l.startswith('FECAP ')]
    sw = [kv(l).get('sw', '') for l in fr]
    g1 = [s.split(',') for s in sw if s.count(',') == 3 and s.split(',')[3] == '1']   # смена прошлого кадра по правилу (меню)
    lateFr = sum(1 for x in g1 if x[1] == '1'); waitFr = sum(1 for x in g1 if x[1:3] == ['1', '1'])
    lines = [f'перелёт NEW GAME: {len(fly)} строк FEFLY; кадров FEFR {len(fr)} (с полем sw {sum(1 for s in sw if s)}, смена по правилу {len(g1)}: опоздали {lateFr}, из них ждали {waitFr})']
    ok, why = True, ''
    if not fly: ok, why = False, 'нет строки FEFLY перелёта NEW GAME'
    else:
        f = fly[-1]
        lines.append(f"FEFLY: кадров {f.get('swaps', '?')}, опоздали {f.get('late', '?')}, ждали {f.get('waited', '?')}, прежнее={f.get('old', '?')}, "
                     f"{f.get('s', '?')} с")
        if 'late' not in f: ok, why = False, 'нет счётчиков смены буфера (прежний движок без правила 293)'
        elif int(f['waited']) != int(f['late']): ok, why = False, f"опоздавшие смены не ждали обратного хода: late={f['late']} waited={f['waited']}"
        elif expect and int(f['late']) == 0: ok, why = False, 'имитация опоздания (swaplate) до перелёта не дошла'
        elif lateFr != waitFr: ok, why = False, f'строки FEFR: опоздали {lateFr}, ждали {waitFr}'
    done = [kv(l) for l in cap if l.startswith('FECAP done')]
    if done: lines.append(f"кадры в ОЗУ: увидено {done[-1].get('seen')}, записано {done[-1].get('wrote')} (fb32={done[-1].get('fb32')}, {done[-1].get('ms')} мс записи)")
    elif cap: lines.append('кадры в ОЗУ: ' + cap[-1])
    if '--quiet' not in sys.argv: print('\n'.join(lines))
    print(('ЗЕЛЁНЫЙ' if ok else 'КРАСНЫЙ: ' + why))
    return 0 if ok else 1

if __name__ == '__main__':
    sys.exit(main())
