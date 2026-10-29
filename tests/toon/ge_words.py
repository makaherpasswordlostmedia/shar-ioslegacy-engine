#!/usr/bin/env python3
"""№428 «мультик»: счётчик слов списка GE (аудит железа TEST27 п.1, класс правки 103). Хост-сборка настоящего skin.c, заглушки sceGu* с ценой в словах
по pspsdk (libpspgu); skinDrawPal на 5 героях, режим выкл и вкл. Оценка skinGeBytes (слов) обязана быть НЕ ниже худшего реального числа слов (все привязки текстур и все матрицы
костей без кэша) с запасом >= 32 слов; красный контроль -DSKIN_GE_TOON_OLD=1 (прежняя +16): запас 4-5 слов (ниже порога) на всех моделях. Запуск: tests/toon/ge_words.py [--stage DIR]
(код ниже — осталось от v2_hull:) 
Для каждой пачки с индексами (flags&4) оболочка должна: лежать внутри своего выделения (границы), рисоваться теми же индексами,
а вершина по индексу — это вершина пачки, сдвинутая по нормали не больше SKIN_TOON_W. Красный контроль: -DSKIN_TOON_V2_OLD=1
(прежнее: копия nverts вершин, без индексов) обязан провалить. Запуск: tests/toon/v2_hull.py [--stage DIR]"""
import argparse, subprocess, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
ap = argparse.ArgumentParser(); ap.add_argument('--stage', type=Path, default=Path.home() / 'Downloads/shar-psp/build/ship_stage'); args = ap.parse_args()
out = ROOT / 'build/toon-ge-words'; out.mkdir(parents=True, exist_ok=True)
source = (ROOT / 'viewer/skin.c').read_text().split('// ---------------------------------------------------------------- drawing', 1)[1]
source = source.replace('\n#ifndef SKIN_HOST', '', 1).rsplit('\n#endif', 1)[0]
constants = sorted(set(re.findall(r'\bGU_[A-Z0-9_]+\b', source)))
functions = sorted(set(re.findall(r'\b(sce(?:Gu|Kernel)\w+)\(', source)) - {'sceGuDrawArray'})
shim = '#define SKIN_HOST\n#include "skin.c"\n#undef SKIN_HOST\n#include <stdio.h>\n#include <stdlib.h>\ntypedef struct { float x,y,z; } ScePspFVector3;\n'
shim += '\n'.join('#define ' + s + ' ' + str(i) for i, s in enumerate(constants)) + '\n'
shim += 'static unsigned char *hullBase; static unsigned hullSize; static void *memalign(unsigned a,unsigned n){ void *p=aligned_alloc(a,(n+a-1)&~(a-1)); hullBase=p; hullSize=n; return p; }\n'
COST = {'sceGuSetMatrix': 13, 'sceGuDisable': 1, 'sceGuEnable': 1, 'sceGuDepthMask': 1, 'sceGuTexFunc': 2, 'sceGuTexFilter': 1, 'sceGuTexScale': 2, 'sceGuTexOffset': 2,
        'sceGuClutMode': 1, 'sceGuLight': 4, 'sceGuLightColor': 1, 'sceGuAmbient': 2, 'sceGuModelColor': 4, 'sceGuAmbientColor': 2, 'sceGuAlphaFunc': 1,
        'sceGuBoneMatrix': 13, 'sceGuClutLoad': 3, 'sceGuTexMode': 2, 'sceGuTexImage': 4, 'sceKernelDcacheWritebackRange': 0}
unknown = [f for f in functions if f not in COST]
if unknown: print('цена не задана (считаем 1 слово):', unknown)
shim += 'static unsigned long W, texImg, boneCalls;\n'
shim += '\n'.join('static void ' + s + '() { W += ' + str(COST.get(s, 1)) + ';' + (' texImg++;' if s == 'sceGuTexImage' else '') + (' boneCalls++;' if s == 'sceGuBoneMatrix' else '') + ' }' for s in functions) + '\n'

shim += 'static void sceGuDrawArray(int p, unsigned vt, unsigned n, const void *idx, const void *verts);\n'
shim += source + '\n'

shim += r"""
static unsigned lastVt = ~0u;
static void sceGuDrawArray(int p, unsigned vt, unsigned n, const void *idx, const void *verts) { W += (vt != lastVt ? 1 : 0) + (idx ? 2 : 0) + 3; lastVt = vt; (void)p; (void)n; (void)verts; }
int main(int argc, char **argv) {
  int worse = 0, below = 0;
  for (int i = 1; i < argc; i++) {
    SkinModel *m = skinLoad(argv[i]); if (!m) return 2;
    SkinPlayer p; skinInit(&p, m); ScePspFMatrix4 w; skinPlace(&w, 0, 0, 0, 0); unsigned nb = m->h->nBatches, bones = 0;
    for (unsigned b = 0; b < nb; b++) bones += m->b[b].nb;
    unsigned est[2], real[2], worst[2];
    for (int on = 0; on < 2; on++) {
      skinSetToon(on); skinToonFlush(); W = texImg = boneCalls = 0; lastVt = ~0u;
      skinDrawPal(m, p.pal, &w, -1);
      real[on] = W; int dt = (int)nb - (int)texImg, db = (int)bones - (int)boneCalls; worst[on] = W + (dt > 0 ? 9 * dt : 0) + (db > 0 ? 13 * db : 0); if (dt < 0 || db < 0) printf("  (привязок %lu при пачек %u, костей %lu из %u)\n", texImg, nb, boneCalls, bones);   // все привязки и все кости, без кэша
      est[on] = skinGeBytes(m) / 4;
      skinSetToon(0); skinToonFlush();
    }
    printf("%s batches=%u: выкл реально %u худшее %u оценка %u | вкл реально %u худшее %u оценка %u (запас %d)\n", argv[i], nb, real[0], worst[0], est[0], real[1], worst[1], est[1], (int)est[1] - (int)worst[1]);
    if (est[0] < worst[0]) worse++;      // базовая оценка ниже худшего (вне контура)
    if ((int)est[1] - (int)worst[1] < 32) below++;   // запас оценки над худшим реальным: не меньше 32 слов (128 Б): свет комнаты, фон, округление
    skinFree(m);
  }
  printf("запас < 32 слов (или оценка ниже худшего): без контура %d, с контуром %d\n", worse, below);
  return below ? 1 : 0;
}
"""
(out / 'host.c').write_text(shim)
models = [args.stage / x for x in ['homer.shr', 'l2/player.shr', 'l3/player.shr', 'l5/player.shr', 'l7/player.shr']]
assert all(p.is_file() for p in models), models
ok = True
for name, flags, expected in [('new', [], 0), ('old', ['-DSKIN_GE_TOON_OLD=1'], 1)]:
    subprocess.run(['cc', '-std=gnu11', '-O0', '-g', '-Wno-deprecated-non-prototype', '-Iviewer', *flags, str(out / 'host.c'), '-lm', '-o', str(out / name)], cwd=ROOT, check=True)
    r = subprocess.run([str(out / name), *map(str, models)], capture_output=True, text=True); (out / (name + '.txt')).write_text(r.stdout + r.stderr)
    print(f'{name}: код {r.returncode} (ждали {expected})'); print('  ' + r.stdout.strip().replace('\n', '\n  '))
    if r.returncode != expected: ok = False; print(r.stderr[-600:])
print('PASS: оценка skinGeBytes с контуром не ниже худшего реального с запасом >= 32 слов; прежняя (SKIN_GE_TOON_OLD=1) почти без запаса (4–5 слов)' if ok else 'FAIL')
sys.exit(0 if ok else 1)
