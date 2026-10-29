#!/usr/bin/env python3
"""Изгородь K9-4 напротив дома держит машину на любой скорости, как на PS2 (ДОБИВКА п. 11; решение Роба 09.10 «изгороди как в
оригинале»; разбор knowledge/twins_library/разбор/twins_ps2.md: v200_hedge, v199_boom).

Записи PS2 (только чтение; HEDGE_K94_O4 — другая папка o4):
  v200_hedge/hedge.tsv — со старта L1 у дома газ импульсами до 4 м/с прямо в изгородь (tools/twins/hedge.py), 900 кадров
  v199_boom/boom.tsv   — тараны той же изгороди (tools/twins/boom.py): разгон, удар, задний ход, снова
Порт: tests/walls/hedge_k94.c (настоящие carUpdate/col, build/level.shr) повторяет ту же политику газа:
  v200 — тот же старт и газ импульсами; каждый таран v199, дошедший до изгороди, — от позы PS2 за 16 кадров (~0,3 с) до удара,
  скорость по сдвигу позиции PS2 между строками трассы, газ до удара, 40 кадров после.
Проверки (z — ось PS2, к изгороди растёт; «дальше» = наибольший z центра машины за прогон; допуск TOL = HEDGE_TOL гейта стен 0,5 м):
  v200: порт встал (v < 1 м/с после разгона > 3), дальше не дальше PS2 + TOL и не ближе PS2 − TOL; за 11 с газа после остановки
        сдвиг от места остановки не больше сдвига PS2 + TOL
  таран: выбираются тараны, где PS2 дошла до полосы изгороди (дальше ≥ линии остановки v200 − 1 м); порт не дальше PS2 + TOL;
        где PS2 упёрлась (дальше ≤ линии v200 + 1 м) — порт упёрся там же (|разница| ≤ TOL)
  самопроверка гейта: тот же прогон в мире без изгороди K9-4 (HEDGE_K94_NO_HEDGE=1 — порт-харнесс убирает ящики и капсулы
        common_gens10/17 у дома) обязан упасть: иначе гейт ничего не доказывает
  python3 tests/walls/hedge_k94.py [--old FLAG] -> 0 зелёный / 1 красный"""
import hashlib, json, os, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; os.chdir(ROOT)
sys.path.insert(0, str(ROOT / 'tools/twins'))
import common as C   # noqa: E402  (C.OUT — build/twins основной папки; записи там те же, cmp 09.10)
_cand = ([Path(os.environ['HEDGE_K94_O4'])] if os.environ.get('HEDGE_K94_O4') else
         [Path.home() / 'Downloads/shar-psp-ps2-w/build/twins/o4', C.OUT / 'o4'])
O4 = next((p for p in _cand if (p / 'v200_hedge/hedge.tsv').exists()), _cand[0])
OUT = ROOT / 'build/hedge_k94'; OUT.mkdir(parents=True, exist_ok=True)
TOL, BAND, LAUNCH = 0.5, 1.0, 8      # м; м; строк трассы (по 2 кадра) до удара


def tsv(p):
    L = p.read_text().splitlines(); h = L[0].split('\t')
    return [dict(zip(h, l.split('\t'))) for l in L[1:]]


def num(r, k):
    return float(r[k])


hed, boom = O4 / 'v200_hedge/hedge.tsv', O4 / 'v199_boom/boom.tsv'
src = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (hed, boom)}
H = tsv(hed); B = tsv(boom)


def stop_of(rows):
    """(кадр, z) первой остановки (v < 1 после v > 3), наибольший z, последняя строка"""
    fast, stop = False, None
    for r in rows:
        if num(r, 'v') > 3: fast = True
        if fast and stop is None and num(r, 'v') < 1: stop = (int(r['кадр']), num(r, 'z'), num(r, 'x'))
    return stop, max(num(r, 'z') for r in rows), rows[-1]


ps_stop, ps_reach, ps_end = stop_of(H)
line = ps_stop[1]                     # линия остановки PS2 у изгороди на 4 м/с (z центра машины)
runs = [dict(id='v200', inp=f"v200 {H[0]['x']} {H[0]['y']} {H[0]['z']} {H[0]['курс']} 0 0 0 pulse {H[-1]['кадр']} 4",
             ps2=dict(stop=ps_stop, reach=ps_reach, end=(num(ps_end, 'x'), num(ps_end, 'z'))))]
for i, r in enumerate(B):
    if not (i and r['фаза'] == 'удар' and B[i - 1]['фаза'] == 'разгон'): continue
    # скорость: величина — столбец v трассы PS2 (горизонтальная), направление — сдвиг позиции за 4 строки вокруг позы
    # (позиции в трассе с точностью 0,01 м, а такт физики PS2 не совпадает с шагом записи: сдвиг за одну строку скачет 15–23 м/с)
    a, b0, b1 = B[i - LAUNCH], B[i - LAUNCH - 2], B[i - LAUNCH + 2]
    dx, dz = num(b1, 'x') - num(b0, 'x'), num(b1, 'z') - num(b0, 'z'); L = (dx * dx + dz * dz) ** .5 or 1.0
    vx, vz = num(a, 'v') * dx / L, num(a, 'v') * dz / L
    win = [q for q in B[i - LAUNCH: i + 21]]              # до удара и 40 кадров после
    reach = max(num(q, 'z') for q in win)
    if reach < line - BAND: continue                      # таран не дошёл до изгороди (будка, машина, столб) — не про изгородь
    runs.append(dict(id='ram' + r['удар'], inp=f"ram{r['удар']} {a['x']} {a['y']} {a['z']} {a['курс']} {vx:.4f} {num(a, 'vy'):.4f} {vz:.4f} ram 400 0",
                     ps2=dict(reach=reach, v=round((vx * vx + vz * vz) ** .5, 2), x=num(a, 'x'), held=reach <= line + BAND)))
(OUT / 'runs.txt').write_text(''.join(q['inp'] + '\n' for q in runs))
(OUT / 'sources.json').write_text(json.dumps(src, ensure_ascii=False, indent=1) + '\n')


def port(tag, flags, env=None):
    exe = OUT / tag
    subprocess.run(['cc', '-std=c11', '-O2', '-w', '-DSKIN_HOST', '-Iviewer', *flags, 'tests/walls/hedge_k94.c', 'viewer/col.c', '-lm', '-o', str(exe)], check=True)
    log = subprocess.check_output([str(exe), str(ROOT / 'build/level.shr'), str(OUT / 'runs.txt')], text=True, env=dict(os.environ, **(env or {})))
    (OUT / (tag + '.log')).write_text(log)
    tr = {}
    for l in log.splitlines():
        c = l.split(); tr.setdefault(c[0], []).append(dict(кадр=c[1], x=c[2], y=c[3], z=c[4], v=c[5], курс=c[6]))
    return tr


def judge(tag, tr):
    ok = True
    for q in runs:
        rows = tr.get(q['id'], []); P = q['ps2']
        if not rows: print(f"FAIL {tag} {q['id']}: нет трассы порта"); ok = False; continue
        st, reach, end = stop_of(rows)
        if q['id'] == 'v200':
            ps_sh = ((P['end'][0] - P['stop'][2]) ** 2 + (P['end'][1] - P['stop'][1]) ** 2) ** .5
            sh = ((num(end, 'x') - st[2]) ** 2 + (num(end, 'z') - st[1]) ** 2) ** .5 if st else 99.0
            good = st is not None and abs(reach - P['reach']) <= TOL and sh <= ps_sh + TOL
            print(f"{'PASS' if good else 'FAIL'} {tag} v200 4 м/с: PS2 встала z {P['stop'][1]:.2f} (кадр {P['stop'][0]}), дальше {P['reach']:.2f}, "
                  f"сдвиг за газом {ps_sh:.2f} м; порт " + (f"встал z {st[1]:.2f} (кадр {st[0]}), дальше {reach:.2f}, сдвиг {sh:.2f} м, "
                  f"курс {float(rows[0]['курс']) - 360:.1f}° → {float(end['курс']) % 360 if float(end['курс']) % 360 < 180 else float(end['курс']) % 360 - 360:.1f}°" if st else f"не встал, дальше {reach:.2f}"))
        else:
            good = reach <= P['reach'] + TOL and (not P['held'] or abs(reach - P['reach']) <= TOL)
            print(f"{'PASS' if good else 'FAIL'} {tag} {q['id']} {P['v']} м/с x {P['x']:.1f}: PS2 дальше {P['reach']:.2f}"
                  f" ({'упёрлась' if P['held'] else 'прошла мимо края'}), порт {reach:.2f}")
        ok &= good
    return ok


old = [a for a in sys.argv[1:] if a.startswith('-D')]
tr = port('old' if old else 'new', old)
ok = judge('old' if old else 'new', tr) and len(runs) >= 5
print(f"{'PASS' if ok else 'FAIL'} изгородь K9-4: проб {len(runs)} (v200 + таранов {len(runs) - 1}), линия PS2 z {line:.2f}" + (f" [{' '.join(old)}]" if old else ''))
if not old:
    self_ok = not judge('без изгороди', port('nohedge', [], {'HEDGE_K94_NO_HEDGE': '1'}))
    print(('самопроверка: без изгороди гейт падает, как должен' if self_ok else 'САМОПРОВЕРКА НЕ УПАЛА: гейт ничего не доказывает'))
    ok &= self_ok
raise SystemExit(0 if ok else 1)
