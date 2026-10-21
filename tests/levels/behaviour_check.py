#!/usr/bin/env python3
"""AddBehaviour с текстом (блокер уровня 7, docs/РЕЦЕПТ_УРОВНЯ.md §3.1, 29.09): разбор ос tools/collect_export.parse_wasps.

На диске один такой вызов: leveli.mfk уровня 7 AddBehaviour("Planet Express Ship", "UFO_BEAM_ALWAYS_ON", "UfoBeam") — третий
аргумент имя составного рисунка/StatePropData луча в art/missions/level07/ufobeam.p3d. До 29.09 разбор делал float() всех
аргументов и падал; теперь число — число, текст — текст, поведение не-осы в CLT1 не идёт (не покрыто: механика уровня 7).
  behaviour_check.py            зелёный: уровни 1–7 разбираются; у 7 текст UfoBeam сохранён как текст, осы — как раньше
  behaviour_check.py --plant    красный: (а) прежний разбор (float всех аргументов) на уровне 7 обязан упасть;
                                (б) текст в числовом поведении осы (ATTRACTION) обязан быть отвергнут, а не проглочен"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools')); sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))
import collect_export as CX   # noqa: E402
GAME = CX.GAME


def calls(lv):
    return CX.mfk_calls(GAME / f'scripts/missions/level0{lv}/leveli.mfk')


def locs(lv):
    art = GAME / 'art'
    return CX.all_locators([art / f'l{lv}_terra.p3d', *sorted(art.glob(f'l{lv}[rzi]*.p3d')), *sorted((art / f'missions/level0{lv}').glob('*.p3d'))])


def old_parse(cs):   # строка разбора до 29.09 (collect_export.parse_wasps, git 0a7e51b)
    for c in cs:
        if c.op == 'AddBehaviour' and len(c.args) >= 3: [float(x) for x in c.args[2:]]


def main():
    plant = '--plant' in sys.argv; bad = []
    if plant:
        try: old_parse(calls(7)); bad.append('прежний разбор уровня 7 не упал')
        except ValueError as e: print(f'(а) прежний разбор уровня 7 падает, как до 29.09: {e}')
        cs = calls(7); L = locs(7)
        for c in cs:
            if c.op == 'AddBehaviour' and str(c.args[0]) == 'beecamera' and str(c.args[1]).upper() == 'ATTRACTION':
                c.args = [c.args[0], c.args[1], 'abc'] + list(c.args[3:]); break
        try: CX.parse_wasps(cs, L); bad.append('текст в ATTRACTION осы проглочен')
        except ValueError as e: print(f'(б) текст в числовом поведении осы отвергнут: {e}')
        print('FAIL (красный, как должен)' if not bad else 'КРАСНЫЙ НЕ ПОЙМАН: ' + '; '.join(bad))
        return 1 if not bad else 0
    for lv in range(1, 8):
        try:
            w, pre = CX.parse_wasps(calls(lv), locs(lv))
            beh = {str(c.args[0]): [CX.behaviour_arg(x) for x in c.args[2:]] for c in calls(lv) if c.op == 'AddBehaviour'}
            txt = {k: v for k, v in beh.items() if any(isinstance(x, str) for x in v)}
            print(f'уровень {lv}: ос {len(w)} (живых {pre}), поведения с текстом {txt or "нет"}')
            if lv == 7 and txt.get('Planet Express Ship') != ['UfoBeam']: bad.append('уровень 7: UfoBeam не сохранён как текст')
            if not w: bad.append(f'уровень {lv}: ос нет')
        except Exception as e: bad.append(f'уровень {lv}: {e!r}')
    for b in bad: print('  ПРОВАЛ:', b)
    print('PASS' if not bad else f'FAIL ({len(bad)})')
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(main())
