#!/usr/bin/env python3
"""Правка Роба 331 (04.10: «камера врезается по краям экрана, входит в текстуры — внутрь машин, домов, людей; после удара с трамплина
уходит под асфальт; камера никогда не заходит за текстуры»). Безоконный PPSSPP без звука (scen.py), два сценария:
tests/camera/camin_car.txt (вдоль стен, разворот у стены, удар, трафик и прохожие вплотную, трамплины, машина разбита на посадке) и
tests/camera/camin_foot.txt (спиной к фасадам с обходом камеры по кругу, узкие проходы, у машины и у прохожего).
Замер движка (viewer/camsafe.c csProbe, строка CAMIN на сцену): кадры камеры игры, где глаз за препятствием от опоры камеры, ближняя
плоскость режет мир (глаз -> углы и середины сторон, стороны прямоугольника), глаз или угол ниже опоры коллизии, глаз/ближняя
плоскость в кузове машины или в человеке. Камеры из данных (комнаты, зоны, наезды, разговор, будка) — не в счёт.
КРАСНЫЙ: тот же сценарий с «flag camsafeold 1» (прежняя камера) — кадры «внутри» хотя бы в MIN_RED сценах.
ЗЕЛЁНЫЙ: в каждой сцене кадров >= MIN_FRAMES и «внутри» 0. Без рывков: кадров со скачком глаза относительно опоры > 0,5 м — не больше,
чем у красного × 1,25 + JUMP_TOL на набор (перелёт CS_GLIDE — шаги до 0,83 м), сумма наибольших скачков сцен — не больше красной + 1 м, и самый большой скачок сцены (кроме сцен с длинными кадрами) не больше красного + 0,5 м (или 1,5 м). Цена: work p95 сцен (STAT, без
сцен с подброшенными длинными кадрами) зелёного не больше красного на FPS_TOL.
    python3 tests/camera/camin.py [EBOOT] [--only car|foot] [--parse]  -> 0 = PASS (--parse — только разбор прогонов CAMIN_TAG)
Переменные: SCEN_HOME (свой HOME эмулятора), CAMIN_TAG (приставка имён прогонов, по умолчанию camin)."""
import os, re, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
SCEN = Path.home() / '.claude/skills/shar-level-polish/scripts/scen.py'
OUT = Path(os.environ.get('SCEN_ROOT', '/Users/USER/Downloads/shar-psp')) / 'build/twins/scen/full'
MIN_RED, MIN_FRAMES, FPS_TOL, JUMP_TOL = 4, 60, 1.15, 3
SETS = ('car', 'foot')


def start(name, eboot, scen, old):
    txt = (['flag camsafeold 1'] if old else []) + (['flag camhighold 1'] if os.environ.get('CAMIN_HEIGHT_OLD') else []) + scen.read_text().splitlines()
    f = tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False); f.write('\n'.join(txt) + '\n'); f.close()
    env = dict(os.environ, SCEN_EBOOT=str(eboot))
    if os.environ.get('SCEN_HOME'): env['SCEN_HOME'] = os.environ['SCEN_HOME'] + '/' + name
    return subprocess.Popen([sys.executable, str(SCEN), name, f.name], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def parse(name):
    p = OUT / name / 'smoke.txt'
    if not p.exists(): return {}, {}
    scene, cam, stat = None, {}, {}
    for l in p.read_text(errors='replace').splitlines():
        if l.startswith('SCENE '): scene = l.split()[1]
        elif l.startswith('CAMIN t=') and scene: cam[scene] = dict(kv.split('=', 1) for kv in l.split()[1:] if '=' in kv)
        elif l.startswith('STAT ') and l.split()[1] != 'start':
            m = re.search(r'frames (\d+) p95 ([\d.]+)', l)
            if m: stat[l.split()[1]] = float(m.group(2))
    return cam, stat


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    only = sys.argv[sys.argv.index('--only') + 1] if '--only' in sys.argv else None
    if only: args = [a for a in args if a != only]
    eb = Path(args[0] if args else ROOT / 'viewer/build/EBOOT.PBP').resolve()
    tag = os.environ.get('CAMIN_TAG', 'camin')
    sets = [s for s in SETS if not only or s == only]
    fails, notes, red_scenes, red_frames, p95r, p95g = [], [], 0, 0, [], []
    for s in sets:
        scen = ROOT / f'tests/camera/camin_{s}.txt'
        if '--parse' not in sys.argv:   # --parse: только разбор уже снятых прогонов (CAMIN_TAG)
            for old, name in ((True, f'{tag}_{s}_red'), (False, f'{tag}_{s}_green')):
                start(name, eb, scen, old).wait(timeout=1500)
        (cr, sr), (cg, sg) = parse(f'{tag}_{s}_red'), parse(f'{tag}_{s}_green')
        want = [l.split()[1] for l in scen.read_text().splitlines() if l.startswith('scene ')]
        for sc in want:
            r, g = cr.get(sc), cg.get(sc)
            if not g: fails.append(f'{s}/{sc}: нет строки CAMIN зелёного (сценарий не дошёл)'); continue
            fr, ag = int(g['frames']), int(g['any'])
            ar = int(r['any']) if r else -1
            if r and ar > 0: red_scenes += 1; red_frames += ar
            notes.append(f'{s}/{sc}: красный {ar}/{r["frames"] if r else "?"} внутри (стена {r.get("eye") if r else "?"}, край кадра {r.get("near") if r else "?"}, '
                         f'земля {r.get("ground") if r else "?"}, машина {r.get("car") if r else "?"}, человек {r.get("person") if r else "?"}) -> '
                         f'зелёный {ag}/{fr}, ближняя мин {g["nearmin"]}, правило {g.get("us", "?")} мкс/кадр (макс {g.get("usmax", "?")})')
            if fr < MIN_FRAMES: fails.append(f'{s}/{sc}: мало кадров ({fr})')
            if ag: fails.append(f'{s}/{sc}: камера внутри в {ag} кадрах из {fr} ({g})')
            if sc in sr and sc in sg and sr[sc] < 40.: p95r.append(sr[sc]); p95g.append(sg[sc])   # 40 мс+ — сцена с длинными кадрами
            if r and 'jmax' in g and 'jmax' in r and sr.get(sc, 0.) < 40.:   # сцены с длинными кадрами недетерминированы по времени — только сумма
                jr, jg = float(r['jmax']), float(g['jmax'])
                if jg > max(jr + .5, 1.5): fails.append(f'{s}/{sc}: рывок глаза {jg:.2f} м за кадр (красный {jr:.2f})')
    for s in sets:
        (cr, sr), (cg, _) = parse(f'{tag}_{s}_red'), parse(f'{tag}_{s}_green')
        det = [k for k in cr if k in cg and sr.get(k, 0.) < 40.]   # без сцен с длинными кадрами (время в них плавает от прогона к прогону)
        jr = sum(int(cr[k].get('jump', 0)) for k in det); jg = sum(int(cg[k].get('jump', 0)) for k in det)
        mr = sum(float(cr[k].get('jmax', 0)) for k in det); mg = sum(float(cg[k].get('jmax', 0)) for k in det)
        notes.append(f'{s}: кадров со скачком глаза > 0,5 м — красный {jr}, зелёный {jg}; сумма наибольших скачков сцен — {mr:.1f} / {mg:.1f} м')
        if jg > jr * 1.25 + JUMP_TOL: fails.append(f'{s}: рывков больше прежнего ({jg} против {jr})')
        if mg > mr + 1.: fails.append(f'{s}: скачки глаза крупнее прежних ({mg:.1f} м против {mr:.1f})')
    if red_scenes < MIN_RED: fails.append(f'красный контроль: «внутри» только в {red_scenes} сценах (нужно >= {MIN_RED}) — сценарий не ловит')
    if p95r and sum(p95g) > sum(p95r) * FPS_TOL:
        fails.append(f'цена: work p95 зелёного {sum(p95g) / len(p95g):.2f} мс против {sum(p95r) / len(p95r):.2f} у красного (> x{FPS_TOL})')
    cost = f'work p95 сцен: красный {sum(p95r) / len(p95r):.2f} мс, зелёный {sum(p95g) / len(p95g):.2f} мс' if p95r else 'work p95: нет STAT'
    print('FAIL: ' + fails[0] if fails else f'PASS: камера игры ни разу не внутри (красный: {red_frames} кадров в {red_scenes} сценах); {cost}')
    for f in fails[1:]: print('  ещё: ' + f)
    if not fails: pass
    else: print('  ' + cost)
    for n in notes: print('  ' + n)
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
