#!/usr/bin/env python3
"""Сверка прогона tests/shop/booth_emu.sh (правка Роба 104): строки PHONEV / PHONE (viewer/phone_view.c, main.c) и снимки окна.
Ожидания — с диска Роба: будка R1P2 (ActionEvent SummonVehiclePhone), список build/phonecars.txt по rewards.mfk уровня 1 — своя
famil_v (defaultcar) открыта, elect_v (streetrace, второй в галерее PS2) закрыта; картинка машины — cars2d/<машина>.p3d (PreviewImage PhoneBooth.pag)
видна и у открытой, и у закрытой (жалоба Роба 30.09: «не отображаются вообще — ни открытые, ни закрытые»).
  booth_check.py ОТЧЁТ [1]   1 — отрицательный прогон (прежний phone.shr без cars2d): PASS, только если сверка упала"""
import re, sys
from pathlib import Path
import numpy as np
from PIL import Image

out, neg = Path(sys.argv[1]), len(sys.argv) > 2 and sys.argv[2] == '1'
log = (out / 'smoke.txt').read_text(errors='replace').splitlines() if (out / 'smoke.txt').exists() else []
pl = [l for l in log if l.startswith('PHONEV') or l.startswith('PHONE ')]
fails = []
def has(pat): return any(re.search(pat, l) for l in pl)
if not has(r'^PHONEV open n=\d+ cur=0 name=famil_v owned=1'): fails.append('△ у будки не открыл экран на своей машине (нет PHONEV open ... famil_v owned=1)')
if not has(r'^PHONEV open .* now=1 dmg=90'): fails.append('у своей машины нет «Damaged: 90%%» (нет PHONEV open ... now=1 dmg=90; запись PS2 37:54)')
# пункт ДОБИВКИ 26 (запись PS2 ps2_v105_booth_access): после своей машины ► — Electaurus (порядок defaultcar, streetrace, bonusmission,
# forsale); до 09.10 порт ставил пикап Клетуса вторым (порядок rewards.mfk). Закрытая машина — та же проверка картинки ниже
if not has(r'^PHONEV sel 1 name=elect_v owned=0'): fails.append('► не показал закрытый Electaurus (нет PHONEV sel 1 elect_v owned=0; запись PS2 ps2_v105_booth_access)')
if not has(r'^PHONEV accept 0 name=famil_v'): fails.append('✕ не вызвал свою машину (нет PHONEV accept famil_v)')
if not has(r'^PHONE (summon|car) '): fails.append('машина не приехала к будке (нет PHONE summon/car)')


def picture(name):   # доля «не синих» пикселей в окне картинки машины (фон страницы синий; стрелки и звёзды — вне окна)
    p = out / f'{name}.png'
    if not p.exists(): return None
    a = np.asarray(Image.open(p).convert('RGB').resize((480, 288))).astype(int)[16:, :][70:170, 120:260]
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    return float(((r > b + 25) | (g > b + 25)).mean())


v = {n: picture(n) for n in ('ph_open', 'ph_locked', 'ph_own')}
miss = [n for n, x in v.items() if x is None]
line = ', '.join('%s %.3f' % (n, x) for n, x in v.items() if x is not None)
if miss: fails.append('нет снимков: ' + ', '.join(miss))
else:
    if v['ph_open'] < .04: fails.append('у открытой машины нет картинки (%.3f)' % v['ph_open'])
    if v['ph_locked'] < .04: fails.append('у закрытой машины нет картинки (%.3f)' % v['ph_locked'])
if neg:
    print(('PASS (красный пойман): ' + fails[0]) if fails else 'FAIL (красный не пойман): ' + line); sys.exit(0 if fails else 1)
if fails: print('FAIL: ' + fails[0] + ' [картинка: ' + line + ']'); sys.exit(1)
print('OK: будка R1P2 — своя famil_v открыта, elect_v закрыта, картинки машин видны (%s), вызов своей (%d строк PHONEV/PHONE); снимки %s'
      % (line, len(pl), out))
