#!/usr/bin/env python3
"""Разбор прогона tests/transit/scenario.txt (tools/smoke.sh): выброс при взрыве и ирис оригинала.

    python tests/transit/check.py build/smoke/<время>

Зелёный, если:
  EJECT   после BOOM (Гомер был за рулём): через 2.5 с пешком, вне кузова остова (clear >= 0.3 м), был в полёте (apex >= 0.1 м; правка Роба 73 — падает рядом с остовом)
  IRIS    для каждой причины сценария (test, overtop, seat, room_in, room_out, msn): закрытие — радиус не растёт и доходит
          до 0, закрыто — 0, раскрытие — не убывает и доходит до полудиагонали 480×272 (276 px), потом done;
          закрытие реальных переходов 8..40 кадров (10 кадров данных при 30 кадр/с = 1/3 с, кадры 30/60 Гц)
  снимки  iris_closed — чёрного >= 90 % кадра; iris_mid — центр не чёрный, углы чёрные (радиус по строке IRIS рядом);
          boom_after — есть (смотреть глазами)
Причина провала — первой строкой, код 1."""
import sys
from pathlib import Path

HALF_DIAG = (240 ** 2 + 136 ** 2) ** .5
WHYS = ['test', 'overtop', 'seat', 'room_in', 'room_out', 'msn']


def kv(line):
    return dict(p.split('=', 1) for p in line.split()[1:] if '=' in p)


def main():
    out = Path(sys.argv[1]); log = (out / 'smoke.txt').read_text().splitlines()
    fails, notes = [], []
    # --- взрыв
    boom = [kv(l) for l in log if l.startswith('BOOM ')]
    ej = [kv(l) for l in log if l.startswith('EJECT ')]
    if not boom: fails.append('нет строки BOOM (взрыв не случился)')
    elif boom[0].get('driving') != '1': fails.append(f"BOOM: Гомер не был за рулём ({boom[0]})")
    if not ej: fails.append('нет строки EJECT (журнал через 2.5 с после взрыва)')
    else:
        e = ej[0]; c, a = float(e['clear']), float(e['apex'])
        notes.append(f"EJECT onfoot={e['onfoot']} clear={c:.2f} м dist={e['dist']} м apex={a:.2f} м ejects={e['ejects']}")
        if e['onfoot'] != '1': fails.append(f"EJECT: Гомер не пешком (onfoot={e['onfoot']} state={e['state']}) — остался в остове")
        if c < .3: fails.append(f'EJECT: Гомер внутри кузова остова (clear {c:.2f} < 0.3 м)')
        if a < .1: fails.append(f'EJECT: не было полёта (apex {a:.2f} < 0.1 м)')   # правка Роба 73: «не так сильно, в сторону» (было 0.5 м)
        if int(e['ejects']) < 1: fails.append('EJECT: выброса взрывом не было (ejects 0)')
    # --- ирис
    iris = [kv(l) for l in log if l.startswith('IRIS ')]
    for why in WHYS:
        seq = [d for d in iris if d.get('why') == why]
        if not seq: fails.append(f'IRIS why={why}: перехода не было'); continue
        close = [float(d['r']) for d in seq if d['phase'] == 'close']
        hold = [float(d['r']) for d in seq if d['phase'] == 'hold']
        opn = [float(d['r']) for d in seq if d['phase'] == 'open']
        done = [d for d in seq if d['phase'] == 'done']
        bad = []
        if len(close) < 2 or any(b > a + 1e-3 for a, b in zip(close, close[1:])): bad.append('закрытие не монотонно')
        if not close or close[-1] > .5: bad.append(f'не закрылся до 0 (r {close[-1] if close else "-"})')
        if any(r > .5 for r in hold): bad.append('в «закрыто» отверстие не 0')
        if len(opn) < 2 or any(b < a - 1e-3 for a, b in zip(opn, opn[1:])): bad.append('раскрытие не монотонно')
        # последний кадр раскрытия при 30 кадр/с — кадр 24 из 25 данных (вес 0.9); кадр done — вес 1, ирис убран
        if not opn or max(opn) < HALF_DIAG * .85: bad.append(f'раскрытие не дошло до краёв кадра (max r {max(opn) if opn else 0:.0f})')
        if not done: bad.append('нет done')
        elif float(done[0]['r']) < HALF_DIAG: bad.append(f"done: отверстие {done[0]['r']} px меньше полудиагонали — углы остались бы чёрными")
        if why != 'test' and not 8 <= len(close) <= 40: bad.append(f'закрытие {len(close)} кадров (ждём 8..40: 1/3 с)')
        notes.append(f"IRIS {why:8}: закрытие {len(close)} кадров {close[0] if close else 0:.0f}->{close[-1] if close else 0:.0f} px, "
                     f"закрыто {len(hold)}, раскрытие {len(opn)} кадров до {max(opn) if opn else 0:.0f} px, done {len(done)}")
        if bad: fails.append(f'IRIS why={why}: ' + '; '.join(bad))
    # --- снимки (пиксели)
    try:
        from PIL import Image
    except ImportError:
        Image = None
    def shot(name):
        p = out / f'{name}.png'
        if not p.exists(): fails.append(f'нет снимка {name}.png'); return None
        im = Image.open(p).convert('L')
        w, h = im.size; return im.crop((0, h - round(w * 272 / 480), w, h))   # окно эмулятора: без заголовка, только кадр 480×272
    def near_r(name):   # радиус из строки IRIS, ближайшей к строке SHOT name (выше по файлу)
        r = None
        for l in log:
            if l.startswith('IRIS '): r = float(kv(l)['r'])
            if l.startswith(f'SHOT {name} '): return r
        return r
    if Image:
        im = shot('iris_closed')
        if im:
            w, h = im.size; px = im.load(); n = sum(1 for y in range(0, h, 2) for x in range(0, w, 2) if px[x, y] < 16)
            frac = n / ((w // 2 + w % 2) * (h // 2 + h % 2)); notes.append(f'снимок iris_closed: чёрного {frac:.0%}')
            if frac < .9: fails.append(f'iris_closed: чёрного {frac:.0%} < 90 %')
        im = shot('iris_mid')
        if im:
            w, h = im.size; px = im.load(); r = near_r('iris_mid')
            def mean(x0, y0, s):
                return sum(px[x, y] for x in range(x0, x0 + s) for y in range(y0, y0 + s)) / (s * s)
            c = mean(w // 2 - 8, h // 2 - 8, 16); k = max(4, w // 60)
            corners = [mean(2, h - k - 2, k), mean(w - k - 2, h - k - 2, k), mean(w - k - 2, 2, k)]   # левый верхний — служебный счётчик
            notes.append(f'снимок iris_mid: r≈{r} px, центр {c:.0f}, углы {", ".join(f"{v:.0f}" for v in corners)}')
            if r is None or not 15 < r < HALF_DIAG * .9: fails.append(f'iris_mid: снят не в середине раскрытия (r {r})')
            if c < 20: fails.append(f'iris_mid: центр чёрный ({c:.0f}) — отверстия нет')
            if max(corners) > 16: fails.append(f'iris_mid: угол не чёрный ({max(corners):.0f}) — ирис не закрывает края')
        shot('boom_after')
    print(('FAIL ' + fails[0]) if fails else 'PASS')
    for n in notes: print('  ' + n)
    for f in fails[1:]: print('  FAIL ' + f)
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
