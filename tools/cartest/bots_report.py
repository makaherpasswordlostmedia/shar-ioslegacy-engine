#!/usr/bin/env python3
"""Отчёт прогона физических ботов (tools/cartest/bots_loop.sh): сводка уровень × тип, топ мест, как повторить.
   python3 tools/cartest/bots_report.py <папка прогона>      -> <папка>/ОТЧЁТ_БОТЫ.md, <папка>/clusters/clusters.tsv
Находки склеивает tools/autoexplore/sborka/cluster.py (тот же формат TSV, что у остальных полос автоисследователя)."""
import collections, glob, json, re, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
KINDS = [  # тип, что это простыми словами, важность
    ('through', 'сквозной проезд: центр кузова прошёл через стену, ящик или забор с лицевой стороны, и машина осталась по ту сторону', 'ошибка'),
    ('stuck', 'ловушка: 12 с под газом не отошла дальше 2 м, и ни один из 7 манёвров игрока (газ/назад, прямо/влево/вправо, газ-назад по кругу — №738) не вывел на 8 м, и игра сама не вернула', 'ошибка'),
    ('embed', 'застряла внутри: глубина проникновения больше 15 см 12 кадров подряд', 'ошибка'),
    ('launch', 'подброс: вылет вверх без зоны прыжка (ударом о стену или поверхность)', 'проверить'),
    ('carunder', 'кузов в кузове другой машины 12 кадров подряд (заезд под машину, наезд)', 'ошибка'),
    ('carover', 'машина полторы секунды и дольше едет на крыше другой машины', 'проверить'),
    ('roof', 'села на крышу или плато выше окружения вне дороги и пробыла там 1,5 с', 'сведение'),
    ('ramp', 'прыжок без зоны прыжка: не меньше 1,5 с в воздухе (трамплин или край)', 'сведение'),
    ('recovery', 'игра сама вернула машину на надёжное место', 'сведение'),
    ('backfence', 'проезд забора с изнанки на лицо: так задумано (сверка PS2 09.10), справочно', 'справочно'),
    ('phantom', 'проезд сквозь прозрачную стену: ящик без рисунка, машину не держит по решению Роба (правка 475, 10.10), справочно', 'справочно'),
    ('death', 'зона DEATH вернула машину в точку возврата, как game.c gameDeath (вода, пропасти), справочно', 'справочно'),
    ('backreturn', 'отскок обратно через звено забора, в которое машина вошла с изнанки (colBackKeep, по замыслу PS2): та же поездка, не проезд с лица, справочно', 'справочно'),
    ('escape', 'собственный выход игры (№738 зажата, перч, тупик 32): сдвиг в точку рядом, идёт сквозь забор по замыслу, справочно', 'справочно'),
    ('stuckbot', 'застрял бот, а игрок выбрался бы: из позы «застряла» один из 7 манёвров (газ/назад, прямо/влево/вправо; газ-назад по кругу — седьмой, он включает №738) вывел машину на 8 м', 'справочно'),
]
KIND_RU = {k: d for k, d, _ in KINDS}


def parse_summary(out):
    """Из строк '# итог L1 seed=… cars=… кадров=N type=записано/всего …' в TSV."""
    runs = collections.defaultdict(lambda: dict(runs=0, ticks=0, cars=0, kinds=collections.defaultdict(lambda: [0, 0])))
    for f in sorted(glob.glob(str(out / 'findings/*.tsv'))):
        for ln in Path(f).read_text(errors='replace').splitlines():
            if not ln.startswith('# итог'): continue
            m = re.match(r'# итог L(\d+) seed=(\d+) cars=(\d+) кадров=(\d+) (.*)', ln)
            if not m: continue
            lv = int(m.group(1)); r = runs[lv]
            r['runs'] += 1; r['ticks'] += int(m.group(4)); r['car_ticks'] = r.get('car_ticks', 0) + int(m.group(4)) * int(m.group(3))
            for k, w, t in re.findall(r'(\w+)=(\d+)/(\d+)', m.group(5)): r['kinds'][k][0] += int(w); r['kinds'][k][1] += int(t)
    return runs


def main():
    out = Path(sys.argv[1]).resolve()
    man = json.loads((out / 'manifest.json').read_text()) if (out / 'manifest.json').exists() else {}
    runs = parse_summary(out)
    # склейка находок: все строки без комментариев в один файл в папке «bots» (cluster.py берёт полосу по имени папки)
    (out / 'bots').mkdir(exist_ok=True)
    rows = []
    for f in sorted(glob.glob(str(out / 'findings/*.tsv'))):
        rows += [ln for ln in Path(f).read_text(errors='replace').splitlines() if ln and not ln.startswith('#')]
    (out / 'bots/all.tsv').write_text('\n'.join(rows) + ('\n' if rows else ''))
    cl = []
    if rows:
        subprocess.run([sys.executable, '-I', str(ROOT / 'tools/autoexplore/sborka/cluster.py'), '--root', str(out / 'bots'), '--tsv', str(out / 'bots/all.tsv'),
                        '--out', str(out / 'clusters'), '--top', '8', '--date', time.strftime('%Y-%m-%d')], check=False, capture_output=True)
        cf = out / 'clusters/clusters.tsv'
        if cf.exists():
            for ln in cf.read_text().splitlines():
                f = ln.split('\t')
                if len(f) >= 14 and f[0].isdigit(): cl.append(dict(level=int(f[0]), x=f[1], y=f[2], z=f[3], kind=f[4], n=int(f[5]), weight=float(f[6]), seeds=f[7], seed=f[9], frame=f[10], desc=f[13]))
    L = [f'# Физические боты · отчёт {time.strftime("%d.%m.%Y %H:%M")}', '',
         f'Прогон: {man.get("started", "—")} … срок {man.get("deadline", "—")}. Дерево: ветка {man.get("branch", "—")}, HEAD {man.get("head", "—")}'
         + (' (в viewer/ или tools/cartest есть непринятые правки)' if man.get('dirty') else '') + f'. Машин в рое {man.get("cars", "—")}, {man.get("seconds", "—")} игровых секунд на уровень за круг, одновременно {man.get("jobs", "—")}.', '',
         'Что это: рой машин на процессоре Мака, без эмулятора и звука. Физика — настоящие `viewer/car.c`, `col.c`, `props.c`, `stateprops.c` текущего дерева (накат, бордюры, отбойники 17.10, кусты №587; зоны DEATH применяются как в game.c), уровень — тот набор, что лежит на PSP. '
         'Боты синтетические: дорожные, дикие и тараны, часть стартует с крыш и склонов; это даёт охват, а не картину обычной игры.', '',
         '## Уровни и охват', '', '| уровень | файл уровня (дата, контроль) | запусков | игровых минут × машин | машино-часов |', '|---|---|---|---|---|']
    for n, v in sorted(man.get('levels', {}).items(), key=lambda t: int(t[0])):
        r = runs.get(int(n))
        L.append(f'| L{n} | {v["mtime"]}, `{v["sha"]}` | {r["runs"] if r else 0} | {(r["ticks"] / 3600 if r else 0):.0f} мин × {man.get("cars", "—")} | {(r["car_ticks"] / 216000 if r else 0):.1f} |')
    L += ['', '## Находки: записано мест (всего срабатываний за прогон)', '',
          '«Записано» — строк в TSV после лимита на место (8 м) и тип; «всего» считает все срабатывания, поэтому «всего» растёт с числом кругов, а «записано» упирается в лимит.', '',
          '| тип | ' + ' | '.join(f'L{n}' for n in sorted(map(int, man.get('levels', {})))) + ' | что это |', '|---|' + '---|' * (len(man.get('levels', {})) + 1)]
    for k, d, _ in KINDS:
        cells = []
        for n in sorted(map(int, man.get('levels', {}))):
            r = runs.get(n); w, t = (r['kinds'][k] if r and k in r['kinds'] else (0, 0))
            cells.append(f'{w} ({t})' if t else '0')
        L.append(f'| {k} | ' + ' | '.join(cells) + f' | {d} |')
    cb = collections.defaultdict(list)
    for c in cl: cb[c['kind']].append(c)
    L += ['', '## Главные места по типам (склейка в радиусе 8 м; вес — тяжесть события: скорость, глубина, длительность)', '']
    for k, d, imp in KINDS:
        if k == 'backfence': continue
        cs = sorted(cb.get(k, []), key=lambda c: (-c['weight'], -c['n']))[:6 if imp == 'ошибка' else 4]
        L += [f'### {k} · {imp}', '', d, '']
        if not cs: L += ['Находок нет.', '']; continue
        for c in cs:
            L.append(f'- L{c["level"]} · x {float(c["x"]):.0f}, y {float(c["y"]):.0f}, z {float(c["z"]):.0f} · повторов {c["n"]} (seed {c["seeds"]}) · вес {c["weight"]:.1f} · {c["desc"]}')
        L.append('')
    L += ['## Как повторить место', '',
          'В описании каждой находки есть `rep=--seed S --cars N --seconds T`. Те же `--level`, `--roads`, `--seed`, `--cars` дают ту же последовательность (рой детерминирован), `--seconds` — до кадра находки:',
          '', '`build/…/bin/bots_swarm --level <уровень>.shr --lvl N --roads roads-lN.bin --out повтор.tsv --seed S --cars N --seconds T`', '',
          '## Ограничения', '',
          '- `through` ловит проход центра кузова через поверхность за один кадр на высоте середины стенового слоя кузова и подтверждается тем, что 20 кадров спустя машина осталась по ту сторону. Тонкую стену, которую пересёк только угол кузова, он не увидит.',
          '- `carunder` и `carover` считают прямоугольники кузовов в плане и общую высоту без учёта наклона; на крутом склоне заезд под машину может пройти мимо.',
          '- Стартовые броски и посадка после спавна (первые 1,5 с эпизода), а также сценарные подбросы 3/4 и разгон со склона 26 м/с в расчёт не берутся.',
          '- Красные контроли детекторов `through`, `stuck`, `launch`, `carunder` — через `--inject` (`bots_swarm --inject through|stuck|launch|carunder`); для `roof`, `carover`, `ramp` синтетического контроля нет. Зоны DEATH: `--nodeath` возвращает прежнее поведение роя (контроль tools/cartest/bots_gate.sh).',
          '- Рой не знает про разговоры, миссии и прочее поведение game.c, кроме зон DEATH; props и состояния предметов берутся как в sandbox.c.']
    (out / 'ОТЧЁТ_БОТЫ.md').write_text('\n'.join(L) + '\n')
    print(out / 'ОТЧЁТ_БОТЫ.md')


if __name__ == '__main__': main()
