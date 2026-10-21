#!/usr/bin/env python3
# Выкладка TEST35 на PSP одним запуском (Роб 18.10: «упакуй всё, как будет нужно» — кнопка «Положить SHAR на PSP» на рабочем столе):
#   полная игра  -> PSP/GAME/SHARVIEW   (build/test35 + EBOOT_SHARVIEW.PBP: название «The Simpsons Hit & Run», картинки и звук меню PSP)
#   тур TEST35   -> PSP/GAME/SHARTEST15 (build/test35tour)
# Только отличающееся по SHA-256; ничего не удаляется: лишнее и итоги прошлого тура — в _prev_TEST34 (с путями); настройки, сохранения и devsave Роба — на месте;
# level_toon.shr в игру не кладётся (мультик с 18.10 без него). Сверка SHA после копии. Карта не извлекается.
import hashlib, os, shutil, sys, time
I = os.path.expanduser('~/Downloads/shar-psp-integ')
PSP = '/Volumes/PSP/PSP/GAME'
KEEP = {'settings.bin', 'save00.bin', 'save01.bin', 'save02.bin', 'save03.bin', 'devsave', 'blackbox.txt', 'blackbox_prev.txt', 'stall.txt', 'me.txt', 'smoke.txt'}
SKIP = {'level_toon.shr'}
TOUR_RESULTS = ['blackbox.txt', 'blackbox_prev.txt', 'smoke.txt', 'me.txt', 'stall.txt', 'shots']

def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()

def files(root, skip_prefix):
    out = {}
    for d, ds, fs in os.walk(root):
        rel_d = os.path.relpath(d, root)
        if rel_d.split(os.sep)[0].startswith(skip_prefix): continue
        for f in fs:
            p = os.path.join(d, f); out[os.path.relpath(p, root)] = p
    return out

def deploy(name, src_dir, eboot, dst, keep, prev_name, move_results):
    t0 = time.time()
    if not os.path.isdir(src_dir): print('НЕТ сборки %s: %s' % (name, src_dir)); return False
    os.makedirs(dst, exist_ok=True)
    prev = os.path.join(dst, prev_name)
    src = files(src_dir, '_prev_')
    if eboot: src['EBOOT.PBP'] = eboot
    for s in SKIP: src.pop(s, None)
    if move_results:   # итоги прошлого тура — в _prev (копии остаются на карте)
        for r in TOUR_RESULTS:
            q = os.path.join(dst, r)
            if os.path.exists(q):
                os.makedirs(prev, exist_ok=True); t = os.path.join(prev, r)
                if os.path.exists(t): t = t + '_' + time.strftime('%H%M%S')
                shutil.move(q, t)
    dstf = files(dst, '_prev_')
    moved = 0
    for rel, p in sorted(dstf.items()):
        if rel in src or rel in keep: continue
        q = os.path.join(prev, rel); os.makedirs(os.path.dirname(q), exist_ok=True)
        if os.path.exists(q): q = q + '_' + time.strftime('%H%M%S')
        shutil.move(p, q); moved += 1
    todo = []
    for rel, p in sorted(src.items()):
        q = os.path.join(dst, rel)
        if not os.path.exists(q) or os.path.getsize(q) != os.path.getsize(p) or sha(q) != sha(p): todo.append(rel)
    mb = sum(os.path.getsize(src[r]) for r in todo) / 1e6
    print('%s: к выкладке %d файлов, %.0f МБ; лишнее в %s: %d' % (name, len(todo), mb, prev_name, moved), flush=True)
    for i, rel in enumerate(todo):
        q = os.path.join(dst, rel); os.makedirs(os.path.dirname(q), exist_ok=True); shutil.copyfile(src[rel], q)
        if (i + 1) % 20 == 0: print('  скопировано %d/%d' % (i + 1, len(todo)), flush=True)
    os.sync()
    bad = [r for r in todo if sha(os.path.join(dst, r)) != sha(src[r])]
    miss = [r for r in src if not os.path.exists(os.path.join(dst, r))]
    print('%s: скопировано %d, расхождений %d, нет на карте %d, EBOOT %s (%.0f с)' % (name, len(todo), len(bad), len(miss), sha(os.path.join(dst, 'EBOOT.PBP'))[:8], time.time() - t0), flush=True)
    for r in bad[:10]: print('  НЕ СОШЛОСЬ:', r)
    return not bad and not miss

if __name__ == '__main__':
    if not os.path.isdir(PSP): print('PSP не подключена: подключи её по USB (режим USB на PSP) и запусти ещё раз'); sys.exit(1)
    ok1 = deploy('Игра SHARVIEW', os.path.join(I, 'build/test35/PSP/GAME/SHARTEST15'), os.path.join(I, 'build/test35/EBOOT_SHARVIEW.PBP'),
                 os.path.join(PSP, 'SHARVIEW'), KEEP, '_prev_TEST34', False)
    ok2 = deploy('Тур SHARTEST15', os.path.join(I, 'build/test35tour/PSP/GAME/SHARTEST15'), None,
                 os.path.join(PSP, 'SHARTEST15'), set(), '_prev_TEST34', True)
    print('ГОТОВО: всё на карте, можно отключать PSP' if ok1 and ok2 else 'ЕСТЬ ОШИБКИ — смотри строки выше')
    sys.exit(0 if ok1 and ok2 else 1)
