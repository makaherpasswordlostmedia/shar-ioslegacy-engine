#!/usr/bin/env python3
"""Гейт правки Роба 244 (видео 03.10 0:45–1:02: «газета на загрузке зависает, не крутится, хотя должно мигать»):
экран загрузки уровня (газета) живой всё время загрузки — кадры не реже GAP_MS (подкачка loadPump из долгих циклов:
проверка дорог mcProbeRoads, шаги новой игры, чтение моделей) и надпись LOADING мигает (LOAD_BLINK_S).
   python3 tests/load/news_gate.py   -> код 0 = зелёный; три прогона безголового эмулятора (без звука) одного EBOOT:
     обычный — зелёный; «flag loadpumpoff» — обязан быть красным по разрыву; «flag loadblinkoff» — по миганию.
Путь: главное меню -> NEW GAME -> газета (строки LOADGAP / LOADBLINK / LOADSHOW движка в smoke.txt)."""
import os, re, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/twins'))
import common as C, port as P
GAP_MS = 400
LOAD_SHR = C.OUT / 'news_load.shr'
subprocess.run([sys.executable, str(ROOT / 'tools/load_export.py'), '--pack', 'load', '--out', str(LOAD_SHR)], check=True, capture_output=True)
SCEN = ['flag menu', 'wait 1', 'press start', 'wait 1', 'press start', 'wait 1', 'press start', 'wait 1.5', 'press cross', 'wait 7', 'end']


def run(name, extra):
    lines = SCEN[:1] + extra + SCEN[1:]
    d, man = P.stage_full(C.OUT / 'scen', name, '\n'.join(lines) + '\n', 5)
    import shutil; shutil.copy2(LOAD_SHR, d / 'load.shr')   # свежий пакет экранов загрузки (метка LOADING газеты)
    eb = os.environ.get('NEWS_EBOOT')
    if eb:
        import shutil; (d / 'EBOOT.PBP').unlink(); shutil.copy2(eb, d / 'EBOOT.PBP')
    home = C.OUT / 'ppsspp_home_news'; home.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, HOME=str(home), TWINS_SMOKE=str(d / 'smoke.txt'), TWINS_SHOTDIR=str(d), DYLD_FRAMEWORK_PATH=str(C.BIN), SDL_AUDIODRIVER='dummy')
    for k in ('XDG_CONFIG_HOME', 'XDG_DATA_HOME'): env.pop(k, None)
    with (d / 'headless.log').open('w') as log:
        pr = subprocess.Popen(['nice', '-n', '10', str(P.HEADLESS), '--graphics=software', '--timeout=300', str(d / 'EBOOT.PBP')],
                              cwd=d, env=env, stdout=log, stderr=subprocess.STDOUT)
        P.watch_no_window(pr, 360)
    txt = (d / 'smoke.txt').read_text(errors='replace') if (d / 'smoke.txt').exists() else ''
    gaps = [int(m) for m in re.findall(r'^LOADGAP ms=(\d+)', txt, re.M)]
    blinks = len(re.findall(r'^LOADBLINK ', txt, re.M)); shown = 'LOADSHOW' in txt
    return shown, max(gaps or [0]), blinks


def verdict(tag, shown, gap, blinks):
    bad = []
    if not shown: bad.append('нет экрана газеты (LOADSHOW)')
    if gap > GAP_MS: bad.append(f'разрыв без кадра {gap} мс > {GAP_MS}')
    if blinks < 4: bad.append(f'LOADING переключился {blinks} раз < 4')
    print(f'{tag}: газета {"есть" if shown else "нет"}, худший разрыв {gap} мс, переключений LOADING {blinks}' + (' — ' + '; '.join(bad) if bad else ''))
    return not bad


ok = verdict('обычный', *run('news_green', []))
red1 = not verdict('красный loadpumpoff', *run('news_pumpoff', ['flag loadpumpoff']))
red2 = not verdict('красный loadblinkoff', *run('news_blinkoff', ['flag loadblinkoff']))
print('ИТОГ:', 'зелёный' if ok and red1 and red2 else f'КРАСНЫЙ (обычный {"ok" if ok else "FAIL"}, красные пойманы {int(red1) + int(red2)}/2)')
sys.exit(0 if ok and red1 and red2 else 1)
