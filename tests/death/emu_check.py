#!/usr/bin/env python3
"""Правка Роба 349 (05.10, L1 K2-8 — двор горящих покрышек за забором): разбор прогона EBOOT по tests/death/emu_scenario.txt.
Прогон — безголовый эмулятор: python3 ~/.claude/skills/shar-level-polish/scripts/scen.py ИМЯ tests/death/emu_scenario.txt
(SCEN_EBOOT — свой EBOOT; уровень с новым блоком JMP1 — tools/jumps_export.py правки 349).
Зелёный (как оригинал, [PS2] 05.10 pcsx2-twins: оба ящика R6D01 и Гомер пешком переносятся, курс машины — курс локатора,
затемнение 0,92 с + чёрный 0,26 с):
  car_box1 (ящик x 262…287 — K2-8), car_box0 (ящик x 284…312), car_ramp (въезд с газом через трамплин jumpzone9),
  foot_box1 (Гомер пешком) — ровно один DEATH R6D01 за сцену, с затемнением (fade=1); после — у точки возврата (285,4; −551,4)
  в 3 м, машина курсом π ± 0,2 (локатор R6D01 смотрит по +z диска); FADE out до a=1 за 0,80–1,10 с, чёрный (hold → done) 0,18–0,40 с;
  control (у дороги вне зоны) — ни одного DEATH.
Красный: тот же сценарий с «flag deathold» в начале (или прежний EBOOT/уровень) — обязан упасть (ящик 1 и Гомер пешком не переносят).
  python3 tests/death/emu_check.py smoke.txt   -> PASS / FAIL"""
import math, re, sys
from pathlib import Path

RET = (285.43, -551.42); RET_H = math.pi


def parse(p):
    sc, cur = {}, None
    for ln in Path(p).read_text(errors='replace').splitlines():
        w = ln.split()
        if not w: continue
        if w[0] == 'SCENE': cur = w[1]; sc[cur] = dict(death=[], fade=[], shot={}, homer=[])
        elif cur is None: continue
        elif w[0] == 'DEATH':
            d = dict(name=w[1], fade=None, foot=None, h=None)
            for k in ('fade', 'foot', 'h', 'rec'):
                m = re.search(rf'\b{k}=(-?[\d.]+)', ln)
                if m: d[k] = float(m.group(1))
            m = re.search(r'-> (-?[\d.]+),(-?[\d.]+),(-?[\d.]+)', ln); d['to'] = tuple(map(float, m.groups())) if m else None
            sc[cur]['death'].append(d)
        elif w[0] == 'FADE':
            kv = dict(x.split('=', 1) for x in w[1:] if '=' in x); sc[cur]['fade'].append(kv)
        elif w[0] == 'SHOT' and len(w) >= 8: sc[cur]['shot'][w[1]] = tuple(map(float, w[4:8]))
        elif w[0] == 'HOMER':
            m = re.search(r'pos=(-?[\d.]+),(-?[\d.]+),(-?[\d.]+)', ln)
            if m: sc[cur]['homer'].append(tuple(map(float, m.groups())))
    return sc


def ang(a): return (a + math.pi) % (2 * math.pi) - math.pi


def main(p):
    sc = parse(p); bad = []
    def need(c, msg):
        print(('ok   ' if c else 'FAIL ') + msg)
        if not c: bad.append(msg)
    for name, foot in (('car_box1', 0), ('car_box0', 0), ('car_ramp', 0), ('foot_box1', 1)):
        s = sc.get(name)
        if not s: need(False, f'{name}: сцены нет в журнале'); continue
        D = [d for d in s['death'] if d['name'] == 'R6D01']
        need(len(s['death']) == 1 and len(D) == 1, f'{name}: DEATH R6D01 ровно один (было {len(s["death"])}: {[d["name"] for d in s["death"]]})')
        if not D: continue
        d = D[0]
        need(d['fade'] == 1, f'{name}: перенос с затемнением (fade={d["fade"]})')
        need(d['foot'] == foot, f'{name}: {"пешком" if foot else "машиной"} (foot={d["foot"]})')
        if not foot:
            sh = next(iter(s['shot'].values()), None) if s['shot'] else None
            sh = s['shot'].get(name + '_after', sh)
            if sh:
                dd = math.hypot(sh[0] - RET[0], sh[2] - RET[1])
                if name != 'car_ramp':   # въезд с газом: газ держится и после переноса — машина отъезжает от точки по курсу локатора
                    need(dd < 3.0, f'{name}: после — у точки возврата R6D01 ({dd:.2f} м)')
                need(abs(ang(sh[3] - RET_H)) < 0.25, f'{name}: курс машины {sh[3]:.3f} ~ курс локатора π')
            else: need(False, f'{name}: нет снимка после')
        else:
            h = s['homer'][-1] if s['homer'] else None
            need(h is not None and math.hypot(h[0] - RET[0], h[2] - RET[1]) < 3.0, f'{name}: Гомер у точки возврата ({h})')
        out = [f for f in s['fade'] if f.get('phase') == 'out' and f.get('why') == 'death']
        hold = [f for f in s['fade'] if f.get('phase') in ('hold', 'done') and f.get('why') == 'death']
        if out:
            a_end, t_end = float(out[-1]['a']), float(out[-1]['tt'])
            mono = all(float(out[i + 1]['a']) >= float(out[i]['a']) for i in range(len(out) - 1))
            need(a_end >= 0.999 and 0.80 <= t_end <= 1.10 and mono and len(out) >= 10,
                 f'{name}: затемнение до чёрного за {t_end:.2f} с, {len(out)} кадров, яркость только падает')
        else: need(False, f'{name}: строк FADE out нет')
        done = [f for f in hold if f.get('phase') == 'done']
        need(bool(done) and 0.18 <= float(done[-1]['tt']) <= 0.40, f'{name}: чёрный после переноса {float(done[-1]["tt"]) if done else -1:.2f} с, потом картинка')
    s = sc.get('control')
    need(s is not None and not s['death'], f'control: вне зоны DEATH нет ({len(s["death"]) if s else "нет сцены"})')
    print('PASS' if not bad else f'FAIL ({len(bad)})')
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
