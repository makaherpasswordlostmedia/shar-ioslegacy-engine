#!/usr/bin/env python3
"""Правка Роба 365 (05.10: «уведомления сильно выше карты-радара — отцентровать по высоте с кружком радара»): центр видимого пузыря
задания/уведомления HUD (альфа картинки пузыря) — на центре кольца радара по высоте, ±1 px; низ блока задания не за краем экрана.
КРАСНЫЙ: UI_OBJ_RADAR_OLD=1 (прежнее место: пузырь выше на 11–15 px) обязан упасть. Нужен диск Роба (как tests/ui/bubble_top.py).
    python3 tests/ui/bubble_radar.py -> 0 = PASS"""
import os, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT / 'tools'))


def measure():
    import ui_export as U
    items, icons = U.build_items('hud')
    out, _ = U.adapt(items, icons, 'psp', U.Assets(), U.FontCache('psp'))
    box = next(t for t in out if t['name'] == 'MessageBox' and t.get('tag') == 'OBJECTIVE')
    bx, by, bw, bh = box['dst']
    bim = U.all_images()[box['frames'][0]]; _, b0, _, b1 = bim.getchannel('A').point(lambda a: 255 if a >= 128 else 0).getbbox()
    bub = by + bh * (b0 + b1) / 2 / bim.height
    radar = [t for t in out if t.get('tag') == 'RADAR' and t.get('dst') and t.get('frames')]
    ring = max(radar, key=lambda t: t['dst'][2] * t['dst'][3]); rad = ring['dst'][1] + ring['dst'][3] / 2
    low = max(t['dst'][1] + t['dst'][3] for t in out if t.get('tag') == 'OBJECTIVE' and t.get('dst'))
    return bub, rad, low


if __name__ == '__main__':
    if '--one' in sys.argv:
        print('%.2f %.2f %.2f' % measure()); sys.exit(0)
    def one(old):
        env = dict(os.environ); env.pop('UI_OBJ_RADAR_OLD', None)
        if old: env['UI_OBJ_RADAR_OLD'] = '1'
        r = subprocess.run([sys.executable, __file__, '--one'], env=env, capture_output=True, text=True)
        try: return tuple(float(v) for v in r.stdout.split()[-3:])
        except ValueError: print(r.stderr[-800:]); return None
    red, green = one(True), one(False)
    if not red or not green: print('FAIL: замер не вышел'); sys.exit(2)
    print(f'красный (UI_OBJ_RADAR_OLD): пузырь {red[0]:.1f}, радар {red[1]:.1f} — {red[0] - red[1]:+.1f} px')
    print(f'зелёный: пузырь {green[0]:.1f}, радар {green[1]:.1f} — {green[0] - green[1]:+.1f} px, низ блока {green[2]:.0f} из 272')
    red_ok = abs(red[0] - red[1]) > 3
    green_ok = abs(green[0] - green[1]) <= 1 and green[2] <= 272
    print('красный:', 'пойман' if red_ok else 'НЕ пойман')
    print('PASS' if red_ok and green_ok else 'FAIL'); sys.exit(0 if red_ok and green_ok else 1)
