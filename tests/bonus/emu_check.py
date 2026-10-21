#!/usr/bin/env python3
"""Разбор прогона бонус-игры в безголовом эмуляторе (tests/bonus/emu.sh, сценарий tests/bonus/emu_scenario.txt).
  python tests/bonus/emu_check.py RUN_DIR [--expect-fail]
Проверки (каждая — числом из smoke.txt и снимков):
  menu    пункт BONUS GAME включён (строка MENU on=… с номером пункта 3) и выбор бонус-игры открылся (BONUS ev=menu)
  load    трасса прочитана: BONUS ev=load col=1, клеток > 0
  start   гонка началась: BONUS ev=start, 8 чекпойнтов b01, путь ИИ > 0 точек
  laps    круги: каждая из 4 машин прошла круг (ev=lap) и финишировала (ev=finish), BONUS ev=done
  cams    обе камеры: ev=cam mode=0 и mode=1; кадры BONUSFR в обеих
  shots   снимки сверху и за машиной не пустые (разброс яркости > 12) и разные (средняя разница > 20)
  back    выход: BONUS ev=exit ok=1, снова главное меню (MENU n=2)
--expect-fail — код 0, только если провалилась проверка menu (красный: сборка -DBONUS_OLD=1, пункт серый)."""
import sys
from pathlib import Path
import numpy as np
from PIL import Image


def kv(l): return dict(p.split('=', 1) for p in l.split()[1:] if '=' in p)


def main():
    run = Path(sys.argv[1]); expect_fail = '--expect-fail' in sys.argv
    log = (run / 'smoke.txt').read_text(errors='replace').splitlines() if (run / 'smoke.txt').exists() else []
    ev = [kv(l) | {'ev': kv(l).get('ev')} for l in log if l.startswith('BONUS ')]
    fr = [kv(l) for l in log if l.startswith('BONUSFR ')]
    menus = [kv(l) for l in log if l.startswith('MENU ')]
    errs, lines = {}, []
    def need(name, ok, msg):
        lines.append(f"  {'ok  ' if ok else 'FAIL'} {name}: {msg}")
        if not ok: errs[name] = msg
    on = menus[0].get('on', '').split(',') if menus else []
    need('menu', '3' in on and any(e['ev'] == 'menu' for e in ev), f"пункты меню включены {on}, выбор бонус-игры {'есть' if any(e['ev'] == 'menu' for e in ev) else 'нет'}")
    ld = [e for e in ev if e['ev'] == 'load']
    need('load', bool(ld) and ld[0].get('col') == '1' and int(ld[0].get('cells', 0)) > 0, f"{ld[0] if ld else 'нет строки load'}")
    st = [e for e in ev if e['ev'] == 'start']
    need('start', bool(st) and st[0].get('cps') == '8' and int(st[0].get('path', 0)) > 0, f"{st[0] if st else 'нет строки start'}")
    laps = {e['car'] for e in ev if e['ev'] == 'lap'}; fin = {e['car'] for e in ev if e['ev'] == 'finish'}; done = [e for e in ev if e['ev'] == 'done']
    need('laps', laps == {'0', '1', '2', '3'} and fin == {'0', '1', '2', '3'} and bool(done),
         f"кругов у машин {sorted(laps)}, финиш {sorted(fin)}, итог {done[0] if done else 'нет'}")
    cams = {e['mode'] for e in ev if e['ev'] == 'cam'}; frc = {f.get('cam') for f in fr}
    fps = [float(f['fps']) for f in fr]
    need('cams', cams >= {'0', '1'} and frc >= {'0', '1'}, f"камеры {sorted(cams)}, кадры в камерах {sorted(frc)}; кадр/с эмулятора {min(fps) if fps else 0:.0f}…{max(fps) if fps else 0:.0f} (не PSP)")
    sh = {}
    for n in ('bonus_top', 'bonus_chase'):
        p = run / f'{n}.png'
        if p.exists(): sh[n] = np.asarray(Image.open(p).convert('L'), np.float64)
    if len(sh) == 2:
        sd = {n: float(a.std()) for n, a in sh.items()}; diff = float(np.abs(sh['bonus_top'] - sh['bonus_chase']).mean())
        need('shots', min(sd.values()) > 12 and diff > 20, f"разброс яркости {sd}, разница снимков {diff:.1f}")
    else: need('shots', False, f"нет снимков ({sorted(sh)})")
    ex = [e for e in ev if e['ev'] == 'exit']
    need('back', bool(ex) and ex[0].get('ok') == '1' and len(menus) >= 2, f"выход {ex[0] if ex else 'нет'}, входов в меню {len(menus)}")
    if expect_fail:
        ok = 'menu' in errs
        print(('OK красный пойман: ' if ok else 'FAIL красный НЕ пойман: ') + '; '.join(f'{k}: {v}' for k, v in errs.items()))
        print('\n'.join(lines)); return 0 if ok else 1
    print(('OK бонус-игра в эмуляторе' if not errs else 'FAIL ' + '; '.join(f'{k}: {v}' for k, v in errs.items())) + f' · {run.name}')
    print('\n'.join(lines))
    return 1 if errs else 0


if __name__ == '__main__':
    sys.exit(main())
