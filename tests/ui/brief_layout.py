#!/usr/bin/env python3
"""Правка Роба 39 (видео с PSP 3:30–3:50): брифинг MissionLoad.pag — название и две нижние кнопки (Continue / Cancel Mission)
капельку крупнее, текст задания чуть ниже картинки. Раскладка — как её собирает tools/ui_export.py (briefing_layout), в пикселях
PSP; сравнение — с прежней раскладкой (UI_BRIEF_OLD=1, отдельный процесс).
Проверки: строка названия и надписей кнопок выше прежней (шаг BRIEF_LH_STEP, та же грань, не крупнее MISSION_EFF_MAX);
значки кнопок крупнее, надпись по центру значка; описание ниже картинки не меньше строки своего шрифта; самое длинное
описание всех уровней (строк после переноса) кончается выше кнопок; всё внутри планшета (background).
    tests/ui/brief_layout.py              -> PASS/FAIL
    tests/ui/brief_layout.py --negative   прежняя раскладка обязана покраснеть (тогда PASS)"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def layout():
    sys.path.insert(0, str(ROOT / 'tools'))
    import ui_export as U
    fc = U.FontCache('psp')
    items, icons = U.build_items('missionload')
    out, _ = U.adapt(items, icons, 'psp', U.Assets(), fc)
    r = {}
    for t in out:
        if t['name'] in ('MissionTitle', 'Continue', 'Abort', 'MissionInfo', 'MissionStartBitmap', 'background'):
            key = t['name'] + (':txt' if t['type'] == U.T_TEXT and t['name'] in ('Continue', 'Abort') else '')
            d = dict(dst=t['dst'])
            if t['type'] == U.T_TEXT:
                f = fc.get(t['font']); d.update(font=t['font'], lh=f['lh'], eff=U.eff_scale(t['font']))
                if t['name'] == 'MissionInfo':
                    d['maxlines'] = max(len(U.wrap_lines(f, s, t['dst'][2], True)) for s in t['strings'] if s)
            r[key] = d
    info = next(t for t in out if t['name'] == 'MissionInfo')   # как ui.c fitW: строк — до ближайшей детали ниже, что перекрывает по x
    x, y, w, h = info['dst']; bottom = 272
    for b in out:
        bx, by, bw, bh = b['dst']
        if b is info or by <= y or b['type'] == U.T_RECT or bx >= x + w or bx + bw <= x:
            continue
        bottom = min(bottom, by)
    r['MissionInfo']['enginelines'] = max(1, (bottom - y) // fc.get(info['font'])['lh'])
    return r


def main():
    if '--dump' in sys.argv:
        print(json.dumps(layout())); return 0
    env = dict(os.environ, UI_BRIEF_OLD='1')
    old = json.loads(subprocess.run([sys.executable, __file__, '--dump'], env=env, capture_output=True, text=True, check=True).stdout)
    envn = dict(os.environ); envn.pop('UI_BRIEF_OLD', None)
    if '--negative' in sys.argv:
        envn['UI_BRIEF_OLD'] = '1'
    new = json.loads(subprocess.run([sys.executable, __file__, '--dump'], env=envn, capture_output=True, text=True, check=True).stdout)
    sys.path.insert(0, str(ROOT / 'tools'))
    import ui_export as U
    chk = []
    t0, t1 = old['MissionTitle'], new['MissionTitle']
    chk.append((t1['lh'] >= t0['lh'] + U.BRIEF_LH_STEP and t1['eff'] <= U.MISSION_EFF_MAX + 1e-6 and t1['font'].split('*')[0] == t0['font'].split('*')[0],
                'название: строка %d -> %d px (+%d), грань %s, x%.2f от 272/480 (<= %.2f)' % (t0['lh'], t1['lh'], U.BRIEF_LH_STEP, t1['font'], t1['eff'], U.MISSION_EFF_MAX)))
    for nm in ('Continue', 'Abort'):
        a0, a1, i0, i1 = old[nm + ':txt'], new[nm + ':txt'], old[nm], new[nm]
        cy_i = i1['dst'][1] + i1['dst'][3] / 2; cy_t = a1['dst'][1] + a1['dst'][3] / 2
        chk.append((a1['lh'] >= a0['lh'] + U.BRIEF_LH_STEP and a1['eff'] <= U.MISSION_EFF_MAX + 1e-6 and i1['dst'][3] > i0['dst'][3] and abs(cy_i - cy_t) <= 1.0,
                    'кнопка %s: надпись %d -> %d px, значок %d -> %d px, центры по высоте %.1f / %.1f' % (nm, a0['lh'], a1['lh'], i0['dst'][3], i1['dst'][3], cy_i, cy_t)))
    pic, info, bg = new['MissionStartBitmap']['dst'], new['MissionInfo'], new['background']['dst']
    gap = info['dst'][1] - (pic[1] + pic[3])
    chk.append((gap >= info['lh'], 'описание ниже картинки на %d px (>= строки %d px; было %d px)' % (gap, info['lh'], old['MissionInfo']['dst'][1] - (old['MissionStartBitmap']['dst'][1] + old['MissionStartBitmap']['dst'][3]))))
    bottom = info['dst'][1] + info['maxlines'] * info['lh']
    btop = min(new['Continue']['dst'][1], new['Abort']['dst'][1], new['Continue:txt']['dst'][1], new['Abort:txt']['dst'][1])
    chk.append((bottom <= btop, 'самое длинное описание (%d строки) кончается на %d px, кнопки с %d px' % (info['maxlines'], bottom, btop)))
    chk.append((info['enginelines'] >= info['maxlines'], 'движок (ui.c fitW) даст описанию %d строк(и), нужно %d' % (info['enginelines'], info['maxlines'])))
    inside = all(bg[0] <= d['dst'][0] and d['dst'][0] + d['dst'][2] <= bg[0] + bg[2] and bg[1] <= d['dst'][1] and d['dst'][1] + d['dst'][3] <= bg[1] + bg[3]
                 for k, d in new.items() if k in ('MissionTitle', 'Continue', 'Abort', 'Continue:txt', 'Abort:txt'))
    chk.append((inside, 'название и кнопки внутри планшета %s' % bg))
    bad = sum(not c for c, _ in chk)
    for c, s in chk:
        print('%-5s %s' % ('ok' if c else 'FAIL', s))
    print('брифинг: %s' % ('OK' if not bad else 'FAIL %d' % bad))
    if '--negative' in sys.argv:
        print('PASS (отрицательный контроль: прежняя раскладка покраснела)' if bad else 'FAIL (прежняя раскладка прошла — сверка ничего не ловит)')
        return 0 if bad else 1
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
