#!/usr/bin/env python3
# CAMPERF (ускорение камеры, дирижёр 23.10): сценарий для tests/camera/camperf.py. Одна и та же программа даёт «старый» и «новый» прогон: разница — только флаги в начале.
#   camperf_gen.py LEVEL VARIANT [det] [walk]
#   LEVEL    1 | 3 | 5   (L1 — со старта, L3/L5 — переход golevel, как в туре)
#   VARIANT  old   — все ускорения выключены флагами (camraysold, cgcoarseold, cgtriold, camstatalwaysold)
#            new   — как в игре
#            newv  — как new + проверка пакетных лучей (CAMSUB mm= считает расхождения с лучами по одному)
#   det      1 — «кадр в кадр»: flag camdet (шаг 1/30 с, бюджет стройки сетки в треугольниках) + camlog (строки CAMF); 0 — как в игре (цена)
#   walk     walk — Гомер пешком по маршруту (вперёд, вправо, вперёд, влево, вперёд); иначе — автопилот по дорогам 40 с
import sys
L = int(sys.argv[1]); var = sys.argv[2]; det = len(sys.argv) > 3 and sys.argv[3] == '1'; walk = len(sys.argv) > 4 and sys.argv[4] == 'walk'
o = ['# камера: %s L%d, %s%s' % ('ходьба' if walk else 'езда автопилотом', L, var, ', кадр в кадр' if det else ''), 'wait 12', 'flag cfgdefaults 1']
if det: o += ['flag camdet 1', 'flag camlog']
if var == 'old': o += ['flag camraysold 1', 'flag cgcoarseold 1', 'flag cgtriold 1', 'flag camstatalwaysold 1']
if var == 'newv': o += ['flag camraysverify 1']
if L == 1: o += ['scene cp_l1', 'wait 2'] + ([] if walk else ['flag repair']) + ['wait 1.5']
else: o += ['scene cp_go_l%d' % L, 'flag golevel %d' % L, 'wait 40'] + ([] if walk else ['press triangle 0.2']) + ['wait 3']
if walk:
    if L == 1: o += ['foot 214 210 -2.4', 'wait 2']
    for b, t in (('up', 6), ('r', 2), ('up', 6), ('l', 3), ('up', 6)): o += ['press %s %d' % (b, t), 'wait %.1f' % (t + .2)]
    o += ['end']
else: o += ['flag drive 40', 'wait 42', 'flag stop', 'end']
print('\n'.join(o))
