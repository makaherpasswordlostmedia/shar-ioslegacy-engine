#!/usr/bin/env python3
"""Выкладка финального пакета на PSP (слово Роба): только изменённые файлы по SHA-256, сверка побайтно.
  tools/psp_sync_game.py PKG [DEST]    DEST по умолчанию /Volumes/PSP/PSP/GAME/SHARVIEW
Ничего не удаляет, кроме служебных флагов, которые мешали бы финалу (meaudio, mefx, mepeak, meaudiooff, nome, jitter, me.txt);
сохранения, настройки и логи на карте не трогает. Файлы '._*' пропускает и стирает на карте."""
import hashlib, os, shutil, sys
def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()
pkg = sys.argv[1]; dest = sys.argv[2] if len(sys.argv) > 2 else '/Volumes/PSP/PSP/GAME/SHARVIEW'
if not os.path.isdir('/Volumes/PSP/PSP'): sys.exit('PSP не подключена')
for f in ('meaudio', 'mefx', 'mepeak', 'meaudiooff', 'nome', 'jitter', 'me.txt', 'mefxmax'):
    if os.path.exists(os.path.join(dest, f)): os.remove(os.path.join(dest, f)); print('убран флаг', f)
chg = []; total = 0; n = 0
for r, _, fs in os.walk(pkg):
    for f in sorted(fs):
        if f.startswith('._'): continue
        s = os.path.join(r, f); d = os.path.join(dest, os.path.relpath(s, pkg)); n += 1
        if not os.path.exists(d) or os.path.getsize(d) != os.path.getsize(s) or sha(d) != sha(s): chg.append((s, d)); total += os.path.getsize(s)
print(f'в пакете {n} файлов, изменилось {len(chg)} ({total >> 20} МБ)', flush=True)
for s, d in chg:
    os.makedirs(os.path.dirname(d), exist_ok=True); shutil.copyfile(s, d)
os.sync()
bad = [s for s, d in chg if sha(s) != sha(d)]
for r, _, fs in os.walk(dest):
    for f in fs:
        if f.startswith('._'): os.remove(os.path.join(r, f))
print('сверка:', 'ВСЕ СОВПАЛИ' if not bad else f'НЕ СОВПАЛО {len(bad)}: {bad[:3]}')
sys.exit(1 if bad else 0)
