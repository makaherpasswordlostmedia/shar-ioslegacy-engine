#!/usr/bin/env python3
"""Гейт регистратора полигона v2 без игры: синтетические журналы прогонов (форматы explorer --cells-out, inspector, chase, CAMINF смоука)
и мини-мир числами (видимые треугольники + коллизия) -> типы, склейка мест, коды L<N> X<r>-<s>, итог ≤ 5 КБ по важности, вердикты
сверки, кадры рядом 480×272 NEAREST. Запуск: python3 tests/polygon/test_registry.py (код 0 — PASS). Красный контроль — tests/polygon/run.sh
(POLY_REG_BREAK=merge: склейка выключена — тест обязан упасть)."""
import collections, math, os, struct, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/polygon')); sys.path.insert(0, str(ROOT / 'tools/bots'))
import numpy as np
import registry as R, geom as G, twinq as Q

FAIL = []
def check(ok, msg):
    print(('  ok   ' if ok else '  FAIL ') + msg)
    if not ok: FAIL.append(msg)


def w(p, txt): p.parent.mkdir(parents=True, exist_ok=True); p.write_text(txt)


def quad(x0, z0, x1, z1, y):   # горизонтальный прямоугольник двумя треугольниками
    return [[[x0, y, z0], [x1, y, z0], [x1, y, z1]], [[x0, y, z0], [x1, y, z1], [x0, y, z1]]]


def wall(x, z0, z1, y0, y1):   # вертикальная стена в плоскости x = const
    return [[[x, y0, z0], [x, y0, z1], [x, y1, z1]], [[x, y0, z0], [x, y1, z1], [x, y1, z0]]]


def test_codes():
    print('коды мест (viewer/placecode.h)')
    check(R.code(-700, -700) == 'A1-1', 'угол сетки -> A1-1')
    check(R.code(-700 + 8 * 100 + 50, -700 + 4 * 100 + 90) == 'J5-8', 'девятый столбец — J (без I), участок 8')
    check(R.code(5000, 0) == '--', 'вне сетки -> --')
    check(all('I' not in R.code(x, z) for x in range(-700, 500, 37) for z in range(-700, 800, 41)), 'буквы I нет нигде')


def test_merge_and_types(tmp):
    print('сбор, типы, склейка')
    run = tmp / 'run1'
    # рой: машина не выезжает дважды в 3 м, Гомер заперт там же; то же место на крыше выше на 6 м — отдельное место; провал
    w(run / 'swarm/runs/s1001/events.tsv',
      'car_trapped\t100.0\t5.0\t200.0\t1.0\t0\t-\t0\n'
      'car_trapped\t102.0\t5.2\t202.0\t2.0\t0\tb12\t0\n'
      'foot_trapped\t101.0\t5.0\t199.0\t3.0\t0\t-\t1\n'
      'car_trapped\t101.0\t11.5\t200.0\t4.0\t1\t-\t0\n'
      'fall\t-300.0\t-2.0\t50.0\t5.0\t0\t-\t0\n')
    # инспектор: перенос DEATH и невзятый гэг; формат с номером точки
    w(run / 'inspector/part0/events.tsv', '# вид\n'
      'death_move\t-150.0\t2.0\t-400.0\t0\t0\tZ3\t0\t17\n'
      'interact_fail\t40.0\t3.0\t-60.0\t0\t0\tgag:bbq\t1\t100004\n')
    # догонялки: вечный угол и одиночное застревание погони (не считается)
    w(run / 'chase/s1/stdout.tsv', 'G\t0\t30.0\t40.0\t0.5\n'
      'X\teternal_corner\t-50.0\t1.0\t300.0\t2\tr.round\t0\t-\n'
      'X\tpursuer_stuck\t-60.0\t1.0\t310.0\t1\tq.round\t0\t-\n')
    logs = tmp / 'logs'; w(logs / 'smoke.txt',
      'CAMINF t=1.00 fl=3 near=0.10 eye=1,2,3 dir=0,0,1 pivot=10.00,1.00,20.00 foot=1 st=0\n'
      'CAMINF t=1.02 fl=3 near=0.10 eye=1,2,3 dir=0,0,1 pivot=10.20,1.00,20.10 foot=1 st=0\n'
      'CAMIN t=9.0 frames=2 any=2\n')
    E = R.collect([run], [logs])
    c = collections.Counter(e['type'] for e in E)
    check(c['stuck_car'] == 3 and c['stuck_foot'] == 1, f'застревания распознаны: {dict(c)}')
    check(c['fall'] == 1 and c['death'] == 1 and c['interact_fail'] == 1, 'провал, DEATH, взаимодействие распознаны')
    check(c['chase_corner'] == 2 and c.get('stuck_car') == 3, 'вечный угол ×2, одиночное застревание погони не считается')
    check(c['cam_inside'] == 1, 'камера внутри: два кадра одного места — одно событие')
    P, new = R.merge(E); R.name_places(P, 1)
    ground = [p for p in P if abs(p['x'] - 101) < 3 and p['y'] < 8]
    check(len(ground) == 1 and ground[0]['n'] == 3, 'три события в 3 м на земле — одно место (×3)')
    g = ground[0] if ground else {'types': {}, 'main': '-', 'id': '-'}
    check(g['main'] == 'stuck_car' and g['types'].get('stuck_foot') == 1, 'у места два типа, главный — машина (×2 против ×1)')
    roof = [p for p in P if abs(p['x'] - 101) < 3 and p['y'] > 8]
    check(len(roof) == 1, 'крыша над тем же местом (+6 м) — отдельное место')
    if roof and ground: check(roof[0]['id'] != g['id'] and roof[0]['id'].split('/')[0] == g['id'], f'один код участка, верх — «/2»: {g["id"]} / {roof[0]["id"]}')
    check(g['id'] == f'L1 {R.code(g["x"], g["z"])}', f'код места: {g["id"]}')
    check(new == len(P), 'все места новые в первом круге')
    # второй круг: то же место снова + одно новое -> новых 1, раз ×4
    E2 = [R.ev('stuck_car', 103.0, 5.0, 201.0, 'swarm'), R.ev('through_wall', 400.0, 0.0, 400.0, 'inspector')]
    P2, new2 = R.merge(E2, roundtrip(P, tmp))   # через registry.tsv на диске, как между кругами
    check(new2 == 1, f'второй круг: новых мест 1 (было {new2})')
    g2 = [p for p in P2 if abs(p['x'] - 101) < 4 and p['y'] < 8]
    check(len(g2) == 1 and g2[0]['n'] == 4, 'старое место набрало ×4, не задвоилось')
    return P2


def roundtrip(P, tmp):
    f = tmp / 'reg.tsv'; R.save(P, f); return R.load(f)


def test_summary(tmp):
    print('итог ≤ 5 КБ, порядок по важности')
    E = []
    for i in range(400): E.append(R.ev('hole_visible', -600 + i * 20.0, 0, 100.0, 'data'))
    for i in range(30): E.append(R.ev('death', -600 + i * 20.0, 0, -300.0, 'inspector'))
    for i in range(5): E.append(R.ev('stuck_foot', -600 + i * 20.0, 0, 500.0, 'swarm'))
    P, new = R.merge(E); R.name_places(P, 3)
    P[0]['verdict'] = 'совпало'   # совпавшее с оригиналом — не расхождение
    md = tmp / 'ИТОГ_L3.md'; size, cut = R.summary(P, 3, new, md)
    t = md.read_text()
    check(size <= 5000 and len(t.encode()) <= 5000, f'размер {len(t.encode())} байт ≤ 5000')
    check(cut == 1 and '… ещё' in t, 'хвост обрезан со ссылкой на registry.tsv')
    i1, i2 = t.find('## 1.'), t.find('## 2.')
    check(0 < i1 < i2, 'застревания раньше видимого')
    check(P[0]['id'] + ' ·' not in t, 'место с вердиктом «совпало» в итог не попало')


def test_geom(tmp):
    print('мини-мир: дыры, невидимая стена, сквозь стену')
    Rt = quad(0, 0, 20, 20, 0.0) + wall(10, 30, 40, 0, 3)            # видимая земля 20×20 и стена x = 10 (z 30…40)
    Rt += wall(14, 30, 40, 0, 3)                                       # ещё стена x = 14 — альфа (куст/решётка)
    RF = [0, 0, 0, 0, 1, 1]
    Ct = quad(0, 0, 10, 20, 0.0) + quad(50, 0, 60, 10, 0.0)           # коллизия: только половина земли + площадка без вида
    geo = G.Geo(Rt, RF, Ct)
    H = geo.holes(); kinds = collections.Counter(h['kind'] for h in H)
    vis = [h for h in H if h['kind'] == 'hole_visible']
    check(kinds['hole_visible'] == 1 and vis and 10 <= vis[0]['x'] <= 20, f'видимая земля без коллизии x 10…20: {H}')
    ph = [h for h in H if h['kind'] == 'hole_phantom']
    check(len(ph) == 1 and 50 <= ph[0]['x'] <= 60, 'коллизия без видимой земли x 50…60')
    check(geo.invisible(55.0, 0.0, 5.0), 'удар у площадки без вида — невидимая стена')
    check(not geo.invisible(10.0, 0.2, 35.0), 'удар у видимой стены — не невидимая')
    segs = [(8.0, 0.0, 35.0, 11.5, 0.0, 35.0, 0),   # машина прошла сквозь стену x = 10 на 1.5 м
            (8.0, 0.0, 35.0, 10.3, 0.0, 35.0, 0),   # упёрлась, 0.3 м за плоскостью — не «сквозь»
            (12.0, 0.0, 35.0, 16.0, 0.0, 35.0, 1)]  # Гомер сквозь куст (альфа) — не стена
    X = geo.crossings(segs)
    check(len(X) == 1 and X[0][3] == 0 and abs(X[0][0] - 10) < .01, f'сквозь видимую стену — только первый отрезок: {X}')
    # trace.bin инспектора -> отрезки
    tb = tmp / 'insp/part0/trace.bin'; tb.parent.mkdir(parents=True, exist_ok=True)
    with tb.open('wb') as f:
        for pt, pr, p in ((0, 1, (8, 0, 35)), (0, 1, (11.5, 0, 35)), (0, 2, (0, 0, 0)), (1, 9, (12, 0, 35)), (1, 9, (16, 0, 35))):
            f.write(struct.pack('<ii3f', pt, pr, *p))
    S = G.read_trace(tb)
    check(len(S) == 2 and S[1][6] == 1, 'след: отрезки внутри одной пробы, проба ≥ 8 — пешком')
    E = R.from_trace(tb, geo, 'part0')
    check(len(E) == 1 and E[0]['type'] == 'through_wall', 'регистратор: сквозь видимую стену из trace.bin')
    w(tmp / 'insp/part0/hits.tsv', '# x\n55.0\t0.0\t5.0\t6.0\t0\t3\t0\t1\t0\t0\t1\n10.0\t0.2\t35.0\t6.0\t0\t1\t0\t1\t0\t0\t1\n')
    E = R.from_hits(tmp / 'insp/part0/hits.tsv', geo, 'part0')
    check(len(E) == 1 and E[0]['type'] == 'invisible_wall' and E[0]['obj'] == 't3', 'регистратор: невидимая стена из hits.tsv')


def test_twin(tmp):
    print('очередь сверки: вердикты, команды, кадры рядом')
    V = Q.verdict
    check(V('stuck_car', dict(ok=False), dict(ok=True)) == 'у порта застревание, у оригинала нет', 'порт застрял, оригинал проехал')
    check(V('stuck_car', dict(ok=False), dict(ok=False)) == 'совпало', 'оба застряли — совпало')
    check(V('through_wall', dict(ok=True), dict(ok=False)) == 'оригинал не пускает', 'порт сквозь стену, оригинал нет')
    check(V('interact_fail', dict(ok=False), dict(ok=True)) == 'взаимодействие отличается', 'гэг: у оригинала сработал')
    check(V('hole_visible', dict(ok=True, dy=-99), dict(ok=True, dy=0.1)) == 'разная опора', 'дыра: порт провалился, оригинал держит')
    check(V('stuck_car', None, dict(ok=True)) == 'не сверено', 'нет данных порта — не сверено')
    a, pc, oc = Q.commands(1, 'L1 D7-5', 'stuck_car', 10.0, 2.0, -20.0, 0.0)
    check(a == 'car' and '--one 10.00 2.00 -20.00' in pc and 'jump.py --start 10.00 2.00 20.00 --heading 180.0' in oc, f'команды машины (оси оригинала z = −z): {oc}')
    a, pc, oc = Q.commands(4, 'L4 B2-1', 'stuck_foot', 1.0, 0.0, 1.0, 0.0)
    check(a == 'foot' and oc == '-' and 'build/levels/l4/level.shr' in pc, 'L4: порт есть, близнеца нет (маршрут только L1)')
    # близнец: jump.tsv в осях игры
    d = tmp / 'o4/x'; w(d / 'jump.tsv', 'кадр\tx\ty\tz\tкурс\tv\tфаза\n' + ''.join(f'{i}\t{10 + i * .5:.2f}\t2.0\t20.0\t90\t4\tp\n' for i in range(-20, 20)))
    r = Q.orig_result(d, 'car', 10.0, 2.0, 20.0)
    check(r and r['ok'], 'оригинал: машина проехала точку дальше 3 м — пускает')
    # кадры: порт 512×272 (буфер) и запись PS2 1280×720 с картинкой 4:3 в середине
    from PIL import Image
    pa = Image.new('RGB', (512, 272), (255, 0, 0)); pa.save(tmp / 'p.png')
    oa = Image.new('RGB', (1280, 720), (0, 0, 0))
    for x in range(160, 1120): oa.putpixel((x, 360), (0, 255, 0) if (x // 3) % 2 else (0, 0, 255))
    oa.save(tmp / 'o.png')
    size = Q.pair(tmp / 'p.png', tmp / 'o.png', tmp / 'pair.png', 'L1 D7-5')
    im = Image.open(tmp / 'pair.png').convert('RGB')
    check(size == (480 + 8 + 363, 290), f'размер пары {size}: порт 480×272, оригинал 4:3 по высоте 272')
    cols = {im.getpixel((x, 18 + 136)) for x in range(488, 488 + 363)} | {im.getpixel((x, 18 + 135)) for x in range(488, 488 + 363)}
    check(cols <= {(0, 255, 0), (0, 0, 255), (0, 0, 0)}, 'оригинал без сглаживания (NEAREST: только исходные цвета)')
    check(im.getpixel((479, 100)) == (255, 0, 0) and im.getpixel((484, 100)) == (20, 20, 20), 'порт 1:1, 480 столбцов')


def main():
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        test_codes(); test_merge_and_types(tmp); test_summary(tmp); test_geom(tmp); test_twin(tmp)
    print('PASS' if not FAIL else f'FAIL ({len(FAIL)})')
    sys.exit(1 if FAIL else 0)


if __name__ == '__main__':
    main()
