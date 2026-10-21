#!/usr/bin/env python3
"""Гейт пункта 12а: разбор smoke.txt прогона tools/menu_scenario.txt (tools/menu_gate.sh запускает и то и другое).
python tools/menu_check.py OUTDIR [--circles 5] [--tol-kb 64] [--copy DIR]
Строки движка (viewer/smoke.h, main.c menuRun): MENU (вход в меню, куча), MENUSEL (курсор после ↑/↓/X),
MENUGO (выбранный пункт), GAME (уровень загружен). Проверки:
  сценарий дошёл до END · входов в меню не меньше circles+1, запусков игры не меньше circles
  · куча при входе в меню номер circles+1 равна первой ±tol КБ (used = mallinfo, как smokeHeapFree)
  · курсор после каждого ↑/↓/X — только на включённом пункте (MENU on=), хотя бы одно ↓ было · запускается только NEW GAME
  · после каждого входа машина в одной точке (спавн) · загрузка прочитала клетки · снимки сценария и loading есть
  · гостиная (строки FE/FEMEM, viewer/frontend3d.c): загружена на каждом выходе из меню, куча после её освобождения = до
    загрузки ±tol
  · порядок пунктов сверху вниз, как нарисован движком (MENU order=), = порядок по данным оригинала: в MainMenu.pag
    (frontend.p3d) все пункты — строки одной карусели в одной точке экрана, ► ведёт к следующей строке по кругу;
    список = карусель от NEW GAME (пункт, с которого меню открывается). Данные читаются с диска Роба на Маке
  · звуки меню (29.09): в главном меню шаг карусели — scroll, × на NEW GAME — accept (строки UISFX, голос выдан h>0), режим
    тюнера меню со слышимой шиной эффектов (global.spt Set<Режим>SfxVolume > 0) [menu_sfx]; на каждом запуске игры —
    стингеры композиции Loading_screen (перелёт к газете) и Newspaper_Spin (газета) с дорожкой из music.sap [stinger]
--copy DIR: снимки фаз (кадр 480x272 без рамки окна) -> DIR/12a_<имя>.png
--expect-fail K1,K2: код 0, только если пойманы именно эти провалы (отрицательный контроль)
Код 0 = OK, 1 = провал (первая строка вывода — причина)."""
import sys
import argparse
from pathlib import Path


def kv(parts):
    return dict(p.split('=', 1) for p in parts if '=' in p)


def data_order():
    """-> (номера пунктов сверху вниз, ключи строк) по MainMenu.pag оригинала, или (None, причина)"""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import ui_export as U
        prj = U.project('frontend.p3d')
        mm = next(e for _, e in U.iter_leaves(prj.pages['MainMenu.pag']) if e['kind'] == 'text' and e['name'] == 'MainMenu')
        keys = [s['key'] for s in mm['strings']]
        return list(range(len(keys))), keys   # карусель: ► ведёт к следующей строке по кругу (номер пункта = номер строки)
    except Exception as ex:   # нет диска / формат — сверка невозможна, это провал
        return None, f'{type(ex).__name__}: {ex}'


MODES = ['Normal', 'Pause', 'MissionScreen', 'Letterbox', 'Dialogue', 'Store', 'OnFoot', 'Minigame', 'JustMusic', 'Credits']   # viewer/sound.h SND_MODE_*


def mode_sfx():
    """громкость шины эффектов по режиму тюнера (global.spt диска): Normal — SetSfxVolume, прочие — Set<Режим>SfxVolume"""
    import re
    t = (Path(__file__).resolve().parents[1] / 'hit-and-run-web/source/game/sound/scripts/global.spt').read_bytes().decode('latin-1')
    out = {}
    for i, m in enumerate(MODES):
        r = re.search(r'Set%sSfxVolume \( ([0-9.]+) \)' % ('' if m == 'Normal' else m), t)
        if r: out[i] = float(r.group(1))
    return out


def parse(log):
    ev = []
    for l in log:
        p = l.split()
        if p and p[0] in ('MENU', 'MENUSEL', 'MENUGO', 'GAME', 'FE', 'FEMEM', 'UISFX', 'FESTING'):
            ev.append((p[0], kv(p[1:])))
    return ev


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out'); ap.add_argument('--circles', type=int, default=5); ap.add_argument('--tol-kb', type=float, default=64)
    ap.add_argument('--copy'); ap.add_argument('--expect-fail', default='')
    a = ap.parse_args(); keyed = set()
    out = Path(a.out)
    log = (out / 'smoke.txt').read_text().splitlines() if (out / 'smoke.txt').exists() else []
    ev = parse(log)
    menus = [d for t, d in ev if t == 'MENU']; games = [d for t, d in ev if t == 'GAME']
    sels = [d for t, d in ev if t == 'MENUSEL']; gos = [d for t, d in ev if t == 'MENUGO']
    fes = [d for t, d in ev if t == 'FE']; fem = [d for t, d in ev if t == 'FEMEM']
    fails = []
    if not any(l.startswith('END') for l in log): fails.append('нет END: упал / завис')
    if len(menus) < a.circles + 1: fails.append(f'входов в меню {len(menus)} < {a.circles + 1}')
    if len(games) < a.circles: fails.append(f'запусков игры {len(games)} < {a.circles}')
    new = int(menus[0]['new']) if menus else -1
    if new < 0: fails.append('в меню нет пункта NEW GAME')
    on = {int(x) for x in menus[0].get('on', str(new)).split(',') if x} if menus else {new}   # включённые пункты (строка MENU on=)
    if new not in on: fails.append(f'NEW GAME ({new}) не среди включённых пунктов {sorted(on)}')
    # карусель (Роб 28.09): ► / ↓ — следующая строка MainMenu.pag по кругу, ◄ / ↑ — предыдущая; курсор обходит все пункты
    # (в гостиной светится предмет каждого), запускается только включённый — проверка ниже (запущен только NEW GAME)
    want, keys = data_order(); n = len(keys) if want is not None else 0
    if want is None: fails.append('порядок оригинала не прочитан: ' + keys)
    prev = new; badstep = []
    for d in sels:
        k, v = d['key'], int(d['sel'])
        exp = (prev + 1) % n if k in ('down', 'right') else (prev - 1) % n if k in ('up', 'left') else prev
        if n and v != exp: badstep.append(f"{k}: {prev}→{v}, ждали {exp} (t {d['t']})")
        prev = new if d.get('act', '-1') != '-1' and k == 'cross' else v
    if badstep: fails.append('шаг карусели не по данным: ' + '; '.join(badstep[:4]))
    if not any(d['key'] in ('down', 'right') for d in sels): fails.append('в меню не было ни одного ► / ↓ (проверка карусели не выполнена)')
    badgo = [d for d in gos if int(d['item']) != new]
    if badgo: fails.append('запущен не NEW GAME: ' + ', '.join(d['item'] for d in badgo))
    if games:
        x0, z0 = map(float, games[0]['car'].split(','))
        off = [(i + 1, d['car']) for i, d in enumerate(games)
               if abs(float(d['car'].split(',')[0]) - x0) > 3 or abs(float(d['car'].split(',')[1]) - z0) > 3]
        if off: fails.append('машина после входа не на спавне: ' + ', '.join(f'вход {i}: {c}' for i, c in off))
        empty = [i + 1 for i, d in enumerate(games) if int(d['cells']) <= 0]
        if empty: fails.append('загрузка не прочитала ни одной клетки: вход ' + ', '.join(map(str, empty)))
    dkb = None
    if len(menus) >= a.circles + 1:
        u0, u1 = int(menus[1]['used']), int(menus[a.circles]['used'])   # правка Роба 3: первое меню — до чтения уровня, сверка со 2-м
        dkb = (u1 - u0) / 1024.0
        if abs(dkb) > a.tol_kb:
            fails.append(f'куча в меню после {a.circles - 1} кругов {dkb:+.0f} КБ ко второму входу (допуск ±{a.tol_kb:.0f})')
    # гостиная (viewer/frontend3d.c, fe.shr): на каждом выходе из меню была загружена и освобождена до байта ±tol
    if len(fes) < len(gos) or any(d.get('ok') != '1' for d in fes): fails.append(f"гостиная меню: загружена {sum(d.get('ok') == '1' for d in fes)} из {len(gos)} выходов")
    femk = [(int(d['after']) - int(d['before'])) / 1024 for d in fem]
    if len(fem) < len(gos) or any(abs(x) > a.tol_kb for x in femk): fails.append('память гостиной после выхода из меню: ' + ', '.join(f'{x:+.0f}' for x in femk) + ' КБ')
    # звуки меню и стингеры (29.09): события по порядку журнала от первого входа в меню до первого запуска
    i0 = next((i for i, (t, _) in enumerate(ev) if t == 'MENU'), None); i1 = next((i for i, (t, _) in enumerate(ev) if t == 'MENUGO'), None)
    if i0 is not None and i1 is not None:
        seg = ev[i0:i1 + 1]; sx = [d for t, d in seg if t == 'UISFX']
        sfx_on = mode_sfx()
        scr = [d for d in sx if d['name'] == 'scroll' and int(d['h']) > 0]; acc = [d for d in sx if d['name'] == 'accept' and int(d['h']) > 0]
        modes = {int(d.get('mode', -1)) for d in sx}
        steps = sum(1 for t, d in seg if t == 'MENUSEL' and d['key'] != 'cross')
        bad_s = []
        if len(scr) < steps: bad_s.append(f'шагов карусели {steps}, звуков scroll {len(scr)}')
        if not acc: bad_s.append('× на NEW GAME без accept')
        mute = [m for m in modes if sfx_on.get(m, 0.0) <= 0.0]
        if mute: bad_s.append('режим тюнера меню глушит эффекты: ' + ', '.join(f'{m} ({MODES[m] if 0 <= m < len(MODES) else "?"})' for m in mute))
        if bad_s: fails.append('[menu_sfx] ' + '; '.join(bad_s)); keyed.add('menu_sfx')
        sfx_note = f'звуки меню: scroll {len(scr)}/{steps}, accept {len(acc)}, режим тюнера ' + ','.join(MODES[m] if 0 <= m < len(MODES) else str(m) for m in sorted(modes))
    else:
        fails.append('[menu_sfx] нет меню или запуска в журнале'); keyed.add('menu_sfx'); sfx_note = ''
    st = [d for t, d in ev if t == 'FESTING']
    # правка 134: за темой меню — один стингер Newspaper_Spin (газета); Loading_screen на × только в прежнем режиме (mode=2)
    got = [d for d in st if d['ev'] == 'newspaper_spin']
    if len(got) < len(gos) or any(d['track'] == '-' for d in got):
        fails.append(f'[stinger] newspaper_spin: {len(got)} из {len(gos)} запусков, дорожки ' + ','.join(d['track'] for d in got)); keyed.add('stinger')
    old_ls = [d for d in st if d['ev'] == 'loading_screen' and d.get('mode', '2') != '2']
    if old_ls: fails.append(f'[stinger] loading_screen на × обрывает тему меню ({len(old_ls)}) — правка 134'); keyed.add('stinger')
    sfx_note += '; стингеры ' + ', '.join(sorted({d['track'] for d in st}))
    scn = (out / 'scenario.txt').read_text().splitlines() if (out / 'scenario.txt').exists() else []
    shots = [l.split()[1] for l in scn if l.startswith('shot ')] + (['loading'] if any(l.strip() == 'flag loadshot' for l in scn) else [])
    miss = [s for s in shots if not (out / f'{s}.png').exists()]
    if miss: fails.append('нет снимков: ' + ', '.join(miss))
    verdict = ('OK: ' + f'{len(games)} входов в игру, {len(menus) - 1} выходов в меню; куча меню 1→{a.circles + 1}: '
               + (f'{dkb:+.1f} КБ (±{a.tol_kb:.0f}, 2→{a.circles + 1})' if dkb is not None else '—')
               + f'; карусель ×{sum(d["key"] != "cross" for d in sels)} шагов по строкам данных (' + ' / '.join(keys) + f'), запуск только NEW GAME ({new})'
               + f'; гостиная ×{len(fes)}, память после меню ' + '/'.join(f'{x:+.0f}' for x in femk) + ' КБ') if not fails else 'ПРОВАЛ: ' + '; '.join(fails)
    lines = [verdict, '', 'меню  used КБ    free МБ   блок КБ | вход  клеток  мс     машина']
    for i in range(max(len(menus), len(games))):
        m = menus[i] if i < len(menus) else None; g = games[i] if i < len(games) else None
        ml = f"{m['n']:>4}  {int(m['used']) / 1024:8.0f}  {float(m['free']):8.3f}  {int(m['maxblk']) / 1024:8.0f}" if m else ' ' * 36
        gl = f"{g['n']:>4}  {g['cells']:>6}  {g['ms']:>5}  {g['car']}" if g else ''
        lines.append(f'{ml} | {gl}')
    lines.insert(1, sfx_note)
    if a.expect_fail:
        want = [k for k in a.expect_fail.split(',') if k]; miss = [k for k in want if k not in keyed]
        print(('menu: КРАСНЫЙ как надо — пойманы ' + ', '.join(want)) if not miss else 'menu: НЕ КРАСНЫЙ — не пойманы ' + ', '.join(miss))
        for f in fails: print('  - ' + f)
        return 0 if not miss else 1
    print('\n'.join(lines))
    (out / 'menu_check.txt').write_text('\n'.join(lines) + '\n')
    if a.copy:
        try:
            from PIL import Image
            dst = Path(a.copy); dst.mkdir(parents=True, exist_ok=True)
            for s in shots:
                p = out / f'{s}.png'
                if not p.exists(): continue
                im = Image.open(p).convert('RGB'); w, h = im.size; ch = min(h, round(w * 272 / 480))   # окно: кадр снизу
                im.crop((0, h - ch, w, h)).resize((480, 272), Image.LANCZOS).save(dst / f'12a_{s}.png')
        except ImportError:
            pass
    return 0 if not fails else 1


if __name__ == '__main__':
    sys.exit(main())
