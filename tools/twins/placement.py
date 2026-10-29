#!/usr/bin/env python3
"""Близнецы · набор «постановка машины» (слово Роба 04.10: «постоянно сверяться с оригиналом PS2 … где какие поведения, откуда
выталкивает, когда ставишь машину, — чтобы мне не говорить про каждый двор каждого дома, можно туда заехать или нельзя»).

  python3 tools/twins/placement.py --level 1 --points auto          всё по порядку: точки → оригинал → порт → сверка → отчёт
  python3 tools/twins/placement.py --level 1 --stage points|orig|port|compare|report|gate [--max-points N] [--budget-min M]
  TWINS_BREAK=placement_flip python3 tools/twins/placement.py --level 1 --stage gate     отрицательный контроль: обязан быть FAIL

Проба (одна точка × один курс), одинаково на обеих сторонах:
  поставить машину в точку (центр масс над опорой + 0,25 м, скорость 0) → 2,5 с без ввода («дали физике»: где она в итоге —
  вытолкнуло, провалилась, застряла, на чём стоит) → 1,5 с газа прямо (проезжает или упирается). Курсы 0/90/180/270° —
  четыре стороны разгона. Оригинал: свой PCSX2 без окна (pcsx2-twins, режим -lockstep, как tools/twins/drive.py), машину
  ставим записью тела (car_cm, car_vel — адреса «можно»), курс набираем ездой по кругу на ближнем перекрёстке (курс записью
  не ставится: адреса нет); порт: мир ботов (tools/twins/placement_light.c — тот же код машины и коллизии, что EBOOT) ставится
  в ФАКТИЧЕСКИЙ курс и точку оригинала. Оси: z порта = −z оригинала, курс порта = π − курс оригинала (README близнецов).
Зоны оригинала: город грузится воротами при езде (атлас build/twins/loadmap); телепорт зон не грузит. Поэтому оригинал
стартует со снимка своей же поездки по дорогам (build/twins/placement/l1/base/snap_*.p2s), где регионы точки загружены
(набор регионов по воротам вдоль поездки; регионы точки — по кускам города level.shr с регионом в ±12 м).
Выход: build/twins/placement/l<N>/ (points.tsv, orig.jsonl, port.jsonl, compare.tsv, сессии оригинала с кадрами) и
build/СВЕРКА_PS2_PSP_L<N>/ (карта.png, ОТЧЁТ.md, compare.tsv, пары кадров). Частичные результаты дописываются по мере расчёта;
повторный запуск продолжает с места (готовые пробы не пересчитываются)."""
import argparse, hashlib, json, math, os, re, shutil, struct, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent))
import common as C   # noqa: E402

VERSION = 2            # меняется при смене протокола пробы: старые результаты не смешиваются с новыми
                       # 2 (04.10 17:23): дальние телепорты «по воздуху» — v1 (прямой телепорт) давал рывки до 146 м/с в первой постановке
ORIG_FPS, PORT_FPS = 50, 60
SETTLE_S, GAS_S = 2.5, 1.5
CM_LIFT = 0.66         # [PS2] центр масс машины над землёй в покое: car_cm.y 4,033 при земле порта 3,367 (state_l1_incar, v1_gravity)
DROP = 0.25            # ставим чуть выше опоры: телепорт в землю подбрасывает машину (ps2-hedge-j94: до 12,8 м)
HEADINGS = (0, 90, 180, 270)


def out_dir(level):
    return C.OUT / 'placement' / f'l{level}'


def report_dir(level):
    return C.DATA / 'build' / f'СВЕРКА_PS2_PSP_L{level}'


def log(msg):
    print(f'[{time.strftime("%H:%M:%S")}] {msg}', flush=True)


# ------------------------------------------------------------------ порт: мир ботов пачкой

def light_bin():
    lib = subprocess.run(['bash', '-c', 'V=viewer; . tools/bots/lib.sh; echo "$BOTS_LIB"'], cwd=C.WT, capture_output=True, text=True,
                         check=True).stdout.split()
    srcs = ['tools/twins/placement_light.c'] + lib
    h = hashlib.sha256()
    # PLACEMENT_CFLAGS — флаги прежнего поведения для красного контроля (например -DCOL_FENCE_BACK_OLD=1, tests/walls); входят в отпечаток
    xf = os.environ.get('PLACEMENT_CFLAGS', '').split()
    h.update(' '.join(xf).encode())
    for s in sorted(set(srcs + [str(p.relative_to(C.WT)) for p in (C.WT / 'viewer').glob('*.h')] +
                        [str(p.relative_to(C.WT)) for p in (C.WT / 'tools/bots').glob('*.h')])):
        h.update(s.encode()); h.update((C.WT / s).read_bytes())
    out = C.OUT / 'placement' / 'bin' / f'placement_light_{h.hexdigest()[:12]}'
    if not out.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(['cc', '-std=c11', '-O2', '-w', '-DSKIN_HOST'] + xf + ['-I', 'viewer', '-I', 'tools/bots'] + srcs + ['-lm', '-o', str(out)],
                           cwd=C.WT, capture_output=True, text=True)
        if r.returncode: raise SystemExit('сборка placement_light: ' + (r.stderr.strip().splitlines() or ['?'])[-1])
    return out


def light_inputs(level):
    b = C.DATA / 'build'
    lv = b / 'level.shr' if level == 1 else b / f'levels/l{level}/level.shr'
    return [str(lv), str(b / 'homer.shr'), '--msn', str(b / f'missions/level{level:02d}.msn')]


def light(level, mode, lines, extra=()):
    exe = light_bin()
    r = subprocess.run([str(exe)] + light_inputs(level) + [mode] + list(extra), input=''.join(l + '\n' for l in lines),
                       capture_output=True, text=True, timeout=3600)
    if r.returncode: raise SystemExit(f'placement_light {mode}: ' + (r.stderr.strip().splitlines() or ['?'])[-1])
    return [json.loads(l) for l in r.stdout.splitlines() if l.startswith('{')], exe.name


# ------------------------------------------------------------------ оригинал: свой PCSX2 без окна, замкнутый цикл

def ps2_ready():
    import orig2
    for p in (orig2.BIN, orig2.P / 'bin/portable.txt', orig2.P / 'bin/data/bios/scph10000.bin', orig2.ISO):
        if not Path(p).exists(): raise SystemExit(f'оригинал: нет {p} (tools/twins/pcsx2_build.sh)')
    orig2.prepare = lambda: None   # всё на месте; общую папку PCSX2 близнецов не трогаем


EXTRA = [('vy', 0xa218b4, 'f32'), ('cx', 0x1298884, 'f32'), ('cy', 0x1298888, 'f32'), ('cz', 0x129888c, 'f32'),
         ('upy', 0xa21884, 'f32'), ('noy', 0xa21894, 'f32'), ('hx', 0xa24a70, 'f32'), ('hy', 0xa24a74, 'f32'), ('hz', 0xa24a78, 'f32')]


def orig_process(out, state, extra, lockstep=2, swthreads=1, null=False):
    """pcsx2-twins в режиме -lockstep (как drive.Original), но со своим числом потоков рисования (бюджет ядер Мака) и сторожем:
    свой процесс впереди, его окно на экране или звук наружу -> остановить свой PID (правила Роба 30.09 и 03.10)"""
    import drive as D, orig2, threading
    ps2_ready()
    o = D.Original.__new__(D.Original)
    o.out = Path(out); o.out.mkdir(parents=True, exist_ok=True); o.cols = list(D.TRACE) + list(extra)
    sc = o.out / 'script.txt'; sc.write_text('0 trace - 1 ' + ' '.join(f'{a:x}:{t}' for _, a, t in o.cols) + '\n')
    # приоритет: без добавочного nice (рой ботов идёт с nice 20 и душит замкнутый цикл: 04.10 при нагрузке ~200 оригинал шёл 2–3 к/с
    # вместо 37); ядер берём не больше трёх (поток EE + 2 потока программного рисования) — бюджет Роба «не больше 4 ядер»
    nice = os.environ.get('PLACEMENT_NICE', '0')
    args = (['nice', '-n', nice] if nice != '0' else []) + [str(orig2.BIN), '-statefile', str(state), '-script', str(sc), '-lockstep', str(lockstep),
            '-bios', 'scph10000.bin', '-renderer', 'sw', '-swthreads', str(swthreads),
            '-set', 'SPU2/Output/Backend=Null'] + (['-set', 'EmuCore/GS/Renderer=11'] if null else []) + ['--', str(orig2.ISO)]   # без звука (Роб 03.10); null — без рисования
    o.log = (o.out / 'log.txt').open('w')
    o.p = subprocess.Popen(args, cwd=str(o.out), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    o.frame = 0; o.bad = []
    wins = C.DATA / 'build/ps2ref/bin/wins'
    def watch():
        k = 0
        while o.p.poll() is None:
            why = ''
            try:
                if orig2.front_pid() == o.p.pid: why = 'вышел вперёд'
                elif k % 10 == 0 and wins.exists() and any(l.startswith('1 ') for l in subprocess.run([str(wins), str(o.p.pid)], capture_output=True, text=True).stdout.splitlines()):
                    why = 'окно на экране'
                elif k % 25 == 5:
                    a = subprocess.run(['pmset', '-g', 'assertions'], capture_output=True).stdout.decode('utf-8', 'replace')
                    if any(f'pid {o.p.pid}(' in l and 'audio' in l.lower() for l in a.splitlines()): why = 'звук наружу'
            except Exception as e:   # сторож не умирает от чужого вывода (04.10: pmset с не-UTF-8 уронил поток)
                o.watch_err = repr(e)
            if why:
                o.bad.append(why); o.p.kill(); return
            k += 1; time.sleep(0.2)
    threading.Thread(target=watch, daemon=True).start()
    return o


def body(x, y, z, vx=0.0, vy=0.0, vz=0.0):
    """телепорт тела машины (адреса «можно»: car_cm 0x1298884, car_vel 0xa218b0) + шкала Hit & Run в 0 (hnr 0x612114, «можно»)"""
    return [f'f32 1298884 {x:.4f}', f'f32 1298888 {y:.4f}', f'f32 129888c {z:.4f}',
            f'f32 a218b0 {vx:.4f}', f'f32 a218b4 {vy:.4f}', f'f32 a218b8 {vz:.4f}', 'f32 612114 0']


def ang(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


class Sky:
    """высота самого высокого в городе (куски level.shr, кроме неба) по клеткам 10 м, оси порта -> высота пролёта отрезка
    (оси оригинала): максимум по клеткам вдоль отрезка ±1 клетка + 10 м"""
    def __init__(self, level):
        import numpy as np, shr7read
        lp = C.DATA / 'build' / ('level.shr' if level == 1 else f'levels/l{level}/level.shr')
        L = shr7read.load(lp); P = L['P'][(L['FL'] & 4) == 0]
        self.x0, self.z0 = float(P[:, :, 0].min()), float(P[:, :, 2].min())
        ix = ((P[:, :, 0].mean(1) - self.x0) // 10).astype(int); iz = ((P[:, :, 2].mean(1) - self.z0) // 10).astype(int)
        self.g = np.full((iz.max() + 2, ix.max() + 2), -50.0); np.maximum.at(self.g, (iz, ix), P[:, :, 1].max(1))

    def __call__(self, ax, az, bx, bz):
        n = max(2, int(math.hypot(bx - ax, bz - az) / 5)); top = -50.0
        for i in range(n + 1):
            x = ax + (bx - ax) * i / n; z = -(az + (bz - az) * i / n)   # оси оригинала -> порта
            gx, gz = int((x - self.x0) // 10), int((z - self.z0) // 10)
            sl = self.g[max(0, gz - 1):gz + 2, max(0, gx - 1):gx + 2]
            if sl.size: top = max(top, float(sl.max()))
        return top + 10.0


def ps2_session(out, state, trials, png=True, max_frames=80000, swthreads=2, ls=None, null=False, alt_fn=None):
    """одна загрузка состояния оригинала, пробы по очереди. trials: [dict(id, P=(x, ycm, z) оси оригинала, R=(x, ycm, z) — место
    покоя/набора курса, turn=None | градусы к курсу прошлой пробы этой точки (набор курса ездой по кругу на R))].
    Проба: R (успокоиться, при turn — набрать курс) -> P -> покой -> газ -> тормоз -> снова P тем же курсом -> покой -> назад.
    -> (результаты по пробам, сведения о сессии). Сессия обрывается, если Гомер вышел из машины (машина разбита) или машина
    перевернулась на R — оставшиеся пробы идут в новую сессию (вызывающий)."""
    import drive as D
    S1, G1 = int(SETTLE_S * ORIG_FPS), int(GAS_S * ORIG_FPS); S2 = int(1.0 * ORIG_FPS)
    out = Path(out); (out / 'png').mkdir(parents=True, exist_ok=True)
    ls = ls or int(os.environ.get('PLACEMENT_LOCKSTEP', '4'))   # кадров на такт обмена: 4 (0,08 с) — вдвое меньше обменов при загруженном Маке
    if null: png = False   # без рисования кадров нет
    o = orig_process(out, state, EXTRA, swthreads=swthreads, lockstep=ls, null=null)
    tr = (out / 'trace.tsv').open('w', buffering=1)
    tr.write('кадр\tпроба\tфаза\tx\ty\tz\tкурс\tv\tvy\tcx\tcy\tcz\tupy\tnoy\thx\thy\thz\n')
    res = []; t0 = time.time(); first_step = None; abort = None; homer0 = None
    k = 0; phase = 'tpR'; ph_f = 0; hold = 0; stuck = 0; rev = 0; cur = None; calm = 0; goal = None; prev_yaw = {}; hops = []
    def rec(s, f):
        nn = math.hypot(s['nx'], s['nz']) or 1.0
        return dict(frame=f, pos=[s['x'], s['y'], s['z']], cm=[s['cx'], s['cy'], s['cz']], yaw=math.atan2(s['nx'], s['nz']),
                    v=math.hypot(s['vx'], s['vz']), va=(s['vx'] * s['nx'] + s['vz'] * s['nz']) / nn, vy=s['vy'], upy=s['upy'], noy=s['noy'])
    def done(cur):
        cur['time'] = round(time.time() - t0, 1); res.append(cur)
        with (out / 'partial.jsonl').open('a') as fo: fo.write(json.dumps(cur, ensure_ascii=False) + '\n')
    while True:
        s = o.step()
        if s is None: break
        f = o.frame
        if first_step is None: first_step = time.time() - t0
        if homer0 is None: homer0 = (s['hx'], s['hz'])
        if k >= len(trials) or f > max_frames or abort:
            o.p.stdin.write('end\n'); o.p.stdin.flush(); break
        t = trials[k]
        if cur is None:
            cur = dict(id=t['id'], point=t['point'], P=list(t['P']), R=list(t['R']), turn=t.get('turn'), notes=[])
        h = math.atan2(s['nx'], s['nz']); v = math.hypot(s['vx'], s['vz'])
        va = (s['vx'] * s['nx'] + s['vz'] * s['nz']) / (math.hypot(s['nx'], s['nz']) or 1.0)   # скорость вдоль носа, со знаком
        stop = ['pad cross %d' % (va < -0.6), 'pad circle %d' % (va > 0.6), *D.axis('l', 'x', 0.0)]   # тормоз: против хода (○ назад — газ)
        tr.write(f"{f}\t{t['id']}\t{phase}\t{s['x']:.3f}\t{s['y']:.3f}\t{s['z']:.3f}\t{math.degrees(h):.2f}\t{v:.3f}\t{s['vy']:.3f}\t"
                 f"{s['cx']:.3f}\t{s['cy']:.3f}\t{s['cz']:.3f}\t{s['upy']:.3f}\t{s['noy']:.3f}\t{s['hx']:.2f}\t{s['hy']:.2f}\t{s['hz']:.2f}\n")
        if math.hypot(s['hx'] - homer0[0], s['hz'] - homer0[1]) > 1.0:   # Гомер в машине не двигается (матрица стоит); сдвинулся — вышел
            abort = 'Гомер вышел из машины (машина разбита?)'; cur['notes'].append(abort); cur['broken'] = True; done(cur); cur = None
            o.p.stdin.write('end\n'); o.p.stdin.flush(); break
        cmds = []
        neutral = ['pad cross 0', 'pad circle 0', *D.axis('l', 'x', 0.0)]
        if phase in ('tpR', 'tpP', 'tpP2'):
            # телепорт. Дальний (на R и с R в точку) — «по воздуху»: вверх над своим местом, по прямой на высоте выше всего города
            # на этом отрезке, вниз в точку (04.10: прямой дальний телепорт оригинала тащит машину сквозь дома по пути — рывки до
            # 146 м/с и сдвиг до 18 м на открытых местах, а та же точка с 5 м — 0,1 м). Короткий (снова в точку после газа) — прямо.
            if hold == 0:
                dest = tuple(t['R'] if phase == 'tpR' else t['P'])
                if phase == 'tpP': cur['before'] = rec(s, f)
                if phase == 'tpP2': cur['before2'] = rec(s, f)
                air = alt_fn is not None and ((phase == 'tpR' and t.get('air_R', True)) or (phase == 'tpP' and t.get('air_P', True)))
                if air:
                    a = alt_fn(s['cx'], s['cz'], dest[0], dest[2])
                    hops = [(s['cx'], max(a, s['cy'] + 2), s['cz']), (dest[0], a, dest[2]), dest, dest]
                else: hops = [dest, dest]
                if phase == 'tpP': cur['air'] = bool(air)
            cmds = body(*hops[hold]) + neutral; hold += 1
            if hold >= len(hops):
                if phase == 'tpR': phase, ph_f, hold, stuck, rev, calm = 'calm', f, 0, 0, 0, 0
                else: phase, ph_f, hold = ('settle' if phase == 'tpP' else 'settle2'), f, 0
        elif phase == 'calm':       # успокоиться на R; если пробе нужен другой курс — набрать ездой по кругу
            el = f - ph_f
            if goal is None and t.get('yaw_abs') is not None: goal = t['yaw_abs']
            if t.get('turn') is not None and goal is None: goal = ang(prev_yaw.get(t['point'], h) + math.radians(t['turn']))
            err = ang(goal - h) if goal is not None else 0.0
            if rev > 0:
                rev -= ls; cmds = ['pad cross 0', 'pad circle 1', *D.axis('l', 'x', -1.0 if err > 0 else 1.0)]
                if rev <= 0: cmds = ['pad circle 0', *D.axis('l', 'x', 0.0)]
            elif goal is not None and abs(err) > math.radians(10) and el < 700:
                cmds = [*D.axis('l', 'x', 1.0 if err > 0 else -1.0), f'pad cross {1 if v < 6.0 else 0}', 'pad circle 0']
                stuck = stuck + ls if v < 0.4 else 0
                if stuck >= 80: rev, stuck = 50, 0
                calm = 0
            else:
                cmds = stop
                calm = calm + ls if v < 0.4 and s['upy'] > 0.9 else 0
                if el >= 900: cur['notes'].append('не успокоилась на R за 18 с')
                if (calm >= 10 and el >= 10) or el >= 900:
                    if s['upy'] < 0.9:
                        abort = 'машина на боку/перевёрнута на R'; cur['notes'].append(abort); cur['broken'] = True; done(cur); cur = None
                        o.p.stdin.write('end\n'); o.p.stdin.flush(); break
                    cur['aim_frames'] = el
                    if goal is not None and abs(err) > math.radians(10): cur['notes'].append(f'курс не набран: ошибка {math.degrees(err):.0f}°')
                    phase, hold, goal = 'tpP', 0, None
        elif phase == 'settle':
            cmds = neutral
            if f - ph_f >= S1:
                cur['settled'] = rec(s, f)
                if png: cmds = cmds + [f"png {out / 'png' / (t['id'] + '_s.png')}"]
                phase, ph_f = 'gas', f
        elif phase == 'gas':
            cmds = ['pad cross 1', 'pad circle 0', *D.axis('l', 'x', 0.0)]
            if f - ph_f >= G1:
                cur['gassed'] = rec(s, f); cmds = neutral
                if png: cmds = cmds + [f"png {out / 'png' / (t['id'] + '_g.png')}"]
                phase, ph_f = 'brake', f
        elif phase == 'brake':      # стоп перед второй постановкой (без вращения); кружок только пока едет вперёд
            cmds = stop
            if v <= 0.6 or f - ph_f >= 60:
                if s['upy'] < 0.9: cur['notes'].append('после газа на боку: вторая постановка пропущена'); phase = 'next'
                else: phase, hold = 'tpP2', 0
        elif phase == 'settle2':
            cmds = neutral
            if f - ph_f >= S2:
                cur['settled2'] = rec(s, f); phase, ph_f = 'rev', f
                if png: cmds = cmds + [f"png {out / 'png' / (t['id'] + '_s2.png')}"]
        elif phase == 'rev':
            cmds = ['pad cross 0', 'pad circle 1', *D.axis('l', 'x', 0.0)]
            if f - ph_f >= G1:
                cur['reversed'] = rec(s, f); cmds = neutral
                if png: cmds = cmds + [f"png {out / 'png' / (t['id'] + '_r.png')}"]
                phase = 'next'
        if phase == 'next':
            if 'before' in cur: prev_yaw[t['point']] = cur['before']['yaw']
            done(cur); cur = None; k += 1; phase, hold = 'tpR', 0
        o.send(*cmds)
    o.close(); tr.close()
    wall = time.time() - t0
    info = dict(state=str(state), trials=len(trials), done=sum(1 for r in res if not r.get('broken')), frames=o.frame, wall_s=round(wall, 1),
                load_s=round(first_step or 0, 1), fps=round(o.frame / (wall - (first_step or 0)), 1) if wall else None, time=C.clock(),
                watchdog=o.bad, abort=abort, swthreads=swthreads, lockstep=ls, renderer='null' if null else 'sw')
    (out / 'session.json').write_text(json.dumps(info, ensure_ascii=False, indent=1))
    if o.bad: log(f'ОРИГИНАЛ ОСТАНОВЛЕН СТОРОЖЕМ: {", ".join(o.bad)} — сессия {out}')
    return res, info


# ------------------------------------------------------------------ точки-кандидаты (все из данных, без координат вручную)

KIND_RU = {'ramp': 'трамплин', 'teleport': 'место телепорта', 'deadend': 'тупик', 'shortcut': 'срезка (тропа ИИ через дворы)',
           'lawn': 'край газона у дороги', 'yard': 'двор у дороги', 'fence_f': 'забор, лицевая сторона', 'fence_b': 'забор, изнанка',
           'hedge': 'у изгороди', 'wall': 'у стены дома', 'bridge': 'под мостом / навесом', 'parked': 'стоянка у стоящих машин',
           'grid': 'сетка кварталов', 'playable': 'край проезжего (карта ботов)'}
QUOTA = {'ramp': 22, 'teleport': 12, 'deadend': 10, 'shortcut': 22, 'fence_f': 14, 'fence_b': 14, 'hedge': 10, 'wall': 18,
         'bridge': 10, 'parked': 10, 'lawn': 18, 'yard': 18, 'playable': 30, 'grid': 40}
MIN_GAP = 14.0   # точки разных видов не ближе (м): одна точка — одно место


def code(x, z):
    import place
    return place.code(x, z)


def level_regions_of_pieces(level):
    """[(x, z центров треугольников города), регион (−1 — без региона: земля и дороги l<N>_terra, грузятся всегда)], имена"""
    import numpy as np, shr7read, regions_export as RE
    lp = C.DATA / 'build' / ('level.shr' if level == 1 else f'levels/l{level}/level.shr')
    b = lp.read_bytes(); L = shr7read.load(lp)
    ptab, = struct.unpack_from('<I', b, 76); npc, = struct.unpack_from('<I', b, 8)
    reg = np.array([struct.unpack_from('<I', b, ptab + 80 * i + 72)[0] for i in range(npc)], np.int64) - 1
    cen = L['P'].mean(1)
    sec = RE.read_section(b)
    return cen[:, 0], cen[:, 2], reg[L['PI']], (sec['names'] if sec else RE.level_regions(level))


class RegionIndex:
    R = 12.0
    def __init__(self, level):
        import numpy as np
        self.x, self.z, self.reg, self.names = level_regions_of_pieces(level)
        k = self.reg >= 0; self.x, self.z, self.reg = self.x[k], self.z[k], self.reg[k]
        self.cell = {}
        for i, (gx, gz) in enumerate(zip(np.floor(self.x / 20).astype(int), np.floor(self.z / 20).astype(int))):
            self.cell.setdefault((gx, gz), []).append(i)
        self.np = np

    def near(self, x, z):
        """регионы, у которых есть город в радиусе R от точки (x, z порта) -> набор имён"""
        out = set(); gx, gz = int(math.floor(x / 20)), int(math.floor(z / 20))
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                for i in self.cell.get((gx + dx, gz + dz), ()):
                    if (self.x[i] - x) ** 2 + (self.z[i] - z) ** 2 <= self.R ** 2: out.add(self.names[self.reg[i]])
        return out


def candidates(level):
    """-> [dict(kind, x, z (оси порта), yhint, src)] — сырой список из данных уровня"""
    import numpy as np, traffic_export as te, place
    out = []
    add = lambda kind, x, z, src, yhint=None: out.append(dict(kind=kind, x=float(x), z=float(z), yhint=yhint, src=src))
    # трамплины: цели ботов (build/bots/targets-l<N>.tsv, вид ramp — зоны прыжка jumpzone* диска)
    tf = C.DATA / 'build/bots' / f'targets-l{level}.tsv'
    if tf.exists():
        for l in tf.read_text().splitlines():
            c = l.split('\t')
            if len(c) > 2 and c[0] == 'ramp':
                x, y, z = map(float, c[2].split()); add('ramp', x, z, f'targets-l{level}.tsv {c[1]}', y)
    for nm, x, z in place.places(level): add('teleport', x, z, f'AddTeleportDest «{nm}»')
    junc, roads = te.road_network(level)
    deg = {}
    for r in roads:
        if r['shortcut']: continue
        deg[r['s']] = deg.get(r['s'], set()) | {r['e']}; deg[r['e']] = deg.get(r['e'], set()) | {r['s']}
    seen = set()
    for r in roads:
        L = np.asarray(r['pts']); cen = L[:, :, :3].mean(0)
        if r['shortcut']:
            s_ = np.r_[0, np.cumsum(np.linalg.norm(np.diff(cen[:, [0, 2]], axis=0), axis=1))]
            for t in np.arange(8, s_[-1] - 4, 25):
                add('shortcut', np.interp(t, s_, cen[:, 0]), np.interp(t, s_, cen[:, 2]), f'дорога ИИ {r["name"]} (срезка), {t:.0f} м')
            continue
        key = (min(r['s'], r['e']), max(r['s'], r['e']))
        if key in seen: continue
        seen.add(key)
        half = r['lanes'] * r['width'] * (2 if r['rev'] != 0xFFFF else 1) / 2
        s_ = np.r_[0, np.cumsum(np.linalg.norm(np.diff(cen[:, [0, 2]], axis=0), axis=1))]
        for t in np.arange(20, s_[-1] - 15, 70):
            i = min(len(s_) - 2, int(np.searchsorted(s_, t)))
            d = cen[i + 1] - cen[i]; d = d / (np.hypot(d[0], d[2]) or 1)
            px, pz = np.interp(t, s_, cen[:, 0]), np.interp(t, s_, cen[:, 2]); nx, nz = d[2], -d[0]
            for sgn in (1, -1):
                add('lawn', px + sgn * nx * (half + 4), pz + sgn * nz * (half + 4), f'дорога {r["name"]}: {half + 4:.0f} м от оси')
                add('yard', px + sgn * nx * (half + 12), pz + sgn * nz * (half + 12), f'дорога {r["name"]}: {half + 12:.0f} м от оси')
    for j, nb in deg.items():
        if len(nb) == 1:
            o = junc[next(iter(nb))]['pos']; p = junc[j]['pos']; d = np.array([p[0] - o[0], p[2] - o[2]]); d /= (np.hypot(*d) or 1)
            add('deadend', p[0] + d[0] * 8, p[2] + d[1] * 8, f'перекрёсток {junc[j]["name"]}: дорога кончается')
    for nm, x, y, z, hg in te.parked_spots(level):
        add('parked', x + math.sin(hg) * 5.5, z + math.cos(hg) * 5.5, f'место стоящей машины {nm} + 5,5 м вдоль', y)
    d, _ = light(level, 'dump', [])
    for g in d:
        if 'seg' in g:
            a, b = np.array(g['a']), np.array(g['b']); ln = float(np.hypot(*(b - a)))
            if ln < 6 or abs(g['y1']) > 1e5: continue   # граница карты (за ней пустота) — не двор
            m = (a + b) / 2; n = np.array(g['n'])
            if g['y0'] < -1e6: add('hedge', m[0] + n[0] * 3, m[1] + n[1] * 3, f'изгородь (забор-куст) seg {g["seg"]}, {ln:.0f} м')
            else:
                add('fence_f', m[0] + n[0] * 3, m[1] + n[1] * 3, f'забор seg {g["seg"]} ({ln:.0f} м, верх {g["y1"]:.1f}), лицом')
                add('fence_b', m[0] - n[0] * 3, m[1] - n[1] * 3, f'забор seg {g["seg"]} ({ln:.0f} м, верх {g["y1"]:.1f}), изнанка')
        elif 'box' in g:
            A = [np.array(g['ax']), np.array(g['ay']), np.array(g['az'])]; h = g['h']
            up = max(range(3), key=lambda i: abs(A[i][1]))
            if h[up] < 2.0: continue
            side = [i for i in range(3) if i != up]
            if max(h[i] for i in side) < 3.0 or max(h[i] for i in side) > 30: continue
            i = max(side, key=lambda i: h[i]); j = [q for q in side if q != i][0]   # длинная стена: нормаль по оси j
            n = A[j][[0, 2]]; n = n / (np.hypot(*n) or 1)
            for sgn in (1, -1):
                add('wall', g['c'][0] + sgn * n[0] * (h[j] + 3), g['c'][2] + sgn * n[1] * (h[j] + 3), f'ящик коллизии {g["box"]} (дом?), 3 м от стены')
    grid = d[0]['grid']; ox, oz, cell, W, H = grid
    for x in np.arange(ox + 20, ox + W * cell - 20, 40):
        for z in np.arange(oz + 20, oz + H * cell - 20, 40): add('grid', x, z, 'сетка 40 м')
    for x in np.arange(ox + 10, ox + W * cell - 10, 10):
        for z in np.arange(oz + 10, oz + H * cell - 10, 10): add('bridge?', x, z, 'сетка 10 м: две опоры с просветом')
    pl = playable_file(level)
    if pl:
        for x, z, src, y in playable_border(pl): add('playable', x, z, src, y)
    return out


def playable_file(level):
    """карта проезжих клеток помощника по ботам (build/playable-l<N>.tsv): в нашей папке данных или в его копии"""
    for p in (C.DATA / 'build' / f'playable-l{level}.tsv', Path('/Users/USER/.claude/jobs/shar-0410/tmp/agentMAP/build') / f'playable-l{level}.tsv'):
        if p.exists(): return p
    return None


def playable_border(path):
    """карта проезжих клеток помощника (tools/bots/anatomy.py map: клетка 6 м, x z — угол клетки, y — высота езды; в файле только
    проезжие клетки) -> клетки на границе зелёного (нет соседа по стороне) -> [(x, z центра, источник, y)]"""
    head = None; cells = {}
    for l in path.read_text(errors='replace').splitlines():
        if l.startswith('#'):
            c = l[1:].strip().split('\t')
            if len(c) > 3 and c[0] == 'x': head = c
            continue
        if not l.strip() or not head: continue
        c = l.split('\t')
        try: x, z, y = float(c[head.index('x')]), float(c[head.index('z')]), float(c[head.index('y')])
        except (ValueError, IndexError): continue
        cells[(round(x, 2), round(z, 2))] = y
    if not cells: return []
    xs = sorted({k[0] for k in cells}); step = min((b - a for a, b in zip(xs, xs[1:]) if b - a > 0.01), default=6.0)
    out = []
    for (x, z), y in sorted(cells.items()):
        miss = [(dx, dz) for dx, dz in ((step, 0), (-step, 0), (0, step), (0, -step)) if (round(x + dx, 2), round(z + dz, 2)) not in cells]
        if miss: out.append((x + step / 2, z + step / 2, f'{path.name}: край зелёного (нет соседа {len(miss)} из 4)', y))
    return out


def counts(items, key='kind'):
    c = {}
    for it in items: c[it[key]] = c.get(it[key], 0) + 1
    return ', '.join(f'{k} {v}' for k, v in sorted(c.items(), key=lambda kv: -kv[1]))


def gen_points(level, max_points=None):
    """кандидаты -> опоры (probe) -> отбор по видам и разносу -> build/twins/placement/l<N>/points.tsv"""
    import numpy as np
    cand = candidates(level)
    log(f'кандидатов: {len(cand)} ({counts(cand)})')
    lines = [f'c{i} {c["x"]:.3f} {c["z"]:.3f}' for i, c in enumerate(cand)]
    pr, exe = light(level, 'probe', lines)
    keep = []
    for c, p in zip(cand, pr):
        L = p['layers']   # сверху вниз: [y, n.y, материал, глубина кузова курс 0, курс 90, объект]
        if not L: continue
        if c['kind'] == 'bridge?':
            if len(L) < 2: continue
            lo, up = L[-1], L[-2]
            if not (4.5 <= up[0] - lo[0] <= 16 and lo[1] > 0.9 and max(lo[3], lo[4]) < 0.05): continue
            c = dict(c, kind='bridge')
            li = len(L) - 1
        elif c['yhint'] is not None:
            li = min(range(len(L)), key=lambda i: abs(L[i][0] - c['yhint']))
        else: li = len(L) - 1   # земля — нижняя опора (двор, газон, тротуар)
        y, ny, mat, d0, d90, obj = L[li]
        if min(d0, d90) > 0.8: continue    # глубоко внутри дома/ящика: не место для машины
        if ny < 0.5: continue
        keep.append(dict(c, y=y, layer=len(L) - 1 - li, nlayers=len(L), ny=ny, depth=[d0, d90], obj=obj))
    RI = RegionIndex(level)
    # отбор: по видам в порядке QUOTA, внутри вида — дальняя точка (детерминированно), не ближе MIN_GAP к уже взятым
    sel = []; quota = dict(QUOTA)
    if max_points:   # трамплины, места телепорта и тупики — все (их мало и они особые); остальные виды — в долю
        fixed = {k: quota[k] for k in ('ramp', 'teleport', 'deadend')}
        scale = (max_points - sum(fixed.values())) / sum(v for k, v in quota.items() if k not in fixed)
        quota = {k: (v if k in fixed else max(1, int(round(v * scale)))) for k, v in quota.items()}
    order = ['ramp', 'teleport', 'deadend', 'bridge', 'shortcut', 'fence_f', 'fence_b', 'hedge', 'wall', 'parked', 'playable', 'lawn', 'yard', 'grid']
    for kind in order:
        pool = [c for c in keep if c['kind'] == kind]
        if not pool: continue
        cx = float(np.mean([c['x'] for c in keep])); cz = float(np.mean([c['z'] for c in keep]))
        taken = 0
        while pool and taken < quota.get(kind, 0):
            def gap(c): return min((math.hypot(c['x'] - q['x'], c['z'] - q['z']) for q in sel), default=1e9)
            if not sel: best = min(pool, key=lambda c: math.hypot(c['x'] - cx, c['z'] - cz))
            else: best = max(pool, key=lambda c: (min(gap(c), 400.0), -c['x'], -c['z']))
            pool.remove(best)
            if gap(best) < MIN_GAP and kind != 'ramp': continue
            sel.append(best); taken += 1
    pts = []
    for n, c in enumerate(sel):
        regs = sorted(RI.near(c['x'], c['z']))
        pts.append(dict(id=f'{c["kind"]}{sum(1 for q in pts if q["kind"] == c["kind"]):03d}', kind=c['kind'], x=round(c['x'], 3), y=round(c['y'], 3),
                        z=round(c['z'], 3), code=code(c['x'], c['z']), layer=c['layer'], nlayers=c['nlayers'], regions=regs,
                        depth=c['depth'], obj=c['obj'], src=c['src']))
    od = out_dir(level); od.mkdir(parents=True, exist_ok=True)
    with (od / 'points.tsv').open('w') as fo:
        fo.write(f'# набор «постановка машины» L{level}: точки из данных (tools/twins/placement.py gen_points), оси порта (z оригинала = −z); '
                 f'опора — высота земли порта под точкой (placement_light probe), слой 0 — нижняя; регионы — файлы зон оригинала с городом в 12 м\n')
        fo.write('id\tвид\tx\ty\tz\tклетка\tслой\tопор\tрегионы\tглубина0\tглубина90\tобъект\tисточник\n')
        for p in pts:
            fo.write(f"{p['id']}\t{p['kind']}\t{p['x']}\t{p['y']}\t{p['z']}\t{p['code']}\t{p['layer']}\t{p['nlayers']}\t{','.join(p['regions']) or '-'}\t"
                     f"{p['depth'][0]:.2f}\t{p['depth'][1]:.2f}\t{p['obj']}\t{p['src']}\n")
    log(f'точек: {len(pts)} ({counts(pts)}) → {(od / "points.tsv").relative_to(C.DATA)}')
    return pts


def load_points(level):
    f = out_dir(level) / 'points.tsv'
    pts = []
    for l in f.read_text().splitlines()[2:]:
        c = l.split('\t')
        pts.append(dict(id=c[0], kind=c[1], x=float(c[2]), y=float(c[3]), z=float(c[4]), code=c[5], layer=int(c[6]), nlayers=int(c[7]),
                        regions=[] if c[8] == '-' else c[8].split(','), depth=[float(c[9]), float(c[10])], obj=c[11], src=c[12]))
    return pts


# ------------------------------------------------------------------ база оригинала: своя поездка по дорогам со снимками

def base_drive(level, every=300, vmax=18.0, frames=17000):
    """поездка бота по дорогам оригинала (route.py route_roads, как drive.py route — тот же руль) со снимком состояния каждые
    every кадров: снимки — старты сессий проб (в них загружены зоны по ходу). -> папка base/ (drive.tsv, snap_*.p2s, base.json)"""
    import drive as D, route as R
    if level != 1: raise SystemExit('база оригинала пока только для L1 (route.py: точки маршрута L1)')
    bd = out_dir(level) / 'base'
    if (bd / 'base.json').exists():
        log(f'база оригинала уже есть: {bd.relative_to(C.DATA)}'); return json.loads((bd / 'base.json').read_text())
    bd.mkdir(parents=True, exist_ok=True)
    pts, _ = R.route_roads()
    pts = [(215.05, 4.05, -170.25), (214.0, 4.0, -159.0)] + pts
    pts, _ = R.resample(pts, 3.0)
    o = orig_process(bd, C.DATA / 'build/ps2ref/state_l1_incar.p2s', [], swthreads=2)
    tsv = (bd / 'drive.tsv').open('w'); tsv.write('кадр\tx\ty\tz\tкурс\tv\tиндекс\n')
    i = 0; stuck = 0; rev = 0; last = 0; boost = 0; snaps = []; t0 = time.time()
    while True:
        s = o.step()
        if s is None: break
        f = o.frame; x, z = s['x'], s['z']; h = math.atan2(s['nx'], s['nz']); v = math.hypot(s['vx'], s['vz'])
        best = min(range(i, min(len(pts), i + 40)), key=lambda k: (pts[k][0] - x) ** 2 + (pts[k][2] - z) ** 2)
        if best > i: i = best; last = f
        end = i >= len(pts) - 2 or f >= frames
        j = min(len(pts) - 1, i + (3 if f > boost else 7)); err = ang(math.atan2(pts[j][0] - x, pts[j][2] - z) - h)
        if rev > 0:
            rev -= 2; cmds = ['pad cross 0', 'pad circle 1', *D.axis('l', 'x', -1.0 if err > 0 else 1.0)]
            if rev <= 0: cmds = ['pad circle 0', *D.axis('l', 'x', 0.0)]; boost = f + 150
        else:
            st = max(-1.0, min(1.0, err * 2.5)); vt = vmax * max(0.35, math.cos(err))
            cmds = [*D.axis('l', 'x', st), f'pad cross {1 if v < vt else 0}', f'pad circle {1 if v > vt + 5 else 0}', 'f32 612114 0']
            stuck = stuck + 2 if v < 0.8 else 0
            if stuck >= 50 or f - last > 500: rev = 60; stuck = 0; last = f
        if f and f % every == 0:
            cmds.append(f"save {bd / f'snap_{f}.p2s'}"); snaps.append(dict(frame=f, pos=[x, s['y'], z], yaw=h))
        tsv.write(f"{f}\t{x:.2f}\t{s['y']:.2f}\t{z:.2f}\t{math.degrees(h):.1f}\t{v:.2f}\t{i}\n")
        if end: o.p.stdin.write('end\n'); o.p.stdin.flush(); break
        o.send(*cmds)
    o.close(); tsv.close()
    info = dict(level=level, frames=o.frame, route_points=len(pts), reached=i, snaps=[sn for sn in snaps if (bd / f"snap_{sn['frame']}.p2s").exists()],
                wall_s=round(time.time() - t0, 1), watchdog=o.bad, time=C.clock(), state='build/ps2ref/state_l1_incar.p2s',
                state_sha256=C.sha256(C.DATA / 'build/ps2ref/state_l1_incar.p2s'), binary_sha256=C.sha256(__import__('orig2').BIN, 16))
    if o.bad: raise SystemExit(f'база оригинала: сторож остановил PCSX2 ({o.bad})')
    (bd / 'base.json').write_text(json.dumps(info, ensure_ascii=False, indent=1))
    log(f'база оригинала: кадров {o.frame}, точек маршрута {i}/{len(pts)}, снимков {len(info["snaps"])}, {info["wall_s"]:.0f} с')
    return info


# ------------------------------------------------------------------ зоны оригинала: ворота подгрузки вдоль поездки и телепортов

START_SET = {'l1z1', 'l1r1', 'l1r7'}   # [диск]+[PS2] набор у дома Симпсонов (AddTeleportDest; b2: первое чтение — только l1z2 у ворот loader)


class Gates:
    """ворота подгрузки оригинала (build/twins/loadmap/gates.json — tools/twins/loadmap.py, сверено ездой: 22 из 22 чтений).
    Оси порта. Въезд в объём ворот: набор := (набор − выгрузить) ∪ загрузить (имена без .p3d, только регионы города)"""
    def __init__(self):
        G = json.loads((C.OUT / 'loadmap' / 'gates.json').read_text())['gates']
        self.g = [dict(name=g['name'], boxes=g['boxes'], load={f[:-4] for f in g['load']}, unload={f[:-4] for f in g['unload']}) for g in G]

    @staticmethod
    def inside_box(b, x, y, z, m=0.5):
        d = [x - b['c'][0], y - b['c'][1], z - b['c'][2]]
        return all(abs(sum(d[j] * b['R'][k][j] for j in range(3))) <= b['half'][k] + m for k in range(3)) or \
               all(abs(sum(d[j] * b['R'][j][k] for j in range(3))) <= b['half'][k] + m for k in range(3))

    def inside(self, x, y, z):
        return {i for i, g in enumerate(self.g) if any(self.inside_box(b, x, y, z) for b in g['boxes'])}

    def apply(self, S, entered):
        S = set(S)
        for i in sorted(entered): S = (S - self.g[i]['unload']) | self.g[i]['load']
        return S

    def walk(self, rows, S0, was=None, jump=5.0):
        """rows: [(кадр, x, y, z оси порта)] -> [(кадр, набор после, ворота)] на каждом въезде ездой; was — ворота, внутри которых
        начали. Прыжок больше jump м между соседними строками — телепорт: ворота НЕ срабатывают ([PS2] tw_b2_hops: телепорты
        в объёмы loader9 (Power Plant Parking Lot) и loader4 (Graveyard) — ни одного чтения файлов зон, build/twins/b2/tw_b2_hops/files.tsv)"""
        S = set(S0); was = set(was or ()); ev = []; prev = None
        for f, x, y, z in rows:
            now = self.inside(x, y, z)
            tele = prev is not None and math.hypot(x - prev[0], z - prev[1]) > jump
            if now - was and not tele: S = self.apply(S, now - was); ev.append((f, set(S), sorted(self.g[i]['name'] for i in now - was)))
            was = now; prev = (x, z)
        return ev, S, was


def base_info(level):
    """база оригинала: своя поездка (--stage base, base/base.json), иначе снимки готовой поездки бота b2_loop (build/twins/o4/b2_loop:
    snap_3000…21000, 01.10, тот же pcsx2-twins) + состояние старта state_l1_incar (у дома Симпсонов). -> dict как base.json"""
    own = out_dir(level) / 'base' / 'base.json'
    if own.exists(): return json.loads(own.read_text())
    if level != 1: raise SystemExit('нет базы оригинала для уровня')
    run = C.OUT / 'o4' / 'b2_loop'; rows = {}
    for l in (run / 'drive.tsv').read_text().splitlines()[1:]:
        c = l.split('\t'); rows[int(c[0])] = (float(c[1]), float(c[2]), float(c[3]), math.radians(float(c[4])))
    snaps = [dict(frame=0, pos=[215.054, 4.051, -170.248], yaw=-0.300, file=str(C.DATA / 'build/ps2ref/state_l1_incar.p2s'))]
    for f in sorted(int(p.stem[5:]) for p in run.glob('snap_*.p2s')):
        k = max(q for q in rows if q <= f); x, y, z, h = rows[k]
        snaps.append(dict(frame=f, pos=[x, y, z], yaw=h, file=str(run / f'snap_{f}.p2s')))
    ext = out_dir(level) / 'base_ext' / 'ext.json'
    if ext.exists(): snaps += json.loads(ext.read_text())['snaps']
    return dict(level=level, source='build/twins/o4/b2_loop' + (' + base_ext' if ext.exists() else ''), drive=str(run / 'drive.tsv'), snaps=snaps,
                ext_drive=str(out_dir(level) / 'base_ext' / 'drive.tsv') if ext.exists() else None)


def extend_base(level, start=21000, upto=24000, every=400, vmax=16.0):
    """продление базы: от снимка b2_loop кадра start дальше по следу той же поездки (её drive.tsv — точки пути), со снимками каждые
    every кадров: в b2_loop после 21000 снимков нет, а зоны l1z7 (кадр ~21470, ворота loader9) и l1r7 (~23680, loader8) грузились
    позже. -> base_ext/ (drive.tsv со сдвигом кадров к b2_loop, snap_*.p2s, ext.json)"""
    import drive as D
    run = C.OUT / 'o4' / 'b2_loop'; ed = out_dir(level) / 'base_ext'
    if (ed / 'ext.json').exists(): log('продление базы уже есть'); return json.loads((ed / 'ext.json').read_text())
    ed.mkdir(parents=True, exist_ok=True)
    trk = []
    for l in (run / 'drive.tsv').read_text().splitlines()[1:]:
        c = l.split('\t'); f = int(c[0])
        if start <= f <= upto + 400: trk.append((float(c[1]), float(c[2]), float(c[3])))
    pts = [trk[0]]
    for q in trk:
        if math.hypot(q[0] - pts[-1][0], q[2] - pts[-1][2]) >= 3.0: pts.append(q)
    o = orig_process(ed, run / f'snap_{start}.p2s', [], swthreads=2, lockstep=2, null=True)
    tsv = (ed / 'drive.tsv').open('w', buffering=1); tsv.write('кадр\tx\ty\tz\tкурс\tv\tиндекс\n')
    i = 0; stuck = 0; rev = 0; last = 0; snaps = []; t0 = time.time()
    while True:
        s = o.step()
        if s is None: break
        f = o.frame; x, z = s['x'], s['z']; h = math.atan2(s['nx'], s['nz']); v = math.hypot(s['vx'], s['vz'])
        best = min(range(i, min(len(pts), i + 40)), key=lambda k: (pts[k][0] - x) ** 2 + (pts[k][2] - z) ** 2)
        if best > i: i = best; last = f
        end = i >= len(pts) - 2 or f >= upto - start
        j = min(len(pts) - 1, i + 3); err = ang(math.atan2(pts[j][0] - x, pts[j][2] - z) - h)
        if rev > 0:
            rev -= 2; cmds = ['pad cross 0', 'pad circle 1', *D.axis('l', 'x', -1.0 if err > 0 else 1.0)]
            if rev <= 0: cmds = ['pad circle 0', *D.axis('l', 'x', 0.0)]
        else:
            st = max(-1.0, min(1.0, err * 2.5)); vt = vmax * max(0.35, math.cos(err))
            cmds = [*D.axis('l', 'x', st), f'pad cross {1 if v < vt else 0}', f'pad circle {1 if v > vt + 5 else 0}', 'f32 612114 0']
            stuck = stuck + 2 if v < 0.8 else 0
            if stuck >= 50 or f - last > 500: rev = 60; stuck = 0; last = f
        if f and f % every == 0:
            cmds.append(f"save {ed / f'snap_{start + f}.p2s'}"); snaps.append(dict(frame=start + f, pos=[x, s['y'], z], yaw=h, file=str(ed / f'snap_{start + f}.p2s'), ext=True))
        tsv.write(f"{start + f}\t{x:.2f}\t{s['y']:.2f}\t{z:.2f}\t{math.degrees(h):.1f}\t{v:.2f}\t{i}\n")
        if end: o.p.stdin.write('end\n'); o.p.stdin.flush(); break
        o.send(*cmds)
    o.close(); tsv.close()
    if o.bad: raise SystemExit(f'продление базы: сторож остановил PCSX2 ({o.bad})')
    info = dict(start=start, frames=o.frame, reached=i, of=len(pts), snaps=[sn for sn in snaps if Path(sn['file']).exists()],
                wall_s=round(time.time() - t0, 1), time=C.clock())
    (ed / 'ext.json').write_text(json.dumps(info, ensure_ascii=False, indent=1))
    log(f'продление базы: кадров {o.frame}, точек следа {i}/{len(pts)}, снимков {len(info["snaps"])}, {info["wall_s"]:.0f} с')
    return info


def base_sets(level, base):
    """набор регионов в памяти оригинала у каждого снимка базы: по воротам вдоль поездки; «надёжный» — тот, что был и за 1,5 с
    до снимка (подгрузка идёт ~1 с фоном)"""
    G = Gates(); bd = out_dir(level) / 'base'
    rows = []
    for l in Path(base.get('drive') or bd / 'drive.tsv').read_text().splitlines()[1:]:
        c = l.split('\t'); rows.append((int(c[0]), float(c[1]), float(c[2]), -float(c[3])))
    ev, _, _ = G.walk(rows, START_SET)
    def at(f, ev=ev, S0=START_SET):
        S = set(S0)
        for fe, Se, _ in ev:
            if fe <= f: S = Se
        return S
    ev2 = None
    if base.get('ext_drive'):   # продление: от набора у снимка старта продления, по своему следу
        rows2 = [(int(c[0]), float(c[1]), float(c[2]), -float(c[3])) for c in (l.split('\t') for l in Path(base['ext_drive']).read_text().splitlines()[1:])]
        S_ext0 = at(rows2[0][0]); ev2, _, _ = G.walk(rows2, S_ext0, G.inside(rows2[0][1], rows2[0][2], rows2[0][3]))
    out = []
    for sn in base['snaps']:
        f = sn['frame']
        if sn.get('ext') and ev2 is not None: full = at(f, ev2, S_ext0); safe = full & at(f - 75, ev2, S_ext0)
        else: full = at(f); safe = full & at(f - 75)
        inside = G.inside(sn['pos'][0], sn['pos'][1], -sn['pos'][2])
        out.append(dict(sn, full=sorted(full), safe=sorted(safe), inside=sorted(inside), file=sn.get('file') or str(bd / f'snap_{f}.p2s')))
    return out, ev


def required_regions(level, pts):
    """регионы, без которых в точке нет её города: куски level.shr с регионом в 12 м ∩ маска клетки REG1 (маска убирает
    «декорации издали» — регионы, которые оригинал отсюда не держит, tools/regions_export.py)"""
    import regions_export as RE, numpy as np
    lp = C.DATA / 'build' / ('level.shr' if level == 1 else f'levels/l{level}/level.shr')
    sec = RE.read_section(lp.read_bytes())
    for p in pts:
        need = set(p['regions'])
        if sec:
            gx = int(math.floor((p['x'] - sec['ox']) / sec['cell'])); gz = int(math.floor((p['z'] - sec['oz']) / sec['cell']))
            if 0 <= gx < sec['W'] and 0 <= gz < sec['H']:
                m = int(sec['mask'][gz, gx]); need &= {n for i, n in enumerate(sec['names']) if m >> i & 1}
        p['need'] = sorted(need)
    return pts


def rest_places(level, pts):
    """место покоя/набора курса R для каждой точки: ближайший перекрёсток дорог оригинала (открытое место на земле terra,
    грузится всегда), не ближе 12 м к точке; высота — опора порта у перекрёстка. -> p['R'] = (x, y, z порта)"""
    import traffic_export as te
    junc, _ = te.road_network(level)
    pr, _ = light(level, 'probe', [f'j{i} {j["pos"][0]:.3f} {j["pos"][2]:.3f}' for i, j in enumerate(junc)])
    J = []
    for j, q in zip(junc, pr):
        if not q['layers']: continue
        y = min(q['layers'], key=lambda L: abs(L[0] - j['pos'][1]))[0]
        J.append((j['pos'][0], y, j['pos'][2], j['name']))
    for p in pts:
        c = sorted(J, key=lambda q: math.hypot(q[0] - p['x'], q[2] - p['z']))
        r = next((q for q in c if math.hypot(q[0] - p['x'], q[2] - p['z']) >= 12), c[0])
        p['R'] = (r[0], r[1], r[2]); p['R_name'] = r[3]
    return pts


def plan_sessions(level, pts, snaps, per=5):
    """точки -> сессии оригинала: снимок базы, где регионы точки в памяти, ближайший
    к точке; не больше per точек на сессию (машина копит урон — после разбития сессия рвётся). -> (сессии, точки без снимка)"""
    G = Gates(); groups = {}; orphan = []
    for p in pts:
        best = None
        for k, sn in enumerate(snaps):
            if set(p['need']) <= set(sn['safe']):   # телепорт ворот не включает: нужен снимок, где регионы точки уже в памяти
                d = math.hypot(sn['pos'][0] - p['x'], -sn['pos'][2] - p['z'])
                if best is None or d < best[0]: best = (d, k)
        if best is None: orphan.append(p); continue
        groups.setdefault(best[1], []).append(p)
    sessions = []
    for k, ps in sorted(groups.items()):
        sn = snaps[k]; cur = (sn['pos'][0], -sn['pos'][2]); order = []
        rest = list(ps)
        while rest:
            q = min(rest, key=lambda p: math.hypot(p['x'] - cur[0], p['z'] - cur[1])); rest.remove(q); order.append(q); cur = (q['x'], q['z'])
        for i in range(0, len(order), per): sessions.append(dict(snap=k, points=order[i:i + per], part=i // per))
    sessions.sort(key=lambda s: (s['part'], s['snap']))   # по кругу снимков: недосчитанный прогон всё равно покрывает весь уровень
    return sessions, orphan


# ------------------------------------------------------------------ сторона оригинала целиком: сессии по плану, дозапись, повтор

def jsonl(path):
    return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()] if Path(path).exists() else []


def run_orig(level, budget_min=None, per=5, only=None, null=None, part=None):
    """все точки на оригинале: план сессий, пропуск готовых проб (orig.jsonl той же версии), обрыв сессии -> остаток в новую
    сессию (одна повторная попытка на точку). Пишет orig.jsonl по мере расчёта и plan.json."""
    od = out_dir(level); pts = load_points(level)
    if null is None: null = os.environ.get('PLACEMENT_RENDER', 'null') == 'null'   # без рисования (проверка: --stage nullcheck); кадры топа — отдельно
    if only: pts = [p for p in pts if p['id'] in only]
    base = base_info(level)
    snaps, _ = base_sets(level, base)
    pts = rest_places(level, required_regions(level, pts))
    pr, _ = light(level, 'probe', [f"{p['id']} {p['x']:.3f} {p['z']:.3f}" for p in pts])
    for p, q in zip(pts, pr):   # над опорой точки есть твёрдая поверхность (мост, навес, крыша; не крона) — спуск сверху её прошьёт
        L = q['layers']; li = len(L) - 1 - p['layer']
        p['overhead'] = any(L[i][2] == 0 and L[i][0] > p['y'] + 1.0 for i in range(len(L)) if i < li)
    sky = Sky(level)
    sessions, orphan = plan_sessions(level, pts, snaps, per)
    pf = od / ('plan.json' if 'PLACEMENT_ORIG_FILE' not in os.environ else 'plan_' + os.environ['PLACEMENT_ORIG_FILE'].replace('.jsonl', '.json'))
    pf.write_text(json.dumps(dict(time=C.clock(), version=VERSION, sessions=[dict(snap=snaps[s['snap']]['frame'],
        points=[p['id'] for p in s['points']]) for s in sessions], orphan=[dict(id=p['id'], need=p['need']) for p in orphan],
        snaps=[dict(frame=sn['frame'], pos=sn['pos'], safe=sn['safe']) for sn in snaps]), ensure_ascii=False, indent=1))
    log(f'план оригинала: {len(sessions)} сессий, точек {sum(len(s["points"]) for s in sessions)}, без снимка с нужной зоной {len(orphan)}')
    of = od / os.environ.get('PLACEMENT_ORIG_FILE', 'orig.jsonl')   # второй параллельный прогон пишет в свой файл (слить потом в orig.jsonl)
    prev = orig_records(level)
    done = {(r['point'], r['id'][-1]) for r in prev}
    yawA = {r['point']: r['before']['yaw'] for r in prev if r['id'].endswith('_A') and 'before' in r}
    t_start = time.time(); retry = {}
    # два прохода: A (курс какой есть: вперёд и назад) по всем точкам, потом B (+90°: две другие стороны) — недосчитанный прогон
    # всё равно даёт каждой точке постановку и две стороны разгона
    mine = [s for i, s in enumerate(sessions) if not part or i % part[1] == part[0] - 1]   # --part k/n: каждая n-я сессия (два PCSX2 рядом)
    queue = [dict(s, attempt=0, tag='A') for s in mine] + [dict(s, attempt=0, tag='B') for s in mine]
    n = 0
    while queue:
        if budget_min and time.time() - t_start > budget_min * 60: log(f'бюджет {budget_min} мин исчерпан: остальное — следующим запуском'); break
        ses = queue.pop(0); sn = snaps[ses['snap']]
        trials = []
        for p in ses['points']:
            # место покоя/набора курса — поза машины бота в самом снимке (там она ехала по дороге: земля и зоны точно есть);
            # 04.10: перекрёсток у Tomacco (197; −438) из снимка 21000 подбросил машину на 30 м и разбил её
            yo = p['y'] + CM_LIFT + DROP; Ro = (sn['pos'][0], sn['pos'][1] - 0.018 + DROP, sn['pos'][2])
            tag = ses['tag']
            if (p['id'], tag) in done: continue
            if tag == 'B' and p['id'] not in yawA: continue   # B ставится курсом A + 90°: без A нечего поворачивать
            trials.append(dict(id=f"{p['id']}_{tag}", point=p['id'], P=(p['x'], yo, -p['z']), R=Ro, air_R=True, air_P=not p['overhead'],
                               yaw_abs=ang(yawA[p['id']] + math.pi / 2) if tag == 'B' else None))
        if not trials: continue
        n += 1; sd = od / 'sessions' / (f"{C.stamp()}_s{sn['frame']}" + (f"_p{part[0]}" if part else ''))
        log(f"сессия {n} ({ses['tag']}): снимок кадра {sn['frame']}, точки {', '.join(p['id'] for p in ses['points'])} ({len(trials)} проб)")
        res, info = ps2_session(sd, sn['file'], trials, null=null, alt_fn=sky)
        if info['watchdog']: raise SystemExit(f'оригинал остановлен сторожем: {info["watchdog"]} — дальше не запускаю')
        chk = zone_check(level, sd, sn, {p['id']: p for p in ses['points']})
        for r in res:
            if r.get('broken'): continue
            r.update(version=VERSION, session=str(sd.relative_to(C.DATA)), snap=sn['frame'], zone=chk.get(r['id'], {}))
            fd = os.open(of, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)   # строка — одним вызовом записи (дозапись не рвётся)
            try: os.write(fd, (json.dumps(r, ensure_ascii=False) + '\n').encode())
            finally: os.close(fd)
            done.add((r['point'], r['id'][-1]))
            if r['id'].endswith('_A') and 'before' in r: yawA[r['point']] = r['before']['yaw']
        log(f"  готово проб {info['done']}/{len(trials)}, {info['frames']} кадров, {info['wall_s']:.0f} с ({info['fps']} к/с)" +
            (f"; обрыв: {info['abort']}" if info['abort'] else ''))
        if info['abort']:
            left = [p for p in ses['points'] if (p['id'], ses['tag']) not in done]
            for p in left: retry[p['id']] = retry.get(p['id'], 0) + 1
            again = [p for p in left if retry[p['id']] <= 1]
            if again: queue.insert(0, dict(ses, points=again, attempt=ses['attempt'] + 1))
    return sessions, orphan


def zone_check(level, sd, sn, pmap):
    """после сессии: набор регионов вдоль её трассы (въезды в ворота — и телепортом) -> у каждой пробы: все ли регионы точки были
    в памяти в начале покоя и не менялся ли набор за 1,5 с до него (подгрузка ещё шла)"""
    G = Gates(); rows = []; first = {}
    for l in (sd / 'trace.tsv').read_text().splitlines()[1:]:
        c = l.split('\t')
        rows.append((int(c[0]), float(c[3]), float(c[4]), -float(c[5])))
        if c[2] == 'settle' and c[1] not in first: first[c[1]] = int(c[0])
    ev, _, _ = G.walk(rows, sn['full'], sn['inside'])
    out = {}
    for tid, f0 in first.items():
        S = set(sn['full']); fresh = False
        for fe, Se, nm in ev:
            if fe <= f0: S = Se; fresh = fe > f0 - 75
        need = set(pmap[tid.rsplit('_', 1)[0]]['need'])
        out[tid] = dict(loaded=need <= S, missing=sorted(need - S), fresh=fresh)
    return out


def port_lines(r, ground, flip=False):
    """проба оригинала -> две пробы порта (оси порта): та же точка (начало модели = P минус смещение центра масс у оригинала в момент
    телепорта), ФАКТИЧЕСКИЙ курс оригинала в момент телепорта; y — опора точки + 0,3 (carPlace ищет опору вниз от y + 2).
    flip — отрицательный контроль гейта (курс порта на 180°: стороны разгона меняются местами)"""
    out = []
    for tag, b, settle, gas, mode in (('f', 'before', SETTLE_S, GAS_S, 'f'), ('r', 'before2', 1.0, GAS_S, 'r')):
        if b not in r or ('settled' if tag == 'f' else 'settled2') not in r: continue
        B = r[b]; dx, dz = B['cm'][0] - B['pos'][0], B['cm'][2] - B['pos'][2]
        x, z = r['P'][0] - dx, -(r['P'][2] - dz)
        h = C.port_h_of_yaw(B['yaw'] + (math.pi if flip else 0.0))
        out.append(f"{r['id']}{tag} {x:.4f} {ground + 0.3:.4f} {z:.4f} {h:.6f} {int(round(settle * PORT_FPS))} {int(round(gas * PORT_FPS))} {mode}")
    return out


# ------------------------------------------------------------------ сторона порта и сверка

REF_FIX = C.WT / 'tests/walls/ps2_ref_fix.json'


def ref_fixes(level, out):
    """исправления эталона (tests/walls/ps2_ref_fix.json, ДОБИВКА п. 11): сорванная проба основного orig.jsonl -> та же проба из
    другой записи PS2. Только если в эталоне лежит ровно известная сорванная строка (sha256 строки) и копия источника цела (sha256);
    трасса пробы — из копии в репо. Остальные пробы не трогаются. PLACEMENT_REF_FIX=0 — без исправлений (прежний эталон)"""
    if os.environ.get('PLACEMENT_REF_FIX', '1') == '0' or not REF_FIX.exists(): return out
    for fx in json.loads(REF_FIX.read_text())['fixes']:
        if fx['level'] != level or fx['id'] not in out: continue
        cur = hashlib.sha256(json.dumps(out[fx['id']], ensure_ascii=False).encode()).hexdigest()
        raw = [l.rstrip('\n') for l in (out_dir(level) / 'orig.jsonl').read_text().splitlines() if f'"id": "{fx["id"]}"' in l]
        if not raw or hashlib.sha256(raw[0].encode()).hexdigest() != fx['broken']['line_sha256']:
            log(f'исправление эталона {fx["id"]}: в orig.jsonl не та строка, что сорванная (перезаписан?) — не применяю'); continue
        line = (C.WT / fx['record']).read_text().splitlines()[0]
        if hashlib.sha256(line.encode()).hexdigest() != fx['record_line_sha256']:
            raise SystemExit(f'исправление эталона {fx["id"]}: копия {fx["record"]} не совпадает с sha источника')
        r = json.loads(line); r['session'] = str(C.WT / fx['session']); r['ref_fix'] = dict(was=cur[:16], source=fx['source']['file'])
        out[fx['id']] = r
    return out


def orig_records(level):
    """пробы оригинала этой версии: orig.jsonl + orig_*.jsonl (параллельные прогоны), без повторов по id (первая запись главная);
    затем исправления сорванных проб (ref_fixes)"""
    od = out_dir(level); out = {}
    for f in [od / 'orig.jsonl'] + sorted(od.glob('orig_*.jsonl')):
        for r in jsonl(f):
            if r.get('version') == VERSION and not r.get('broken') and r['id'] not in out: out[r['id']] = r
    return list(ref_fixes(level, out).values())


def orig_sha(level):
    h = hashlib.sha256()
    for r in sorted(orig_records(level), key=lambda r: r['id']): h.update(json.dumps(r, sort_keys=True, ensure_ascii=False).encode())
    return h.hexdigest()[:16]


def run_port(level, flip=False, out_name='port.jsonl'):
    """все пробы оригинала (orig.jsonl) -> те же пробы в мире ботов -> port.jsonl (пересчитывается целиком: детерминированно, секунды)"""
    od = out_dir(level); pts = {p['id']: p for p in load_points(level)}
    O = orig_records(level)
    L = []
    for r in O: L += port_lines(r, pts[r['point']]['y'], flip)
    if not L: log('порт: проб оригинала ещё нет'); return []
    t0 = time.time(); got, exe = light(level, 'run', L)
    inp = light_inputs(level)
    meta = dict(time=C.clock(), bin=exe, flip=flip, trials=len(got), wall_s=round(time.time() - t0, 2), code=C.git_head(),
                inputs={Path(f).name: C.sha256(f, 16) for f in (inp[0], inp[1], inp[3])})
    with (od / out_name).open('w') as fo:
        fo.write(json.dumps(dict(meta=meta), ensure_ascii=False) + '\n')
        for g in got: fo.write(json.dumps(g, ensure_ascii=False) + '\n')
    log(f'порт: проб {len(got)} за {meta["wall_s"]} с ({exe}) → {(od / out_name).relative_to(C.DATA)}')
    return got


VERD = ['совпало', 'порт пускает, PS2 нет', 'PS2 пускает, порт нет', 'выталкивает в разные стороны', 'разная опора (провал / крыша)',
        'неясно', 'не сверено']
VERD_SHORT = {'совпало': 'совп', 'порт пускает, PS2 нет': 'порт+', 'PS2 пускает, порт нет': 'PS2+', 'выталкивает в разные стороны': 'толчок',
              'разная опора (провал / крыша)': 'опора', 'неясно': '?', 'не сверено': 'н/с'}
STILL, PUSHED, DY, BLOCK_V, DPROG = 0.7, 1.2, 1.5, 1.0, 2.0


def _xz(a, b):
    return (b[0] - a[0], b[1] - a[1])


def verdict_place(o0, o1, ovmax, p0, p1, pvmax):
    """постановка: o0/p0 — куда ставили (x, z оригинала), o1/p1 — где после покоя (x, y, z оригинала); vmax — наибольшая скорость
    на покое (рывок). Вытолкнуло — сдвиг > PUSHED или рывок > 6 м/с; стоит — сдвиг < STILL и рывок < 3 м/с.
    Одна сторона выталкивает, другая оставляет на месте -> «пускает» та, что оставила (в ней машине там можно стоять)"""
    po = math.hypot(o1[0] - o0[0], o1[2] - o0[1]); pp = math.hypot(p1[0] - p0[0], p1[2] - p0[1]); dy = o1[1] - p1[1]
    d = dict(push_o=round(po, 2), push_p=round(pp, 2), dy=round(dy, 2), vmax_o=round(ovmax, 1), vmax_p=round(pvmax, 1))
    if abs(dy) > DY: return 'разная опора (провал / крыша)', d
    o_out, p_out = po > PUSHED or ovmax > 6, pp > PUSHED or pvmax > 6
    o_still, p_still = po < STILL and ovmax < 3, pp < STILL and pvmax < 3
    if o_still and p_still: return 'совпало', d
    if o_out and p_still: return 'порт пускает, PS2 нет', dict(d, why='PS2 выталкивает' + (' рывком' if ovmax > 6 else '') + ', порт оставляет')
    if p_out and o_still: return 'PS2 пускает, порт нет', dict(d, why='порт выталкивает' + (' рывком' if pvmax > 6 else '') + ', PS2 оставляет')
    if o_out and p_out:
        if po > 0.3 and pp > 0.3:
            vo = (o1[0] - o0[0], o1[2] - o0[1]); vp = (p1[0] - p0[0], p1[2] - p0[1])
            cos = (vo[0] * vp[0] + vo[1] * vp[1]) / (po * pp)
            if cos < 0.5: return 'выталкивает в разные стороны', dict(d, why=f'угол между сдвигами {math.degrees(math.acos(max(-1, min(1, cos)))):.0f}°')
        if abs(po - pp) > 2.5: return 'выталкивает в разные стороны', dict(d, why='сдвиг на разное расстояние')
        return 'совпало', d
    return 'неясно', d


def verdict_move(o_prog, o_v, p_prog, p_v):
    """разгон: прогресс вдоль курса (м, со знаком стороны) и скорость в конце вдоль стороны (м/с); упёрся — скорость < BLOCK_V"""
    ob, pb = o_v < BLOCK_V, p_v < BLOCK_V
    d = dict(prog_o=round(o_prog, 2), prog_p=round(p_prog, 2), v_o=round(o_v, 2), v_p=round(p_v, 2), blk_o=ob, blk_p=pb)
    if not ob and not pb: return 'совпало', d
    if ob and pb:
        if abs(p_prog - o_prog) <= DPROG: return 'совпало', d
        return ('порт пускает, PS2 нет' if p_prog > o_prog else 'PS2 пускает, порт нет'), dict(d, why='оба упёрлись, но на разном месте')
    if ob and not pb: return ('порт пускает, PS2 нет', dict(d, why='PS2 упёрлась, порт едет')) if p_prog > o_prog + 1.0 else ('неясно', d)
    return ('PS2 пускает, порт нет', dict(d, why='порт упёрся, PS2 едет')) if o_prog > p_prog + 1.0 else ('неясно', d)


def settle_vmax(sd, tid, phase, ls=None):
    """наибольшая скорость оригинала на покое пробы по сдвигу позиции между строками трассы сессии (м/с, 3D); первые 2 строки после
    телепорта не в счёт"""
    rows = []
    for l in (C.DATA / sd / 'trace.tsv').read_text().splitlines()[1:]:
        c = l.split('\t')
        if c[1] == tid and c[2] == phase: rows.append((int(c[0]), float(c[3]), float(c[4]), float(c[5])))
    vm = 0.0
    for a, b in zip(rows[2:], rows[3:]):
        dt = (b[0] - a[0]) / ORIG_FPS
        if dt > 0: vm = max(vm, math.dist(a[1:], b[1:]) / dt)
    return vm


def port_vmax(g):
    """то же у порта: трасса покоя (каждые 6 кадров), первые 2 строки не в счёт"""
    t = g['trace']; vm = 0.0
    for a, b in zip(t[2:], t[3:]):
        dt = (b[0] - a[0]) / PORT_FPS
        if dt > 0: vm = max(vm, math.dist(a[1:4], b[1:4]) / dt)
    return vm


def compare(level, port_name='port.jsonl'):
    """сверка по пробам и точкам -> compare.tsv (по точке), trials.tsv (по проверке), summary.json"""
    od = out_dir(level); pts = {p['id']: p for p in load_points(level)}
    O = orig_records(level)
    PL = jsonl(od / port_name); meta = PL[0].get('meta', {}) if PL else {}
    Pm = {g['id']: g for g in PL[1:]}
    rows = []; by_pt = {}
    for r in O:
        p = pts[r['point']]; zone = r.get('zone') or {}
        for tag, b, sk, gk, phs, sgn in (('f', 'before', 'settled', 'gassed', 'settle', 1), ('r', 'before2', 'settled2', 'reversed', 'settle2', -1)):
            g = Pm.get(r['id'] + tag)
            if b not in r or sk not in r or g is None: continue
            B = r[b]; cm_dx, cm_dz = B['cm'][0] - B['pos'][0], B['cm'][2] - B['pos'][2]
            o0 = (r['P'][0] - cm_dx, r['P'][2] - cm_dz)
            o1 = r[sk]['pos']; lift = g['lift']
            p0 = (g['ask'][0], -g['ask'][2]); p1 = (g['settled']['x'], g['settled']['y'] + lift, -g['settled']['z'])
            ovm = settle_vmax(r['session'], r['id'], phs)
            pvm = port_vmax(g)
            if zone and not zone.get('loaded', True):
                vp, dp = 'не сверено', dict(why='регион точки не в памяти оригинала: ' + ','.join(zone.get('missing', [])))
            elif p['code'] == '--': vp, dp = 'не сверено', dict(why='точка вне карты уровня')
            else: vp, dp = verdict_place(o0, o1, ovm, p0, p1, pvm)
            rows.append(dict(point=p['id'], trial=r['id'] + tag, test='постановка' if tag == 'f' else 'постановка 2', verdict=vp, **dp,
                             yaw_o=round(math.degrees(B['yaw'])), code=p['code']))
            by_pt.setdefault(p['id'], []).append(rows[-1])
            if gk in r:
                yo = r[sk]['yaw']; ox, oz = r[gk]['pos'][0] - o1[0], r[gk]['pos'][2] - o1[2]
                o_prog = (ox * math.sin(yo) + oz * math.cos(yo)) * sgn
                o_v = (r[gk].get('va', r[gk]['v'] * (1 if o_prog > 0 else -1) * sgn)) * sgn
                hp = g['settled']['h']; px, pz = g['gassed']['x'] - g['settled']['x'], g['gassed']['z'] - g['settled']['z']
                p_prog = (px * math.sin(hp) + pz * math.cos(hp)) * sgn; p_v = g['gassed']['v'] * sgn
                gap = math.hypot(o1[0] - p1[0], o1[2] - p1[2])   # где стояли обе машины перед разгоном
                if zone and not zone.get('loaded', True): vm, dm = 'не сверено', dict(why='регион не в памяти оригинала')
                elif p['code'] == '--': vm, dm = 'не сверено', dict(why='точка вне карты уровня')
                elif gap > 3.0 or abs(o1[1] - p1[1]) > DY:
                    vm, dm = 'неясно', dict(prog_o=round(o_prog, 2), prog_p=round(p_prog, 2), v_o=round(o_v, 2), v_p=round(p_v, 2),
                                            why=f'разгон с разных мест: машины перед ним в {gap:.1f} м')
                else: vm, dm = verdict_move(o_prog, o_v, p_prog, p_v)
                rows.append(dict(point=p['id'], trial=r['id'] + tag, test='разгон вперёд' if tag == 'f' else 'разгон назад', verdict=vm, **dm,
                                 yaw_o=round(math.degrees(yo)), code=p['code']))
                by_pt[p['id']].append(rows[-1])
    PT = []
    for pid, rs in by_pt.items():
        p = pts[pid]; mm = [x for x in rs if x['verdict'] not in ('совпало', 'неясно', 'не сверено')]
        if all(x['verdict'] == 'не сверено' for x in rs): cat = 'не сверено'
        elif not mm: cat = 'совпало' if any(x['verdict'] == 'совпало' for x in rs) else 'неясно'
        else:
            cnt = {}
            for x in mm: cnt[x['verdict']] = cnt.get(x['verdict'], 0) + 1
            cat = max(cnt, key=lambda k: (cnt[k], -VERD.index(k)))
        sev = 0.0
        for x in mm:
            sev += abs(x.get('prog_p', 0) - x.get('prog_o', 0)) if 'prog_o' in x else max(abs(x.get('push_o', 0) - x.get('push_p', 0)), abs(x.get('dy', 0)), abs(x.get('vmax_o', 0) - x.get('vmax_p', 0)) / 3)
        PT.append(dict(id=pid, kind=p['kind'], code=p['code'], x=p['x'], z=p['z'], y=p['y'], cat=cat, n=len(rs), mism=len(mm), sev=round(sev, 2),
                       tests=' '.join(f"{x['test'].replace('постановка', 'пост').replace('разгон ', '')}:{VERD_SHORT[x['verdict']]}" for x in rs)))
    plan = json.loads((od / 'plan.json').read_text()) if (od / 'plan.json').exists() else {}
    orph = {o['id']: o['need'] for o in plan.get('orphan', [])}
    for pid, p in pts.items():   # точки без проб: нет снимка оригинала с их регионами / ещё не дошла очередь
        if pid in by_pt: continue
        why = f"нет снимка оригинала с регионами {','.join(orph[pid])}" if pid in orph else 'ещё не прогнана на оригинале'
        PT.append(dict(id=pid, kind=p['kind'], code=p['code'], x=p['x'], z=p['z'], y=p['y'], cat='не сверено', n=0, mism=0, sev=0.0, tests=why))
    PT.sort(key=lambda q: (-q['sev'], q['id']))
    with (od / 'trials.tsv').open('w') as fo:
        keys = ['point', 'trial', 'code', 'test', 'verdict', 'yaw_o', 'push_o', 'push_p', 'dy', 'vmax_o', 'vmax_p', 'prog_o', 'prog_p', 'v_o', 'v_p', 'why']
        fo.write('\t'.join(keys) + '\n')
        for x in rows: fo.write('\t'.join(str(x.get(k, '')) for k in keys) + '\n')
    with (od / 'compare.tsv').open('w') as fo:
        fo.write('id\tвид\tклетка\tx\tz\tигра_z\tитог\tпроверок\tрасхождений\tтяжесть\tпроверки\n')
        for q in PT: fo.write(f"{q['id']}\t{q['kind']}\t{q['code']}\t{q['x']}\t{q['z']}\t{-q['z']}\t{q['cat']}\t{q['n']}\t{q['mism']}\t{q['sev']}\t{q['tests']}\n")
    summ = dict(time=C.clock(), version=VERSION, port=meta, points=len(PT), trials=len(rows),
                by_point={k: sum(1 for q in PT if q['cat'] == k) for k in VERD},
                by_test={k: sum(1 for x in rows if x['verdict'] == k) for k in VERD},
                mismatch_points=sum(1 for q in PT if q['cat'] not in ('совпало', 'неясно', 'не сверено')),
                mismatch_tests=sum(1 for x in rows if x['verdict'] not in ('совпало', 'неясно', 'не сверено')),
                points_list={q['id']: q['cat'] for q in PT})
    (od / ('summary.json' if port_name == 'port.jsonl' else 'summary_' + port_name.replace('.jsonl', '.json'))).write_text(json.dumps(summ, ensure_ascii=False, indent=1))
    return PT, rows, summ


# ------------------------------------------------------------------ итог для Роба: карта, пары кадров, отчёт

COL = {'совпало': (46, 160, 67), 'порт пускает, PS2 нет': (220, 40, 40), 'PS2 пускает, порт нет': (40, 90, 230),
       'выталкивает в разные стороны': (245, 140, 0), 'разная опора (провал / крыша)': (150, 60, 190), 'неясно': (150, 150, 150),
       'не сверено': (200, 200, 200)}


def draw_map(level, PT, top, path, px_per_m=1.25):
    """вид сверху: город уровня бледными цветами текстур (как tools/place.py --sheet), сетка кодов мест (viewer/placecode.h),
    точки цветом по итогу сверки, топ — номерами"""
    import numpy as np, shr7read, place
    from PIL import Image, ImageDraw, ImageFont
    lp = C.DATA / 'build' / ('level.shr' if level == 1 else f'levels/l{level}/level.shr')
    L = shr7read.load(lp); means = place.tex_means(lp.read_bytes())
    P = L['P']; keep = (L['FL'] & 4) == 0
    xs, zs = P[keep][:, :, 0], P[keep][:, :, 2]
    x0, x1 = float(np.percentile(xs, 0.2)) - 30, float(np.percentile(xs, 99.8)) + 30
    z0, z1 = float(np.percentile(zs, 0.2)) - 30, float(np.percentile(zs, 99.8)) + 30
    PAD, LEG = 46, 250
    W, H = int((x1 - x0) * px_per_m) + 2 * PAD, int((z1 - z0) * px_per_m) + 2 * PAD + LEG
    img = Image.new('RGB', (W, H), (244, 242, 236)); dr = ImageDraw.Draw(img)
    ex = lambda x: PAD + (x - x0) * px_per_m; ez = lambda z: PAD + (z - z0) * px_per_m
    pale = lambda c: tuple(int(v * .45 + 244 * .55) for v in c)
    for i in np.argsort(P[:, :, 1].max(1)):
        if not keep[i] or L['TEX'][i] < 0: continue
        q = P[i]; dr.polygon([(ex(q[k, 0]), ez(q[k, 2])) for k in range(3)], fill=pale(means[L['TEX'][i]]))
    def font(sz, bold=False):
        try: return ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Bold.ttf' if bold else '/System/Library/Fonts/Supplemental/Arial.ttf', sz)
        except OSError: return ImageFont.load_default()
    f_big, f_mid, f_sm = font(22, True), font(15, True), font(13)
    X0, Z0, CELL = place.X0, place.Z0, place.CELL
    for c in range(int(math.floor((x0 - X0) / CELL)), int(math.ceil((x1 - X0) / CELL)) + 1):
        X = ex(X0 + c * CELL)
        if PAD <= X <= W - PAD: dr.line([X, PAD, X, H - PAD - LEG], fill=(200, 70, 50), width=2)
        for k in (1, 2):
            xx = ex(X0 + (c + k / 3) * CELL)
            if PAD <= xx <= W - PAD: dr.line([xx, PAD, xx, H - PAD - LEG], fill=(232, 190, 180), width=1)
        xc = ex(X0 + (c + .5) * CELL)
        if 0 <= c < len(place.LETTERS) and PAD <= xc <= W - PAD:
            dr.text((xc - 7, 10), place.LETTERS[c], fill=(200, 70, 50), font=f_big); dr.text((xc - 7, H - LEG - PAD + 10), place.LETTERS[c], fill=(200, 70, 50), font=f_big)
    for r in range(int(math.floor((z0 - Z0) / CELL)), int(math.ceil((z1 - Z0) / CELL)) + 1):
        Z = ez(Z0 + r * CELL)
        if PAD <= Z <= H - PAD - LEG: dr.line([PAD, Z, W - PAD, Z], fill=(200, 70, 50), width=2)
        for k in (1, 2):
            zz = ez(Z0 + (r + k / 3) * CELL)
            if PAD <= zz <= H - PAD - LEG: dr.line([PAD, zz, W - PAD, zz], fill=(232, 190, 180), width=1)
        zc = ez(Z0 + (r + .5) * CELL)
        if 0 <= r < place.ROWS and PAD <= zc <= H - PAD - LEG:
            dr.text((8, zc - 12), str(r + 1), fill=(200, 70, 50), font=f_big); dr.text((W - PAD + 8, zc - 12), str(r + 1), fill=(200, 70, 50), font=f_big)
    rank = {q['id']: i + 1 for i, q in enumerate(top)}
    for q in sorted(PT, key=lambda q: (q['id'] in rank, q['cat'] != 'совпало')):
        X, Z = ex(q['x']), ez(q['z']); c = COL[q['cat']]; r_ = 7 if q['id'] in rank else 5
        dr.ellipse([X - r_, Z - r_, X + r_, Z + r_], fill=c, outline=(30, 30, 30), width=1)
    boxes = []
    for q in top:
        X, Z = ex(q['x']), ez(q['z']); t = f"{rank[q['id']]} {q['code']}"; tw = dr.textlength(t, font=f_mid); ty = Z - 10
        while any(X + 9 < b[2] and b[0] < X + 13 + tw and ty < b[3] and b[1] < ty + 19 for b in boxes): ty += 19
        if ty != Z - 10: dr.line([X, Z, X + 9, ty + 9], fill=(30, 30, 30))
        dr.rectangle([X + 9, ty, X + 13 + tw, ty + 19], fill=(255, 255, 255), outline=COL[q['cat']], width=2)
        dr.text((X + 11, ty + 1), t, fill=(20, 20, 20), font=f_mid); boxes.append((X + 9, ty, X + 13 + tw, ty + 19))
    # легенда
    ly = H - LEG + 6; dr.rectangle([PAD, ly, W - PAD, H - 10], fill=(255, 255, 255), outline=(180, 180, 180))
    dr.text((PAD + 14, ly + 10), f'L{level} · постановка машины: оригинал PS2 против порта · {len(PT)} точек', fill=(20, 20, 20), font=f_big)
    yy = ly + 46
    for i, k in enumerate(VERD):
        n = sum(1 for q in PT if q['cat'] == k)
        cx = PAD + 20 + (i % 2) * ((W - 2 * PAD) // 2); cy = yy + (i // 2) * 30
        dr.ellipse([cx, cy, cx + 16, cy + 16], fill=COL[k], outline=(30, 30, 30)); dr.text((cx + 26, cy - 1), f'{k}: {n}', fill=(20, 20, 20), font=f_mid)
    dr.text((PAD + 14, H - 40), 'Квадрат 100 м: буква по x + номер ряда; участок 33 м — цифра 1–9 как на телефоне (1 2 3 сверху). Номер у точки — место в топе ОТЧЁТ.md.',
            fill=(70, 70, 70), font=f_sm)
    path.parent.mkdir(parents=True, exist_ok=True); img.save(path)
    return path


def worst_test(rows, pid):
    mm = [x for x in rows if x['point'] == pid and x['verdict'] not in ('совпало', 'неясно', 'не сверено')]
    def sev(x): return abs(x.get('prog_p', 0) - x.get('prog_o', 0)) if 'prog_o' in x else max(abs(x.get('push_o', 0) - x.get('push_p', 0)), abs(x.get('dy', 0)), abs(x.get('vmax_o', 0) - x.get('vmax_p', 0)) / 3)
    return max(mm, key=sev) if mm else None


def port_full_shots(level, items, rd):
    """тот же опыт в полном порту: EBOOT в своём PPSSPPHeadless (port.py), один запуск, сценарий goto → покой → (газ/назад) → снимок
    на каждую точку топа. -> {номер: (png, поза SHOT)}"""
    import port
    lines = ['scene twins']
    for n, it in items:
        g = it['g']; x, z, h = g['ask'][0], g['ask'][2], g['ask'][3]
        lines += [f'goto {x:.3f} {z:.3f} {h:.5f}', 'wait 2.5']
        if it['test'].startswith('разгон'):
            if it['test'].endswith('назад'): lines[-1] = 'wait 1.0'
            lines += [f"press {'circle' if it['test'].endswith('назад') else 'cross'} 1.5", 'wait 1.5']
        lines.append(f'shot top{n:02d}')
    lines += ['end', '']
    run = rd / '_port_full'; run.mkdir(parents=True, exist_ok=True)
    d, man = port.stage_full(run, 'top', '\n'.join(lines), 0)
    home = C.OUT / 'ppsspp_home'; home.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, HOME=str(home), TWINS_SMOKE=str(d / 'smoke.txt'), TWINS_SHOTDIR=str(d), DYLD_FRAMEWORK_PATH=str(C.BIN), SDL_AUDIODRIVER='dummy')
    for k in ('XDG_CONFIG_HOME', 'XDG_DATA_HOME'): env.pop(k, None)
    with (d / 'headless.log').open('w') as lg:
        pr = subprocess.Popen([str(port.HEADLESS), '--graphics=software', '--timeout=1500', str(d / 'EBOOT.PBP')], cwd=d, env=env, stdout=lg, stderr=subprocess.STDOUT)
        bad = port.watch_no_window(pr, 1600)
    if bad: log(f'полный порт: {bad}'); return {}
    smk = (d / 'smoke.txt').read_text(errors='replace') if (d / 'smoke.txt').exists() else ''
    out = {}
    for m in re.finditer(r'^SHOT top(\d+) ([\d.]+) pos (\S+) (\S+) (\S+) (\S+)', smk, re.M):
        n = int(m.group(1)); bmp = d / f'top{n:02d}.bmp'; png = run / f'top{n:02d}_port.png'
        if bmp.exists(): port.bmp_to_png(bmp, png)
        out[n] = (png if png.exists() else None, [float(v) for v in m.groups()[2:]])
    return out


def orig_shots(level, items, rd):
    """кадры оригинала для топа: те же пробы ещё раз с программным рисованием (массовый прогон шёл без рисования — проверка
    --stage nullcheck), тот же снимок старта, та же точка, курс пробы набирается на месте покоя. -> {номер: (папка сессии, id пробы, сдвиг
    позы после покоя от массового прогона, м)}"""
    base = base_info(level); snaps, _ = base_sets(level, base); byf = {sn['frame']: sn for sn in snaps}
    groups = {}
    for n, it in items:
        r = it['r']; sn = byf[r['snap']]; key = 'before' if it['w']['trial'].endswith('f') else 'before2'
        Ro = (sn['pos'][0], sn['pos'][1] - 0.018 + DROP, sn['pos'][2])
        groups.setdefault(r['snap'], []).append((n, dict(id=f"top{n:02d}_{r['id']}", point=f'top{n:02d}', P=tuple(r['P']), R=Ro,
                                                          yaw_abs=r[key]['yaw'] if key in r else r['before']['yaw'], air_P=r.get('air', True)), r))
    out = {}
    for f, lst in sorted(groups.items()):
        sd = rd / '_orig_shots' / f's{f}'
        if sd.exists(): shutil.rmtree(sd)
        log(f'кадры оригинала для топа: снимок {f}, проб {len(lst)}')
        res, info = ps2_session(sd, byf[f]['file'], [t for _, t, _ in lst], png=True, null=False, alt_fn=Sky(level))
        got = {x['id']: x for x in res}
        for n, t, r in lst:
            x = got.get(t['id']); d = None
            if x and 'settled' in x and 'settled' in r: d = round(math.dist(x['settled']['pos'], r['settled']['pos']), 2)
            out[n] = (sd, t['id'], d)
    return out


def pair_image(o_png, p_png, title, sub, path):
    from PIL import Image, ImageDraw, ImageFont
    W = 480 * 2 + 30; Hh = 58 + 336 + 28
    img = Image.new('RGB', (W, Hh), (250, 249, 245)); dr = ImageDraw.Draw(img)
    try: f1 = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Bold.ttf', 17); f2 = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 14)
    except OSError: f1 = f2 = ImageFont.load_default()
    dr.text((10, 8), title, fill=(20, 20, 20), font=f1); dr.text((10, 32), sub, fill=(70, 70, 70), font=f2)
    for k, (pth, lab) in enumerate(((o_png, 'оригинал PS2'), (p_png, 'порт (EBOOT в эмуляторе PSP)'))):
        x = 10 + k * 490
        if pth and Path(pth).exists():
            im = Image.open(pth).convert('RGB'); im.thumbnail((480, 336)); img.paste(im, (x, 58))
        else: dr.rectangle([x, 58, x + 480, 58 + 272], outline=(180, 180, 180)); dr.text((x + 10, 70), 'кадра нет', fill=(120, 120, 120), font=f2)
        dr.text((x + 4, Hh - 18), lab, fill=(60, 60, 60), font=f2)
    path.parent.mkdir(parents=True, exist_ok=True); img.save(path)


def build_report(level, ntop=20, shots=True):
    od = out_dir(level); rd = report_dir(level); rd.mkdir(parents=True, exist_ok=True)
    PT, rows, summ = compare(level)
    if not PT: log('отчёт: сверять нечего'); return
    pts = {p['id']: p for p in load_points(level)}
    O = {r['id']: r for r in orig_records(level)}
    Pm = {g['id']: g for g in jsonl(od / 'port.jsonl')[1:]}
    top = [q for q in PT if q['cat'] not in ('совпало', 'неясно', 'не сверено')][:ntop]
    items = []
    for n, q in enumerate(top, 1):
        w = worst_test(rows, q['id']); tid = w['trial']; r = O[tid[:-1]]; g = Pm[tid]
        suf = {'постановка': '_s', 'разгон вперёд': '_g', 'постановка 2': '_s2', 'разгон назад': '_r'}[w['test']]
        o_png = C.DATA / r['session'] / 'png' / (r['id'] + suf + '.png')
        if not o_png.exists() and suf == '_s2': o_png = C.DATA / r['session'] / 'png' / (r['id'] + '_r.png')
        items.append((n, dict(q=q, w=w, r=r, g=g, test=w['test'], o_png=o_png)))
    full = port_full_shots(level, items, rd) if shots and items else {}
    nsh = int(os.environ.get('PLACEMENT_ORIG_SHOTS', '10'))   # кадры оригинала — повтор с рисованием, по умолчанию первые 10 (минуты на загруженном Маке)
    osh = orig_shots(level, items[:nsh], rd) if shots and items else {}
    pd = rd / 'пары'; pd.mkdir(exist_ok=True)
    for n, it in items:
        q, w = it['q'], it['w']
        if n in osh:
            sd, tid, d = osh[n]; suf = it['o_png'].name.split(it['r']['id'])[-1]
            cand = sd / 'png' / (tid + suf)
            if cand.exists(): it['o_png'] = cand; it['orig_repeat'] = d
        sub = f"{w['test']}: {w['verdict']}" + (f" ({w['why']})" if w.get('why') else '')
        pair_image(it['o_png'], (full.get(n) or (None,))[0], f"{n}. L{level} {q['code']} · {KIND_RU.get(q['kind'], q['kind'])} · движок x {q['x']:.0f} z {q['z']:.0f} (игра z {-q['z']:.0f})", sub, pd / f'{n:02d}_{q["code"]}_{q["id"]}.png')
        it['pair'] = f'пары/{n:02d}_{q["code"]}_{q["id"]}.png'; it['full'] = full.get(n)
    draw_map(level, PT, top, rd / 'карта.png')
    for f in ('compare.tsv', 'trials.tsv', 'points.tsv', 'summary.json'): shutil.copy2(od / f, rd / f)
    write_md(level, rd, PT, rows, summ, items)
    log(f'отчёт: {(rd / "ОТЧЁТ.md").relative_to(C.DATA)}, карта {(rd / "карта.png").relative_to(C.DATA)}, пар {len(items)}')


def describe(w):
    t = w['test']
    if t.startswith('разгон'):
        dirn = 'вперёд' if t.endswith('вперёд') else 'назад'
        so = f"PS2 {'упёрлась' if w['blk_o'] else 'едет'} через {w['prog_o']:.1f} м" ; sp = f"порт {'упёрся' if w['blk_p'] else 'едет'} через {w['prog_p']:.1f} м"
        return f"газ {dirn} 1,5 с: {so}, {sp}"
    return (f"после 2,5 с покоя: PS2 сдвинуло на {w['push_o']:.1f} м, порт — на {w['push_p']:.1f} м; высоты расходятся на {w['dy']:+.1f} м"
            + (f"; рывок до {w['vmax_o']:.0f} / {w['vmax_p']:.0f} м/с" if max(w['vmax_o'], w['vmax_p']) > 3 else ''))


def write_md(level, rd, PT, rows, summ, items):
    bp = summ['by_point']; bt = summ['by_test']; pm = summ.get('port') or {}
    od = out_dir(level)
    nc = json.loads((od / 'nullcheck' / 'result.json').read_text()) if (od / 'nullcheck' / 'result.json').exists() else {}
    pl = playable_file(level)
    ran = sum(1 for q in PT if q['n']); never = [q for q in PT if not q['n']]
    full_ok = [it for _, it in items if it.get('full') and it['full'][1]]
    def agree(it):   # полный EBOOT против мира ботов: та же поза в конце опыта (оси порта)
        g = it['g']; k = 'gassed' if it['test'].startswith('разгон') else 'settled'
        return math.hypot(it['full'][1][0] - g[k]['x'], it['full'][1][2] - g[k]['z'])
    L = [f'# Сверка PS2 и PSP · уровень {level} · постановка машины', '',
         f'Собрано (date): {C.clock()}. Порт: код {pm.get("code", "?")}, мир ботов `{pm.get("bin", "?")}`, данные {pm.get("inputs", {})}.', '',
         '**Что делали.** В каждой точке одинаково на обеих сторонах: ставим машину (та же точка, тот же курс), 2,5 с без кнопок — куда',
         'вытолкнет и где встанет; потом 1,5 с газа вперёд; потом снова в ту же точку и 1,5 с назад. Курса два: какой вышел и +90°, —',
         'на точку четыре постановки и четыре стороны разгона. Оригинал — наш PCSX2 без окна и звука, порт — мир ботов (тот же код',
         'машины и коллизии, что EBOOT); для топа тот же опыт повторён в самом EBOOT в эмуляторе PSP (кадры справа в парах).', '',
         f'Точек в наборе: **{len(PT)}**, прогнано на оригинале: **{ran}**, проверок: {summ["trials"]}.', '',
         '| итог по точке | точек | проверок |', '|---|---|---|']
    for k in VERD: L.append(f'| {k} | {bp.get(k, 0)} | {bt.get(k, 0)} |')
    L += ['', '- **порт пускает, PS2 нет** — в порту машина проезжает (или спокойно стоит), а оригинал упирается (или выталкивает).',
          '- **PS2 пускает, порт нет** — наоборот: в оригинале проезд есть, порт упирается или выталкивает.',
          '- **выталкивает в разные стороны** — обе стороны сдвигают машину, но в разные стороны или на разное расстояние.',
          '- **разная опора** — после покоя машины на разной высоте (больше 1,5 м): провал, крыша, ступень.',
          '- **неясно** — между порогами (например, порт ещё не доехал до места, где упёрся оригинал); **не сверено** — нет проб.', '',
          '![карта](карта.png)', '', f'## Топ-{len(items)}: где порт сильнее всего расходится с оригиналом', '',
          '| № | клетка | место | движок x, z (игра z) | что не так | кадры |', '|---|---|---|---|---|---|']
    for n, it in items:
        q, w = it['q'], it['w']
        L.append(f"| {n} | **{q['code']}** | {KIND_RU.get(q['kind'], q['kind'])} | {q['x']:.0f}, {q['z']:.0f} ({-q['z']:.0f}) | "
                 f"{w['verdict']}: {describe(w)} | [пара]({it['pair']}) |")
    L += ['']
    for n, it in items:
        rep = it.get('orig_repeat'); fa = agree(it) if it.get('full') and it['full'][1] else None
        L += [f"### {n}. {it['q']['code']} · {it['q']['id']}", '', f"![{n}]({it['pair']})", '',
              f"Источник точки: {next((p['src'] for p in load_points(level) if p['id'] == it['q']['id']), '?')}. "
              f"Кадр оригинала — повтор той же пробы с рисованием" + (f" (поза после покоя отличается от массового прогона на {rep:.1f} м)" if rep is not None else '') +
              (f"; EBOOT против мира ботов — {fa:.1f} м в конце опыта." if fa is not None else '.'), '']
    cnt = {}
    for q in PT:
        if not q['n']: continue
        c = cnt.setdefault(q['kind'], [0, 0]); c[1] += 1
        if q['cat'] not in ('совпало', 'неясно', 'не сверено'): c[0] += 1
    L += ['## Где расхождения по видам мест', '', '| вид места | расходится / прогнано |', '|---|---|']
    for k, (a, b) in sorted(cnt.items(), key=lambda kv: -kv[1][0] / max(1, kv[1][1])): L.append(f'| {KIND_RU.get(k, k)} | {a} / {b} |')
    L += ['', '## Что важно знать про сам опыт', '',
          '- [PS2] Машину в оригинале ставим записью тела (центр масс и скорость — адреса «можно»). Дальний телепорт напрямую тащит',
          '  машину сквозь дома по пути: на месте телепорта «Burns\' Mansion» её сдвигало на 10,6 м рывком 106 м/с, а та же точка',
          '  телепортом «по воздуху» (вверх, по прямой над городом, вниз) — 0,16 м, с 5 м по земле — 0,08 м',
          '  (build/twins/placement/l1/_v1_direct_teleport/_airtest). Поэтому протокол v2: дальние телепорты по воздуху; первый прогон',
          '  (v1, прямой) отложен в _v1_direct_teleport и в сверку не входит. Над точкой мост или навес — спуск сверху их прошьёт,',
          '  там телепорт прямой (поле air в пробах).',
          f"- [PS2] Пробы шли без рисования (в 1,7 раза быстрее); проверка: тот же рецепт с рисованием и без — трасса байт в байт "
          f"({'PASS' if nc.get('ok') else 'нет проверки'}, build/twins/placement/l1/nullcheck/result.json). Кадры топа — повтор с рисованием.",
          '- [PS2] Город оригинала грузится воротами при езде, телепорт зон не грузит (tw_b2_hops). Старты — снимки поездки бота',
          '  b2_loop и её продления; пробу берём только со снимка, где регионы точки уже в памяти.'
          + (f' Не сверено из-за этого: {sum(1 for q in never if "регионами" in q["tests"])} точек (регион l1r4b не грузился ни в одной поездке).' if never else ''),
          '- [PS2] Машина оригинала копит урон; разбилась (Гомер вышел) — сессия рвётся, точка повторяется с нового снимка (одна попытка).',
          '- [порт] Порт ставится в ФАКТИЧЕСКИЙ курс и точку оригинала в момент телепорта; мир ботов детерминирован — повтор даёт те же числа.',
          f'- Точки: из данных уровня (дороги трафика и срезки ИИ, трамплины, места телепорта, тупики, стоянки, заборы и изгороди коллизии,'
          f' стены-ящики, мосты, сетка 40 м) и края зелёного карты проезжих клеток помощника по ботам'
          + (f' ({pl.name}, {time.strftime("%d.%m %H:%M", time.localtime(pl.stat().st_mtime))})' if pl else '') + '.', '',
          '## Осторожно с цифрами и что не успели', '',
          f"- Прогон частичный: проход A (курс какой вышел: вперёд и назад) — {len({r['point'] for r in orig_records(level) if r['id'].endswith('_A')})} точек, "
          f"проход B (+90°: две другие стороны) — {len({r['point'] for r in orig_records(level) if r['id'].endswith('_B')})}. Продолжение — та же команда (готовые пробы не пересчитываются).",
          '- Рывки в сотни м/с и сдвиги в десятки метров у оригинала — чаще всего машина вошла в твёрдое (изгородь, ящик) и её выбросило;',
          '  часть может остаться от телепорта. Смотреть пары кадров; мерило для правок — проверки с малыми числами («упёрлась через 0,2 м»).',
          '- «Разная опора» с оригиналом на 15–25 м ниже порта (сетка кварталов, края карты) — похоже на регион, которого нет в памяти',
          '  оригинала (расчёт регионов по кускам города в 12 м — правило порта, не сверено); до проверки по кадрам — не править по ним.',
          '- Курс-ось трамплинов: у порта зоны прыжка подкидывают машину (рывки у порта на F10-8, F12-3) — отдельный разбор.', '',
          '## Как повторить и как проверять правку коллизии', '',
          '```', 'python3 tools/twins/placement.py --level 1 --points auto        # всё: точки → оригинал (дозапись) → порт → сверка → отчёт',
          'python3 tools/twins/placement.py --level 1 --stage gate          # после правки коллизии: стало ли расхождений меньше',
          'TWINS_BREAK=placement_flip python3 tools/twins/placement.py --level 1 --stage gate   # красный контроль: обязан FAIL', '```', '',
          'Данные: `compare.tsv` (точка: итог, проверки), `trials.tsv` (каждая проверка с числами), `points.tsv` (откуда точка взялась),',
          '`summary.json`. Пороги судьи (tools/twins/placement.py): покой — сдвиг < 0,7 м и рывок < 3 м/с; вытолкнуло — сдвиг > 1,2 м или',
          'рывок > 6 м/с; упёрся — скорость в конце разгона < 1 м/с; «на разном месте» — разница пути > 2 м; разная опора — > 1,5 м.', '']
    (rd / 'ОТЧЁТ.md').write_text('\n'.join(L) + '\n')


# ------------------------------------------------------------------ гейт: после правки коллизии — стало ли расхождений меньше

def gate(level, rebase=False):
    """порт заново по тем же пробам оригинала (orig.jsonl не трогаем) -> сверка -> сравнение с базой gate_base.json.
    PASS: расхождений не больше, чем в базе, и ни одна совпадавшая точка не разошлась. База пишется первым прогоном (или --rebase).
    TWINS_BREAK=placement_flip — красный контроль: курс порта на 180° (стороны разгона наоборот), гейт обязан упасть."""
    od = out_dir(level); brk = os.environ.get('TWINS_BREAK', '')
    flip = brk == 'placement_flip'
    osha = orig_sha(level)
    run_port(level, flip=flip, out_name='port_gate.jsonl')
    PT, rows, summ = compare(level, port_name='port_gate.jsonl')
    bf = od / 'gate_base.json'
    if (rebase or not bf.exists()) and not brk:
        bf.write_text(json.dumps(dict(time=C.clock(), orig_sha=osha, port=summ['port'], mismatch_points=summ['mismatch_points'],
                                      mismatch_tests=summ['mismatch_tests'], points_list=summ['points_list']), ensure_ascii=False, indent=1))
        print(f"PASS гейт «постановка»: база записана — точек {summ['points']}, расходится {summ['mismatch_points']}, проверок с расхождением {summ['mismatch_tests']}")
        return 0
    B = json.loads(bf.read_text())
    if B['orig_sha'] != osha: print('ВНИМАНИЕ: пробы оригинала дополнены после базы — сравниваю только общие точки')
    bad = lambda c: c not in ('совпало', 'неясно', 'не сверено')
    common = [k for k in summ['points_list'] if k in B['points_list']]
    was = sum(1 for k in common if bad(B['points_list'][k])); now = sum(1 for k in common if bad(summ['points_list'][k]))
    new = [k for k in common if bad(summ['points_list'][k]) and not bad(B['points_list'][k])]
    fixed = [k for k in common if bad(B['points_list'][k]) and not bad(summ['points_list'][k])]
    ok = now <= was and not new
    res = dict(ok=ok, time=C.clock(), brk=brk, common=len(common), was=was, now=now, new=new, fixed=fixed, port=summ['port'])
    g = C.OUT / 'gates'; g.mkdir(parents=True, exist_ok=True)
    (od / f'gate_{C.stamp()}.json').write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(f"{'PASS' if ok else 'FAIL'} гейт «постановка»{' [' + brk + ']' if brk else ''}: точек {len(common)}, расходится было {was} → стало {now}; "
          f"новых расхождений {len(new)}{(' (' + ', '.join(new[:8]) + ')') if new else ''}; исправлено {len(fixed)}")
    return 0 if ok else 1


def null_check(level):
    """проверка: рисование не влияет на игру — рецепт гейта О4 (tools/twins/recipes/o4_gas.json, газ 60–300 кадров) дважды тем же
    бинарником: программное рисование (как все прогоны близнецов) и пустое (EmuCore/GS/Renderer=11, Null). PASS — строки трассы те же
    байты. Нужна, чтобы гонять пробы без рисования (быстрее на загруженном Маке), а кадры снимать только для топа."""
    import orig2
    ps2_ready()
    r = json.loads((C.WT / 'tools/twins/recipes/o4_gas.json').read_text()); r['shots'] = []
    res = dict(time=C.clock(), binary_sha256=C.sha256(orig2.BIN, 16))
    for mode in ('sw', 'null'):
        run = out_dir(level) / 'nullcheck' / mode; shutil.rmtree(run, ignore_errors=True); run.mkdir(parents=True)
        orig2.script(r, run)
        args = [str(orig2.BIN), '-statefile', str(C.DATA / r['state']), '-script', str(run / 'script.txt'), '-bios', 'scph10000.bin',
                '-renderer', 'sw', '-swthreads', '2', '-set', 'SPU2/Output/Backend=Null'] + (['-set', 'EmuCore/GS/Renderer=11'] if mode == 'null' else []) + ['--', str(orig2.ISO)]
        t0 = time.time()
        with (run / 'log.txt').open('w') as lg:
            pr = subprocess.Popen(args, cwd=str(run), stdout=lg, stderr=subprocess.STDOUT)
            bad = watch_proc(pr, 900)
        wall = time.time() - t0
        rows = (run / 'trace.raw').read_text().splitlines()[1:] if (run / 'trace.raw').exists() else []
        res[mode] = dict(rows=len(rows), wall_s=round(wall, 1), watchdog=bad, sha=hashlib.sha256('\n'.join(rows).encode()).hexdigest()[:16],
                         renderer=next((l.strip()[-60:] for l in (run / 'log.txt').read_text(errors='replace').splitlines() if 'renderer' in l.lower()), ''))
        if bad: raise SystemExit(f'проверка рисования: сторож остановил PCSX2 ({bad})')
    ref = C.OUT / 'o4' / 'o4_gas_g00' / 'trace.tsv'
    res['o4_ref_same'] = ref.exists() and hashlib.sha256('\n'.join(ref.read_text().splitlines()[1:]).encode()).hexdigest()[:16] == res['sw']['sha']
    ok = res['sw']['rows'] > 30 and res['sw']['sha'] == res['null']['sha']
    res['ok'] = ok
    (out_dir(level) / 'nullcheck' / 'result.json').write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(f"{'PASS' if ok else 'FAIL'} рисование не влияет: строк {res['sw']['rows']}/{res['null']['rows']}, отпечаток {res['sw']['sha']} / {res['null']['sha']}, "
          f"время {res['sw']['wall_s']} / {res['null']['wall_s']} с; совпадает с эталоном О4 01.10 (другой бинарник): {res['o4_ref_same']}")
    return 0 if ok else 1


def watch_proc(pr, limit):
    """сторож своего процесса PCSX2 без замкнутого цикла: впереди / окно / звук наружу / время -> остановить свой PID"""
    import orig2
    wins = C.DATA / 'build/ps2ref/bin/wins'; t_end = time.time() + limit; k = 0
    while pr.poll() is None:
        why = ''
        try:
            if orig2.front_pid() == pr.pid: why = 'вышел вперёд'
            elif k % 10 == 0 and wins.exists() and any(l.startswith('1 ') for l in subprocess.run([str(wins), str(pr.pid)], capture_output=True).stdout.decode('utf-8', 'replace').splitlines()):
                why = 'окно на экране'
            elif k % 25 == 5 and any(f'pid {pr.pid}(' in l and 'audio' in l.lower() for l in subprocess.run(['pmset', '-g', 'assertions'], capture_output=True).stdout.decode('utf-8', 'replace').splitlines()):
                why = 'звук наружу'
        except Exception: pass
        if time.time() > t_end: why = 'не уложился во время'
        if why: pr.kill(); pr.wait(); return why
        k += 1; time.sleep(0.2)
    return ''


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--level', type=int, default=1); ap.add_argument('--points', default='auto')
    ap.add_argument('--stage', default='all'); ap.add_argument('--max-points', type=int, default=170); ap.add_argument('--budget-min', type=float, default=None); ap.add_argument('--only', default=None); ap.add_argument('--no-shots', action='store_true'); ap.add_argument('--rebase', action='store_true'); ap.add_argument('--part', default=None)
    a = ap.parse_args()
    if a.stage == 'nullcheck':
        return null_check(a.level)
    if a.stage == 'gate':
        return gate(a.level, a.rebase)
    if a.stage == 'all':
        if a.points not in ('auto', 'regen'): raise SystemExit('--points: auto (есть — взять, нет — построить) или regen (построить заново)')
        if a.points == 'regen' or not (out_dir(a.level) / 'points.tsv').exists(): gen_points(a.level, a.max_points)
        nc = out_dir(a.level) / 'nullcheck' / 'result.json'
        if os.environ.get('PLACEMENT_RENDER', 'null') == 'null' and not (nc.exists() and json.loads(nc.read_text()).get('ok')):
            if null_check(a.level): raise SystemExit('пустое рисование меняет игру — массовый прогон только с PLACEMENT_RENDER=sw')
        if a.level == 1: extend_base(a.level)   # зоны l1z7/l1r7: снимки продления базы
        run_orig(a.level, a.budget_min)
        run_port(a.level); build_report(a.level, shots=not a.no_shots)
        return 0
    if a.stage == 'report':
        build_report(a.level, shots=not a.no_shots); return 0
    if a.stage == 'points':
        gen_points(a.level, a.max_points); return 0
    if a.stage == 'base':
        base_drive(a.level); return 0
    if a.stage == 'extend':
        extend_base(a.level); return 0
    if a.stage == 'orig':
        run_orig(a.level, a.budget_min, only=set(a.only.split(',')) if a.only else None,
                 part=tuple(int(v) for v in a.part.split('/')) if a.part else None); return 0
    if a.stage == 'port':
        run_port(a.level); return 0
    if a.stage == 'compare':
        PT, rows, summ = compare(a.level); print(json.dumps({k: summ[k] for k in ('points', 'trials', 'by_point', 'by_test')}, ensure_ascii=False)); return 0
    raise SystemExit(f'неизвестная стадия {a.stage!r}: all | points | base | extend | orig | port | compare | report | gate | nullcheck')

if __name__ == '__main__':
    sys.exit(main())
