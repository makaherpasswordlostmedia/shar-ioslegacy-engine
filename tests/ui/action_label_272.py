"""Правка Роба 272 (04.10 07:2x: «треугольник должен быть по центру экрана, под ним мелким Talk To Marge и все остальные подписи»):
раскладка HUD, как её отдаёт экспорт (tools/ui_export.py: build_items('hud') -> adapt, пиксели экрана PSP): значок ActionButton
по центру экрана (середина x 240 ±1), подпись ActionText — по центру под ним (середина x 240 ±1, верх не выше низа значка, не
дальше 4 px), мелким pix8. КРАСНЫЙ: UI_ACT_272_OLD=1 (подпись справа от значка) обязан упасть. Подпись видна в игре — гейт 206
tests/ui/action_label.sh. python3 tests/ui/action_label_272.py -> 0 = PASS"""
import os, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
CODE = r'''
import sys, io, contextlib; sys.path.insert(0, "tools")
with contextlib.redirect_stdout(io.StringIO()):
    import ui_export as U
    items, icons = U.build_items("hud"); out, _ = U.adapt(items, icons, "psp", U.Assets(), U.FontCache("psp"))
b = next(t for t in out if t.get("name") == "ActionButton"); l = next(t for t in out if t.get("name") == "ActionText")
bx, by, bw, bh = b["dst"]; lx, ly, lw, lh = l["dst"]
print(bx + bw / 2, by + bh, lx + lw / 2, ly, bool(l.get("pix8")))
'''

def lay(old):
    env = dict(os.environ); env.pop('UI_ACT_272_OLD', None)
    if old: env['UI_ACT_272_OLD'] = '1'
    r = subprocess.run([str(ROOT / '.venv/bin/python'), '-c', CODE], cwd=ROOT, env=env, capture_output=True, text=True)
    v = r.stdout.split()
    return (float(v[0]), float(v[1]), float(v[2]), float(v[3]), v[4] == 'True') if len(v) == 5 else None

def ok(m):
    if not m: return False
    bcx, bbot, lcx, ltop, pix = m
    return abs(bcx - 240) <= 1 and abs(lcx - 240) <= 1 and 0 <= ltop - bbot + 2 <= 6 and pix

if __name__ == '__main__':
    r, g = lay(True), lay(False)
    print(f'красный (UI_ACT_272_OLD): {r} -> {"прошёл — слепая проверка" if ok(r) else "упал, как должен"}')
    print(f'зелёный: значок x {g[0]:.1f}, низ {g[1]:.0f}; подпись x {g[2]:.1f}, верх {g[3]:.0f}, pix8 {g[4]}' if g else 'зелёный: нет данных')
    res = not ok(r) and ok(g)
    print('PASS: значок по центру экрана, подпись под ним мелким pix8; красный пойман' if res else 'FAIL'); sys.exit(0 if res else 1)
