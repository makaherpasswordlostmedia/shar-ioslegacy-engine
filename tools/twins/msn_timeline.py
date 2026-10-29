#!/usr/bin/env python3
"""Близнецы · таймлайн миссий оригинала (Атлас миссий, правка 332, 05.10): что игра делает по этапам — из памяти PS2.

Своя сборка PCSX2 без окна и без звука (pcsx2-twins, tools/twins/README.md §8): бот проходит начало миссии, через каждые
--snap кадров снимок памяти (.p2s, в нём кадр экрана), кадры экрана каждые --png; дальше раскопка: какие слова памяти меняются
ровно на сменах этапов (метки — по событиям бота и кадрам экрана), и чтение найденных адресов в любом прогоне.

  python3 tools/twins/msn_timeline.py run --plan m0 --out DIR [--frames 9000] [--snap 100] [--png 50]
        план m0: от state_l1_start (Гомер у Мардж, «TALK TO MARGE») — к свечению, △, ✕ «Start Mission», ✕ «Continue»
        на карточке, разговор, к машине, △, по дорогам к Kwik-E-Mart (route.py), выход, к двери, △ — до «TALK TO APU»
        план sr3: от state_l1_incar (Гомер в машине у дома) — по дорогам к Ральфу у церкви, пешком к свечению, △, ✕, ✕ (по экрану
        в памяти), уличная гонка 3 по контрольным точкам; в гонке снимок каждые 50 кадров и кадр экрана каждые 25 (место на HUD)
        → DIR/trace.tsv (кадр, машина, Гомер, камера), events.tsv (что бот нажал и почему), stages.tsv (смены этапа/экрана),
          snap_<кадр>.p2s, png/f<кадр>.png
  python3 tools/twins/msn_timeline.py dig LABELS.tsv [--out cand.tsv] [--lo HEX --hi HEX]
        LABELS.tsv: «снимок.p2s<TAB>метка» или «ПАПКА_ПРОГОНА:кадр_от-кадр_до<TAB>метка» (метка этапа, как в атласе: m0sd.0, m0.0 …),
        снимки разных прогонов из одного состояния можно смешивать: одна метка = одно состояние этапа
        → слова u32 (выровненные), постоянные внутри каждого отрезка и меняющиеся на каждой смене меток, плюс расшифровка:
          малое число (номер), указатель в EE (объект этапа), float (таймер)
  python3 tools/twins/msn_timeline.py read (--labels LABELS.tsv | --dir DIR) --addr HEX[:u32|f32|s32|x] … → значения в каждом снимке
  python3 tools/twins/msn_timeline.py timeline DIR [--mission m0]  → смены этапа по кадрам: тип цели, номер и текст задания,
        значок, персонаж (поля этапа из памяти, адреса ниже), экран; что читалось с диска (прогон с --cdvd) → DIR/timeline.json
  python3 tools/twins/msn_timeline.py gate DIR [--mission m0 --min 6]  → гейт: этапы из памяти по порядку = этапы скрипта диска
        (тип цели, номер текста, значок); TWINS_BREAK=msn_offset (поле текста +4 байта) обязан дать FAIL
Окна нет, звука нет (SPU2 Backend=Null), фокус не берётся (setActivationPolicy Prohibited в pcsx2-twins). Кадры — vsync 50/с
от загрузки состояния. Код игры не читаем: только данные (снимки) и экран."""
import argparse, json, math, os, sys, zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common as C   # noqa: E402

HOMER = [('hx', 0xa24a70, 'f32'), ('hy', 0xa24a74, 'f32'), ('hz', 0xa24a78, 'f32')]    # walk.py: перенос матрицы Гомера
CAM = [('fx', 0x7aabb8, 'f32'), ('fz', 0x7aabc0, 'f32')]                                # addrs.tsv cam_fwd
# найдено этим инструментом 05.10 (dig по 4 этапам m0, проверено чтением полей этапа — см. docs/МИССИИ_КАК_ЧИТАТЬ_ОРИГИНАЛ.md):
STAGE = [('stage', 0x5db570, 'u32'),    # указатель на текущий этап миссии (объект этапа; меняется ровно на смене этапа)
         ('screen', 0x8470c4, 'u32')]   # экран игры: 1 игра, 7 «Start Mission / Cancel» (разговор), 5 карточка миссии
EE = 32 << 20

# точки уровня 1 в осях оригинала (z = −z порта; локаторы диска — compile.py JSON)
MARGE = (219.29, -177.08)          # m1_marge_sd
KWIK_SPHERE = (203.54, -286.01)    # m0_kwickemart (carsphere)
KWIK_DOOR = (213.91, -302.74)      # KwikEMart (вход, doorstar)
CAR0 = (215.1, -170.31)            # level1_carstart: машина Гомера у дома (state_l1_start, кадр экрана)


def ang(a): return (a + math.pi) % (2 * math.pi) - math.pi


class Walker:
    """Гомер пешком к точке. Стик относительно камеры: сначала проба (20 кадров «вверх», 20 «вправо») — куда идёт Гомер
    относительно взгляда камеры (cam_fwd); дальше стик = решение 2×2 по этим двум направлениям на каждом шаге"""
    def __init__(self): self.t0 = None; self.u = self.r = None; self.p = {}

    def cmds(self, s, f, tx, tz):
        import drive as D
        c = math.atan2(s['fx'], s['fz']); hx, hz = s['hx'], s['hz']; d = math.hypot(tx - hx, tz - hz)
        if self.t0 is None: self.t0 = f
        k = f - self.t0
        if self.u is None or self.r is None:     # проба
            if k == 0: self.p['a'] = (hx, hz, c); return ['pad lup 1', 'pad ldown 0'], d
            if k == 20: self.p['b'] = (hx, hz, c); return ['pad lup 0', 'pad lright 1', 'pad lleft 0'], d
            if k == 40:
                (ax, az, ca), (bx, bz, cb) = self.p['a'], self.p['b']
                self.u = ang(math.atan2(bx - ax, bz - az) - ca); self.r = ang(math.atan2(hx - bx, hz - bz) - cb)
                return ['pad lright 0'], d
            return [], d
        a = math.atan2(tx - hx, tz - hz); ux, uz = math.sin(c + self.u), math.cos(c + self.u); rx, rz = math.sin(c + self.r), math.cos(c + self.r)
        tx_, tz_ = math.sin(a), math.cos(a); det = ux * rz - uz * rx
        if abs(det) < 1e-3: sy, sx = 1.0, 0.0
        else: sy = (tx_ * rz - tz_ * rx) / det; sx = (ux * tz_ - uz * tx_) / det
        n = max(1e-6, math.hypot(sx, sy)); sx, sy = sx / n, sy / n
        if d < 1.0: sx = sy = 0.0
        return [*D.axis('l', 'y', sy), *D.axis('l', 'x', sx)], d

    def stop(self):
        import drive as D
        return [*D.axis('l', 'y', 0.0), *D.axis('l', 'x', 0.0)]


def plan_m0(o, out, frames, snap, png):
    """начало «The Cola Caper»: события по кадрам — в events.tsv"""
    import drive as D, route as R
    ev = (out / 'events.tsv').open('w'); ev.write('кадр\tсобытие\n')
    tsv = (out / 'trace.tsv').open('w'); tsv.write('кадр\t' + '\t'.join(n for n, _, _ in o.cols) + '\tфаза\n')
    def E(f, t): ev.write(f'{f}\t{t}\n'); ev.flush()
    pts, _ = R.route_roads([('старт', 215.05, 4.05, -170.25), ('Kwik', KWIK_SPHERE[0], 4.0, KWIK_SPHERE[1])])
    pts = [(215.05, 4.05, -170.25), (214.0, 4.0, -159.0)] + pts + [(KWIK_SPHERE[0], 4.0, KWIK_SPHERE[1])]
    pts, _ = R.resample(pts, 3.0)
    phase, t0, i, W, tries, last_prog, tri = 'к Мардж', 0, 0, Walker(), 0, 0, 0
    tl = (out / 'stages.tsv').open('w'); tl.write('кадр\tэтап (указатель)\tэкран\tфаза бота\n'); last_key = None; snap_at = set()
    stuck, rev = 0, 0
    while True:
        s = o.step()
        if s is None: break
        f = o.frame; cmds = []
        x, z = s['x'], s['z']; h = math.atan2(s['nx'], s['nz']); v = math.hypot(s['vx'], s['vz'])   # матрица машины игрока 0xa21870: пока Гомер пешком — (0, 8, 20), не обновляется
        if phase == 'к Мардж':   # проверено прогоном p2 05.10: стик вправо 30 кадров — Гомер в свечении у Мардж, над ним △
            if f == 40: cmds += ['pad lright 1']
            if f == 70: cmds += ['pad lright 0']
            if f == 90: cmds += ['pad triangle 1']; E(f, '△ у Мардж (свечение)')
            if f == 96: cmds += ['pad triangle 0']
            if f == 150: cmds += ['pad cross 1']; E(f, '✕ Start Mission')
            if f == 156: cmds += ['pad cross 0']
            if f == 450: cmds += ['pad cross 1']; E(f, '✕ Continue на карточке миссии')
            if f == 456: cmds += ['pad cross 0']; phase, t0 = 'разговор', f
        elif phase == 'разговор':   # прогон m0a 05.10: «GET INTO YOUR VEHICLE» на кадре 600 — ждём, потом к машине
            if f - t0 >= 250: phase, t0, W = 'к машине', f, Walker(); E(f, 'иду к машине')
        if tries > 3: phase = 'конец'
        elif phase == 'к машине':
            c, d = W.cmds(s, f, *CAR0)   # к машине (стоит на level1_carstart; матрица и car_cm пешком не годятся — прогон m0b): у машины △
            cmds += c
            if d < 3.5 and not tri: cmds += W.stop() + ['pad triangle 1']; tri = f; E(f, f'△ у машины, {d:.1f} м')
            if tri and f == tri + 6: cmds += ['pad triangle 0']
            if tri and f >= tri + 200: phase, t0 = 'дорога', f; E(f, 'газ: проверка, в машине ли'); last_prog = f; tri = 0
        elif phase == 'дорога':
            best = min(range(i, min(len(pts), i + 40)), key=lambda k: (pts[k][0] - x) ** 2 + (pts[k][2] - z) ** 2)
            if best > i: i = best; last_prog = f
            j = min(len(pts) - 1, i + 3); err = ang(math.atan2(pts[j][0] - x, pts[j][2] - z) - h)
            dk = math.hypot(KWIK_SPHERE[0] - x, KWIK_SPHERE[1] - z)
            vt = 12.0 * max(0.35, math.cos(err)) if dk > 25 else 5.0
            if rev > 0:   # манёвр выхода (как drive.py): назад с рулём в другую сторону
                rev -= 1; cmds += ['pad cross 0', 'pad circle 1', *D.axis('l', 'x', -1.0 if err > 0 else 1.0)]
                if rev == 0: cmds += ['pad circle 0']; last_prog = f
            else:
                cmds += [*D.axis('l', 'x', max(-1.0, min(1.0, err * 2.5))), f'pad cross {1 if v < vt else 0}', f'pad circle {1 if v > vt + 3 else 0}']
                stuck = stuck + 1 if (v < 0.8 and f - t0 > 250) else 0
                if stuck >= 60: rev, stuck = 70, 0; E(f, 'упёрся: назад 70 кадров')
            if f - t0 == 200 and v < 0.5: cmds += ['pad cross 0']; phase, t0, W = 'к машине', f, Walker(); E(f, 'не в машине — снова к машине'); tries += 1
            elif f - t0 == 200: E(f, f'в машине, едет {v:.1f} м/с')
            if f - last_prog > 500 and rev == 0: rev = 90; last_prog = f; E(f, 'нет продвижения 10 с: назад 90 кадров')
            if dk < 4.0: cmds += ['pad cross 0', 'pad circle 1', *D.axis('l', 'x', 0.0)]; phase, t0 = 'стоп', f; E(f, f'у Kwik-E-Mart, {dk:.1f} м от сферы')
        elif phase == 'стоп':
            if v < 0.5 or f - t0 > 150: cmds += ['pad circle 0']
            if f - t0 == 250: cmds += ['pad triangle 1']; E(f, '△ выйти из машины')
            if f - t0 == 256: cmds += ['pad triangle 0']
            if f - t0 >= 400: phase, t0 = 'к двери', f; E(f, 'иду к двери Kwik-E-Mart')
        elif phase == 'к двери':
            if f == t0: W = Walker()
            c, d = W.cmds(s, f, *KWIK_DOOR); cmds += c
            if d < 2.0 and (f - t0) % 40 == 0: cmds += ['pad triangle 1']; E(f, f'△ у двери, {d:.1f} м')
            elif (f - t0) % 40 == 6: cmds += ['pad triangle 0']
            if f - t0 > 1500: phase, t0 = 'конец', f; E(f, 'дверь: время вышло')
            if math.hypot(s['hx'] - KWIK_DOOR[0], s['hz'] - KWIK_DOOR[1]) > 60 and f - t0 > 100: cmds += W.stop(); phase, t0 = 'внутри', f; E(f, 'Гомер далеко от двери — внутри (комнаты оригинала под городом)')
        elif phase == 'внутри':
            if f - t0 >= 900: phase = 'конец'
        key = (s['stage'], s['screen'])
        if key != last_key:   # смена этапа или экрана: строка таймлайна и снимок через 10 кадров (поля этапа уже записаны)
            tl.write(f"{f}\t{s['stage']:x}\t{s['screen']}\t{phase}\n"); tl.flush(); last_key = key; snap_at.add(f + 10)
        if f in snap_at: cmds.append(f'save {out}/snap_{f:05d}.p2s')
        if f % png == 0: cmds.append(f'png {out}/png/f{f:05d}.png')
        if f % snap == 0 and f and f not in snap_at: cmds.append(f'save {out}/snap_{f:05d}.p2s')
        if f % 10 == 0: tsv.flush()
        if f % 10 == 0: tsv.write(f'{f}\t' + '\t'.join(f'{s[n]:.3f}' if isinstance(s[n], float) else str(s[n]) for n, _, _ in o.cols) + f'\t{phase}\n')
        if phase == 'конец' or f >= frames:
            E(f, 'конец прогона'); o.p.stdin.write('end\n'); o.p.stdin.flush(); break
        o.send(*cmds)
    o.close(); ev.close(); tsv.close(); tl.close()


class Driver:
    """за рулём по ломаной (оси оригинала): упреждение 3 точки (~9 м), руль пропорционально углу, газ до vmax; упёрся — назад"""
    def __init__(self, pts, vmax=12.0, E=None):
        self.pts, self.vmax, self.i, self.rev, self.stuck, self.last, self.E, self.t0 = pts, vmax, 0, 0, 0, None, E, None

    def cmds(self, s, f, slow_at=None):
        import drive as D
        x, z = s['x'], s['z']; h = math.atan2(s['nx'], s['nz']); v = math.hypot(s['vx'], s['vz']); P = self.pts
        if self.t0 is None: self.t0 = self.last = f
        best = min(range(self.i, min(len(P), self.i + 40)), key=lambda k: (P[k][0] - x) ** 2 + (P[k][2] - z) ** 2)
        if best > self.i: self.i = best; self.last = f
        j = min(len(P) - 1, self.i + 3); err = ang(math.atan2(P[j][0] - x, P[j][2] - z) - h)
        vt = self.vmax * max(0.35, math.cos(err))
        if slow_at and math.hypot(slow_at[0] - x, slow_at[1] - z) < 25: vt = min(vt, 5.0)
        if self.rev > 0:
            self.rev -= 1; c = ['pad cross 0', 'pad circle 1', *D.axis('l', 'x', -1.0 if err > 0 else 1.0)]
            if self.rev == 0: c += ['pad circle 0']; self.last = f
            return c
        c = [*D.axis('l', 'x', max(-1.0, min(1.0, err * 2.5))), f'pad cross {1 if v < vt else 0}', f'pad circle {1 if v > vt + 3 else 0}']
        self.stuck = self.stuck + 1 if (v < 0.8 and f - self.t0 > 150) else 0
        if self.stuck >= 60: self.rev, self.stuck = 70, 0; self.E and self.E(f, 'упёрся: назад 70 кадров')
        elif f - self.last > 500: self.rev = 90; self.last = f; self.E and self.E(f, 'нет продвижения 10 с: назад 90 кадров')
        return c

    def done(self): return self.i >= len(self.pts) - 2


def plan_sr3(o, out, frames, snap, png):
    """уличная гонка 3 «Checkpoint Race» (Ральф у церкви): от state_l1_incar (Гомер в машине у дома) по дорогам к Ральфу, выйти,
    к свечению, △, ✕ на «Start Mission», ✕ на карточке (по экрану в памяти), гонка по контрольным точкам; снимки каждые --snap"""
    import drive as D, route as R
    ev = (out / 'events.tsv').open('w'); ev.write('кадр\tсобытие\n')
    tsv = (out / 'trace.tsv').open('w'); tsv.write('кадр\t' + '\t'.join(n for n, _, _ in o.cols) + '\tфаза\n')
    tl = (out / 'stages.tsv').open('w'); tl.write('кадр\tэтап (указатель)\tэкран\tфаза бота\n'); last_key = None; snap_at = set()
    def E(f, t): ev.write(f'{f}\t{t}\n'); ev.flush()
    RALPH, PLAYER = (194.99, -572.88), (193.2, -572.88)   # sr3_ralph_sd, sr3_player (оси оригинала; диск leveli.mfk / level.p3d)
    CPS = [(253.08, -0.17, -422.36), (341.62, 5.22, -120.13), (339.33, 0.17, 280.0), (224.87, 5.06, 520.39), (65.39, 0.0, 304.42)]   # sr3_waypoint1–4, sr3_finish
    pts, _ = R.route_roads([('старт', 215.05, 4.05, -170.25), ('Ральф', PLAYER[0], 0.0, PLAYER[1] + 8)])
    pts = [(215.05, 4.05, -170.25), (214.0, 4.0, -159.0)] + pts + [(PLAYER[0], 0.0, PLAYER[1] + 4)]
    pts, _ = R.resample(pts, 3.0)
    E(0, f'к Ральфу: {len(pts) * 3} м по дорогам')
    drv = Driver(pts, 13.0, E); phase, t0, W, race = 'к Ральфу', 0, None, None
    while True:
        s = o.step()
        if s is None: break
        f = o.frame; cmds = []; v = math.hypot(s['vx'], s['vz'])
        if phase == 'к Ральфу':
            cmds += drv.cmds(s, f, slow_at=PLAYER)
            if math.hypot(PLAYER[0] - s['x'], PLAYER[1] - s['z']) < 7 or drv.done():
                cmds += ['pad cross 0', 'pad circle 1', *D.axis('l', 'x', 0.0)]; phase, t0 = 'стоп', f; E(f, f"у Ральфа ({s['x']:.0f}, {s['z']:.0f})")
        elif phase == 'стоп':
            if v < 0.5 or f - t0 > 150: cmds += ['pad circle 0']
            if f - t0 == 200: cmds += ['pad triangle 1']; E(f, '△ выйти из машины')
            if f - t0 == 206: cmds += ['pad triangle 0']
            if f - t0 >= 350: phase, t0, W = 'к Ральфу пешком', f, Walker(); E(f, 'пешком к свечению у Ральфа')
        elif phase == 'к Ральфу пешком':
            c, d = W.cmds(s, f, RALPH[0] - 1.2, RALPH[1]); cmds += c
            if d < 1.3 and (f - t0) % 40 == 0: cmds += W.stop() + ['pad triangle 1']; E(f, f'△ у Ральфа, {d:.1f} м')
            elif (f - t0) % 40 == 6: cmds += ['pad triangle 0']
            if s['screen'] == 7: phase, t0 = 'старт', f; cmds += W.stop() + ['pad triangle 0']; E(f, 'экран «Start Mission / Cancel»')
            if f - t0 > 2500: phase = 'конец'; E(f, 'не дошёл до Ральфа')
        elif phase == 'старт':
            if f - t0 == 40: cmds += ['pad cross 1']; E(f, '✕ Start Mission')
            if f - t0 == 46: cmds += ['pad cross 0']
            if s['screen'] == 5 and f - t0 > 60: phase, t0 = 'карточка', f; E(f, 'карточка миссии')
        elif phase == 'карточка':
            if f - t0 == 250: cmds += ['pad cross 1']; E(f, '✕ Continue')
            if f - t0 == 256: cmds += ['pad cross 0']
            if s['screen'] == 1 and f - t0 > 256: phase, t0 = 'гонка', f; E(f, 'игра: гонка (отсчёт)')
        elif phase == 'гонка':
            if race is None:
                rp = [(s['x'], 0.0, s['z'])]
                for a, b in zip([(s['x'], 0.0, s['z'])] + CPS[:-1], CPS):
                    seg, _ = R.route_roads([('a', a[0], a[1], a[2]), ('b', b[0], b[1], b[2])]); rp += seg + [b]
                rp, _ = R.resample(rp, 3.0); race = Driver(rp, 16.0, E); E(f, f'маршрут гонки {len(rp) * 3} м')
            cmds += race.cmds(s, f)
            if race.done() or f - t0 > 4500: phase = 'конец'; E(f, 'гонка: конец маршрута / время')
        key = (s['stage'], s['screen'])
        if key != last_key:
            tl.write(f"{f}\t{s['stage']:x}\t{s['screen']}\t{phase}\n"); tl.flush(); last_key = key; snap_at.add(f + 10)
        snap_now = f in snap_at or (f % snap == 0 and f) or (phase == 'гонка' and f % 50 == 0)
        if snap_now: cmds.append(f'save {out}/snap_{f:05d}.p2s')
        if f % png == 0 or (phase == 'гонка' and f % 25 == 0): cmds.append(f'png {out}/png/f{f:05d}.png')
        if f % 10 == 0: tsv.write(f'{f}\t' + '\t'.join(f'{s[n]:.3f}' if isinstance(s[n], float) else str(s[n]) for n, _, _ in o.cols) + f'\t{phase}\n'); tsv.flush()
        if phase == 'конец' or f >= frames:
            E(f, 'конец прогона'); o.p.stdin.write('end\n'); o.p.stdin.flush(); break
        o.send(*cmds)
    o.close(); ev.close(); tsv.close(); tl.close()


def cmd_run(a):
    import drive as D
    out = Path(a.out).resolve(); (out / 'png').mkdir(parents=True, exist_ok=True)
    state = {'m0': 'build/ps2ref/state_l1_start.p2s', 'sr3': 'build/ps2ref/state_l1_incar.p2s'}[a.plan]
    o = D.Original(out, state=state, lockstep=1, extra=HOMER + CAM + STAGE, renderer=a.renderer, cdvd=a.cdvd)
    (out / 'run.json').write_text(json.dumps(dict(plan=a.plan, frames=a.frames, snap=a.snap, png=a.png, started=C.clock(),
                                                  state=state, code=C.git_head()), ensure_ascii=False, indent=1))
    {'m0': plan_m0, 'sr3': plan_sr3}[a.plan](o, out, a.frames, a.snap, a.png)
    print('готово', out)


# ------------------------------------------------------------------ раскопка
def load_ee(p):
    import numpy as np
    with zipfile.ZipFile(p) as z: b = z.read('eeMemory.bin')
    if len(b) != EE: raise ValueError(f'{p}: eeMemory {len(b)}')
    return np.frombuffer(b, dtype='<u4')


def snaps(d):
    return sorted((int(p.stem.split('_')[1]), p) for p in Path(d).glob('snap_*.p2s'))


def snap_list(path):
    """список снимков с метками: строки «файл<TAB>метка» (файл — .p2s или ПАПКА:кадр_от-кадр_до — снимки прогона в диапазоне);
    путь относительный — от основной папки данных (C.DATA) или от папки самого списка. Порядок строк = порядок отрезков"""
    base = Path(path).resolve().parent; out = []
    for ln in Path(path).read_text().splitlines():
        if not ln.strip() or ln.startswith('#'): continue
        f, lab = [x.strip() for x in ln.split('\t')[:2]]
        rng = None
        if ':' in f and not f.endswith('.p2s'): f, r = f.rsplit(':', 1); lo, hi = r.split('-'); rng = (int(lo), int(hi))
        P = Path(f) if Path(f).is_absolute() else (base / f if (base / f).exists() else C.DATA / f)
        if rng: out += [(str(p), lab) for fr, p in snaps(P) if rng[0] <= fr <= rng[1]]
        else: out.append((str(P), lab))
    return out


def as_f32(v):
    import numpy as np
    return float(np.frombuffer(np.uint32(v).tobytes(), '<f4')[0])


def cmd_dig(a):
    """слова памяти, постоянные внутри каждого отрезка (одна метка подряд) и разные у соседних отрезков; снимки грузятся по одному"""
    import numpy as np
    S = [(p, l) for p, l in snap_list(a.labels) if l != '-']   # «-» — снимок не в счёт (переход, неясное состояние)
    sid, seglab = [], []
    for _, l in S:
        if not seglab or seglab[-1] != l: seglab.append(l)
        sid.append(len(seglab) - 1)
    print(f'снимков {len(S)}, отрезков {len(seglab)}: {" → ".join(seglab)}')
    first = {}; ok = None
    for (p, l), g in zip(S, sid):
        m = load_ee(p)
        if ok is None: ok = np.ones(m.shape[0], bool)
        if g not in first: first[g] = m.copy()
        else: ok &= m == first[g]
    for g in range(1, len(seglab)): ok &= first[g] != first[g - 1]
    if a.lo or a.hi: ok[:int(a.lo or '0', 16) // 4] = False; ok[int(a.hi or '2000000', 16) // 4:] = False
    idx = np.nonzero(ok)[0]
    rows = []
    for i in idx:
        vals = [int(first[g][i]) for g in range(len(seglab))]
        same = all(vals[g] == vals[h] for g in range(len(seglab)) for h in range(len(seglab)) if seglab[g] == seglab[h])
        fl = [as_f32(v) for v in vals]
        kind = 'малое' if all(v < 256 for v in vals) else 'указатель' if all(0x100000 <= v < 0x2000000 for v in vals) else \
               'float' if all(math.isfinite(x) and 1e-3 < abs(x) < 1e5 for x in fl) else 'другое'
        rows.append((i * 4, kind, same, vals))
    order = {'малое': 0, 'указатель': 1, 'float': 2, 'другое': 3}
    rows.sort(key=lambda r: (not r[2], order[r[1]], r[0]))
    out = Path(a.out or Path(a.labels).with_suffix('.dig.tsv'))
    with out.open('w') as fo:
        fo.write('# отрезки: ' + ' → '.join(seglab) + f'\n# снимков {len(S)}; {C.clock()}\n')
        fo.write('адрес\tвид\tметка=значение\tзначения по отрезкам\n')
        for ad, kind, same, vals in rows:
            fo.write(f'{ad:07x}\t{kind}\t{"да" if same else "нет"}\t' + ' '.join(fmt(v, kind) for v in vals) + '\n')
    print(f'кандидатов {len(rows)} (из них «метка = значение» {sum(1 for r in rows if r[2])}) → {out}')
    for ad, kind, same, vals in rows[:a.show]:
        print(f'  {ad:07x} {kind:9s} {"да " if same else "нет"} ' + ' '.join(fmt(v, kind) for v in vals))


def fmt(v, kind):
    return f'{v:x}' if kind == 'указатель' else f'{as_f32(v):.3f}' if kind == 'float' else str(v)


def cmd_read(a):
    cols = []
    for s in a.addr:
        ad, _, t = s.partition(':'); cols.append((int(ad, 16), t or 'u32'))
    S = snap_list(a.labels) if a.labels else [(str(p), '') for _, p in snaps(a.dir)]
    print('снимок\tметка\t' + '\t'.join(f'{ad:x}:{t}' for ad, t in cols))
    for p, l in S:
        m = load_ee(p); row = []
        for ad, t in cols:
            v = int(m[ad // 4])
            row.append(f'{as_f32(v):.3f}' if t == 'f32' else str(v - (1 << 32) if v >= 1 << 31 else v) if t == 's32' else f'{v:x}' if t == 'x' else str(v))
        print(f'{Path(p).parent.name}/{Path(p).stem}\t{l}\t' + '\t'.join(row))


# ------------------------------------------------------------------ чтение этапа из памяти (наблюдение 05.10, прогоны m0a–m0d)
STAGE_PTR = 0x5db570          # → объект текущего этапа (MissionStage)
SCREEN = 0x8470c4             # экран: 1 игра, 7 «Start Mission / Cancel», 6 переход, 5 карточка миссии
ST_OBJECTIVE = 0x68           # этап + 0x68 → объект цели
ST_MSG = 0x2b4                # этап + 0x2b4: номер текста задания (SetStageMessageIndex; −1 — нет)
ST_ICON = 0x434               # этап + 0x434..0x450: имя файла значка HUD («marage.png», «kwike.png»; SetHUDIcon)
OBJ_TYPE = 0x08               # цель + 0x08: тип цели (1 goto, 7 talkto, 8 dialogue, 9 getin, 12 interior — по m0; остальные — по мере наблюдения)
OBJ_NPC, OBJ_LOC = 0x14, 0x40 # цель talkto: имя персонажа и локатора строками
OBJ_NAMES = {1: 'goto', 7: 'talkto', 8: 'dialogue', 9: 'getin', 12: 'interior'}
SCREEN_RU = {1: 'игра', 7: '«Start Mission / Cancel» (идёт разговор)', 6: 'переход', 5: 'карточка миссии (LOADING → Continue)'}


def cstr(b, a, n):
    raw = bytes(b[a:a + n]); out = []
    for ch in raw:
        if ch == 0: break
        out.append(ch)
    t = bytes(out).decode('latin1')
    return t if t and all(32 <= ord(c) < 127 for c in t) else ''


def decode_stage(m):
    """снимок памяти → поля текущего этапа (только данные, без кода игры)"""
    b = m.view('u1'); w = lambda a: int(m[a // 4]) if 0 <= a < EE else 0
    p = w(STAGE_PTR); r = dict(ptr=p, screen=w(SCREEN))
    if not 0x100000 <= p < EE: return r
    msg = w(p + ST_MSG); r['msg'] = None if msg == 0xffffffff else msg
    ic = ''
    for k in range(0, 16):                 # имя значка: первая читаемая строка, кончается на .png
        t = cstr(b, p + ST_ICON + k, 28)
        if t.endswith('.png') and len(t) > 4: ic = t[:-4]; break
    r['icon'] = ic
    o = w(p + ST_OBJECTIVE)
    if 0x100000 <= o < EE:
        r['obj'] = w(o + OBJ_TYPE); r['obj_name'] = OBJ_NAMES.get(r['obj']); r['obj_vt'] = w(o)
        npc, loc = cstr(b, o + OBJ_NPC, 32), cstr(b, o + OBJ_LOC, 40)
        if npc: r['npc'] = npc
        if loc: r['loc'] = loc
    return r


def reads_of(d):
    """log.txt прогона с --cdvd: «[кадр N] … DvdRead: Reading Sector» → файлы диска с первым кадром чтения (isomap, таблица диска)"""
    import re, isomap
    rx = re.compile(r'^\[кадр (\d+)\]\s*\[\s*[\d.]+\]\s+(DvdRead|CDRead|CdAudioRead): Reading Sector (\d+) \((\d+) Blocks')
    lg = Path(d) / 'log.txt'
    if not lg.exists(): return []
    files = isomap.diskmap(); per = {}
    for ln in lg.read_text(errors='replace').splitlines():
        mm = rx.match(ln)
        if not mm: continue
        fr, lsn, n = int(mm.group(1)), int(mm.group(3)), int(mm.group(4))
        st, en = lsn * isomap.SEC, (lsn + n) * isomap.SEC
        for f in isomap.files_in(files, st, en):
            q = per.setdefault(f['path'], dict(frame=fr, bytes=0)); q['bytes'] += min(en, f['end']) - max(st, f['start'])
    return [dict(frame=v['frame'], file=k, kb=round(v['bytes'] / 1024)) for k, v in sorted(per.items(), key=lambda kv: kv[1]['frame'])]


def timeline(d, bible_get=None, mission='m0'):
    """прогон → смены этапа/экрана с полями этапа (снимок через 10 кадров после смены), события бота, чтения диска"""
    d = Path(d); rows = []
    for ln in (d / 'stages.tsv').read_text().splitlines()[1:]:
        f = ln.split('\t'); rows.append((int(f[0]), int(f[1], 16), int(f[2]), f[3] if len(f) > 3 else ''))
    run = json.loads((d / 'run.json').read_text()) if (d / 'run.json').exists() else {}
    ev = [ln.split('\t', 1) for ln in (d / 'events.tsv').read_text().splitlines()[1:]] if (d / 'events.tsv').exists() else []
    out = []
    for fr, ptr, scr, ph in rows:
        sp = d / f'snap_{fr + 10:05d}.p2s'
        r = decode_stage(load_ee(sp)) if sp.exists() else dict(ptr=ptr, screen=scr)
        r.update(frame=fr, bot=ph, screen=scr, screen_ru=SCREEN_RU.get(scr, str(scr)))
        if r.get('msg') is not None and bible_get: r['text'] = bible_get(f"MISSION_OBJECTIVE_{r['msg']:02d}") or ''
        png = d / 'png' / f'f{(fr + 49) // 50 * 50:05d}.png'
        if png.exists(): r['png'] = str(png)
        out.append(r)
    # этап: смена указателя (смена только экрана — в той же строке экрана)
    stages, last = [], None
    for r in out:
        if r['ptr'] != last: stages.append(dict(r, screens=[(r['frame'], r['screen'])])); last = r['ptr']
        else: stages[-1]['screens'].append((r['frame'], r['screen']))
    reads = reads_of(d)
    for x in reads:
        x['stage'] = next((f"{s.get('obj_name') or s.get('obj')}" + (f" №{s['msg']}" if s.get('msg') is not None else '') for s in reversed(stages) if s['frame'] <= x['frame']), '')
    return dict(run=d.name, plan=run.get('plan'), mission=mission, made=run.get('started'), stages=stages, changes=out, events=ev, reads=reads)


def cmd_timeline(a):
    get = None
    try:
        sys.path.insert(0, str(C.WT / 'tools/missions')); sys.path.insert(0, str(C.WT / 'hit-and-run-web/tools'))
        import compile as MC; get = MC.bible()
    except Exception as e:
        print('текстовая библия недоступна:', e)
    T = timeline(a.dir, get, a.mission)
    for s in T['stages']:
        scr = ' → '.join(f"{f}:{SCREEN_RU.get(x, x)}" for f, x in s['screens'])
        print(f"кадр {s['frame']:5d} ({s['frame'] / 50:6.1f} с)  этап {s['ptr']:x}  цель {s.get('obj_name') or s.get('obj')}  текст №{s.get('msg')} «{s.get('text', '')}»"
              f"  значок {s.get('icon') or '—'}" + (f"  {s['npc']} @ {s.get('loc')}" if s.get('npc') else '') + f"  | экран {scr}")
    print(f"чтений диска: файлов {len(T['reads'])}")
    out = Path(a.out or Path(a.dir) / 'timeline.json'); out.write_text(json.dumps(T, ensure_ascii=False, indent=1)); print('→', out)


def cmd_gate(a):
    """гейт: снимки прогона на сменах этапа → (тип цели, номер текста, значок) по порядку = этапы миссии из скрипта диска.
    Красный контроль: TWINS_BREAK=msn_offset — поле текста читается со сдвигом +4 байта, гейт обязан упасть"""
    global ST_MSG
    if 'msn_offset' in os.environ.get('TWINS_BREAK', ''): ST_MSG += 4
    sys.path.insert(0, str(C.WT / 'tools/missions')); sys.path.insert(0, str(C.WT / 'hit-and-run-web/tools'))
    import compile as MC
    c = MC.Compiler(a.level); c.compile(); P = c.pack; S = lambda i: P.strings[i]
    m = next(x for x in P.missions if S(x[0]) == a.mission)
    want = []
    for phi in (m[5], m[6]):
        if phi == 0xFFFF: continue
        ph = P.phases[phi]
        for st in P.stages[ph[6]:ph[6] + ph[7]]:
            want.append((MC.CMD.OBJECTIVES[st[9] - 1], None if st[4] == 0xFFFF else st[4], S(st[6])))
    d = Path(a.dir); rows = [ln.split('\t') for ln in (d / 'stages.tsv').read_text().splitlines()[1:]]
    got, last = [], None
    for f in rows:
        fr, ptr = int(f[0]), int(f[1], 16)
        if ptr == last: continue
        last = ptr; sp = d / f'snap_{fr + 10:05d}.p2s'
        if not sp.exists(): sp = next(iter(sorted(d.glob(f'snaps/snap_{fr + 10:05d}.p2s'))), sp)
        r = decode_stage(load_ee(sp)); got.append((fr, r.get('obj_name') or r.get('obj'), r.get('msg'), r.get('icon') or ''))
    ok, n = True, min(len(want), len(got))
    for k in range(n):
        w, g = want[k], got[k]
        same = w[0] == g[1] and w[1] == g[2] and (w[2] or '') == g[3]
        ok &= same
        print(f"{'=' if same else '≠'} этап {k}: скрипт {w[0]} №{w[1]} значок {w[2] or '—'} | память кадр {g[0]}: {g[1]} №{g[2]} значок {g[3] or '—'}")
    ok &= n >= a.min
    print(f"сверено этапов {n} (нужно ≥ {a.min}) → {'PASS' if ok else 'FAIL'}" + (' [TWINS_BREAK=msn_offset]' if 'msn_offset' in os.environ.get('TWINS_BREAK', '') else ''))
    sys.exit(0 if ok else 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    r = sp.add_parser('run'); r.add_argument('--plan', default='m0', choices=['m0', 'sr3']); r.add_argument('--out', required=True)
    r.add_argument('--frames', type=int, default=9000); r.add_argument('--snap', type=int, default=100); r.add_argument('--png', type=int, default=50)
    r.add_argument('--renderer', default='sw'); r.add_argument('--cdvd', action='store_true', help='чтения диска с кадром в log.txt (msn_timeline.py reads)')
    d = sp.add_parser('dig'); d.add_argument('labels'); d.add_argument('--out'); d.add_argument('--show', type=int, default=40)
    d.add_argument('--lo'); d.add_argument('--hi')
    q = sp.add_parser('read'); q.add_argument('--labels'); q.add_argument('--dir'); q.add_argument('--addr', nargs='+', required=True)
    t = sp.add_parser('timeline'); t.add_argument('dir'); t.add_argument('--mission', default='m0'); t.add_argument('--out')
    g = sp.add_parser('gate'); g.add_argument('dir'); g.add_argument('--mission', default='m0'); g.add_argument('--level', type=int, default=1)
    g.add_argument('--min', type=int, default=6, help='сколько этапов обязано совпасть')
    a = ap.parse_args()
    {'run': cmd_run, 'dig': cmd_dig, 'read': cmd_read, 'timeline': cmd_timeline, 'gate': cmd_gate}[a.cmd](a)


if __name__ == '__main__':
    main()
