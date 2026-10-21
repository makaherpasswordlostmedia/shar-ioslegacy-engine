#!/usr/bin/env python3
"""О1 · вопрос оригиналу без рук и без окна (ОРАКУЛ_PS2 §3): tools/ps2ref/ask.py РЕЦЕПТ.json [--check]

Рецепт (JSON): {"id", "profile": 1..3, "state": "build/ps2ref/….p2s", "state_sha256",
  "frames": сколько кадров игры идти (единицы счётчика frame 0x5167d8, 50 в секунду PAL),
  "trace": ["frame", "mat", "mat[12]", …] — имена из addrs.tsv (целиком или элемент), "every": шаг строк в кадрах,
  "writes": [{"at": кадр от старта, "name": имя, "value": число, "hold": кадров держать}],
  "shots": [кадры от старта] — PINE save → Screenshot.png и eeMemory.bin (атомарный снимок для dig.py),
  "stop": {"name", "op": "<|<=|>|>=|==|!=", "value"} — досрочная остановка}
Выход build/ps2ref/answers/<id>/: trace.tsv, shot_<кадр>.png, snap_<кадр>.p2s, report.json (sha256 состояния и рецепта,
версия PCSX2, адреса, темп, фокус, окна, хеши личного профиля Роба до/после). В консоль — сводка до 20 строк.

Запуск (диагноз 30.09, MainWindow.cpp/QtHost.cpp v2.6.3): фокус забирал raise() главного окна на старте →
[NSApp activateIgnoringOtherApps]. Поэтому: -nogui (главное окно не показывается и не поднимается), open -j -g (скрыто, без
вывода вперёд), QT_MAC_SET_RAISE_PROCESS=0 (raise не активирует процесс). Сторож каждые 50 мс: наш PID впереди
(lsappinfo) или наше окно на экране (wins) → остановить свой PID, FAIL. Останавливаем только свой PID (profile.owned_pid).
--check: только проверка рецепта и адресов, без запуска. --gate: гейты без запуска (испорченный адрес/имя, чужое состояние →
FAIL). --repeat РЕЦЕПТ: тот же рецепт дважды, значения по одинаковым кадрам должны совпасть (без ввода игра повторяется?).
Кадры рецепта ("at", "shots", "frames") — от счётчика frame в самом состоянии, поэтому одинаковы в каждом прогоне;
PINE подключается через 1–3 с после старта, раньше этого записи и снимки не успеют.
Не проверено вживую (30.09): запуск упёрся в системное окно доступа к «Загрузкам», см. STATUS.md.""" 
import hashlib, json, math, os, re, shutil, struct, subprocess, sys, threading, time, zipfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import profile as prof
from pine import Pine, MSG

ROOT = prof.ROOT
ADDRS = ROOT / 'tools/ps2ref/addrs.tsv'
ISO = ROOT / 'game/Hit and Run.iso'
WINS = ROOT / 'build/ps2ref/bin/wins'
EE = 32 << 20
TYPES = {'u8': ('<B', 1, MSG['r8']), 'u16': ('<H', 2, MSG['r16']), 'u32': ('<I', 4, MSG['r32']),
         's32': ('<i', 4, MSG['r32']), 'f32': ('<f', 4, MSG['r32'])}
TYPES['ptr'] = TYPES['u32']   # addrs.tsv:23 (player_sim) помечен ptr: указатель EE = u32; без псевдонима orig2/rampjump/placement падали на загрузке таблицы
OPS = {'<': lambda a, b: a < b, '<=': lambda a, b: a <= b, '>': lambda a, b: a > b, '>=': lambda a, b: a >= b,
       '==': lambda a, b: a == b, '!=': lambda a, b: a != b}
SAVE_SLOT = 9


class Fail(Exception):
    pass


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load_addrs(path=None):
    """имя → (адрес, тип, сколько); испорченная строка → Fail с причиной."""
    out = {}; path = path or ADDRS
    for n, line in enumerate(Path(path).read_text().splitlines(), 1):
        if not line.strip() or line.startswith('#'): continue
        f = line.split('\t')
        if len(f) < 4: raise Fail(f'addrs.tsv:{n}: ждём 4+ столбца (имя адрес тип сколько), а тут {len(f)}')
        name, a, typ, cnt = f[:4]
        if not re.fullmatch(r'[a-z][a-z0-9_]*', name): raise Fail(f'addrs.tsv:{n}: плохое имя {name!r}')
        try: addr = int(a, 16)
        except ValueError: raise Fail(f'addrs.tsv:{n}: {name}: адрес {a!r} не шестнадцатеричный')
        if typ not in TYPES: raise Fail(f'addrs.tsv:{n}: {name}: тип {typ!r} не из {sorted(TYPES)}')
        try: cnt = int(cnt)
        except ValueError: raise Fail(f'addrs.tsv:{n}: {name}: сколько {cnt!r} не число')
        size = TYPES[typ][1]
        if cnt < 1 or addr % size or addr < 0 or addr + size * cnt > EE:
            raise Fail(f'addrs.tsv:{n}: {name}: адрес 0x{addr:x}×{cnt} {typ} вне памяти EE (32 МБ) или не выровнен')
        out[name] = (addr, typ, cnt)
    if 'frame' not in out: raise Fail('addrs.tsv: нет счётчика кадров frame — время только в кадрах игры')
    return out


BODY = {'car_cm', 'car_vel'}   # тело машины: позиция и скорость — одна операция телепорта с толчком


def writable(path=None):
    """имена, в которые можно писать: 9-й столбец addrs.tsv «запись» = «можно» (адрес данных меняется в снимках и запись
    в него подтверждена вторым событием). Правило после сбоя 22:00 (87 меток в непроверенные адреса уронили PCSX2)."""
    out = set()
    for line in Path(path or ADDRS).read_text().splitlines():
        if not line.strip() or line.startswith('#'): continue
        f = line.split('\t')
        if len(f) >= 9 and f[8].strip() == 'можно': out.add(f[0])
    return out


def resolve(name, addrs):
    """'mat' → все элементы; 'mat[12]' → один. Возвращает [(колонка, адрес, тип)]."""
    m = re.fullmatch(r'([a-z][a-z0-9_]*)(?:\[(\d+)\])?', name)
    if not m: raise Fail(f'рецепт: имя {name!r} — не имя и не имя[индекс]')
    if m.group(1) not in addrs: raise Fail(f'рецепт: имени {m.group(1)!r} нет в addrs.tsv')
    addr, typ, cnt = addrs[m.group(1)]; size = TYPES[typ][1]
    if m.group(2) is None:
        return [(m.group(1) if cnt == 1 else f'{m.group(1)}[{i}]', addr + i * size, typ) for i in range(cnt)]
    i = int(m.group(2))
    if i >= cnt: raise Fail(f'рецепт: {name}: индекс вне 0..{cnt - 1}')
    return [(name, addr + i * size, typ)]


def raw(e):
    """Сырой адрес раскопки: {"addr": "hex", "type": "f32", "label": "..."} → (колонка, адрес, тип)."""
    try: addr = int(str(e['addr']), 16); typ = e.get('type', 'f32')
    except (KeyError, ValueError): raise Fail(f'рецепт: сырой адрес {e!r} — нужен "addr" в hex')
    if typ not in TYPES: raise Fail(f'рецепт: тип {typ!r} не из {sorted(TYPES)}')
    if addr % TYPES[typ][1] or not 0 <= addr < EE - TYPES[typ][1] + 1: raise Fail(f'рецепт: 0x{addr:x} вне EE или не выровнен')
    return (e.get('label') or f'@{addr:x}', addr, typ)


def value_in(ee, addr, typ):
    return struct.unpack_from(TYPES[typ][0], ee, addr)[0]


def check_recipe(path):
    """Проверка без запуска. Возвращает (рецепт, колонки трассы, записи, ee состояния)."""
    path = Path(path)
    try: r = json.loads(path.read_text())
    except (OSError, ValueError) as e: raise Fail(f'рецепт {path}: не читается как JSON ({e})')
    for k in ('id', 'state', 'state_sha256', 'frames', 'trace'):
        if k not in r: raise Fail(f'рецепт: нет поля {k!r}')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', str(r['id'])): raise Fail('рецепт: id — латиница, цифры, _.-')
    if r.get('profile', 1) not in (1, 2, 3): raise Fail('рецепт: profile только 1..3 (свои наблюдатели)')
    st = (ROOT / r['state']).resolve()
    if not st.is_relative_to((ROOT / 'build/ps2ref').resolve()): raise Fail('рецепт: состояние только из build/ps2ref')
    if not st.exists(): raise Fail(f'рецепт: нет состояния {r["state"]}')
    got = sha(st)
    if got != r['state_sha256']:
        raise Fail(f'чужое состояние: sha256 {got[:16]}… не совпадает с рецептом {str(r["state_sha256"])[:16]}…')
    addrs = load_addrs()
    cols = resolve('frame', addrs); named = set()
    for n in r['trace']:
        for c in (resolve(n, addrs) if isinstance(n, str) else [raw(n)]):
            if isinstance(n, str): named.add(c[0])
            if c[0] not in [x[0] for x in cols]: cols.append(c)
    writes = []; can = writable(); win = {}
    for w in r.get('writes', []):
        # сторож записи (L1_ФИНИШ П2, урок 14 КАНОН_УРОВНЯ): только по имени реестра, только «можно», по одному
        if 'name' not in w:
            raise Fail(f'запись в сырой адрес {w.get("addr")!r} запрещена: писать только в проверенный адрес addrs.tsv по имени (урок 22:00)')
        base = re.match(r'[a-z][a-z0-9_]*', str(w['name']))
        base = base.group(0) if base else str(w['name'])
        if base in addrs and base not in can:
            raise Fail(f'запись в {w["name"]!r} запрещена: в addrs.tsv у {base} нет «можно» (не проверен записью вторым событием)')
        if base not in BODY:
            a0 = int(w.get('at', 0)); win.setdefault(base, []).append((a0, a0 + int(w.get('hold', 0))))
            if len(win) > 2:
                raise Fail(f'пачка записей {sorted(win)}: кроме тела машины (car_cm, car_vel) — не больше двух проверенных адресов, по очереди')
        cs = resolve(w['name'], addrs)
        if len(cs) != 1: raise Fail(f'рецепт: запись {w["name"]!r} — укажите один элемент [i]')
        col, addr, typ = cs[0]
        src = None
        if 'from' in w:   # относительная запись: значение по другому адресу в тот же отсчёт + add (телепорт к подвижной цели)
            src = raw(w['from']); w = dict(w, value=float(w['from'].get('add', 0.0)))
        if not isinstance(w.get('value'), (int, float)): raise Fail(f'рецепт: запись {col}: value не число')
        until = None
        if 'until' in w:   # удержание записи до условия по величине в том же отсчёте (например, таймер ареста > 100)
            u = w['until']
            if u.get('op') not in OPS: raise Fail(f'рецепт: until.op из {sorted(OPS)}')
            uc = resolve(u['name'], addrs)[0] if 'name' in u else raw(u)
            if uc[0] not in [x[0] for x in cols]: cols.append(uc)
            until = (uc[0], u['op'], u['value'])
        writes.append(dict(at=int(w.get('at', 0)), hold=int(w.get('hold', 0)), col=col, addr=addr, typ=typ, value=w['value'], src=src, until=until))
    if len(win) == 2:   # «по одному»: два адреса — только в разные отсчёты (окна записи с удержанием не пересекаются)
        (n1, w1), (n2, w2) = win.items()
        if any(a1 <= b2 and a2 <= b1 for a1, b1 in w1 for a2, b2 in w2):
            raise Fail(f'пачка записей {sorted(win)}: {n1} и {n2} пишутся в одни отсчёты — только по одному, в разное время')
    if 'stop' in r:
        s = r['stop']
        if s.get('op') not in OPS: raise Fail(f'рецепт: stop.op из {sorted(OPS)}')
        resolve(s['name'], addrs)
    with zipfile.ZipFile(st) as z: ee = z.read('eeMemory.bin')
    for col, addr, typ in cols:   # адрес реестра указывает на мусор/код → в состоянии там не число (сырые адреса раскопки — без проверки)
        if col not in named and col != 'frame': continue
        v = value_in(ee, addr, typ)
        if typ == 'f32' and (not math.isfinite(v) or abs(v) > 1e7 or 0 < abs(v) < 1e-30):   # целые/указатели как float — денормали
            raise Fail(f'испорченный адрес: {col} = 0x{addr:x} в состоянии даёт {v!r} — не величина')
    if value_in(ee, cols[0][1], 'u32') == 0: raise Fail('frame в состоянии 0 — счётчик не тот')
    return r, cols, writes, ee


# ---------- живой запуск ----------

def front_pid():
    a = subprocess.run(['lsappinfo', 'front'], capture_output=True, text=True).stdout.strip()
    o = subprocess.run(['lsappinfo', 'info', '-only', 'pid', a], capture_output=True, text=True).stdout
    m = re.search(r'=(\d+)', o); return int(m.group(1)) if m else None


def onscreen(pid):
    if not WINS.exists(): subprocess.run(['swiftc', '-O', str(ROOT / 'tools/ps2ref/wins.swift'), '-o', str(WINS)], check=True)
    return [l for l in subprocess.run([str(WINS), str(pid)], capture_output=True, text=True).stdout.splitlines() if l.startswith('1 ')]


def our_pids(exe):
    out = subprocess.run(['ps', '-axo', 'pid=,command='], capture_output=True, text=True).stdout
    return [int(l.split(None, 1)[0]) for l in out.splitlines() if len(l.split(None, 1)) == 2 and l.split(None, 1)[1].startswith(exe + ' ')]


class Watchdog(threading.Thread):
    def __init__(self, pid, idx):
        super().__init__(daemon=True); self.pid = pid; self.idx = idx; self.bad = []; self.stop_flag = False
    def run(self):
        k = 0
        while not self.stop_flag:
            if front_pid() == self.pid: self.bad.append(('впереди', time.time()))
            if k % 5 == 0 and onscreen(self.pid): self.bad.append(('окно на экране', time.time()))
            if self.bad:
                try: os.kill(prof.owned_pid(self.idx), 15)
                except Exception: pass
                return
            k += 1; time.sleep(0.05)


def launch_hidden(idx, state):
    base, app, data = prof.prepare(idx); prof.validate(idx)
    exe = str(app / 'Contents/MacOS/PCSX2')
    if our_pids(exe): raise Fail(f'наш observer{idx} уже запущен — сначала profile.py --index {idx} stop')
    dst = data / 'sstates/ask_start.p2s'; shutil.copy2(state, dst)
    log = base / 'stdout.log'
    subprocess.run(['open', '-j', '-g', '-n', '--env', 'QT_MAC_SET_RAISE_PROCESS=0',
                    '--env', 'QT_MAC_DISABLE_FOREGROUND_APPLICATION_TRANSFORM=1', '-a', str(app),
                    '--stdout', str(log), '--stderr', str(log), '--args', '-portable', '-nogui', '-nofullscreen',
                    '-statefile', str(dst), '--', str(ISO)], check=True)
    for _ in range(100):
        p = our_pids(exe)
        if p: break
        time.sleep(0.05)
    else: raise Fail('PCSX2 не появился за 5 с')
    (base / 'process.json').write_text(json.dumps(dict(pid=p[0], slot=28120 + idx, executable=exe, started=time.time())) + '\n')
    return p[0], data


def stop_own(idx):
    try: pid = prof.owned_pid(idx)
    except Exception: return
    os.kill(pid, 15)
    for _ in range(100):
        if not subprocess.run(['ps', '-p', str(pid)], capture_output=True).returncode == 0: return
        time.sleep(0.1)
    os.kill(pid, 9)


def wcall(w):
    t, a, v = w['typ'], w['addr'], w['value']
    if t == 'f32': return (MSG['w32'], struct.pack('<If', a, float(v)))
    if t == 'u8': return (MSG['w8'], struct.pack('<IB', a, int(v) & 0xFF))
    if t == 'u16': return (MSG['w16'], struct.pack('<IH', a, int(v) & 0xFFFF))
    return (MSG['w32'], struct.pack('<II', a, int(v) & 0xFFFFFFFF))


def save_snapshot(p, data):
    old = max([f.stat().st_mtime for f in (data / 'sstates').glob(f'*.{SAVE_SLOT:02d}.p2s')], default=0)
    p.save(SAVE_SLOT)
    for _ in range(300):   # ≤ 30 с: файл дописывается после ответа PINE — ждём, пока размер стоит и zip читается
        c = [f for f in (data / 'sstates').glob(f'*.{SAVE_SLOT:02d}.p2s') if f.stat().st_mtime > old]
        if c:
            f = c[0]; s1 = f.stat().st_size; time.sleep(0.3)
            if f.stat().st_size == s1:
                try:
                    with zipfile.ZipFile(f) as z: z.getinfo('eeMemory.bin'); z.getinfo('Screenshot.png')
                    return f
                except (zipfile.BadZipFile, KeyError, OSError): pass
        time.sleep(0.1)
    raise Fail('PINE save: файл состояния не появился за 30 с')


def run(recipe_path):
    r, cols, writes, ee = check_recipe(recipe_path)
    c0 = value_in(ee, cols[0][1], 'u32')   # кадры рецепта считаются от счётчика в самом состоянии: одинаково в каждом прогоне
    idx = r.get('profile', 1); out = ROOT / 'build/ps2ref/answers' / r['id']
    if out.exists(): shutil.rmtree(out)
    out.mkdir(parents=True)
    before = prof.protected_hashes(); t0 = time.time()
    pid, data = launch_hidden(idx, ROOT / r['state'])
    wd = Watchdog(pid, idx); wd.start()
    rows, shots, p, err = [], [], None, None
    try:
        for _ in range(300):
            if wd.bad: raise Fail(f'окно забрало управление: {wd.bad[0][0]} — свой PID остановлен')
            try: p = Pine(28120 + idx, timeout=5); break
            except OSError: time.sleep(0.1)
        else: raise Fail('PINE не ответил за 30 с')
        for _ in range(300):
            try:
                if p.status() == 'идёт': p.title(); break
            except IOError: pass
            time.sleep(0.1)
        version = p.version()
        calls = [(TYPES[t][2], struct.pack('<I', a)) for _, a, t in cols]
        fmt = '<' + ''.join(TYPES[t][0][1] for _, _, t in cols)
        stop = r.get('stop'); stop_i = [c[0] for c in cols].index(resolve(stop['name'], load_addrs())[0][0]) if stop else None
        shot_at = sorted(set(int(x) for x in r.get('shots', []))); every = max(1, int(r.get('every', 1)))
        last = None
        while True:
            if wd.bad: raise Fail(f'окно забрало управление: {wd.bad[0][0]} — свой PID остановлен')
            ts = time.time(); vals = struct.unpack(fmt, p.batch(calls)); f = vals[0]
            rel = f - c0
            names = [c[0] for c in cols]
            for w in writes:
                if w.get('until') and w.get('done') is not None and w.get('stopped') is None:
                    n, op, v = w['until']
                    if OPS[op](vals[names.index(n)], v): w['stopped'] = rel
            due = [w for w in writes if rel >= w['at'] and w.get('stopped') is None and (w.get('done') is None or rel <= w['at'] + w['hold'])]
            if due:   # PINE не синхронен с кадром: все записи отсчёта одним пакетом на первом отсчёте не раньше "at"; факт — в отчёте
                rel_src = [w for w in due if w.get('src')]
                if rel_src:
                    got = struct.unpack('<' + 'f' * len(rel_src), p.batch([(MSG['r32'], struct.pack('<I', w['src'][1])) for w in rel_src]))
                    for w, g in zip(rel_src, got): w['base'] = g
                p.batch([wcall(dict(w, value=w['value'] + w.get('base', 0.0))) for w in due])
                for w in due: w.setdefault('done', rel); w['last'] = rel
            if last is None or f - last >= every: rows.append((round(ts - t0, 4), rel) + vals); last = f
            while shot_at and rel >= shot_at[0]:
                k = shot_at.pop(0); snap = save_snapshot(p, data)
                shutil.copy2(snap, out / f'snap_{k}.p2s')
                with zipfile.ZipFile(snap) as z: (out / f'shot_{k}.png').write_bytes(z.read('Screenshot.png'))
                with zipfile.ZipFile(snap) as z: sf = struct.unpack_from('<I', z.read('eeMemory.bin'), cols[0][1])[0]
                shots.append(dict(at=k, frame_in_snapshot=sf - c0, file=f'snap_{k}.p2s'))
            if rel >= int(r['frames']) or (stop and OPS[stop['op']](vals[stop_i], stop['value'])): break
    except Exception as e: err = str(e) if isinstance(e, Fail) else f'{type(e).__name__}: {e}'
    finally:
        wd.stop_flag = True
        if p: p.close()
        stop_own(idx)
    after = prof.protected_hashes()
    with (out / 'trace.tsv').open('w') as fo:
        fo.write('\t'.join(['t_mac', 'rel'] + [c[0] for c in cols]) + '\n')
        for row in rows: fo.write('\t'.join(f'{x:.6g}' if isinstance(x, float) else str(x) for x in row) + '\n')
    span = (rows[-1][1] - rows[0][1]) if len(rows) > 1 else 0; wall = (rows[-1][0] - rows[0][0]) if len(rows) > 1 else 0
    steps = sorted(b[1] - a[1] for a, b in zip(rows, rows[1:]))
    rep = dict(id=r['id'], ok=err is None and not wd.bad and before == after, error=err,
               recipe=str(recipe_path), recipe_sha256=sha(recipe_path), state=r['state'], state_sha256=r['state_sha256'],
               pcsx2=locals().get('version'), profile=idx, pine_slot=28120 + idx,
               addrs={c[0]: [hex(c[1]), c[2]] for c in cols}, rows=len(rows), frames=span,
               game_fps=round(span / wall, 2) if wall else None, median_step_frames=steps[len(steps) // 2] if steps else None,
               focus_violations=[b[0] for b in wd.bad], personal_profile_unchanged=before == after,
               personal_files=len(before), shots=shots, writes=[{k: w.get(k) for k in ('col', 'at', 'hold', 'value', 'base', 'done', 'last', 'stopped')} for w in writes])
    (out / 'report.json').write_text(json.dumps(rep, ensure_ascii=False, indent=1) + '\n')
    print(f"{'PASS' if rep['ok'] else 'FAIL'} {r['id']}: строк {len(rows)}, кадров {span}, темп {rep['game_fps']} к/с, "
          f"шаг {rep['median_step_frames']} к; фокус/окна {rep['focus_violations'] or 'чисто'}; личный профиль "
          f"{'тот же' if before == after else 'ИЗМЕНИЛСЯ'}; снимков {len(shots)}" + (f'; ошибка: {err}' if err else ''))
    print('→', out.relative_to(ROOT))
    return rep


def gate_offline():
    """Гейты О1 без запуска: хороший рецепт проходит; испорченное имя/адрес и чужое состояние — FAIL с причиной."""
    global ADDRS
    d = ROOT / 'build/ps2ref/gates/ask'; d.mkdir(parents=True, exist_ok=True)
    incar = 'build/ps2ref/state_l1_incar.p2s'; good = dict(id='gate_good', profile=1, state=incar, state_sha256=sha(ROOT / incar),
                                                           frames=100, trace=['mat[12]', 'mat[13]', 'mat[14]'])
    real = ADDRS; cases = []

    def case(name, recipe, addrs_text=None, expect_ok=False):
        global ADDRS
        rp = d / f'{name}.json'; rp.write_text(json.dumps(recipe, ensure_ascii=False))
        if addrs_text is not None: ap = d / f'{name}.addrs.tsv'; ap.write_text(addrs_text); ADDRS = ap
        try: check_recipe(rp); got, why = True, 'рецепт принят'
        except Fail as e: got, why = False, str(e)
        finally: ADDRS = real
        ok = got == expect_ok; cases.append(dict(case=name, expect='OK' if expect_ok else 'FAIL', got='OK' if got else 'FAIL', why=why, pass_=ok))
        print(f"{'PASS' if ok else 'ПРОМАХ'} {name}: ждём {'OK' if expect_ok else 'FAIL'}, получено {'OK' if got else 'FAIL'} — {why}")

    base = real.read_text()
    case('good', good, expect_ok=True)
    case('bad_name', dict(good, trace=['matt[12]']))
    case('bad_index', dict(good, trace=['mat[16]']))
    case('addr_not_hex', good, base.replace('mat\ta21870', 'mat\ta2187z'))
    case('addr_out_of_ee', good, base.replace('mat\ta21870', 'mat\t2a21870'))
    case('addr_misaligned', good, base.replace('mat\ta21870', 'mat\ta21872'))
    case('addr_not_a_value', good, base.replace('mat\ta21870', 'mat\ta21800'))
    case('frame_wrong', good, base.replace('frame\t5167d8', 'frame\t5167dc'))
    case('foreign_state', dict(good, state='build/ps2ref/state_l1_start.p2s'))
    # сторож записи (правила после сбоя 22:00, L1_ФИНИШ П2): только проверенные адреса реестра по имени и по одному
    tp = [dict(name=f'car_cm[{i}]', value=v, at=150, hold=2) for i, v in enumerate((215.0, 6.0, -170.2))]
    case('write_teleport_ok', dict(good, writes=tp + [dict(name='car_vel[2]', value=5.0, at=150, hold=10)]), expect_ok=True)
    case('write_raw_addr', dict(good, writes=[dict(addr='1298888', type='f32', value=7.0, at=150)]))
    case('write_unverified_name', dict(good, writes=[dict(name='hnr_view', value=50.0, at=150)]))
    case('write_batch_names', dict(good, writes=tp + [dict(name='hnr', value=100.0, at=150), dict(name='coins', value=80, at=150)]))
    case('write_two_in_turn_ok', dict(good, writes=tp + [dict(name='coins', value=200, at=100), dict(name='hnr', value=100.0, at=150)]), expect_ok=True)
    case('write_overlap_hold', dict(good, writes=[dict(name='coins', value=200, at=100, hold=60), dict(name='hnr', value=100.0, at=150)]))
    case('write_three_names', dict(good, writes=[dict(name='coins', value=200, at=100), dict(name='hnr', value=100.0, at=150),
                                                 dict(name='hnr_pause_ms', value=0.0, at=200)]))
    ok = all(c['pass_'] for c in cases)
    (ROOT / 'build/ps2ref/gates/ask_offline.json').write_text(json.dumps(dict(ok=ok, cases=cases), ensure_ascii=False, indent=1) + '\n')
    print('PASS' if ok else 'FAIL', f'{sum(c["pass_"] for c in cases)}/{len(cases)} → build/ps2ref/gates/ask_offline.json')
    return 0 if ok else 1


def repeat(path, reuse=False):
    """Гейт повторяемости: тот же рецепт дважды без ввода. Главное — атомарные снимки (PINE save) на тех же кадрах
    совпадают байт в байт (eeMemory.bin); трасса PINE — вторично: PINE не синхронен с кадром, отсчёт может попасть
    до или после обновления величины внутри кадра (фаза), такие расхождения считаются и показываются отдельно."""
    r = json.loads(Path(path).read_text()); ids = []
    for suf in ('a', 'b'):
        i = f'{r["id"]}_{suf}'; ids.append(i); rep = ROOT / f'build/ps2ref/answers/{i}/report.json'
        if reuse and rep.exists() and json.loads(rep.read_text())['ok']: continue
        rp = ROOT / f'build/ps2ref/gates/ask/{i}.json'; rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(json.dumps(dict(r, id=i), ensure_ascii=False))
        if not run(rp)['ok']: print('FAIL: прогон', suf); return 1
    snaps = []
    for k in sorted(set(int(x) for x in r.get('shots', []))):
        h = [hashlib.sha256(zipfile.ZipFile(ROOT / f'build/ps2ref/answers/{i}/snap_{k}.p2s').read('eeMemory.bin')).hexdigest() for i in ids]
        snaps.append(dict(at=k, same=h[0] == h[1]))
    rows = []
    for i in ids:
        d = {}
        for line in (ROOT / f'build/ps2ref/answers/{i}/trace.tsv').read_text().splitlines()[1:]:
            f = line.split('\t'); d[int(f[1])] = f[3:]
        rows.append(d)
    common = sorted(set(rows[0]) & set(rows[1])); bad = [k for k in common if rows[0][k] != rows[1][k]]
    res = dict(ok=bool(snaps) and all(x['same'] for x in snaps), snapshots=snaps, trace_common_frames=len(common),
               trace_phase_mismatches=len(bad), first_mismatch=bad[:5])
    (ROOT / f'build/ps2ref/gates/ask_repeat_{r["id"]}.json').write_text(json.dumps(res, ensure_ascii=False) + '\n')
    print(('PASS' if res['ok'] else 'FAIL'), 'повтор: снимки', ', '.join(f"кадр {x['at']} {'байт в байт' if x['same'] else 'РАЗНЫЕ'}" for x in snaps),
          f'| трасса PINE: общих кадров {len(common)}, расхождений фазы {len(bad)} {bad[:5]}')
    return 0 if res['ok'] else 1


def main():
    a = sys.argv[1:]
    if not a: print(__doc__); return 2
    if a[0] == '--gate': return gate_offline()
    if a[0] == '--repeat': return repeat(a[1], '--reuse' in a)
    try:
        if '--check' in a:
            r, cols, writes, _ = check_recipe(a[0])
            print(f'OK рецепт {r["id"]}: колонок {len(cols)}, записей {len(writes)}, состояние sha совпало'); return 0
        return 0 if run(a[0])['ok'] else 1
    except Fail as e:
        print('FAIL:', e); return 1


if __name__ == '__main__':
    sys.exit(main())
