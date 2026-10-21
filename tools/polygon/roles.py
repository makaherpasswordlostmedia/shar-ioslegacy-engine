#!/usr/bin/env python3
"""Роли ботов полигона v2 поверх готовых (tools/bots): мир, физика и ввод — тот же C-код, что EBOOT; здесь только раздача работы.

  python3 tools/polygon/roles.py points  --level N --swarm DIR --out FILE    точки инспектора из роя (клетки 6 м: машина по земле и
                                                                             пешком; середина проездов, курс ботов; не чаще 1 на клетку)
  python3 tools/polygon/roles.py inspect --level N --points FILE --out DIR [--procs 6] [--modes car,foot,jump]
        инспектор (tools/bots/inspector) в --procs частях по nice 15 + один проход взаимодействий (гэги, двери); продолжение после
        остановки (--resume у каждой части: файл done.txt)
  python3 tools/polygon/roles.py chase   --level N --out DIR [--procs 2] [--gens 12]
        догоняющий и убегающий: tools/bots/chase (погоня A* по дорогам против беглеца, коэволюция); места — строки X stdout.tsv
        (вечный угол: беглец не пойман; погоня застряла) -> регистратор
Повторяемость: каждая часть пишет args.json (бинарник sha, данные уровня sha, seed/часть, команда)."""
import argparse, hashlib, json, math, os, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/bots'))
import anatomy as A
BIN = Path(os.environ.get('BOTS_BIN', ROOT / 'build/bots'))


def sha(p):
    try: return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16]
    except OSError: return '-'


def points(a):
    """клетки роя (cells.tsv) -> «x y z h»: машина по земле — средняя точка и средний курс ботов; клетки только пешком — тоже (инспектор
    ставит туда машину и выходит; не встала — проба пешком из ближайшей). Порядок — по коду места (части равномерно по городу)"""
    cells = {}
    for r in sorted((Path(a.swarm) / 'runs').glob('s*')): A.read_cells(r / 'cells.tsv', cells)
    best = {}
    for (x, z, y, mode, sup), v in cells.items():
        if sup != 'ground': continue
        k = (x, z, y); n = v[0]
        if k not in best or (mode == 'car' and best[k][4] != 'car') or n > best[k][3]:
            h = v[8] if v[8] == v[8] else 0.0
            best[k] = (v[2] / n, v[3] / n, v[4] / n, n, mode, h)
    rows = sorted(best.values(), key=lambda r: (A.code(r[0], r[2]), r[1]))
    with open(a.out, 'w') as f:
        f.write(f'# точки инспектора L{a.level}: рой {a.swarm}; x y z курс (движок); клеток {len(rows)}\n')
        for x, y, z, n, mode, h in rows: f.write(f'{x:.2f} {y + .3:.2f} {z:.2f} {h:.4f}\n')
    print(f'точек {len(rows)} -> {a.out}')


def level_paths(n):
    A.set_level(n); return A.LVL, A.HOM, A.RDS


def inspect(a):
    lvl, hom, _ = level_paths(a.level); out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    binp = BIN / 'inspector'
    if not binp.exists(): sys.exit(f'нет {binp}: BINS=inspector tools/bots/build.sh')
    if not lvl.exists() or not hom.exists(): print(f'L{a.level}: нет данных уровня {lvl} / {hom}', file=sys.stderr); sys.exit(2)
    jobs = []
    for k in range(a.procs):
        d = out / f'part{k}'; d.mkdir(exist_ok=True)
        cmd = ['nice', '-n', '15', str(binp), str(lvl), str(hom), str(a.points), '--modes', a.modes, '--part', f'{k}/{a.procs}', '--resume', '--out', str(d)]
        if k == 0: cmd.insert(-2, '--interact')
        (d / 'args.json').write_text(json.dumps(dict(cmd=cmd, bin=sha(binp), level=sha(lvl), player=sha(hom), points=sha(a.points)), ensure_ascii=False))
        jobs.append(subprocess.Popen(cmd, stdout=open(d / 'stdout.txt', 'w'), stderr=open(d / 'stderr.txt', 'w'), stdin=subprocess.DEVNULL))
    while any(j.poll() is None for j in jobs):
        if (ROOT / 'build/polygon/STOP').exists():
            for j in jobs: j.terminate()
        time.sleep(5)
    print(f'инспектор L{a.level}: частей {a.procs}, коды выхода {[j.returncode for j in jobs]} -> {out}')


def chase(a):
    lvl, hom, rds = level_paths(a.level); out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    binp = BIN / 'chase'
    if not binp.exists() or not rds.exists(): print(f'L{a.level}: нет {binp} или дорог {rds} — догонялки пропущены', file=sys.stderr); return
    jobs = []
    for k in range(a.procs):
        d = out / f's{a.seed + k}'; d.mkdir(exist_ok=True)
        cmd = ['nice', '-n', '15', str(binp), str(lvl), str(hom), str(rds), '--gens', str(a.gens), '--pop', '16', '--rounds', '4', '--seed', str(a.seed + k), '--out', str(d)]
        (d / 'args.json').write_text(json.dumps(dict(cmd=cmd, bin=sha(binp), level=sha(lvl), roads=sha(rds)), ensure_ascii=False))
        jobs.append(subprocess.Popen(cmd, stdout=open(d / 'stdout.tsv', 'w'), stderr=open(d / 'stderr.txt', 'w'), stdin=subprocess.DEVNULL))
    for j in jobs: j.wait()
    print(f'догонялки L{a.level}: процессов {a.procs} -> {out}')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    p = sp.add_parser('points'); p.add_argument('--swarm', required=True); p.add_argument('--out', required=True)
    i = sp.add_parser('inspect'); i.add_argument('--points', required=True); i.add_argument('--out', required=True)
    i.add_argument('--procs', type=int, default=6); i.add_argument('--modes', default='car,foot,jump')
    c = sp.add_parser('chase'); c.add_argument('--out', required=True); c.add_argument('--procs', type=int, default=2)
    c.add_argument('--gens', type=int, default=12); c.add_argument('--seed', type=int, default=int(time.strftime('%j')) * 100)
    for x in (p, i, c): x.add_argument('--level', type=int, required=True, choices=range(1, 8))
    a = ap.parse_args()
    a.procs = max(1, min(getattr(a, 'procs', 1), 6))   # не больше 6 процессов (Роб: половина–две трети Мака)
    {'points': points, 'inspect': inspect, 'chase': chase}[a.cmd](a)


if __name__ == '__main__':
    main()
