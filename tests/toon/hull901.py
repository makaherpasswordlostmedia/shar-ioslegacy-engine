#!/usr/bin/env python3
"""№901 «контур Cartoon»: гейт оболочки героев на настоящих моделях (хост-сборка настоящего viewer/skin.c).
Проверка 1 (непрерывность): вершины одной позиции (по всей модели, все пачки; 0,5 мм) после раздувания оболочки обязаны остаться вместе;
  щель между ними на силуэте — разрыв обводки (Гомер на бегу: ботинок, штаны/рубашка). Считаем группы с разлётом больше половины толщины ступени.
  Красный контроль: -DTOON_SMOOTH901_OLD=1 (раздувание по нормали самой вершины) обязан дать щели.
Проверка 2 (строчки образцов): тонкие кольца цвета сланца на моделях-образцах (Гомер: щиколотки, воротник) — toonSeams при первом вызове исправляет вершины, при втором — 0;
  красный контроль: -DTOON_SEAM901_OLD=1 — оболочка их не трогает (в хосте проверяем вызовом, число исправлений 0 = «как было»).
Проверка 3 (кольцо целиком, доводка после TEST54): вершины одной строчки (одна клетка образца) после toonSeams либо все исправлены, либо ни одна;
  вершины, оставшиеся тёмными среди исправленных, тянут текстурную координату через соседние клетки атласа (бледные точки у щиколотки Гомера на бегу).
  Красный контроль: -DTOON_SEAM_RING901_OLD=1 (по вершине, как TEST54) оставляет по 2 вершины на кольцо.
Запуск: tests/toon/hull901.py [--set DIR]  (DIR: homer.shr и chars/*.chr; по умолчанию набор тура SHARTEST15)"""
import argparse, subprocess, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
ap = argparse.ArgumentParser(); ap.add_argument('--set', type=Path, default=Path.home() / 'Downloads/shar-psp-integ/build/test52tour/PSP/GAME/SHARTEST15'); args = ap.parse_args()
out = ROOT / 'build/toon-hull901'; out.mkdir(parents=True, exist_ok=True)
source = (ROOT / 'viewer/skin.c').read_text().split('// ---------------------------------------------------------------- drawing', 1)[1]
source = source.replace('\n#ifndef SKIN_HOST', '', 1).rsplit('\n#endif', 1)[0]
constants = sorted(set(re.findall(r'\bGU_[A-Z0-9_]+\b', source)))
functions = sorted(set(re.findall(r'\b(sce(?:Gu|Kernel)\w+)\(', source)) - {'sceGuDrawArray', 'sceGuCheckList'})   # sceGuCheckList — число (счётчик слов SKWM), ниже
shim = '#define SKIN_HOST\n#include "skin.c"\n#undef SKIN_HOST\n#include <stdio.h>\n#include <stdlib.h>\nvoid skinToonFlush(void);\ntypedef struct { float x,y,z; } ScePspFVector3;\nstatic void *memalign(unsigned long a, unsigned long n) { return aligned_alloc(a, (n + a - 1) & ~(a - 1)); }\n'
shim += '\n'.join('#define ' + s + ' ' + str(i) for i, s in enumerate(constants)) + '\n'
shim += 'static unsigned sceGuCheckList(void) { return 0; }\n'
shim += '\n'.join('static void ' + s + '() {}' for s in functions) + '\n'
shim += 'static void sceGuDrawArray(int p, unsigned vt, unsigned n, const void *idx, const void *verts) { (void)p; (void)vt; (void)n; (void)idx; (void)verts; }\n'
shim += source + '\n'
shim = shim.replace('TOON_STORED(c)', 'toonStored(c)')
MAIN = r'''
typedef struct { int k[3]; float h[3], n[3]; } HV;
static int cmpk(const void *a, const void *b) { const HV *x = a, *y = b; for (int i = 0; i < 3; i++) if (x->k[i] != y->k[i]) return x->k[i] < y->k[i] ? -1 : 1; return 0; }
int main(int argc, char **argv) {
  unsigned totOpen = 0, totGroups = 0, totSeam = 0, totSeam2 = 0, totHalf = 0; int models = 0;
  for (int a = 1; a < argc; a++) {
    SkinModel *m = skinLoad(argv[a]); if (!m) { printf("%s: не читается\n", argv[a]); return 2; }
    skinSetToon(1); if (!skinToonEnabled()) { puts("FAIL toon not available"); return 3; }
    unsigned short **snap = calloc(m->h->nBatches, sizeof *snap); int *toff = calloc(m->h->nBatches, sizeof(int));   // клетки образца каждой вершины до правки
    for (unsigned bi = 0; bi < m->h->nBatches; bi++) { const SkinBatch *b = &m->b[bi]; int no, po; unsigned sv = toonStored(b);
      if ((b->flags & 3) || !vfmtOffsets(b->vtype, b->stride, &no, &po) || (b->vtype & 3) != 2) continue;
      static const int wsz[4] = {0, 1, 2, 4}; int wf = (int)((b->vtype >> 9) & 3), nw = wf ? (int)((b->vtype >> 14) & 7) + 1 : 0, to = (nw * wsz[wf] + 1) & ~1; if (to + 4 > (int)b->stride) continue;
      snap[bi] = malloc(sv * 4); toff[bi] = to; for (unsigned v = 0; v < sv; v++) memcpy(snap[bi] + v * 2, m->base + b->offVerts + v * b->stride + to, 4); }
    int fx = TOON_SEAM901_OLD ? 0 : toonSeams((SkinModel *)m), fx2 = TOON_SEAM901_OLD ? 0 : toonSeams((SkinModel *)m);   // №901: строчки — до оболочки, как в игре
    unsigned half = 0;   // кольца образца (вершины одной клетки цвета сланца, тоньше 3,5 см), исправленные не целиком
    for (unsigned bi = 0; bi < m->h->nBatches; bi++) { if (!snap[bi]) continue; const SkinBatch *b = &m->b[bi]; unsigned sv = toonStored(b); int cs[3];
      for (unsigned v = 0; v < sv; v++) { if (!toonSwatchRGB(m, b->tex, snap[bi][v * 2], snap[bi][v * 2 + 1], cs) || !toonSlate(cs)) continue;
        unsigned t = 0, c = 0, first = 1; for (unsigned w = 0; w < sv; w++) if (snap[bi][w * 2] == snap[bi][v * 2] && snap[bi][w * 2 + 1] == snap[bi][v * 2 + 1]) { if (w < v) first = 0; t++; unsigned short nw_[2]; memcpy(nw_, m->base + b->offVerts + w * b->stride + toff[bi], 4); if (nw_[0] != snap[bi][w * 2] || nw_[1] != snap[bi][w * 2 + 1]) c++; }
        if (first && c > 0 && c < t) half++; }
      free(snap[bi]); }
    free(snap); free(toff); totHalf += half;
    skinToonFlush(); unsigned char *h = toonHull(m, 1); if (!h) { printf("%s: оболочки нет\n", argv[a]); continue; }
    unsigned tot = 0; for (unsigned i = 0; i < m->h->nBatches; i++) tot += toonStored(&m->b[i]);
    HV *hv = malloc(sizeof(HV) * (tot ? tot : 1)); unsigned n = 0, ho = 0;
    for (unsigned i = 0; i < m->h->nBatches; i++) {
      const SkinBatch *b = &m->b[i]; int no, po; unsigned sv = toonStored(b);
      if (!(b->flags & 3) && vfmtOffsets(b->vtype, b->stride, &no, &po))
        for (unsigned v = 0; v < sv; v++) { float p[3], q[3]; memcpy(p, m->base + b->offVerts + v * b->stride + po, 12); memcpy(q, h + ho + v * b->stride + po, 12);
          const signed char *nn = (const signed char *)(m->base + b->offVerts + v * b->stride + no); if (!nn[0] && !nn[1] && !nn[2]) continue;
          float l_ = sqrtf((float)(nn[0] * nn[0] + nn[1] * nn[1] + nn[2] * nn[2])); for (int c = 0; c < 3; c++) { hv[n].k[c] = toonKey(p[c]); hv[n].h[c] = q[c]; hv[n].n[c] = nn[c] / l_; } n++; }
      ho += (sv * b->stride + 15) & ~15u;
    }
    qsort(hv, n, sizeof(HV), cmpk);
    unsigned groups = 0, open = 0; float worst = 0.f, lim = .5f * toonWk(1);
    for (unsigned i = 0; i < n; ) { unsigned j = i + 1; while (j < n && !cmpk(&hv[i], &hv[j])) j++;
      if (j - i > 1) { float mx = 0.f; int sheet = 0; for (unsigned p = i; p < j; p++) for (unsigned q = p + 1; q < j; q++) { if (hv[p].n[0] * hv[q].n[0] + hv[p].n[1] * hv[q].n[1] + hv[p].n[2] * hv[q].n[2] < -.5f) sheet = 1; }   // спинка к спинке (двойной лист: шип, ухо) — вытяжка в обе стороны по замыслу
        if (!sheet) { groups++; for (unsigned p = i; p < j; p++) for (unsigned q = p + 1; q < j; q++) { float dx = hv[p].h[0] - hv[q].h[0], dy = hv[p].h[1] - hv[q].h[1], dz = hv[p].h[2] - hv[q].h[2], d = sqrtf(dx * dx + dy * dy + dz * dz); if (d > mx) mx = d; }
        if (mx > lim) open++; if (mx > worst) worst = mx; } }
      i = j; }
    printf("%s: групп одной позиции %u, разорваны %u, худший разлёт %.1f мм (предел %.1f мм), строчек исправлено %d (повтор %d), половинных колец %u\n", argv[a], groups, open, worst * 1000.f, lim * 1000.f, fx, fx2, half);
    totOpen += open; totGroups += groups; totSeam += (unsigned)fx; totSeam2 += (unsigned)fx2; models++;
    free(hv); skinToonFlush(); skinFree(m);
  }
  printf("ИТОГ моделей %d, групп %u, разорваны %u, строчек исправлено %u, при повторе %u, половинных колец %u\n", models, totGroups, totOpen, totSeam, totSeam2, totHalf);
  return 0;
}
'''
(out / 'host.c').write_text(shim + MAIN)
models = [args.set / 'homer.shr'] + sorted((args.set / 'chars').glob('*.chr'))
assert models[0].is_file() and len(models) > 10, args.set
res = {}
for name, flags in [('new', []), ('old_smooth', ['-DTOON_SMOOTH901_OLD=1']), ('old_seam', ['-DTOON_SEAM901_OLD=1']), ('old_ring', ['-DTOON_SEAM_RING901_OLD=1'])]:
    subprocess.run(['cc', '-std=gnu11', '-O1', '-g', '-fsanitize=address', '-w', '-Iviewer', *flags, str(out / 'host.c'), '-lm', '-o', str(out / name)], cwd=ROOT, check=True)
    r = subprocess.run([str(out / name), *map(str, models)], capture_output=True, text=True); (out / (name + '.txt')).write_text(r.stdout + r.stderr)
    last = (r.stdout.strip().splitlines() or ['?'])[-1]; print(f'{name}: код {r.returncode} · {last}')
    m = re.search(r'разорваны (\d+), строчек исправлено (\d+), при повторе (\d+), половинных колец (\d+)', last); res[name] = tuple(map(int, m.groups())) if m else None
    if r.returncode: print(r.stderr[-800:])
ok = bool(res['new'] and res['old_smooth'] and res['old_seam'] and res['old_ring'])
ok = ok and res['new'][0] == 0 and res['old_smooth'][0] > 0          # непрерывность: новое 0 щелей, красное — есть
ok = ok and res['new'][1] > 0 and res['new'][2] == 0 and res['old_seam'][1] == 0   # строчки: исправляет и идемпотентно; красное не трогает
ok = ok and res['new'][3] == 0 and res['old_ring'][3] > 0   # кольца целиком; красное (по вершине) оставляет половинные
print('PASS: оболочка без разрывов у общих вершин, строчки образцов слиты; красные контроли красные' if ok else 'FAIL', res)
sys.exit(0 if ok else 1)
