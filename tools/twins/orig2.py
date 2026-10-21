#!/usr/bin/env python3
"""Близнецы · О4: оригинал с вводом из файла — свой PCSX2 v2.6.3 без окна (tools/twins/pcsx2_build.sh → pcsx2-twins).

  python3 tools/twins/orig2.py run RECIPE.json [--keep]      → build/twins/o4/<id>/: trace.tsv, shot_<кадр>.png, snap_<кадр>.p2s, report.json
  python3 tools/twins/orig2.py check RECIPE.json             только проверка рецепта (имена, запись, кадры), без запуска
Рецепт (JSON): {"id", "state": "build/ps2ref/….p2s", "frames": N (кадры = vsync 50/с от загрузки состояния),
  "trace": ["mat", "car_vel[0]", …] (имена tools/ps2ref/addrs.tsv), "every": шаг строк,
  "pad": [[кадр, "кнопка", 0..1], …]  кнопки: up right down left triangle circle cross square select start l1 l2 r1 r2 l3 r3
         lup lright ldown lleft rup rright rdown rleft (стики — полуоси 0..1); значение держится до следующей строки той же кнопки,
  "writes": [{"at": кадр, "name": "car_cm[0]", "value": v}]  — только адреса со словом «можно» в addrs.tsv и тело машины (car_cm, car_vel),
  "shots": [кадры] — сохранение состояния (в нём Screenshot.png), "pngs": [[от, до, шаг]] — кадры экрана, "wav": кадр — звук с этого кадра}
Всё по номеру кадра: без гонок PINE, повторяемо байт в байт. Окна нет, значка в Доке нет, фокус не берётся (setActivationPolicy:
Prohibited в pcsx2-twins); сторож всё равно следит: свой PID впереди или его окно на экране → остановить и FAIL.
Данные эмулятора — своя папка build/twins/pcsx2/bin/data (portable.txt), BIOS — копия из observer1 (диск и BIOS Роба)."""
import argparse, hashlib, json, os, re, shutil, subprocess, sys, time, zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C
sys.path.insert(0, str(C.WT / 'tools/ps2ref'))
import ask   # noqa: E402

P = C.DATA / os.environ.get('PCSX2_DIR', 'build/twins/pcsx2')   # свой экземпляр стенда: PCSX2_DIR=build/twins/pcsx2_s3
O4 = os.environ.get('O4_DIR') or os.environ.get('O4_NAME') or 'o4'   # свой каталог выхода у каждого стенда (Стенд3: O4_DIR, Стенд2: O4_NAME)
BIN = P / 'bin/pcsx2-twins'
ISO = Path(os.environ['ISO_PATH']) if os.environ.get('ISO_PATH') else C.DATA / 'game/Hit and Run.iso'
BIOS_SRC = C.DATA / 'build/ps2ref/profiles/observer1/data/bios'
BINDS = set('up right down left triangle circle cross square select start l1 l2 r1 r2 l3 r3 lup lright ldown lleft rup rright rdown rleft'.split())
TYPE = {'f32': 'f32', 'u32': 'u32', 's32': 's32', 'u16': 'u16', 'u8': 'u8'}


class Fail(Exception):
    pass


def prepare():
    if not BIN.exists(): raise Fail('нет pcsx2-twins: tools/twins/pcsx2_build.sh deps && tools/twins/pcsx2_build.sh core')
    d = P / 'bin/data'; (d / 'bios').mkdir(parents=True, exist_ok=True)
    (P / 'bin/portable.txt').write_text('data\n')
    pz = P / 'bin/resources/patches.zip'   # встроенные правки игр (GameDB) — как у официального PCSX2 наблюдателя
    if not pz.exists():
        app = next(Path('/Applications').glob('PCSX2*.app'), None)
        if app and (app / 'Contents/Resources/patches.zip').exists(): shutil.copy2(app / 'Contents/Resources/patches.zip', pz)
    for lib in ('default', 'Metal22', 'Metal23'):   # шейдеры Metal той же версии 2.6.3 (без бандла ядро ищет их в resources)
        m = P / f'bin/resources/{lib}.metallib'
        app = next(Path('/Applications').glob('PCSX2*.app'), None)
        if not m.exists() and app and (app / f'Contents/Resources/{lib}.metallib').exists(): shutil.copy2(app / f'Contents/Resources/{lib}.metallib', m)
    for f in BIOS_SRC.glob('scph10000.*'):
        if not (d / 'bios' / f.name).exists(): shutil.copy2(f, d / 'bios' / f.name)
    return d


def script(r, run):
    ask.ADDRS = C.WT / 'tools/ps2ref/addrs.tsv'
    addrs = ask.load_addrs(ask.ADDRS); can = ask.writable(ask.ADDRS) | ask.BODY
    L = []
    cols = []
    for name in r.get('trace', []):
        if isinstance(name, dict):   # стенд: адрес напрямую {addr,type,label}
            cols.append((name['label'], int(name['addr'], 16), name['type'])); continue
        for col, addr, typ in ask.resolve(name, addrs): cols.append((col, addr, typ))
    if cols:
        L.append(f"0 trace {run / 'trace.raw'} {int(r.get('every', 1))} " + ' '.join(f'{a:x}:{TYPE[t]}' for _, a, t in cols))
    for f, b, v in r.get('pad', []):
        if b not in BINDS: raise Fail(f'рецепт: кнопка {b!r} не из {sorted(BINDS)}')
        if not 0 <= float(v) <= 1: raise Fail(f'рецепт: кнопка {b}: значение {v} не 0..1')
        L.append(f'{int(f)} pad {b} {float(v):g}')
    for w in r.get('writes', []):
        base = re.match(r'[a-z0-9_]+', w['name']).group(0)
        if base not in can: raise Fail(f'рецепт: запись в {w["name"]}: адрес не помечен «можно» в addrs.tsv (правило после сбоя 30.09)')
        (col, addr, typ), = ask.resolve(w['name'], addrs)
        L.append(f"{int(w['at'])} {TYPE[typ] if typ != 's32' else 'u32'} {addr:x} {w['value']}")
    for at, addr, val in r.get('rawwrites', []):   # стенд: правка ОЗУ эталона для съёмки (не из addrs.tsv); только u32, только в клоне состояния
        L.append(f"{int(at)} u32 {int(addr, 16):x} {int(val)}")
    for k in r.get('shots', []): L.append(f"{int(k)} save {run / f'snap_{int(k)}.p2s'}")
    for a, b, st in r.get('pngs', []):   # последовательность кадров экрана: [от, до, шаг] → png/f<кадр>.png
        (run / 'png').mkdir(exist_ok=True)
        for k in range(int(a), int(b) + 1, int(st)): L.append(f"{k} png {run / 'png' / f'f{k:05d}.png'}")
    if r.get('wav') is not None: L.append(f"{int(r['wav'])} wav {run / 'audio.wav'}")
    L.append(f"{int(r['frames'])} end")
    (run / 'script.txt').write_text('\n'.join(L) + '\n')
    return cols


def front_pid():
    a = subprocess.run(['lsappinfo', 'front'], capture_output=True, text=True).stdout.strip()
    m = re.search(r'=(\d+)', subprocess.run(['lsappinfo', 'info', '-only', 'pid', a], capture_output=True, text=True).stdout)
    return int(m.group(1)) if m else None


def run(recipe_path, keep=False):
    r = json.loads(Path(recipe_path).read_text())
    st = C.DATA / r['state'] if r.get('state') else None   # без состояния — загрузка с BIOS и диска (меню, заставки)
    if st and r.get('state_sha256') and C.sha256(st) != r['state_sha256']: raise Fail('рецепт: чужое состояние (sha256 не совпало)')
    prepare()
    out = C.OUT / O4 / r['id']
    if out.exists(): shutil.rmtree(out)
    out.mkdir(parents=True)
    cols = script(r, out)
    t0 = time.time(); bad = []
    with (out / 'log.txt').open('w') as log:
        pr = subprocess.Popen(['nice', '-n', '10', str(BIN)] + (['-statefile', str(st)] if st else []) + ['-script', str(out / 'script.txt'),
                               '-bios', 'scph10000.bin', '-renderer', r.get('renderer', 'sw'), '-swthreads', '2',
                               '-set', 'SPU2/Output/Backend=Null',   # без звука (Роб 03.10); WAV пишет крючок spu2Output мимо вывода
                               '--', str(ISO)], cwd=str(out), stdout=log, stderr=subprocess.STDOUT,
                              env=dict(os.environ, PCSX2_NOCONSOLE='1'))
        wins = C.DATA / 'build/ps2ref/bin/wins'; k = 0
        limit = float(r.get('timeout', 600))
        while pr.poll() is None:
            if front_pid() == pr.pid: bad.append('впереди')
            elif k % 10 == 0 and wins.exists() and any(l.startswith('1 ') for l in subprocess.run([str(wins), str(pr.pid)], capture_output=True, text=True).stdout.splitlines()):
                bad.append('окно на экране')
            if time.time() - t0 > limit: bad.append('не уложился во время')
            if bad: pr.kill(); pr.wait(); break
            k += 1; time.sleep(0.2)
    wall = time.time() - t0
    log = (out / 'log.txt').read_text(errors='replace')
    ended = re.search(r'^TWINS (\d+) end', log, re.M)
    rows = 0
    if (out / 'trace.raw').exists():
        raw = (out / 'trace.raw').read_text().splitlines()
        head = ['rel'] + [c for c, _, _ in cols]
        (out / 'trace.tsv').write_text('\t'.join(head) + '\n' + ''.join(l + '\n' for l in raw[1:]))
        rows = len(raw) - 1
    shots = []
    for k in r.get('shots', []):
        f = out / f'snap_{int(k)}.p2s'
        if f.exists():
            try:
                with zipfile.ZipFile(f) as z: (out / f'shot_{int(k)}.png').write_bytes(z.read('Screenshot.png'))
                shots.append(int(k))
            except (zipfile.BadZipFile, KeyError) as e: bad.append(f'снимок {k}: {e}')
            if not keep and k != max(r.get('shots', [0])): pass
    rep = dict(id=r['id'], ok=bool(ended) and not bad, error=', '.join(bad) or (None if ended else 'нет строки TWINS end — см. log.txt'),
               recipe=str(Path(recipe_path)), recipe_sha256=C.sha256(recipe_path), state=r.get('state'), state_sha256=C.sha256(st) if st else None,
               binary_sha256=C.sha256(BIN, 16), frames=int(r['frames']), rows=rows, shots=shots, wall_s=round(wall, 1),
               fps=round(int(r['frames']) / wall, 1) if wall else None, focus_violations=bad, time=C.clock())
    (out / 'report.json').write_text(json.dumps(rep, ensure_ascii=False, indent=1) + '\n')
    print(f"{'PASS' if rep['ok'] else 'FAIL'} {r['id']}: кадров {r['frames']}, строк {rows}, снимков {len(shots)}, {wall:.0f} с "
          f"({rep['fps']} к/с){'; ' + rep['error'] if rep['error'] else ''} → {out.relative_to(C.DATA)}")
    return rep


def gate(recipe_path, n=20):
    """гейт О4 (ОРАКУЛ §3): n прогонов одного рецепта с вводом — трассы байт в байт; тот же рецепт без ввода (испорченный ввод) —
    трасса другая. PASS только если оба условия."""
    r = json.loads(Path(recipe_path).read_text()); base = r['id']; tmp = C.OUT / O4 / '_gate'; tmp.mkdir(parents=True, exist_ok=True)
    hs = []
    for i in range(n):
        q = dict(r, id=f'{base}_g{i:02d}'); f = tmp / f'{q["id"]}.json'; f.write_text(json.dumps(q, ensure_ascii=False))
        rep = run(f)
        if not rep['ok']: print(f'FAIL гейт О4: прогон {i} не дошёл до конца'); return 1
        hs.append(hashlib.sha256((C.OUT / O4 / q['id'] / 'trace.tsv').read_bytes()).hexdigest())
    q = dict(r, id=f'{base}_broken', pad=[]); f = tmp / f'{q["id"]}.json'; f.write_text(json.dumps(q, ensure_ascii=False)); run(f)
    hb = hashlib.sha256((C.OUT / O4 / q['id'] / 'trace.tsv').read_bytes()).hexdigest()
    same = len(set(hs)) == 1; differs = hb != hs[0]
    ok = same and differs
    res = dict(ok=ok, time=C.clock(), runs=n, identical=same, distinct_hashes=len(set(hs)), broken_differs=differs, recipe=str(recipe_path))
    g = C.OUT / 'gates'; g.mkdir(parents=True, exist_ok=True); (g / f'o4_{C.stamp()}.json').write_text(json.dumps(res, ensure_ascii=False, indent=1) + '\n')
    print(('PASS' if ok else 'FAIL'), f'гейт О4: {n} прогонов с вводом — одинаковых трасс {"все" if same else "НЕТ, разных " + str(len(set(hs)))}; '
          f'без ввода — {"другая трасса" if differs else "ТА ЖЕ трасса (ввод не действует)"}')
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['run', 'check', 'gate']); ap.add_argument('--n', type=int, default=20); ap.add_argument('recipe'); ap.add_argument('--keep', action='store_true')
    a = ap.parse_args()
    try:
        if a.cmd == 'check':
            r = json.loads(Path(a.recipe).read_text()); tmp = C.OUT / O4 / '_check'; tmp.mkdir(parents=True, exist_ok=True)
            script(r, tmp); print('OK', (tmp / 'script.txt').read_text().count('\n'), 'строк сценария'); return 0
        if a.cmd == 'gate': return gate(a.recipe, a.n)
        return 0 if run(a.recipe, a.keep)['ok'] else 1
    except (Fail, ask.Fail) as e:
        print('FAIL:', e); return 1


if __name__ == '__main__':
    sys.exit(main())
