#!/usr/bin/env python3
"""Тексты миссий уровня (пакет «Миссии»: пункт 3) — из текстовой библии диска (art/frontend/scrooby/resource/txtbible/srr2.p3d),
как их показывает PSP: задание этапа (HUD, рамка задания), название и описание (брифинг MissionLoad), причина и подсказки
провала (MissionOver), служебные строки (MISSION COMPLETE, GO ...). Проверки для всех миссий уровня (сюжетные m0..m7 и бонусы):
  * у каждого этапа с SetStageMessageIndex есть текст; у каждой миссии — название, у сюжетной — описание брифинга;
  * у каждой причины провала — текст и хотя бы одна подсказка;
  * ни одного символа, которого нет в шрифте своего экрана (ui.shr, шрифты Scrooby), и ни одного «\\» (перенос строки
    библии должен стать переносом, а не символом);
  * вписывание в рамки проверяет движок (tests/missions/emu_hud.sh, flag uifit).
   python tests/missions/texts_check.py [--level 1] [--plant]   -> код 0 = зелёный
   --plant: отрицательный контроль — подложены пустое задание, «\\» в описании и символ вне шрифта -> обязан быть красным"""
import argparse, importlib.util, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools')); sys.path.insert(0, str(ROOT / 'tools/missions'))
import ui_export as U

ap = argparse.ArgumentParser(); ap.add_argument('--level', type=int, default=1); ap.add_argument('--plant', action='store_true')
a = ap.parse_args()
spec = importlib.util.spec_from_file_location('mc', ROOT / 'tools/missions/compile.py'); mc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mc)
c = mc.Compiler(a.level); c.compile(); P = c.pack; S = P.strings

fc = U.FontCache('psp')
def face(screen, name):
    items, _ = U.build_items(screen)
    it = next(t for t in items if t['type'] == U.T_TEXT and t['name'] == name)
    return set(fc.get(it['font'])['glyphs'].keys())
G = dict(stage=face('hud', 'Message'), title=face('missionload', 'MissionTitle'), info=face('missionload', 'MissionInfo'),
         fail=face('missionover', 'MissionFailureReason'), hint=face('missionover', 'MissionFailureHint'))

texts = []   # (вид, где, текст)
for m in P.missions:
    code, title, info, flags = S[m[0]], S[m[1]], S[m[2]], m[3]
    texts.append(('title', code, title)); texts.append(('info', code, info))
    if not title or title == code: texts.append(('missing', code, 'нет названия миссии в библии'))
    if not info and not (flags & (mc.MF_NOSCRIPT)) and not code.startswith(('sr', 'gr', 'bm')): texts.append(('missing', code, 'нет описания брифинга'))
nst = 0
for st in P.stages:
    msg, text = st[4], S[st[5]]
    if msg != 0xFFFF:
        nst += 1; texts.append(('stage', f'MISSION_OBJECTIVE_{msg:02d}', text))
        if not text: texts.append(('missing', f'MISSION_OBJECTIVE_{msg:02d}', 'нет текста задания'))
for r in mc.FAIL_TEXT_KEYS:
    k = f'MISSION_FAILED_{r}'
    if k not in P.texts: texts.append(('missing', k, 'нет причины провала')); continue
    texts.append(('fail', k, P.texts[k]))
    hints = [P.texts[f'{k}_HINT{i}'] for i in range(8) if f'{k}_HINT{i}' in P.texts]
    if not hints: texts.append(('missing', k, 'нет подсказок'))
    texts += [('hint', f'{k}_HINT{i}', h) for i, h in enumerate(hints)]
if a.plant:
    texts += [('missing', 'plant', 'нет текста задания'), ('info', 'plant', 'GO TO THE\\KWIK-E-MART'), ('stage', 'plant', 'CAFÉ Ω')]
bad = []
for kind, where, t in texts:
    if kind == 'missing': bad.append(f'{where}: {t}'); continue
    if '\\' in t: bad.append(f'{where}: «\\» в тексте «{t[:40]}»')
    miss = sorted({ch for ch in t if ch not in '\n' and ord(ch) not in G[kind]})
    if miss: bad.append(f'{where}: нет в шрифте {miss} «{t[:40]}»')
print(f'уровень {a.level}: миссий {len(P.missions)}, заданий этапов {nst}, текстов всего {len([x for x in texts if x[0] != "missing"])}')
for b in bad[:20]: print('  ', b)
print('ИТОГ:', 'зелёный' if not bad else f'КРАСНЫЙ ({len(bad)})')
sys.exit(1 if bad else 0)
