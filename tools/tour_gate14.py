#!/usr/bin/env python3
"""Гейт тура 14 (tests/me/psp_tour_14.txt). Читает smoke.txt нового формата (docs/handoff/ФОРМАТ_ТЕСТ14_СТРОКИ_2026-10-11.md):
  HIST/HISTG (корзины по кадрам, HISTG — только st=game), WORST (20 худших кадров сцены), SCENE_OK/SCENE_FAIL (expect в сценарии),
  строки таблицы с st= и rec=, телеметрия дня (GROUNDBIAS ground=N, b1_us/ui_us в RFAST, UIPROF, MCR pre/load, warm=).
  tools/tour_gate14.py build/psp-tour/<папка> [ещё]
Красное: сцена не дошла до места (SCENE_FAIL), у езды (*_D, H_*, J*, L1_aes, gb*, B538) нет кадров игры, доля игровых кадров <= 33,3 мс ниже 95 %,
  нет строки телеметрии (HIST у каждой сцены), GROUNDBIAS ground=0 при пересобранных данных. Переходы (*_T): показываем худший кадр не в загрузке и
  число кадров > 100 мс вне загрузки (информативно, красным не считается: порог рывка при старте решает Роб)."""
import re, sys
from pathlib import Path
KV = re.compile(r'(\w+)=(\S+)')
def main(dirs):
    bad = 0
    for d in dirs:
        f = Path(d) / 'smoke.txt'
        if not f.exists(): print(f'нет {f}'); bad += 1; continue
        hist, histg, worst, ok, fail, scenes, tel = {}, {}, {}, {}, [], [], {}
        for ln in f.read_text(errors='replace').splitlines():
            m = re.match(r'SCENE (\S+)', ln)
            if m: scenes.append(m.group(1))
            if ln.startswith(('HIST ', 'HISTG ')):
                kv = dict(KV.findall(ln)); t = {k: int(v) for k, v in kv.items() if k != 'scene'}
                (hist if ln.startswith('HIST ') else histg)[kv['scene']] = t
            elif ln.startswith('WORST '):
                kv = dict(KV.findall(ln)); worst.setdefault(kv['scene'], []).append((float(kv['ms']), kv['st'], kv['t']))
            elif ln.startswith('SCENE_OK'): ok[dict(KV.findall(ln))['scene']] = ln
            elif ln.startswith('SCENE_FAIL'): fail.append(ln)
            elif ln.startswith('GROUNDBIAS'): tel['groundbias'] = ln
            elif 'b1_us=' in ln: tel['b1_us'] = 1
            elif ln.startswith('UIPROF'): tel['UIPROF'] = 1
            elif ln.startswith('MCR pre') or 'MCR pre/' in ln: tel['MCR'] = 1
            elif ' warm=' in ln: tel['warm'] = 1
        print(f'== {d}: сцен {len(scenes)}, HIST у {len(hist)}')
        for sc in scenes:
            if sc not in hist: print(f'  {sc:20s} НЕТ HIST (строка телеметрии не пришла)'); bad += 1; continue
            h = hist[sc]; g = histg.get(sc, {}); gn = g.get('frames', 0)
            kind = 'ПЕРЕХОД' if sc.endswith('_T') else ('загрузка' if sc.endswith('_load') or sc in ('start',) else 'ЕЗДА')
            if kind == 'ЕЗДА':
                share33 = (g.get('le16', 0) + g.get('le33', 0)) / gn if gn else 0.0; share16 = g.get('le16', 0) / gn if gn else 0.0
                good = gn > 0 and share33 >= 0.95; bad += not good
                print(f'  {sc:20s} ЕЗДА  кадров игры {gn:4d}  <=16,7: {share16*100:5.1f} %  <=33,3: {share33*100:5.1f} %  >50: {g.get("le100",0)+g.get("gt100",0)+g.get("le50",0):3d}  {"ПРОШЛА" if good else "НЕТ"}')
            elif kind == 'ПЕРЕХОД':
                w = [x for x in worst.get(sc, []) if x[1] != 'load']; wm = max([x[0] for x in w], default=0)
                over = sum(1 for x in w if x[0] > 100)
                print(f'  {sc:20s} ПЕРЕХОД  худший кадр вне загрузки {wm:6.1f} мс (кадров >100 мс среди 20 худших: {over})')
        for sc, ln in ok.items(): pass
        print(f'  SCENE_OK: {len(ok)}, SCENE_FAIL: {len(fail)}')
        for ln in fail: print('   ', ln[:150]); bad += 1
        for k in ('b1_us', 'UIPROF', 'MCR', 'warm'):
            if k not in tel: print(f'  НЕТ телеметрии: {k}'); bad += 1
        gb = tel.get('groundbias')
        if not gb: print('  НЕТ телеметрии: GROUNDBIAS'); bad += 1
        elif re.search(r'ground=0\b', gb): print('  ', gb[:120], '-> ground=0: данные без метки «земля» (нужна пересборка level.shr)'); bad += 1
        else: print('  ', gb[:120])
    return 1 if bad else 0
if __name__ == '__main__': sys.exit(main(sys.argv[1:]) if len(sys.argv) > 1 else print(__doc__) or 2)
