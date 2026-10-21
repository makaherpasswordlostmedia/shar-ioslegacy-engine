#!/usr/bin/env python3
"""Очередь сверки с оригиналом (план Роба: «спорное место сверять с оригиналом — PS2-эмулятор в ту же точку: выбрасывает ли, пускает ли;
так же для взаимодействий. Это путь чести»). Места — из реестра регистратора (build/polygon/L<N>/registry.tsv).

  python3 tools/polygon/twinq.py plan --level N [--max 40]       -> OUT/twinq.tsv: на место — действие, команда порта, команда близнеца
  python3 tools/polygon/twinq.py run  --level N [--budget-min 60] [--limit 12]
        по одному, nice 15: порт — tools/bots/inspector --one (тот же код мира, CPU) + кадр EBOOT (tools/twins/port.py run_full, только L1);
        оригинал — скрытый PCSX2 (tools/twins/jump.py машиной, walk.py пешком / с действием; маршрут по дорогам — пока только L1);
        вердикт и кадры рядом -> OUT/twinq.tsv, OUT/twin/<место>/пара.png; регистратор берёт вердикт в итог
  python3 tools/polygon/twinq.py pair PORT.png ORIG.png OUT.png  кадры рядом: порт 480×272 1:1, оригинал 4:3 по высоте 272, NEAREST

Действия: car — машину в точку, газ 2.5 с (порт: 8 заходов инспектора; PS2: подъезд на 15 км/ч курсом h и 4 с дальше);
foot — Гомер пешком в точку и на 6 м дальше (порт: 8 сторон бегом и прыжками); interact — к гэгу/двери и △.
Оси: близнец пишет в осях игры (z = −z движка), курс игры = 180° − курс движка (tools/twins/common.py port_h_of_yaw — сверить на Маке).
Вердикты (VERDICTS): совпало / оригинал не пускает / у порта застревание, у оригинала нет / взаимодействие отличается / разная опора /
не сверено (нет данных одной стороны, уровень без маршрута близнеца). «совпало» в итог не идёт."""
import argparse, json, math, os, shutil, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent)); sys.path.insert(0, str(ROOT / 'tools/bots'))
import registry as REG

VERDICTS = ('совпало', 'оригинал не пускает', 'у порта застревание, у оригинала нет', 'взаимодействие отличается', 'разная опора', 'не сверено')
ACTION = {'stuck_car': 'car', 'invisible_wall': 'car', 'hole_visible': 'car', 'hole_phantom': 'car', 'death': 'car',
          'stuck_foot': 'foot', 'cam_inside': 'foot', 'interact_fail': 'interact', 'through_wall': 'car', 'fall': 'car'}
TWIN_LEVELS = (1,)   # маршрут близнеца по дорогам (tools/twins/route.py) — уровень 1
PASS_M = 3.0         # м: проехал/прошёл дальше точки — «пускает»
HEAD = '# место\tтип\tдействие\tx\ty\tz\tкурс\tпорт\tоригинал\tвердикт\tкадры\n'


def out_dir(level): return ROOT / f'build/polygon/L{level}'


def slug(pid): return pid.replace(' ', '_').replace('/', '_')


def orig_axes(x, z, h): return x, -z, (180.0 - math.degrees(h)) % 360.0


def commands(level, pid, typ, x, y, z, h, foot=False):
    """-> (действие, команда порта, команда оригинала или '-')"""
    act = ACTION.get(typ, '-')
    if typ == 'through_wall' and foot: act = 'foot'
    if act == '-': return '-', '-', '-'
    lv, pl = (ROOT / 'build/level.shr', ROOT / 'build/homer.shr') if level == 1 else (ROOT / f'build/levels/l{level}/level.shr', ROOT / f'build/levels/l{level}/player.shr')
    d = f'build/polygon/L{level}/twin/{slug(pid)}'
    modes = {'car': 'car', 'foot': 'foot,jump', 'interact': 'foot'}[act]
    port = (f'build/bots/inspector {lv.relative_to(ROOT)} {pl.relative_to(ROOT)} --one {x:.2f} {y:.2f} {z:.2f} {h:.4f} --modes {modes}'
            + (' --interact' if act == 'interact' else '') + f' --out {d}/port')
    if level not in TWIN_LEVELS: return act, port, '-'
    ox, oz, oh = orig_axes(x, z, h); tag = f'poly_{slug(pid)}'
    if act == 'car': orig = f'python3 tools/twins/jump.py --start {ox:.2f} {y:.2f} {oz:.2f} --heading {oh:.1f} --kmh 15 --runup 60 --out {tag}'
    elif act == 'foot':
        fx, fz = ox + 6 * math.sin(math.radians(oh)), oz + 6 * math.cos(math.radians(oh))
        orig = f'python3 tools/twins/walk.py --to {ox:.2f} {oz:.2f} {fx:.2f} {fz:.2f} --after 300 --out {tag}'
    else: orig = f'python3 tools/twins/walk.py --to {ox:.2f} {oz:.2f} --act triangle --after 300 --out {tag}'
    return act, port, orig


# ------------------------------------------------------------------ вердикт (чистая функция: тесты)
def verdict(typ, port, orig):
    """port, orig — dict(ok=пускает/сработало: True/False/None, dy=перепад высоты от точки, м или None).
    ok у порта для места-события известен заранее (застрял — False, прошёл сквозь — True), повтор --one его подтверждает"""
    po, oo = (port or {}).get('ok'), (orig or {}).get('ok')
    if po is None or oo is None: return 'не сверено'
    if typ in ('hole_visible', 'hole_phantom', 'fall'):
        pd, od = (port or {}).get('dy'), (orig or {}).get('dy')
        if pd is not None and od is not None and abs(pd - od) > 1.5: return 'разная опора'
    if ACTION.get(typ) == 'interact': return 'совпало' if po == oo else 'взаимодействие отличается'
    if po == oo: return 'совпало'
    if po and not oo: return 'оригинал не пускает'
    return 'у порта застревание, у оригинала нет'


def port_result(d, act):
    """итог inspector --one: заперт (events.tsv: car_trapped / foot_trapped / interact_fail) -> ok False; провал -> dy"""
    E = REG._tsv(Path(d) / 'events.tsv')
    if not (Path(d) / 'done.txt').exists(): return None
    kinds = {f[0] for f in E}
    bad = {'car': {'car_trapped'}, 'foot': {'foot_trapped', 'foot_trapped_jump'}, 'interact': {'interact_fail'}}[act]
    r = dict(ok=not (kinds & bad), dy=None)
    if 'fall' in kinds: r['dy'] = -99.0
    return r


def orig_result(d, act, ox, oy, oz):
    """итог близнеца: jump.tsv (машина: после старта уехала дальше PASS_M) или walk.tsv (дошёл до точки ближе 1.6 м и дальше)"""
    d = Path(d)
    if act == 'car':
        rows = REG._tsv(d / 'jump.tsv')[1:] if (d / 'jump.tsv').exists() else []
        pts = []
        for f in rows:
            try: pts.append((float(f[1]), float(f[2]), float(f[3])))
            except (ValueError, IndexError): pass
        if not pts: return None
        i0 = min(range(len(pts)), key=lambda k: math.hypot(pts[k][0] - ox, pts[k][2] - oz))
        if math.hypot(pts[i0][0] - ox, pts[i0][2] - oz) > 6: return dict(ok=False, dy=None)   # не доехал до точки
        far = max(math.hypot(p[0] - ox, p[2] - oz) for p in pts[i0:])
        return dict(ok=far > PASS_M, dy=pts[-1][1] - oy)
    rows = REG._tsv(d / 'walk.tsv')[1:] if (d / 'walk.tsv').exists() else []
    ds = []
    for f in rows:
        try: ds.append(math.hypot(float(f[1]) - ox, float(f[2]) - oz))
        except (ValueError, IndexError): pass
    if not ds: return None
    reach = min(ds) < 1.6
    if act == 'interact': return dict(ok=reach, dy=None)   # TODO близнец: признак «гэг заиграл» в памяти PS2 (адрес не найден) — пока «дошёл и нажал»
    return dict(ok=reach and ds[-1] > PASS_M, dy=None)


# ------------------------------------------------------------------ кадры рядом
def pair(port_png, orig_png, out, title=''):
    """порт 480×272 1:1 (512×272 буфера -> левые 480), оригинал: 16:9 запись -> середина 4:3 (crop 960:720:160:0 у 1280×720),
    дальше по высоте 272 NEAREST; между — 8 px, сверху строка подписи 18 px"""
    from PIL import Image, ImageDraw
    P = Image.open(port_png).convert('RGB')
    if P.size == (512, 272): P = P.crop((0, 0, 480, 272))
    if P.size != (480, 272): P = P.resize((480, 272), Image.NEAREST)
    O = Image.open(orig_png).convert('RGB'); w, h = O.size
    if abs(w / h - 16 / 9) < .05:   # запись 16:9 с картинкой 4:3 по центру
        cw = round(h * 4 / 3); x0 = (w - cw) // 2; O = O.crop((x0, 0, x0 + cw, h)); w = cw
    O = O.resize((max(1, round(w * 272 / h)), 272), Image.NEAREST)
    im = Image.new('RGB', (480 + 8 + O.size[0], 272 + 18), (20, 20, 20)); im.paste(P, (0, 18)); im.paste(O, (488, 18))
    ImageDraw.Draw(im).text((4, 3), (title + '   ' if title else '') + 'порт PSP 480×272 | оригинал PS2', fill=(235, 235, 235))
    Path(out).parent.mkdir(parents=True, exist_ok=True); im.save(out)
    return im.size


# ------------------------------------------------------------------ очередь
def load_q(level):
    rows = {}
    for f in REG._tsv(out_dir(level) / 'twinq.tsv'):
        if len(f) >= 11: rows[f[0]] = f
    return rows


def save_q(level, rows):
    p = out_dir(level) / 'twinq.tsv'; p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(HEAD + ''.join('\t'.join(r) + '\n' for r in sorted(rows.values(), key=lambda r: (REG.rank(r[1]), r[0]))))


def plan(a):
    P = REG.load(out_dir(a.level) / 'registry.tsv'); Q = load_q(a.level); n = 0
    for p in sorted(P, key=lambda p: (REG.rank(p['main']), -p['n'], p['id'])):
        if p['id'] in Q or n >= a.max: continue
        foot = p['main'] in ('stuck_foot',) or 'stuck_foot' in p['types']
        act, pc, oc = commands(a.level, p['id'], p['main'], p['x'], p['y'], p['z'], 0.0, foot)
        if act == '-': continue
        Q[p['id']] = [p['id'], p['main'], act, f'{p["x"]:.2f}', f'{p["y"]:.2f}', f'{p["z"]:.2f}', '0', pc, oc, '-', '-']; n += 1
    save_q(a.level, Q)
    print(f'очередь L{a.level}: добавлено {n}, всего {len(Q)} -> {out_dir(a.level) / "twinq.tsv"}')


def sh(cmd, log, timeout):
    with open(log, 'a') as f:
        f.write(f'$ {cmd}\n'); f.flush()
        try: return subprocess.run(['nice', '-n', '15', 'bash', '-c', cmd], cwd=ROOT, stdout=f, stderr=f, stdin=subprocess.DEVNULL, timeout=timeout).returncode
        except subprocess.TimeoutExpired: f.write('таймаут\n'); return 124


def port_frame(level, pid, x, z, h, d):
    """кадр EBOOT в точке (своя PPSSPPHeadless, программная отрисовка 480×272) — только L1 (сцена twins); нет эмулятора — без кадра"""
    if level != 1: return None
    try:
        sys.path.insert(0, str(ROOT / 'tools/twins')); import port as PT
        pk, _ = PT.run_full(slug(pid), d, 2.5, place=(x, 0, z, h))
        shots = sorted(Path(pk).glob('*.png'))
        return shots[-1] if shots else None
    except Exception as e:
        (d / 'port_frame.txt').write_text(f'кадр порта не снят: {e}\n'); return None


def run(a):
    Q = load_q(a.level); t0 = time.time(); done = 0
    for pid, r in sorted(Q.items(), key=lambda kv: (REG.rank(kv[1][1]), kv[0])):
        if r[9] != '-' or done >= a.limit or (time.time() - t0) / 60 > a.budget_min: continue
        if (ROOT / 'build/polygon/STOP').exists(): break
        d = out_dir(a.level) / 'twin' / slug(pid); (d / 'port').mkdir(parents=True, exist_ok=True); log = d / 'run.log'
        typ, act, x, y, z, h = r[1], r[2], float(r[3]), float(r[4]), float(r[5]), float(r[6])
        sh(r[7], log, 600); pr = port_result(d / 'port', act)
        if typ == 'through_wall' and pr: pr['ok'] = True   # место-событие: порт прошёл сквозь стену (повтор --one не ловит след)
        orr = None; ofr = None
        if r[8] != '-':
            sh(r[8], log, 1800)
            od = ROOT / 'build/twins/o4' / r[8].rsplit('--out ', 1)[1].split()[0]
            ox, oz, _ = orig_axes(x, z, h); orr = orig_result(od, act, ox, y, oz)
            pngs = sorted((od / 'png').glob('*.png')); ofr = pngs[len(pngs) // 2] if pngs else None
        v = verdict(typ, pr, orr); pf = port_frame(a.level, pid, x, z, h, d)
        img = '-'
        if pf and ofr:
            pair(pf, ofr, d / 'пара.png', pid); img = str((d / 'пара.png').relative_to(ROOT))
        (d / 'result.json').write_text(json.dumps(dict(port=pr, orig=orr, verdict=v), ensure_ascii=False))
        r[9], r[10] = v, img; save_q(a.level, Q); done += 1
        print(f'{pid}: {v}')
    print(f'сверено {done} мест за {(time.time() - t0) / 60:.0f} мин')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    p = sp.add_parser('plan'); p.add_argument('--level', type=int, required=True); p.add_argument('--max', type=int, default=40)
    r = sp.add_parser('run'); r.add_argument('--level', type=int, required=True); r.add_argument('--budget-min', type=float, default=60); r.add_argument('--limit', type=int, default=12)
    q = sp.add_parser('pair'); q.add_argument('port'); q.add_argument('orig'); q.add_argument('out')
    a = ap.parse_args()
    if a.cmd == 'plan': plan(a)
    elif a.cmd == 'run': run(a)
    else: print(pair(a.port, a.orig, a.out))


if __name__ == '__main__':
    main()
