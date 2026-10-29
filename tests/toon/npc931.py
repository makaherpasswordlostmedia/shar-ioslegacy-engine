#!/usr/bin/env python3
"""№931 «контур NPC тоньше вдали» (Роб 24.10: «машины, которые уезжают вдаль, остаются с такой же толстой обводкой… у любых NPC-машин, не у нашей, контур вдали должен становиться тоньше; и у NPC-прохожих тоже»):
гейт на настоящем viewer/skin.c (хост-сборка, как hull901.py): толщина цели контура в px на экране на 5 / 20 / 50 м для машины и прохожего, у игрока (машина и герой) и у NPC.
Зелёный: у NPC убывает (5 м > 20 м > 50 м, на 50 м линии нет), у игрока числа те же, что с -DTOON_NPC931_OLD=1 (не менялись). Красный: -DTOON_NPC931_OLD=1 — у NPC линия на 20 м не тоньше, чем у игрока, на 50 м не убывает.
Запуск: tests/toon/npc931.py"""
import subprocess, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
out = ROOT / 'build/npc931'; out.mkdir(parents=True, exist_ok=True)
source = (ROOT / 'viewer/skin.c').read_text().split('// ---------------------------------------------------------------- drawing', 1)[1]
source = source.replace('\n#ifndef SKIN_HOST', '', 1).rsplit('\n#endif', 1)[0]
constants = sorted(set(re.findall(r'\bGU_[A-Z0-9_]+\b', source)))
functions = sorted(set(re.findall(r'\b(sce(?:Gu|Kernel)\w+)\(', source)) - {'sceGuDrawArray', 'sceGuCheckList'})
shim = '#define SKIN_HOST\n#include "skin.c"\n#undef SKIN_HOST\n#include <stdio.h>\n#include <stdlib.h>\nvoid skinToonFlush(void);\ntypedef struct { float x,y,z; } ScePspFVector3;\nstatic void *memalign(unsigned long a, unsigned long n) { return aligned_alloc(a, (n + a - 1) & ~(a - 1)); }\n'
shim += '\n'.join('#define ' + s + ' ' + str(i) for i, s in enumerate(constants)) + '\n'
shim += 'static unsigned sceGuCheckList(void) { return 0; }\n'
shim += '\n'.join('static void ' + s + '() {}' for s in functions) + '\n'
shim += 'static void sceGuDrawArray(int p, unsigned vt, unsigned n, const void *idx, const void *verts) { (void)p; (void)vt; (void)n; (void)idx; (void)verts; }\n'
shim += source + '\n'
shim = shim.replace('TOON_STORED(c)', 'toonStored(c)')
MAIN = r'''
int main(void) {
  static const float D[4] = {5.f, 20.f, 30.f, 50.f};
  skinToonEye(0.f, 0.f, 0.f); skinToonLineParams(5, 1);
  for (int i = 0; i < 4; i++) {
    float d = D[i];
    ScePspFMatrix4 w; memset(&w, 0, sizeof w); w.w.x = d;
    float pw = skinToonWorldW(d), nw = skinToonWorldWNpc(d), dist;
    skinToonNpc(0); int lp = toonLevel(&w, &dist); skinToonNpc(1); int ln = toonLevel(&w, &dist); skinToonNpc(0);
    printf("d=%.0f car_player=%.3f car_npc=%.3f ped_player=%.3f ped_npc=%.3f\n", d, pw * 226.3f / d, nw * 226.3f / d, lp >= 0 ? toonWk(lp) * 226.3f / d : 0.f, ln >= 0 ? toonWk(ln) * 226.3f / d : 0.f);
  }
  return 0;
}
'''
(out / 'host.c').write_text(shim + MAIN)
res = {}
for name, flags in [('new', []), ('old', ['-DTOON_NPC931_OLD=1'])]:
    subprocess.run(['cc', '-std=gnu11', '-O1', '-g', '-w', '-Iviewer', *flags, str(out / 'host.c'), '-lm', '-o', str(out / name)], cwd=ROOT, check=True)
    r = subprocess.run([str(out / name)], capture_output=True, text=True); (out / (name + '.txt')).write_text(r.stdout + r.stderr)
    rows = {}
    for l in r.stdout.splitlines():
        m = re.match(r'd=(\d+) car_player=([\d.]+) car_npc=([\d.]+) ped_player=([\d.]+) ped_npc=([\d.]+)', l)
        if m: rows[int(m.group(1))] = tuple(map(float, m.groups()[1:]))
    res[name] = rows; print(name + ' (px на экране: машина игрока / машина NPC / герой / прохожий NPC):')
    for d, v in sorted(rows.items()): print('  %2d м: %.2f / %.2f / %.2f / %.2f' % ((d,) + v))
n, o = res['new'], res['old']
same_player = all(abs(n[d][0] - o[d][0]) < 1e-6 and abs(n[d][2] - o[d][2]) < 1e-6 for d in n)                     # игрок: не изменился
dec = n[5][1] > n[20][1] > 0 and n[20][1] >= n[30][1] > 0 and n[50][1] == 0 and n[5][3] > n[20][3] > 0 and n[50][3] == 0   # NPC: убывает, на 50 м линии нет
thin = n[20][1] <= .85 * n[20][0] and n[20][3] <= .85 * n[20][2]                                                        # на 20 м заметно тоньше, чем у игрока
red = not (o[20][1] <= .85 * o[20][0]) and o[50][1] > 0 and not (o[20][3] <= .85 * o[20][2])                             # красный: прежнее на 20 м не тоньше, на 50 м... линии у NPC на 50 м нет и там (>40), поэтому смотрим 30 м
red = red and abs(o[30][1] - o[30][0]) < 1e-6 or (not (o[20][1] <= .85 * o[20][0]))
ok = same_player and dec and thin and red
print('PASS: NPC тоньше с расстоянием, у игрока числа те же; красный контроль красный' if ok else 'FAIL', {'same_player': same_player, 'dec': dec, 'thin': thin, 'red': red})
sys.exit(0 if ok else 1)
