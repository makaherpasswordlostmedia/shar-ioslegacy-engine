#!/usr/bin/env python3
"""Разбор прогона «подборы, ловушки, огонь, DEATH» бонус-игры в безголовом эмуляторе (tests/bonus/emu_pickups.sh,
сценарий tests/bonus/emu_pickups.txt: гонка 1 круг на b07, потом на b04).
  python tests/bonus/emu_pickups_check.py RUN_DIR [--expect-fail]
Проверки (числа из smoke.txt, строки BONUS ev=… viewer/bonus_play.h):
  items   на обеих трассах данные подборов и ловушек прочитаны: BONUS ev=items track=7 picks=4 models=4 traps=1 и track=4 picks=5
          models=5 traps=1 (модель каждого подбора найдена в SPR1 трассы, объект ловушки ANM1 связан); DEATH b07 = 2 объёма
  races   обе гонки дошли до итога (BONUS ev=effects track=7 и track=4)
  picks   машины брали подборы (ev=pick) хотя бы раз
  traps   ловушки сработали в гонке на обеих трассах (ev=trap после start каждой трассы)
  light   машина въезжала в зону огня b07 (ev=light argb=BBFF9A3F)
  shots   снимки гонок не пустые (разброс яркости > 12)
--expect-fail — код 0, только если нет ни одного эффекта (picks, traps, light, launch, death — все нули): красный -DBONUS_PICKUPS_OLD=1."""
import sys
from pathlib import Path
import numpy as np
from PIL import Image


def kv(l): return dict(p.split('=', 1) for p in l.split()[1:] if '=' in p)


def main():
    run = Path(sys.argv[1]); expect_fail = '--expect-fail' in sys.argv
    log = (run / 'smoke.txt').read_text(errors='replace').splitlines() if (run / 'smoke.txt').exists() else []
    ev = [kv(l) for l in log if l.startswith('BONUS ')]
    errs, lines = {}, []
    def need(name, ok, msg):
        lines.append(f"  {'ok  ' if ok else 'FAIL'} {name}: {msg}")
        if not ok: errs[name] = msg
    items = {e.get('track'): e for e in ev if e.get('ev') == 'items'}
    i7, i4 = items.get('7', {}), items.get('4', {})
    need('items', i7.get('picks') == '4' and i7.get('models') == '4' and i7.get('traps') == '1' and i7.get('death') == '2'
         and i4.get('picks') == '5' and i4.get('models') == '5' and i4.get('traps') == '1', f"b07 {i7 or 'нет'}; b04 {i4 or 'нет'}")
    eff = {e.get('track'): e for e in ev if e.get('ev') == 'effects'}
    need('races', '7' in eff and '4' in eff, f"итоги эффектов: {eff or 'нет'}")
    picks = [e for e in ev if e.get('ev') == 'pick']
    need('picks', len(picks) > 0, f"подборов {len(picks)}: " + ', '.join(f"{e.get('name')}:{e.get('item')}" for e in picks[:8]))
    # ловушки по трассам: ev=trap между ev=start гонки и её ev=effects
    cur, trap = None, {}
    for e in ev:
        if e.get('ev') == 'items': cur = e.get('track')
        elif e.get('ev') == 'trap' and cur: trap[cur] = trap.get(cur, 0) + 1
    need('traps', trap.get('7', 0) > 0 and trap.get('4', 0) > 0, f"срабатываний ловушек: {trap}")
    lt = [e for e in ev if e.get('ev') == 'light']
    need('light', any(e.get('argb') == 'BBFF9A3F' for e in lt), f"въездов в свет огня {len(lt)} ({lt[0] if lt else 'нет'})")
    sd = {}
    for n in ('pick_b07_top', 'pick_b04_top'):
        p = run / f'{n}.png'
        if p.exists(): sd[n] = float(np.asarray(Image.open(p).convert('L'), np.float64).std())
    need('shots', len(sd) == 2 and min(sd.values()) > 12, f"разброс яркости {sd}")
    exits = [e for e in ev if e.get('ev') == 'exit']
    back = any(e.get('ok') == '1' for e in exits) and sum(l.startswith('MENU ') for l in log) >= 2
    need('back', back, 'exit to main menu restores bonus resources')
    deaths = [e for e in ev if e.get('ev') == 'death']; launch = [e for e in ev if e.get('ev') == 'launch']
    lines.append(f"  инфо: DEATH-возвратов {len(deaths)}, подбросов B04G {len(launch)}; итоги {list(eff.values())}")
    if expect_fail:
        nz = len(picks) + sum(trap.values()) + len(lt) + len(deaths) + len(launch)
        ok = back and nz == 0 and set(eff) == {'7', '4'} and i7.get('picks') == '4' and i7.get('models') == '4' and i7.get('death') == '2' and i4.get('picks') == '5' and i4.get('models') == '5'
        print(('OK красный пойман: эффектов 0, гонки дошли до итога' if ok else f'FAIL красный НЕ пойман: эффектов {nz}, итогов {len(eff)}'))
        print('\n'.join(lines)); return 0 if ok else 1
    print(('OK подборы, ловушки, огонь в эмуляторе' if not errs else 'FAIL ' + '; '.join(f'{k}: {v}' for k, v in errs.items())) + f' · {run.name}')
    print('\n'.join(lines))
    return 1 if errs else 0


if __name__ == '__main__':
    sys.exit(main())
