#!/usr/bin/env python3
"""Сверка прогона tests/shop/wardrobe_emu.sh (правка Роба 107): строки WARDV / WARDROBE (viewer/wardrobe_view.c, main.c homerWear)
и снимки окна. Ожидания — с диска Роба, независимо от движка: костюмы уровня 1 — BindReward "skin" уровня 1 в rewards.mfk
(порядок файла, цена forsale), модель — art\\chars\\<модель>.p3d -> homer-<модель>.shr (обычный — homer.shr).
  wardrobe_check.py ОТЧЁТ [1]   1 — отрицательный прогон (без монет): PASS, только если сверка упала"""
import re, sys
from pathlib import Path
import numpy as np
from PIL import Image
ROOT = Path(__file__).resolve().parents[2]
GAME = ROOT / 'hit-and-run-web/source/game'

out, neg = Path(sys.argv[1]), len(sys.argv) > 2 and sys.argv[2] == '1'
log = (out / 'smoke.txt').read_text(errors='replace').splitlines() if (out / 'smoke.txt').exists() else []
wl = [l for l in log if l.startswith('WARDV') or l.startswith('WARDROBE')]
rw = re.sub(r'//[^\n]*', '', (GAME / 'scripts/missions/rewards.mfk').read_text(errors='replace'))
sk = []
for m in re.finditer(r'BindReward\s*\(([^)]*)\)', rw):
    a = [x.strip().strip('"') for x in m.group(1).split(',')]
    if len(a) >= 5 and a[2] == 'skin' and a[4] == '1':
        mdl = a[1].replace('\\', '/').split('/')[-1][:-4]
        sk.append((a[0], 'homer.shr' if mdl == 'homer_m' else f'homer-{mdl}.shr', int(a[5]) if a[3] == 'forsale' else 0))
fails = []
def has(pat): return any(re.search(pat, l) for l in wl)
n, (n1, f1, p1), (n0, f0, _) = len(sk), sk[1], sk[0]
if not has(rf'^WARDV open n={n} cur=0 coins=300 name={n0}\b'): fails.append(f'△ у места костюмов не открыл гардероб ({n} костюмов с диска, надет {n0}; нет WARDV open)')
if not has(rf'^WARDV sel 1 name={n1} price={p1} owned=0'): fails.append(f'► не показал {n1} за {p1} (нет WARDV sel 1)')
if not has(rf'^WARDV buy 1 name={n1} price={p1} coins={300 - p1}'): fails.append(f'✕ не купил {n1} за {p1} (нет WARDV buy ... coins={300 - p1})')
if not has(rf'^WARDROBE wear 1 {re.escape(f1)}'): fails.append(f'Гомер не переоделся в {f1} (нет WARDROBE wear 1)')
if not has(rf'^WARDV open n={n} cur=1 coins={300 - p1} name={n1}\b'): fails.append('второй раз гардероб открылся не на надетом костюме')
if not has(rf'^WARDROBE wear 0 {re.escape(f0)}'): fails.append(f'обратно в {n0} не переоделся (нет WARDROBE wear 0)')
lp = [l for l in log if l.startswith('LEVELSTATS pause')]   # LEVEL PROGRESS после покупки: одежда — обычный + купленный
if not lp or not re.search(rf' skins=2/{n}\b', lp[-1]): fails.append('покупка не засчитана в LEVEL PROGRESS (ждём skins=2/%d): %s' % (n, lp[-1][:90] if lp else 'экрана нет'))
if has(r'^WARDV (refuse|nopack)'): fails.append('гардероб отказал: ' + next(l for l in wl if re.search(r'^WARDV (refuse|nopack)', l)))


def crop(name):   # окно 480×(272+заголовок) -> кадр PSP 480×272
    p = out / f'{name}.png'
    if not p.exists(): return None
    return np.asarray(Image.open(p).convert('RGB').resize((480, 288))).astype(int)[16:, :]


im = {k: crop(k) for k in ('wr_before', 'wr_open', 'wr_undr', 'wr_worn', 'wr_back')}
miss = [k for k, v in im.items() if v is None]
line = ''
if miss: fails.append('нет снимков: ' + ', '.join(miss))
else:
    d = lambda a, b, box=(0, 0, 480, 272): float(np.abs(im[a][box[1]:box[3], box[0]:box[2]] - im[b][box[1]:box[3], box[0]:box[2]]).mean())
    mid = (160, 40, 320, 240)   # середина кадра: Гомер у места костюмов (камера комнаты та же до и после)
    dv = dict(open=d('wr_before', 'wr_open'), page=d('wr_open', 'wr_undr', (40, 40, 440, 230)), worn=d('wr_before', 'wr_worn', mid),
              back=d('wr_before', 'wr_back', mid))
    line = 'разница: страница %.1f, ► %.1f, в костюме %.1f, обратно %.1f' % (dv['open'], dv['page'], dv['worn'], dv['back'])
    if dv['open'] < 8: fails.append('страница гардероба не на экране (снимок как до △)')
    if dv['page'] < 1.5: fails.append('► не сменил картинку/имя костюма на странице')
    if dv['worn'] < 1.0: fails.append('на снимке Гомер не в костюме (кадр как до покупки)')
    if dv['back'] > dv['worn']: fails.append('после возврата в обычное Гомер не похож на прежнего')
if neg:
    print(('PASS (красный пойман): ' + fails[0]) if fails else 'FAIL (красный не пойман): ' + line); sys.exit(0 if fails else 1)
if fails: print('FAIL: ' + fails[0] + (' [' + line + ']' if line else '')); sys.exit(1)
print('OK: гардероб уровня 1 — %d костюмов с диска (%s), куплен %s за %d, надет и снят (%d строк WARDV/WARDROBE); %s; снимки %s'
      % (n, ', '.join(f'{a} {c}' for a, _, c in sk), n1, p1, len(wl), line, out))
