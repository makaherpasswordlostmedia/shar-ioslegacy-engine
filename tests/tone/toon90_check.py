#!/usr/bin/env python3
"""№754: движок (toon90 в viewer/tone.c) = проба preset90.py, по которой оценивался вид; плюс правила рефа: нет чистого чёрного и белого, серое — к барвинку.
   python3 tests/tone/toon90_check.py   (собирает build/toon90-host)   код 0 = PASS"""
import os, subprocess, sys
import numpy as np
R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, os.path.join(R, 'tests', 'tone'))
import preset90 as P
exe = os.path.join(R, 'build', 'toon90-host')
subprocess.run(['cc', '-O1'] + (['-DTONE_T90_GATE_RED'] if os.environ.get('T90_RED') == '1' else []) + ['-I', os.path.join(R, 'viewer'), os.path.join(R, 'tests', 'tone', 'toon90_host.c'), '-lm', '-o', exe], check=True)
a = np.array([[int(x) for x in l.split()] for l in subprocess.run([exe], capture_output=True, text=True).stdout.split('\n') if l.strip()], float)
src, eng, lut = a[:, :3] / 255., a[:, 3:6], a[:, 6:9]
ref = np.clip(P.preset(src[None])[0], 0, 1) * 255
d = np.abs(eng - ref).max(1); ok1 = d.max() <= 3
blk = eng[(src == 0).all(1)][0]; wht = eng[(src == 1).all(1)][0]; gry = eng[(np.abs(src - .5) < .04).all(1)][0]
ok2 = blk.max() >= 30 and blk[2] > blk[0]; ok3 = wht.min() < 250 and wht[2] < wht[0]; ok4 = gry[2] > gry[0] + 8
print('движок против пробы: наибольшая разница %.1f (порог 3), средняя %.2f' % (d.max(), d.mean()))
print('чёрное -> %s (индиго), белое -> %s (кремовый), серое 136 -> %s (барвинок)' % (blk.astype(int).tolist(), wht.astype(int).tolist(), gry.astype(int).tolist()))
dl = np.abs(lut - ref).max(1); p99 = np.percentile(dl, 99); ok5 = np.percentile(dl, 95) <= 14 and dl.mean() <= 4.0
print('таблица против пробы: средняя %.2f (порог 4), 95-й %.1f (порог 14), 99-й %.1f, наибольшая %.1f (на скачках оттенка между цветами палитры)' % (dl.mean(), np.percentile(dl, 95), p99, dl.max()))
ok = ok1 and ok2 and ok3 and ok4 and ok5; print('PASS' if ok else 'FAIL'); sys.exit(0 if ok else 1)
