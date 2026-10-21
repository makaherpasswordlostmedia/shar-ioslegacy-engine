#!/usr/bin/env python3
"""Правка Роба 301 (04.10, голосом: «Дом Гомера: на потолке всё равно дырки — полигоны не достраиваются; у телевизора тыльная
часть пустая, как будто просто рамка»). Две проверки пакета рисования комнат (build/interiors-l1-gfx.bin):

  see_through.py cams [ПАКЕТ]    камеры оригинала не смотрят сквозь мебель (на Маке, без эмулятора). Гомер в узлах пола 1 м
      (земля COL1 комнаты, не в ящиках мебели), камера — viewer/roomcam.c, как в EBOOT (tests/rooms/view_host.c), кадр 160×90;
      всё рисуется с обеих сторон, «сквозь» — первым в пикселе виден своей изнанкой треугольник, который движок рисует только
      лицом по обходу комнаты (флаг 128 без 8, tools/roomorient.py; слои 64/512 — своё правило, не в счёт): в EBOOT там
      видно то, что за ним (спинка телевизора — ковёр сквозь корпус). Кадр, где «сквозь» больше SEEN_MAX, — камера за стеной (правка 27), не в
      счёт. Провал — кадр «в счёт» с долей «сквозь» больше SEE_MAX.
  see_through.py holes [ПАКЕТ] [--eboot E]   дыр фона нет (эмулятор, безголовый, без звука). Копия пакета с фоном каждой
      комнаты пурпурным 0xFFFF00FF, сценарий tests/rooms/emu_holes.txt (снимок из каждой камеры комнат и гостиная Симпсонов с
      достижимого пола); провал — снимок комнаты с пурпурными пикселями больше HOLE_MAX (фон кадра — дыра в геометрии).
  see_through.py gate [ПАКЕТ] [--eboot E]    красный, потом зелёный: пакет по прежним правилам (экспорт с SHR_ROOM_CAMSIDE=0
      SHR_ROOM_CEIL=0 в build/rooms_holes/old/) обязан провалить обе проверки, ПАКЕТ — пройти обе. PASS / FAIL."""
import argparse, os, shutil, struct, subprocess, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools')); sys.path.insert(0, str(ROOT / 'tests/rooms'))
SEE_MAX = 0.005      # доля кадра «сквозь» в кадре камеры оригинала
HOLE_MAX = 40        # пурпурных пикселей в снимке комнаты 480×272 (0,03 %): дизеринг и край кадра — шум
MAGENTA = 0xFFFF00FF
ROOM_SHOTS = ('kc', 'se_', 'sh_')   # снимки внутри комнат в tests/rooms/emu_holes.txt
OUT = ROOT / 'build/rooms_holes'


def cams(pkg):
    """-> (провалы, строки сводки)"""
    import shr7read, roomorient, walls
    rooms = shr7read.load_rooms(pkg); cols = walls.rooms_col(Path(pkg).with_name('interiors-l1.bin') if Path(pkg).with_name('interiors-l1.bin').exists()
                                                                else ROOT / 'build/interiors-l1.bin')
    host = roomorient.view_host(); req = []
    for name, (TR, BX) in cols.items():
        if name in rooms: req += [f'{name} {p[0]:.4f} {p[1]:.4f} {p[2]:.4f}' for p in roomorient.floor_points(TR, BX, 1.0)]
    res = subprocess.run([str(host), str(pkg)], input='\n'.join(req) + '\n', capture_output=True, text=True, check=True).stdout.splitlines()
    fails, notes = [], []
    for name, d in rooms.items():
        FL = d['FL']; cull = ((FL & 128) != 0) & ((FL & (4 | 8 | 64)) == 0)   # обход комнаты (setFlags viewer/main.c); слои (64/512,
        # правки 37/43: сдвиг глубины и отсечение со стороны подложки, цена — свес за край не виден) — своё правило, здесь не в счёт
        views = [l.split() for l in res if l.startswith('VIEW ' + name + ' ') and l.split()[5] != '-1']
        if not views: continue
        V = np.array([[float(x) for x in v[8:14]] + [float(v[7]), roomorient.VIEW_W / roomorient.VIEW_H] for v in views], np.float32)
        _, pv = roomorient.seen(d['P'], ~cull, V)
        frac = pv / float(roomorient.VIEW_W * roomorient.VIEW_H); counted = frac <= roomorient.SEEN_MAX
        bad = counted & (frac > SEE_MAX)
        worst = int(np.argmax(np.where(counted, frac, -1)))
        notes.append(f'{name}: кадров {len(V)} (камера за стеной, не в счёт: {int((~counted).sum())}); «сквозь»: в среднем {frac[counted].mean():.2%}, '
                     f'макс {frac[worst]:.2%} (камера {views[worst][6]}, Гомер у {views[worst][2]} {views[worst][4]})')
        if bad.any(): fails.append(f'{name}: {int(bad.sum())} кадров камер оригинала смотрят сквозь отсечённую изнанку (> {SEE_MAX:.1%} кадра)')
    return fails, notes


def paint(src, dst):
    b = bytearray(Path(src).read_bytes()); assert b[:4] == b'SHG1'
    n, = struct.unpack_from('<I', b, 4)
    for r in range(n):
        off, = struct.unpack_from('<I', b, 16 + 48 * r + 32)
        assert b[off:off + 4] == b'RMG1'; struct.pack_into('<I', b, off + 20, MAGENTA)   # RMG1 @20 — цвет фона (tools/interior_export.py)
    Path(dst).write_bytes(bytes(b))


def holes(pkg, eboot, tag):
    """прогон tests/rooms/emu_holes.txt с пурпурным фоном комнат -> (провалы, сводка)"""
    sys.path.insert(0, str(ROOT / 'tools/twins'))
    import common as C, port as P
    from PIL import Image
    OUT.mkdir(parents=True, exist_ok=True); painted = OUT / f'{tag}-gfx.bin'; paint(pkg, painted)
    d, man = P.stage_full(OUT, tag, (ROOT / 'tests/rooms/emu_holes.txt').read_text(), 5)
    for nm, s in (('EBOOT.PBP', eboot), ('interiors-l1-gfx.bin', painted)):
        if s is None: continue
        t = d / nm
        if t.exists() or t.is_symlink(): t.unlink()
        shutil.copy2(s, t)
    home = OUT / 'ppsspp_home'; home.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, HOME=str(home), TWINS_SMOKE=str(d / 'smoke.txt'), TWINS_SHOTDIR=str(d), DYLD_FRAMEWORK_PATH=str(C.BIN))
    for k in ('XDG_CONFIG_HOME', 'XDG_DATA_HOME'): env.pop(k, None)
    with (d / 'headless.log').open('w') as log:
        pr = subprocess.Popen(['nice', '-n', '10', str(P.HEADLESS), '--graphics=software', '--timeout=600', str(d / 'EBOOT.PBP')],
                              cwd=d, env=env, stdout=log, stderr=subprocess.STDOUT)
        P.watch_no_window(pr, 660)
    for b in sorted(d.glob('*.bmp')): P.bmp_to_png(b, b.with_suffix('.png'))
    shots = sorted(p for p in d.glob('*.png') if p.stem.startswith(ROOM_SHOTS))
    want = [l.split()[1] for l in (ROOT / 'tests/rooms/emu_holes.txt').read_text().splitlines() if l.startswith('shot ') and l.split()[1].startswith(ROOM_SHOTS)]
    fails, notes, rows = [], [], []
    miss = sorted(set(want) - {p.stem for p in shots})
    if miss: fails.append(f'нет снимков: {" ".join(miss)} (прогон {d})')
    for p in shots:
        a = np.asarray(Image.open(p).convert('RGB')).astype(int)
        m = (a[..., 0] > 200) & (a[..., 1] < 60) & (a[..., 2] > 200); k = int(m.sum()); rows.append((k, p.stem))
        if k > HOLE_MAX: fails.append(f'{p.stem}: фон сквозь геометрию {k} пикс. ({k / m.size:.2%} кадра)')
    rows.sort(reverse=True)
    notes.append(f'снимков комнат {len(shots)}, пурпурных пикселей всего {sum(k for k, _ in rows)}; больше всех: ' +
                 ', '.join(f'{s} {k}' for k, s in rows[:4]) + f' (прогон {d})')
    return fails, notes


def report(title, fails, notes):
    print(f'{title}: ' + ('FAIL: ' + fails[0] if fails else 'PASS'))
    for f in fails[1:]: print('  ещё: ' + f)
    for n in notes: print('  ' + n)
    return 1 if fails else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('what', choices=('cams', 'holes', 'gate'))
    ap.add_argument('pkg', nargs='?', default=str(ROOT / 'build/interiors-l1-gfx.bin'))
    ap.add_argument('--eboot', default=None, help='свой EBOOT (по умолчанию build/EBOOT.PBP)')
    a = ap.parse_args()
    if a.what == 'cams': return report('камеры оригинала сквозь мебель', *cams(a.pkg))
    if a.what == 'holes': return report('дыры фона в комнатах', *holes(a.pkg, a.eboot, 'pkg'))
    old = OUT / 'old'; old.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, SHR_ROOM_CAMSIDE='0', SHR_ROOM_CEIL='0', SHR_TMP=str(OUT / 'tmp'))
    r = subprocess.run([sys.executable, str(ROOT / 'tools/interior_export.py'), '--outdir', str(old)], env=env, capture_output=True, text=True)
    if r.returncode: print('FAIL: экспорт по прежним правилам:', r.stderr[-400:]); return 1
    print('красный — пакет по прежним правилам (SHR_ROOM_CAMSIDE=0 SHR_ROOM_CEIL=0):')
    r1 = report(' камеры оригинала сквозь мебель', *cams(old / 'interiors-l1-gfx.bin'))
    r2 = report(' дыры фона в комнатах', *holes(old / 'interiors-l1-gfx.bin', a.eboot, 'old'))
    print('зелёный —', a.pkg + ':')
    g1 = report(' камеры оригинала сквозь мебель', *cams(a.pkg))
    g2 = report(' дыры фона в комнатах', *holes(a.pkg, a.eboot, 'new'))
    ok = r1 and r2 and not g1 and not g2
    print('PASS (красный пойман обеими проверками, зелёный прошёл)' if ok else 'FAIL')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
