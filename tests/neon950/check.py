#!/usr/bin/env python3
# №950: на причале L6 C8-6 свечения вывесок (аддитивные плашки таблицы света, невысокие вертикальные) нет, конусы ламп остались.
#   check.py ПАПКА_ПРОГОНА -> строки SLENTRY сцен SIGN_n (flag neonsign950 1) и SIGN_o (0): плашек (высота ≤ 1,5 ширины) и конусов; светлее ли кадр без правки (o_*.png против n_*.png)
#   OK: в новом плашек 0, в прежнем ≥ 5, конусов в новом не меньше, чем в прежнем; кадры прежнего светлее нового на ≥ 3000 пикселей (сумма RGB > 30), новый светлее прежнего не больше чем на 1500
import re, sys
import numpy as np
from PIL import Image
d = sys.argv[1]
cnt = {'SIGN_n': [0, 0], 'SIGN_o': [0, 0]}
for l in open(d + '/smoke.txt', errors='replace'):
    m = re.match(r'SLENTRY sc=(\S+) k=\d+ kind=(\d) tex=\S+ p=\S+ X=([\d.\-]+),\S+ Y=\S+?,([\d.\-]+),', l)
    if m and m.group(1) in cnt: cnt[m.group(1)][0 if float(m.group(4)) > 1.5 * float(m.group(3)) else 1] += 1
bo = bn = 0
for k in 'abc':
    n = np.asarray(Image.open('%s/n_%s.png' % (d, k)).convert('RGB')).astype(int); o = np.asarray(Image.open('%s/o_%s.png' % (d, k)).convert('RGB')).astype(int)
    df = (o - n).sum(axis=2)[70:, :]; bo += int((df > 30).sum()); bn += int((df < -30).sum())
print('замер: плашек свечения вывесок — новое %d, прежнее %d; конусов — новое %d, прежнее %d; пикселей светлее у прежнего %d, у нового %d' % (cnt['SIGN_n'][1], cnt['SIGN_o'][1], cnt['SIGN_n'][0], cnt['SIGN_o'][0], bo, bn))
ok = cnt['SIGN_n'][1] == 0 and cnt['SIGN_o'][1] >= 5 and cnt['SIGN_n'][0] >= cnt['SIGN_o'][0] and bo >= 3000 and bn <= 1500
print('OK' if ok else 'BAD'); sys.exit(0 if ok else 1)
