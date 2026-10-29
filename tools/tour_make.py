#!/usr/bin/env python3
"""Замер-тур уровня 1 на PSP (просьба Роба 03.10 вечер: «версия, которая сама походит в комнатах и по местам, всё замерит и
запишет в отчёты, чтобы я тебе не переносил»). Собирает scenario.txt для папки PSP/GAME/SHARTOUR (tools/tour_psp.sh):
сценарий смоука (viewer/smoke.h) идёт на самой PSP, по каждой сцене — строка STAT (кадр p95/p99/max, пропуски, видимые
незагруженные клетки, куча, список GE), раз в секунду — строка ящика BB (процессор потоков, задержка клеток), снимки shot —
сама игра пишет shots/ИМЯ.bmp (на железе; SHOTFILE с числом пурпурных пикселей).

Части тура (по порядку; последняя — отдельно, может «повесить» PSP):
  A  швы: 12 видов tools/seams_scenario.txt, у каждого три снимка — обычный, «щели» (clearchk + nosky + seamchk: щель
     остаётся пурпурной) и «щели как до правки» (seamsold 1) — сверка правок 224/237/251 на железе
  B  тяжёлые виды: худшие виды стенда (bench.txt на PSP, строки «worst P1 views»)
  C  комнаты: все камеры комнат L1 (tests/rooms/emu_cams.txt: Kwik-E-Mart, школа, дом)
  D  проезды: прямые разгоны из точек вида A (autostraight) — подгрузка клеток на скорости
  E  место зависания 252 (tests/crash_f10/scenario.txt, автопилот по пути Роба) — последним, только с --freeze-route

  python3 tools/tour_make.py [--out build/tour/scenario.txt] [--freeze-route] [--quick]
--quick — по одному виду каждой части (проверка тура в эмуляторе)."""
import argparse, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import tour_playable as TP   # точки тура только на проезжих клетках (карта ботов build/playable-l1.tsv, tools/bots/anatomy.py)

ROOT = Path(__file__).resolve().parents[1]


def views_seams():
    """(имя, команда goto) из tools/seams_scenario.txt"""
    out, name = [], None
    for ln in (ROOT / 'tools/seams_scenario.txt').read_text().splitlines():
        p = ln.split()
        if not p or p[0].startswith('#'): continue
        if p[0] == 'scene': name = p[1]
        elif p[0] == 'goto' and name: out.append((name, ln.strip()))
    return out


def views_bench():
    """худшие виды стенда: строки «x z heading work» после «worst P1 views» в свежем bench.txt"""
    cands = sorted((ROOT / 'build/psp-logs').glob('*/bench.txt'), key=lambda p: p.stat().st_mtime)
    if not cands: return []
    txt = cands[-1].read_text(errors='replace').splitlines(); out = []; on = False
    for ln in txt:
        if ln.startswith('worst P1 views'): on = True; continue
        if on:
            m = re.match(r'\s+(-?\d+)\s+(-?\d+)\s+(\d)\s+[\d.]+', ln)
            if not m: break
            x, z, h = int(m.group(1)), int(m.group(2)), int(m.group(3))
            out.append((f'w{len(out) + 1:02d}', f'goto {x} {z} {h * 1.5708:.4f}'))
    return out


def rooms():
    """тело tests/rooms/emu_cams.txt без «end»"""
    lines = (ROOT / 'tests/rooms/emu_cams.txt').read_text().splitlines()
    return [l for l in lines if l.strip() and not l.startswith('#') and l.split()[0] != 'end']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=str(ROOT / 'build/tour/scenario.txt'))
    ap.add_argument('--freeze-route', action='store_true')
    ap.add_argument('--quick', action='store_true')
    ap.add_argument('--fresh-msn', action='store_true', help='в начале: старт миссии m0 сразу после загрузки (проба зависания 259 без объезда)')
    ap.add_argument('--me', action='store_true', help='TEST 8: добавить пробу Media Engine последней частью (может повесить PSP)')
    ap.add_argument('--test8', action='store_true', help='TEST 8 (04.10, правки 275/265/274/273/ME): вместо частей A–D — F замер листов 275 '
                    '(тяжёлые виды и проезды: листы и прежний путь), M перелёт меню (265), S проба сохранения (274), последним ME проба')
    ap.add_argument('--test9', action='store_true', help='TEST 9 (04.10, правки 303/293/296 и др.): X музыка выхода из машины и погони '
                    'пешком (строки MUS/SNDMODE/AUDV), M9 настоящий перелёт меню с журналом по кадрам (FEFR), плюс части помощников, если готовы')
    ap.add_argument('--test10', action='store_true', help='TEST 10 (04.10 вечер, Роб: «тест очень медленный, постепенно пробивай всё, и Media Engine»): '
                    'обычный обход A–D, потом L — нагрузка ступенями (трафик, прохожие, погоня, взрыв), часть меню помощника 293 (если в дереве), '
                    'последним — лесенка Media Engine tests/me/psp_test10_ladder.txt')
    ap.add_argument('--test17', action='store_true', help='TEST 17: звук на Media Engine (флаг-файл meaudio=u кладёт tour_psp.sh)')
    ap.add_argument('--all-levels', action='store_true', help='08.10: тур всех 7 уровней (tests/me/psp_tour_all_levels.txt) — CPU/ME апки')
    ap.add_argument('--test16', action='store_true', help='TEST 16: работа ME из памяти игры (сумма, время, верхняя память, после ролика)')
    ap.add_argument('--test15', action='store_true', help='TEST 15: функция ME в памяти игры (ступени 15–16)')
    ap.add_argument('--test14', action='store_true', help='TEST 14: ME по схеме автора MIST (ступени 13–14)')
    ap.add_argument('--test13', action='store_true', help='TEST 13: ME «всё одним вызовом» (ступени 10–12, без роликов)')
    ap.add_argument('--test12', action='store_true', help='TEST 12: лесенка ME до любого ролика (видео-модули прошивки — после установки ячейки)')
    ap.add_argument('--test11', action='store_true', help='TEST 11 (04.10 вечер): только лесенка Media Engine подряд, без роликов между ступенями (~3 мин)')
    ap.add_argument('--room-check', action='store_true', help='правка 259: вместо частей A–D — старт миссий из дома: R1 исправленный, '
                    'R2 как до правки (msnoldroom) под защитой камеры — PSP не должна встать')
    a = ap.parse_args()
    S = ['# Замер-тур L1 (tools/tour_make.py). Части: A швы, B тяжёлые виды, C комнаты, D проезды' + (', E место зависания 252' if a.freeze_route else ''),
         'scene start', 'flag trace 1', 'wait 3']   # след 259/252 по фазам — в туре включён
    if a.fresh_msn:   # правки 252/259 (03.10 22:2x): тур трижды вставал в первом кадре камеры миссии m0 после объезда — встаёт ли без него
        S += ['scene E0_fresh_msn', 'flag player', 'wait 2', 'flag msn', 'wait 8', 'shot E0_after_msn', 'wait 2']
    A = views_seams(); B = views_bench(); C = rooms()
    # Роб 04.10: «зачем тест ставит машину в места, где ездить нельзя, в текстуры, в дома?» — виды B взяты сеткой стенда по всему
    # уровню, без проверки, можно ли там ездить. Пока нет карты проезжих клеток по ботам (build/playable-l1.tsv) — B не брать
    if not (ROOT / 'build/playable-l1.tsv').exists() and B:
        print(f'  (виды B: {len(B)} точек стенда без проверки проезжести — пропущены до карты build/playable-l1.tsv)'); B = []
    elif B: B = TP.playable_views(B, ROOT / 'build/playable-l1.tsv')   # карта есть: только виды с проезжих клеток (tools/tour_playable.py)
    if a.quick: A, B = A[:1], B[:1]
    if a.room_check:   # правка 259 (03.10): тур 5 раз из 5 вставал на старте миссий из дома; замеры A–D уже сняты турами 1–4
        house = ['foot 228.94 180.5 0 3.83', 'wait 3', 'press up 0.3', 'press circle 0.3', 'wait 1', 'press triangle', 'wait 2',
                 'foot 500.316 398.080 0 -17.40', 'wait 3']
        # R2 первым: до любой камеры миссии кадр «в комнате» получает FOV 0 — ровно тот кадр, на котором вставали туры 1–5
        S += ['scene R2_house'] + house + ['shot R2_in_house', 'scene R2_msn_old', 'flag player', 'wait 2', 'flag msnoldroom 1', 'flag msn', 'wait 6',
              'shot R2_after_old', 'flag msnoldroom 0', 'flag msn', 'wait 4', 'shot R2_after_clean']
        S += ['scene R1_house'] + house + ['shot R1_in_house', 'scene R1_msn', 'wait 2', 'flag msn', 'wait 8', 'shot R1_after_msn']
        A, B, C = [], [], []
    if a.test8:   # TEST 8 (04.10): части помощников — файлами, если они уже в дереве; ME — последним (может повесить PSP)
        def body(rel):
            f = ROOT / rel
            if not f.exists(): print(f'  (нет {rel} — часть пропущена)'); return []
            return [l for l in f.read_text().splitlines() if l.strip() and not l.startswith('#') and l.split()[0] != 'end']
        for name, go in B[:8]:   # F — правка 275 на железе: тот же вид с листами и прежним путём, строки STAT по сценам
            S += [f'scene F_{name}_dl', go, 'flag dloff 0', 'wait 4', f'shot F_{name}_dl', f'scene F_{name}_old', 'flag dloff 1', 'wait 4', 'flag dloff 0']
        for name, go in A[:3]:
            S += [f'scene F_drive_{name}_dl', go, 'flag dloff 0', 'wait 2', 'flag autostraight 8', 'wait 10', 'flag stop',
                  f'scene F_drive_{name}_old', go, 'flag dloff 1', 'wait 2', 'flag autostraight 8', 'wait 10', 'flag stop', 'flag dloff 0']
        # U — правка 279 на железе: погоня Hit & Run 10 с; строки AUDV раз в секунду (шина музыки, пауза, поток, наполнение кольца)
        S += ['scene U_music_hnr', 'goto 220 172 1.5708', 'wait 2', 'flag hnr 100', 'wait 10', 'shot U_music_hnr', 'flag hnr 0', 'wait 4']
        S += body('tests/fe_guard/psp_test8_menu.txt') + body('tests/save/psp_test8_save.txt')
        # проба ME — только ключом --me: на PSP Роба 04.10 13:1x ME задание не исполнил (ME timeout), после пробы ролик (sceJpeg на ME)
        # повесил приставку — build/psp-tour/20261004-1316/me.txt
        if a.me: S += body('tests/me/psp_test8_me.txt')
        A, B, C = [], [], []
    if a.all_levels:
        import os   # ME-доля (10.10): TOUR_SCENARIO — свой файл дороги вместо полного тура
        S = Path(os.environ.get('TOUR_SCENARIO') or (ROOT / 'tests/me/psp_tour_all_levels.txt')).read_text().rstrip('\n').split('\n')
        out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True); out.write_text('\n'.join(S) + '\n')
        print('тур всех уровней: %d строк -> %s' % (len(S), out)); return
    if a.test11 or a.test12 or a.test13 or a.test14 or a.test15 or a.test16 or a.test17:   # TEST 11–14: только ME (12 — до ролика, 13 — одним вызовом, 14 — схема автора)
        f = ROOT / ('tests/me/psp_test17_audio.txt' if a.test17 else 'tests/me/psp_test16_work.txt' if a.test16 else 'tests/me/psp_test15_gamefn.txt' if a.test15 else 'tests/me/psp_test14_combo.txt' if a.test14 else 'tests/me/psp_test13_combo.txt' if a.test13 else 'tests/me/psp_test12_ladder.txt' if a.test12 else 'tests/me/psp_test11_ladder.txt')
        S += [l for l in f.read_text().splitlines() if l.strip() and not l.startswith('#') and l.split()[0] != 'end']
        A, B, C = [], [], []
    if a.test9:   # TEST 9 (04.10 вечер): явные отчёты по открытым правкам Роба — только то, что эмулятор не показывает
        def body9(rel):
            f = ROOT / rel
            if not f.exists(): print(f'  (нет {rel} — часть пропущена)'); return []
            return [l for l in f.read_text().splitlines() if l.strip() and not l.startswith('#') and l.split()[0] != 'end']
        S += ['flag sfxlog']   # журнал звуков и музыки (MUS, SNDMODE) — в smoke.txt тура
        # X — правка 303 («после выхода из машины мелодия 2 с и заново, снова и снова»): езда, остановка, выход, 12 с пешком; потом
        # погоня Hit & Run, выход пешком под погоней, ещё 12 с — строки MUS/SNDMODE/AUDV покажут, что и как часто просится
        S += ['scene X_exit_car', 'goto 220 172 1.5708', 'wait 2', 'flag autostraight 3', 'wait 4', 'flag stop', 'wait 2', 'press triangle', 'wait 12',
              'shot X_exit_car', 'scene X_exit_hnr', 'goto 220 172 1.5708', 'wait 2', 'flag hnr 100', 'wait 6', 'flag stop', 'press triangle', 'wait 12',
              'shot X_exit_hnr', 'flag hnr 0', 'wait 3']
        # M9 — правка 293 («в самом начале наезда к газете мигает пол»): НАСТОЯЩИЙ перелёт NEW GAME (не покадровый), строка FEFR на
        # каждый кадр: позиция камеры, мс кадра, процессор, куски и треугольники, куски пола, «главный вид» (home)
        S += ['scene M9_menu_fly', 'flag feframelog 1', 'wait 1', 'press start', 'wait 1', 'press up', 'wait 0.5', 'press cross', 'wait 4',
              'flag idle 1000', 'press cross', 'wait 3', 'press cross', 'wait 14', 'scene M9_after', 'flag feframelog 0', 'wait 3']
        S += body9('tests/race/psp_test9_race.txt') + body9('tests/foliage/psp_test9_bushes.txt') + body9('tests/rooms/psp_test9_house.txt')
        A, B, C = [], [], []
    # A — швы: обычный кадр, щели нового движка, щели как до правки
    for name, go in A:
        S += [f'scene A_{name}', go, 'wait 3', f'shot A_{name}',
              'flag clearchk 1', 'flag nosky 1', 'flag seamchk 1', 'wait 0.5', f'shot A_{name}_gap',
              'flag seamsold 1', 'wait 0.5', f'shot A_{name}_gapold',
              'flag seamsold 0', 'flag seamchk 0', 'flag nosky 0', 'flag clearchk 0', 'wait 0.3']
    # B — тяжёлые виды стенда
    for name, go in B:
        S += [f'scene B_{name}', go, 'wait 3', f'shot B_{name}']
    # C — комнаты (вход через дверь и все камеры)
    if a.quick:
        C = [l for l in C][:C.index('scene kc02') if 'scene kc02' in C else len(C)]
    if C: S += ['scene C_rooms_go'] + [('scene C_' + l.split()[1]) if l.split()[0] == 'scene' else (f'shot C_{l.split()[1]}' if l.split()[0] == 'shot' else l) for l in C]
    # TEST 10 на железе (04.10, Роб: «дошло до дома и просто стоит, ничего дальше не происходит, могу походить»): обход комнат кончался
    # в доме Симпсонов, а goto следующих частей двигает только машину — Гомер оставался в комнате. Выйти из дома и сесть за руль
    if C: S += ['scene C_exit', 'foot 228.94 180.5 0 3.83', 'wait 2', 'goto 220 172 1.5708', 'flag repair', 'wait 3']
    # D — проезды: разгон прямо 8 с из точек вида A (камера, клетки, задержка подгрузки на скорости)
    for name, go in (A[:4] if not a.quick else A[:1]) if not (a.room_check or a.test8) else []:
        S += [f'scene D_{name}', go, 'wait 2', 'flag autostraight 8', 'wait 10', f'shot D_{name}_end', 'flag stop']
    if a.test10:
        def body10(rel):
            f = ROOT / rel
            if not f.exists(): print(f'  (нет {rel} — часть пропущена)'); return []
            return [l for l in f.read_text().splitlines() if l.strip() and not l.startswith('#') and l.split()[0] != 'end']
        S += ['flag sfxlog']
        # L — нагрузка ступенями на одной улице (у дома Симпсонов): каждая ступень ~25 с, строки BB раз в секунду и STAT по сцене —
        # где у PSP запас и где кадр упирается (решение, что отдавать Media Engine)
        go = 'goto 220 172 1.5708'
        S += ['scene L0_idle', go, 'wait 30',
              'scene L1_drive', go, 'wait 2', 'flag autostraight 12', 'wait 18', 'flag stop', 'wait 3',
              'scene L2_traffic', go, 'wait 2', 'flag trfahead 20', 'wait 1', 'flag trfahead 35', 'wait 1', 'flag trfahead 50', 'wait 28',
              'scene L3_peds', go, 'wait 2', 'flag pedahead 12', 'wait 1', 'flag pedahead 20', 'wait 1', 'flag pedahead 28', 'wait 28',
              'scene L4_traffic_peds_drive', 'flag trfahead 30', 'flag pedahead 15', 'wait 1', 'flag autostraight 12', 'wait 18', 'flag stop', 'wait 10',
              'scene L5_hnr_chase', go, 'wait 2', 'flag hnr 100', 'wait 3', 'flag autostraight 12', 'wait 25', 'flag stop', 'wait 10', 'flag hnr 0', 'wait 8',
              'scene L6_boom', go, 'wait 2', 'flag testboom', 'wait 15', 'flag repair', 'wait 2',   # после взрыва — снова целая машина и за рулём
              'scene L7_long_world', go, 'wait 180']   # 3 мин живого мира без сброса: куча и подгрузка по строкам BB
        S += body10('tests/fe_guard/psp_test10_menu.txt')
        S += body10('tests/me/psp_test10_ladder.txt')
    if a.freeze_route:
        body = [l for l in (ROOT / 'tests/crash_f10/scenario.txt').read_text().splitlines() if l.strip() and not l.startswith('#') and l.split()[0] != 'end']
        S += ['scene E_freeze252'] + body
    # Роб 04.10: каждая точка goto (части A, B, D, L, F, U, X …) — на проезжей клетке по ботам (build/playable-l1.tsv): не там — сдвиг
    # на ближайшую проезжую с курсом вдоль движения ботов («сдвинута на N м») или сцена выбрасывается («выброшена»)
    S, _ = TP.fix_tour(S, ROOT / 'build/playable-l1.tsv')
    # Роб 04.10 (TEST 10 на железе): «он теперь просто в машине горящей после всяких тестов с машиной в разных местах, долго» — машина
    # билась при постановках (виды B в домах), а goto двигает её как есть. После каждой постановки — целая машина и Гомер за рулём
    S2 = []
    for i, l in enumerate(S):
        S2.append(l)
        if l.startswith('goto ') and not (i + 1 < len(S) and S[i + 1] == 'flag repair'): S2.append('flag repair')
    S = S2
    S += ['end']
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True); out.write_text('\n'.join(S) + '\n')
    n_shot = sum(1 for l in S if l.startswith('shot'))
    print(f'{out}: строк {len(S)}, сцен {sum(1 for l in S if l.startswith("scene"))}, снимков {n_shot} (~{n_shot * 0.39:.0f} МБ), '
          f'частей: A {len(A)} видов, B {len(B)}, C {sum(1 for l in C if l.startswith("scene"))} сцен комнат, D {min(4, len(A))} проездов'
          + (', E место 252' if a.freeze_route else ''))


if __name__ == '__main__':
    main()
