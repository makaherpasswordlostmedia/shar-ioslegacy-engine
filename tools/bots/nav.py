#!/usr/bin/env python3
"""Навигатор на всех ядрах (пункт Б1): tools/bots/nav --table в N процессах с низким приоритетом, сводка «точка -> точка:
лучшее время, путь, повтор» и места, где боты теряют время (застревания, сетка 8 м). Без AI и сети.
  python3 tools/bots/nav.py [--routes 32] [--procs 6] [--gens 60] [--pop 32] [--seed 1]  -> build/bots/runs/nav/<время>/
  python3 tools/bots/nav.py --gate                                                     гейты навигатора (tools/bots/nav --gate)
Повтор маршрута: build/bots/game_headless LEVEL HOMER --input <папка>/rNNN.in (старт машины — в первой строке файла)."""
import argparse, collections, concurrent.futures, hashlib, json, os, subprocess, sys, time
from pathlib import Path
ROOT = Path(os.environ.get('BOTS_ROOT') or Path(__file__).resolve().parents[2])   # ночь запускает замороженную копию скрипта (Т1.1)
IN = Path(os.environ.get('BOTS_IN') or ROOT / 'build')   # входы: общие build/ или замороженный комплект ночи
BIN = Path(os.environ.get('BOTS_BIN', ROOT / 'build/bots'))   # ночь играет своей копией бинарников (дневная пересборка их не трогает)


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16]


def repro_cmd(p):   # команда повтора: старт машины из первой строки файла (--start), дальше ввод (30 кадров стоя + маршрут)
    import re
    try: st = re.search(r'--start ([-0-9.e ]+);', Path(p).read_text().split('\n', 1)[0]).group(1).strip()
    except Exception: st = '?'
    return f'build/bots/game_headless build/level.shr build/homer.shr --input {Path(p).relative_to(ROOT)} --start {st}'


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--routes', type=int, default=32); ap.add_argument('--procs', type=int, default=max(1, (os.cpu_count() or 4) - 4))
    ap.add_argument('--gens', type=int, default=60); ap.add_argument('--pop', type=int, default=32); ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--gate', action='store_true'); ap.add_argument('--out', type=Path)
    a = ap.parse_args()
    if not os.environ.get('BOTS_NO_BUILD'): subprocess.run([str(ROOT / 'tools/bots/build.sh')], check=True, capture_output=True)   # ночь собирает один раз сама
    os.environ['BW_FRAMES'] = '1'
    lvl, hom, rds = IN / 'level.shr', IN / 'homer.shr', IN / 'sandbox/roads-l1.bin'
    stamp = time.strftime('%Y%m%d-%H%M%S'); out = a.out or ROOT / 'build/bots/runs/nav' / (stamp + ('-gate' if a.gate else '')); out.mkdir(parents=True, exist_ok=True)
    binp = BIN / 'nav'
    if a.gate:
        r = subprocess.run([str(binp), str(lvl), str(hom), str(rds), '--gate', '--gens', str(a.gens), '--pop', str(a.pop), '--out', str(out)], capture_output=True, text=True)
        (out / 'gate.txt').write_text(r.stdout); print(r.stdout.strip().splitlines()[-1]); return r.returncode
    def one(k):
        cmd = ['nice', '-n', '10', str(binp), str(lvl), str(hom), str(rds), '--table', str(a.routes), str(k), str(a.procs),
               '--gens', str(a.gens), '--pop', str(a.pop), '--seed', str(a.seed), '--out', str(out)]
        return subprocess.run(cmd, capture_output=True, text=True).stdout
    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(a.procs) as ex:
        outs = list(ex.map(one, range(a.procs)))
    rows = []; frames = 0
    for o in outs:
        for l in o.splitlines():
            f = l.split('\t')
            if f[0] == 'F': frames += int(f[1])
            if f[0] != 'R': continue
            rows.append(dict(tag=f[1], a=[float(f[2]), float(f[3])], b=[float(f[4]), float(f[5]), float(f[6])], straight=float(f[7]), road=float(f[8]),
                             reached=f[9] == 'доехал', base=f[10], best=f[11], replay=f[12], stuck=[[float(v) for v in s.split(',')] for s in f[14:]],
                             repro=repro_cmd(out / (f[1] + '.in'))))
    rows.sort(key=lambda r: r['tag'])
    cells = collections.Counter()
    for r in rows:
        for x, z in r['stuck']: cells[(int(x // 8) * 8 + 4, int(z // 8) * 8 + 4)] += 1
    def secs(s): return float(s.split()[0]) if s.endswith('с') else None
    gains = [(secs(r['base']), secs(r['best'])) for r in rows if secs(r['base']) and secs(r['best'])]
    res = dict(stamp=stamp, levelSha=sha(lvl), roadsSha=sha(rds), binarySha=sha(binp), routes=len(rows), reached=sum(r['reached'] for r in rows),
               replayOk=sum(r['replay'] == 'тот_же_кадр' for r in rows), gens=a.gens, pop=a.pop, seed=a.seed, wallSeconds=round(time.time() - t0, 1), gameMinutes=round(frames / 3600, 1),
               meanGain=round(sum(b - c for b, c in gains) / len(gains), 2) if gains else None,
               lossCells=[dict(x=x, z=z, n=n) for (x, z), n in cells.most_common(20)], rows=rows)
    (out / 'nav.json').write_text(json.dumps(res, ensure_ascii=False, indent=1))
    L = [f'# Навигатор {stamp}', '', f'Маршрутов {len(rows)}, доехал {res["reached"]}, повтор в тот же кадр {res["replayOk"]}; эволюция {a.gens} поколений × {a.pop}; '
         f'выигрыш эволюции в среднем {res["meanGain"]} с; {res["wallSeconds"] / 60:.1f} мин на {a.procs} процессах. Уровень {res["levelSha"]}', '',
         '| маршрут | A | B | прямая, м | по дорогам, м | итог | по умолчанию | лучший | повтор |', '|---|---|---|---|---|---|---|---|---|'] + [
         f"| {r['tag']} | {r['a'][0]:.0f} {r['a'][1]:.0f} | {r['b'][0]:.0f} {r['b'][2]:.0f} | {r['straight']:.0f} | {r['road']:.0f} | {'доехал' if r['reached'] else 'НЕДОСТИЖИМО'} | {r['base']} | {r['best']} | `{r['tag']}.in` |"
         for r in rows] + ['', '## Где боты теряют время (застревания, клетка 8 м)', ''] + [f"- ({c['x']}, {c['z']}): {c['n']}" for c in res['lossCells']]
    (out / 'nav.md').write_text('\n'.join(L) + '\n')
    print('\n'.join(L[:3])); print('->', out / 'nav.md')
    return 0


if __name__ == '__main__':
    sys.exit(main())
