#!/usr/bin/env python3
"""Трасса клипа оригинала (станок С2): запись ввода .p2m2 проигрывается в PCSX2 (tools/ps2ref/play.sh), по PINE каждый кадр
читаются адреса карты tools/ps2ref/addrs.tsv непрерывным опросом. Диск PAL: PCSX2 идёт 50 кадров в секунду (часы игры +7,2 с
за 360 кадров записи), игра считает физику 25 раз в секунду (счётчик кадров +2 за такт); метка трассы — кадр записи (1/50 с),
а матрицу машины пишет посреди такта: каждое НОВОЕ состояние (матрица) записывается с меткой счётчика в момент его первого
появления — метка детерминирована, пока опрос быстрее промежутка между записью матрицы и следующим шагом счётчика.
  python3 tools/ps2ref/trace.py CLIP.p2m2 OUT.tsv            PCSX2 уже запущен (tools/ps2ref/launch.py), PINE включён
  python3 tools/ps2ref/trace.py --probe [--addrs FILE]      проба карты адресов на клипе t0 (разгон прямо): каждый адрес
                                                            проверяется по смыслу; сломанный адрес обязан дать FAIL
  python3 tools/ps2ref/trace.py --same A.tsv B.tsv          два прохода одного клипа: покадрово одинаково?"""
import math, os, struct, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from pine import Pine, MSG
ROOT = Path(__file__).resolve().parents[2]
from profile import owned_pid
PID = lambda: str(owned_pid(int(os.environ.get('PS2REF_SLOT', '28121')) - 28120))


def addrs(path=None):
    A = {}
    for l in Path(path or ROOT / 'tools/ps2ref/addrs.tsv').read_text().splitlines():
        if l.strip() and not l.startswith('#'):
            f = l.split('\t'); A[f[0]] = (int(f[1], 16), f[2], int(f[3]))   # имя, адрес, тип (u32/f32), сколько подряд
    return A


def menu_pause():
    subprocess.run(['osascript', '-e', f'tell application "System Events" to tell (first process whose unix id is {PID()}) to click menu item "Pause" of menu 1 of menu bar item "System" of menu bar 1'], capture_output=True)


def trace(clip, out, amap=None, frames=None):
    A = addrs(amap)
    # запись запускать на идущей игре: PCSX2 грузит её сохранение и встаёт на паузу в кадре 0. На время загрузки соединение
    # PINE не держим; клиента PINE посреди ответа не убивать — PCSX2 умирает от SIGPIPE
    q = Pine(timeout=2); before = q.r32(A['frame'][0]); q.s.close()
    r = subprocess.run([str(ROOT / 'tools/ps2ref/play.sh'), str(clip)], capture_output=True, text=True, timeout=120)
    if r.returncode: raise RuntimeError('play.sh: ' + (r.stdout + r.stderr).strip()[-300:])
    # кадр 0 записи: пауза, счётчик уже не прежний (сохранение записи загружено) и не меняется полсекунды
    prev_c, stable, p = None, 0, None
    for _ in range(100):   # PINE обслуживает одного клиента: соединение закрывать всегда, иначе следующие ждут вечно
        p = None
        try:
            p = Pine(timeout=2); st = p.status(); c = p.r32(A['frame'][0])
            stable = stable + 1 if (c == prev_c and st == 'пауза' and c != before) else 0; prev_c = c
            if stable >= 3: break
        except OSError: pass
        if p: p.s.close()
        time.sleep(0.3)
    else: raise RuntimeError('запись не встала в кадр 0')
    cnt = A['frame'][0]; names = [n for n in A if n != 'frame']
    calls = [(MSG['r32'], struct.pack('<I', cnt))]
    for n in names:
        a, t, k = A[n]; calls += [(MSG['r32'], struct.pack('<I', a + 4 * i)) for i in range(k)]
    calls.append((MSG['r32'], struct.pack('<I', cnt)))
    def sample():
        d = p.batch(calls); v = struct.unpack('<%dI' % (len(d) // 4), d)
        if v[0] != v[-1]: return None
        row, i = [v[0]], 1
        for n in names:
            a, t, k = A[n]
            row += [struct.unpack('<f', struct.pack('<I', x))[0] if t == 'f32' else x for x in v[i:i + k]]; i += k
        return row
    rows = {}; r0 = sample(); rows[r0[0]] = r0; f0 = r0[0]; prev = tuple(r0[1:]); polls = 0; clash = 0
    menu_pause()   # снять паузу: запись пошла
    t0 = last = time.time(); total = frames or (Path(clip).stat().st_size - 570) // 36; fcur = f0
    limit = time.time() + total / 30 + 60   # общий предел: запись в реальном времени вдвое медленнее + минута
    while time.time() - last < 3.0 and time.time() < limit:
        r = sample(); polls += 1
        if not r: continue
        if r[0] != fcur: fcur = r[0]; last = time.time()
        if tuple(r[1:]) != prev:   # новое состояние: метка — счётчик при первом появлении
            if r[0] in rows: clash += 1   # два новых состояния за одну метку — опрос опоздал
            rows[r[0]] = r; prev = tuple(r[1:])
        if r[0] - f0 >= total: break   # конец записи по счётчику (PCSX2 встаёт на паузу в конце не всегда)
    print(f'опросов {polls} за {time.time() - t0:.1f} с ({polls / max(1e-3, time.time() - t0):.0f}/с), совпадений меток {clash}')
    if p.status() == 'идёт': menu_pause()   # держать мир в конце записи (снимок памяти, проверки)
    hdr = ['frame'] + [f'{n}{i}' if A[n][2] > 1 else n for n in names for i in range(A[n][2])]
    L = ['\t'.join(hdr)] + ['\t'.join([str(r[0] - f0)] + ['%.6g' % x if isinstance(x, float) else str(x) for x in r[1:]]) for _, r in sorted(rows.items())]
    Path(out).write_text('\n'.join(L) + '\n')
    miss = clash
    return rows, f0, miss


def load(path):
    lines = Path(path).read_text().splitlines()
    if not lines: raise ValueError('пустой файл')
    h = lines[0].split('\t')
    if len(h) < 2 or h[0] != 'frame' or len(set(h)) != len(h) or any(not x for x in h):
        raise ValueError('неверные колонки')
    rows = {}; previous = -1
    for line in lines[1:]:
        fields = line.split('\t')
        if len(fields) != len(h): raise ValueError('неполная строка')
        frame = int(fields[0])
        if frame <= previous: raise ValueError('повтор или обратный порядок кадров')
        if not all(math.isfinite(float(x)) for x in fields[1:]): raise ValueError('NaN/Inf')
        rows[frame] = fields[1:]; previous = frame
    return h, rows


def same(a, b, expected_frames=None, step=2):
    """Dense trace: frame zero, every physics tick, finite values, same schema.
    Live gates must supply expected_frames from the input recording, not the traces.
    Without it this checks internal coverage only, not completion of a scenario.
    """
    try:
        if step < 1: raise ValueError('неверный шаг')
        ha, A = load(a); hb, B = load(b)
        if ha != hb: raise ValueError('разные колонки')
        for rows in (A, B):
            fr = list(rows)
            if len(fr) < 2: raise ValueError('пустая или слишком короткая трасса')
            if fr[0] != 0 or any(y - x != step for x, y in zip(fr, fr[1:])):
                raise ValueError('неполное покрытие кадров')
            if expected_frames is not None:
                if expected_frames < step * 2 or fr[-1] not in (expected_frames - step, expected_frames):
                    raise ValueError('трасса не покрывает длину сценария')
        if A != B: raise ValueError('разные кадры или значения')
    except (OSError, ValueError, IndexError) as e:
        print('FAIL:', e); return False
    print(f'OK: {len(A)} кадров, одинаковые колонки, полное покрытие' + (' заданного сценария' if expected_frames is not None else 'между первой и последней метками'))
    return True


def probe(amap=None):
    """Проба карты на клипе t0 (разгон прямо 4 с из машины у дома): счётчик +1 за кадр, матрица ортонормальна, позиция
    сдвинулась > 5 м вдоль «вперёд» матрицы, скорость из позиции согласована с адресом скорости (если он есть)."""
    out = ROOT / 'build/ps2ref/clips/t0/probe.tsv'; rows, f0, miss = trace(ROOT / 'build/ps2ref/clips/t0/t0.p2m2', out, amap)
    h, R = load(out); fr = sorted(R); col = {n: i for i, n in enumerate(h[1:])}
    val = lambda f, n: float(R[f][col[n]])
    why = []
    steps = [b - a for a, b in zip(fr, fr[1:])]
    if not fr or len(fr) < 100 or fr[-1] - fr[0] < 300: why.append(f'счётчик кадров: {len(fr)} состояний, до кадра {fr[-1] - fr[0] if fr else 0}')
    bad = [s_ for s_ in steps if s_ != 2]   # такт физики = 2 кадра: шаг метки ровно 2 (сломанный адрес счётчика так не растёт)
    if bad: why.append(f'счётчик кадров: шаги {sorted(set(steps))[:6]}, не по 2 — {len(bad)} раз')
    for f in fr[::30]:
        m = [[val(f, f'mat{4 * r + c}') for c in range(3)] for r in range(3)]
        for r in range(3):
            n = math.sqrt(sum(x * x for x in m[r]))
            if abs(n - 1) > .02: why.append(f'матрица: строка {r} длины {n:.3f} в кадре {f}'); break
        if why: break
    p0 = [val(fr[0], f'mat{12 + i}') for i in range(3)]; p1 = [val(fr[-1], f'mat{12 + i}') for i in range(3)]
    fw = [val(fr[0], f'mat{8 + i}') for i in range(3)]; dx = [b - a for a, b in zip(p0, p1)]
    along = sum(a * b for a, b in zip(dx, fw))
    if not (math.dist(p0, p1) > 5 and along > 3): why.append(f'позиция: сдвиг {math.dist(p0, p1):.1f} м, вдоль «вперёд» {along:.1f} м')
    print(f"проба карты: кадров {len(fr)} (пропущено {miss}), сдвиг {math.dist(p0, p1):.1f} м, вдоль вперёд {along:.1f} м -> {'FAIL: ' + '; '.join(why) if why else 'OK'}")
    return not why


def main():
    a = sys.argv[1:]
    if not a: print(__doc__); return 2
    am = a[a.index('--addrs') + 1] if '--addrs' in a else None
    if a[0] == '--probe': return 0 if probe(am) else 1
    if a[0] == '--same':
        expected = int(a[a.index('--expected-frames') + 1]) if '--expected-frames' in a else None
        return 0 if same(a[1], a[2], expected) else 1
    rows, f0, miss = trace(a[0], a[1], am); print(a[1], len(rows), 'кадров, пропущено', miss); return 0


if __name__ == '__main__':
    sys.exit(main())
