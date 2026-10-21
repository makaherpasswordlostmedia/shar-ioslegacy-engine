"""Близнецы · сторона «Оригинал» (docs/handoff/БЛИЗНЕЦЫ_2026-10-01.md §1): свой PCSX2 скрыто, через tools/ps2ref/ask.py.

Профиль близнецов — observer3 (PINE 28123; observer1 — у терминала и оракула). setup(): ввод observer3 очищен для автоматики
(раскладка Pad1 Роба и SDL сняты — ОРАКУЛ_PS2 §8), звук выключен; прежний ini — копией в build/twins/backup/. Личный PCSX2 Роба,
его ini и слот 28011 не трогаются (ask.py сверяет хеши его профиля до и после).
Запуск — только проверенный скрытый ask.launch_hidden (-nogui, open -j -g, QT_MAC_SET_RAISE_PROCESS=0) со сторожем фокуса:
наш PID впереди или наше окно на экране -> остановить свой PID, FAIL. Попытки считаются в build/twins/orig_attempts.tsv:
после 3 подряд неудачных запусков (окно/фокус/не поднялся) — отказ до разбора (правило Роба «не больше 3 попыток»).
Запись в память — только через ask.py (его сторож: имена addrs.tsv с «можно», по одному); точка = состояние оригинала,
синхронизация хирургией тела (car_cm, car_vel) — только если точка не совпадает с позой состояния."""
import json, math, os, re, shutil, sys, zipfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
sys.path.insert(0, str(C.WT / 'tools/ps2ref'))
import profile as prof   # noqa: E402
import ask               # noqa: E402

ATTEMPTS = C.OUT / 'orig_attempts.tsv'
TRACE = ['frame', 'mat', 'car_cm', 'car_vel', 'coins', 'hnr', 'chase']


class OrigFail(Exception):
    pass


def bind():
    """ask.py и profile.py из рабочей копии, данные (диск, состояния, профили) — основной папки проекта."""
    prof.ROOT = C.DATA; prof.BASE = C.DATA / 'build/ps2ref/profiles'
    ask.ROOT = C.DATA; ask.ISO = C.DATA / 'game/Hit and Run.iso'; ask.WINS = C.DATA / 'build/ps2ref/bin/wins'
    ask.ADDRS = C.WT / 'tools/ps2ref/addrs.tsv'


def setup(idx=C.PROFILE):
    """observer3 -> профиль автоматики (идемпотентно). Возвращает список изменений."""
    bind()
    base = prof.BASE / f'observer{idx}'; ini = base / 'data/inis/PCSX2.ini'
    if not (base / 'PCSX2.app').exists() or not ini.exists():
        raise OrigFail(f'нет observer{idx} (копия PCSX2.app и ini) — новую копию .app близнецы не делают')
    t = ini.read_text(); changes = []
    bk = C.OUT / 'backup' / f'observer{idx}-PCSX2.ini.orig'
    if not bk.exists(): bk.parent.mkdir(parents=True, exist_ok=True); bk.write_text(t); changes.append(f'копия прежнего ini -> {bk.relative_to(C.DATA)}')
    if re.search(r'^OutputMuted = false$', t, re.M): t = re.sub(r'^OutputMuted = false$', 'OutputMuted = true', t, flags=re.M); changes.append('звук выключен')
    m = re.search(r'^\[InputSources\]\n(.*?)(?=^\[)', t, re.M | re.S)
    if m and ('SDL = true' in m.group(1) or 'Keyboard' in m.group(1)):
        t = t[:m.start(1)] + 'SDL = false\n\n\n' + t[m.end(1):]; changes.append('ввод SDL/клавиатуры снят')
    m = re.search(r'^\[Pad1\]\n(.*?)(?=^\[|\Z)', t, re.M | re.S)
    if m and m.group(1).strip() != 'Type = DualShock2':
        t = t[:m.start(1)] + 'Type = DualShock2\n\n\n' + t[m.end(1):]; changes.append('раскладка Pad1 снята (пустой DualShock2)')
    if changes: ini.write_text(t)
    prof.validate(idx)
    return changes


def _attempts():
    if not ATTEMPTS.exists(): return []
    return [l.split('\t') for l in ATTEMPTS.read_text().splitlines()[1:] if l.strip()]


def _log_attempt(rid, ok, why):
    if not ATTEMPTS.exists(): ATTEMPTS.parent.mkdir(parents=True, exist_ok=True); ATTEMPTS.write_text('время\tid\tитог\tпричина\n')
    with ATTEMPTS.open('a') as f: f.write(f'{C.clock()}\t{rid}\t{"ok" if ok else "FAIL"}\t{why}\n')


def _with_open_errors(fn, *a):
    """ask.launch_hidden зовёт `open ... check=True` без вывода: при отказе причина терялась (01.10 01:31). Здесь тот же вызов
    с перехватом текста ошибки `open`; всё остальное — как в ask.py."""
    import subprocess
    real = subprocess.run

    def patched(cmd, *pa, **pk):
        if isinstance(cmd, list) and cmd[:1] == ['open']:
            r = real(cmd, capture_output=True, text=True)
            if r.returncode: raise OrigFail(f'open вернул {r.returncode}: ' + ((r.stderr or '') + (r.stdout or '')).strip()[:400])
            return r
        return real(cmd, *pa, **pk)
    subprocess.run = patched
    try: return fn(*a)
    finally: subprocess.run = real


def state_pose(state):
    """поза машины в самом состоянии (атомарный снимок eeMemory.bin): начало модели, курс, скорость, кадр"""
    with zipfile.ZipFile(state) as z: ee = z.read('eeMemory.bin')
    a = ask.load_addrs(ask.ADDRS)
    mat = [ask.value_in(ee, a['mat'][0] + 4 * i, 'f32') for i in range(16)]
    vel = [ask.value_in(ee, a['car_vel'][0] + 4 * i, 'f32') for i in range(3)]
    return dict(pos=mat[12:15], heading=C.yaw_of_mat(mat), vel=vel, frame=ask.value_in(ee, a['frame'][0], 'u32'))


def recipe_for(point, frames, rid):
    st = C.DATA / point['state']
    r = dict(id=rid, profile=C.PROFILE, state=point['state'], state_sha256=C.sha256(st), frames=int(frames), every=2,
             trace=TRACE, shots=[int(frames)])
    if point.get('teleport'):   # точка не в позе состояния: тело машины (одна операция телепорта) и нулевая скорость, 2 отсчёта
        x, y, z = point['teleport']
        r['writes'] = [dict(name=f'car_cm[{i}]', value=v, at=10, hold=2) for i, v in enumerate((x, y, z))] + \
                      [dict(name=f'car_vel[{i}]', value=0.0, at=10, hold=2) for i in range(3)]
    return r


def run_point(point, run, frames, fresh=False):
    """-> (пакет, сведения). Кэш: тот же рецепт (sha) с ok-ответом не гоняется второй раз (без ввода игра повторяется байт в байт,
    ask.py --repeat 30.09); --fresh — заново."""
    bind()
    import hashlib
    key = hashlib.sha256(json.dumps(dict(recipe_for(point, frames, 'x'), id=None), sort_keys=True).encode()).hexdigest()[:10]
    rid = f'twins_{point["name"]}_{key}'
    rec = recipe_for(point, frames, rid)
    rp = run / 'recipes' / f'{rid}.json'; rp.parent.mkdir(parents=True, exist_ok=True); rp.write_text(json.dumps(rec, ensure_ascii=False, indent=1))
    ans = C.DATA / 'build/ps2ref/answers' / rid
    rep = None
    if not fresh and (ans / 'report.json').exists():
        rep = json.loads((ans / 'report.json').read_text())
        if not rep.get('ok'): rep = None
    cached = rep is not None
    if rep is None:
        bad = 0
        for row in reversed(_attempts()):
            if row[2] == 'ok': break
            bad += 1
        if bad >= 3: raise OrigFail('3 неудачных запуска PCSX2 подряд (build/twins/orig_attempts.tsv) — стоп до разбора, новых попыток нет')
        ask.check_recipe(rp)   # сторож записи и адресов до запуска
        try: rep = _with_open_errors(ask.run, rp)
        except Exception as e:
            _log_attempt(rid, False, f'{type(e).__name__}: {e}'[:300]); raise OrigFail(f'оригинал не запустился: {e}')
        why = rep.get('error') or ('окно/фокус: ' + ','.join(rep.get('focus_violations') or []) if rep.get('focus_violations') else '')
        _log_attempt(rid, bool(rep.get('ok')), why or 'чисто')
        if not rep.get('ok'): raise OrigFail(f'оригинал: {why or "прогон не ok"} (build/ps2ref/answers/{rid}/report.json)')
    return orig_packet(point['name'], run, ans, int(frames)), dict(recipe=str(rp.relative_to(C.DATA)), answer=str(ans.relative_to(C.DATA)),
                                                                   cached=cached, game_fps=rep.get('game_fps'), pcsx2=rep.get('pcsx2'),
                                                                   profile=rep.get('profile'), focus=rep.get('focus_violations'),
                                                                   personal_profile_unchanged=rep.get('personal_profile_unchanged'))


def orig_packet(name, run, ans, frames):
    rows = [l.split('\t') for l in (ans / 'trace.tsv').read_text().splitlines()]
    head, rows = rows[0], rows[1:]
    col = {k: i for i, k in enumerate(head)}
    last = rows[-1]
    v = lambda k: float(last[col[k]])
    p = C.packet(name, 'orig')
    p['frame'] = int(float(last[col['rel']]))
    mat = [v(f'mat[{i}]') for i in range(16)]
    p['pos'] = [round(x, 5) for x in mat[12:15]]
    p['heading'] = round(C.yaw_of_mat(mat), 6)
    p['vel'] = [round(v(f'car_vel[{i}]'), 5) for i in range(3)]
    shot = ans / f'shot_{frames}.png'
    if shot.exists():
        dst = run / 'shots' / f'{name}_orig.png'; dst.parent.mkdir(exist_ok=True); shutil.copy2(shot, dst)
        p['shot'] = str(dst.relative_to(run))
    return p
