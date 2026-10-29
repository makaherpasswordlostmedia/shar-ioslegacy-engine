#!/usr/bin/env python3
"""№574: масштаб элемента — от центра, пропорционально, центр не уезжает; панель (scaleRect2) и экспорт игры (ui_typo._scale_img_xy) дают одни и те же прямоугольники.
  python tests/ui/element_scale.py [страница панели]            зелёный: 0
  python tests/ui/element_scale.py --plant corner               красный контроль: масштаб от левого верхнего угла — обязан упасть"""
import json, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import ui_typo as UT

class A:   # заглушка набора картинок: только прямоугольник
    images = {}
    def put(self, k, im): return k
    def scaled(self, f, w, h, tag=''): return '%s@%dx%d' % (f, w, h)
hs = lambda im, w, h: None

def py_rect(r, kx, ky, plant):
    t = dict(dst=list(r))
    UT._scale_img_xy(t, kx, ky, A(), hs)
    if plant == 'corner':
        t['dst'] = [r[0], r[1], t['dst'][2], t['dst'][3]]   # прежний дефект: масштаб от угла
    return t['dst']

CASES = [([389, 217, 65, 42], 2.0, 2.0), ([29, 233, 26, 28], 2.0, 2.0), ([45, 246, 345, 2], 1.0, 3.0), ([108, 29, 263, 184], 0.5, 0.5), ([403, 248, 17, 17], 1.12, 1.08), ([-30, 10, 41, 15], 2.5, 1.0)]
def main():
    args = sys.argv[1:]; plant = args[args.index('--plant') + 1] if '--plant' in args else ''
    page = Path([a for a in args if not a.startswith('--') and a != plant][0] if [a for a in args if not a.startswith('--') and a != plant] else ROOT / 'build/ТИПОГРАФИКА_ПАНЕЛЬ/index.html')
    js = r'''
const fs = require('fs'), vm = require('vm'); const html = fs.readFileSync(process.argv[2], 'utf8');
const blocks = [...html.matchAll(/<script(?: id="core")?>\n([\s\S]*?)<\/script>/g)].map(m => m[1]);
const ctx = {atob: s => Buffer.from(s, 'base64').toString('binary'), Math, Float32Array, Float64Array, Uint8Array, Int32Array, Object, JSON, Date};
ctx.window = ctx; ctx.globalThis = ctx; vm.createContext(ctx); vm.runInContext(blocks[0], ctx); vm.runInContext(blocks[1], ctx);
const cases = JSON.parse(process.argv[3]); console.log(JSON.stringify(cases.map(c => ctx.TC.scaleRect2(c[0], c[1], c[2]))));'''
    f = Path(tempfile.mkdtemp()) / 't.js'; f.write_text(js)
    jr = json.loads(subprocess.run(['node', str(f), str(page), json.dumps(CASES)], capture_output=True, text=True, check=True).stdout)
    bad = 0
    for (r, kx, ky), j in zip(CASES, jr):
        p = py_rect(r, kx, ky, plant); c0 = (r[0] + r[2] / 2, r[1] + r[3] / 2); c1 = (p[0] + p[2] / 2, p[1] + p[3] / 2)
        centre_ok = abs(c0[0] - c1[0]) <= 0.5 + 1e-9 and abs(c0[1] - c1[1]) <= 0.5 + 1e-9
        size_ok = abs(p[2] - r[2] * kx) <= 0.5 + 1e-9 and abs(p[3] - r[3] * ky) <= 0.5 + 1e-9
        same = p == j
        print('%-4s %s x(%.2f,%.2f) -> экспорт %s, панель %s, центр %s' % ('ok' if centre_ok and size_ok and same else 'FAIL', r, kx, ky, p, j, 'на месте' if centre_ok else 'УЕХАЛ'))
        bad += not (centre_ok and size_ok and same)
    print('PASS' if not bad else 'FAIL %d' % bad)
    return 1 if bad else 0
sys.exit(main())
