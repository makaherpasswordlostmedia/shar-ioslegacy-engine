// Сравнение COL1 двух level.shr (отгруженного и перевыпущенного с правилом кустов №587): что стало мягким, что изменилось сверх этого.
//   col_diff OLD.shr NEW.shr [fol_report.tsv]    код возврата: 0 — различия только «твёрдый объём -> листва (pad 0 -> 1)»; 1 — есть другие
// Объёмы сопоставляются по центру и размерам (индексы могут сдвигаться: невидимые куски режутся уже после правила). Заборы (ColSeg) и земля (ColTri) обязаны совпасть побайтно.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "col.h"
static ColWorld A, B;
static unsigned char *load(const char *path, ColWorld *w) {
  FILE *f = fopen(path, "rb"); if (!f) return NULL; fseek(f, 0, SEEK_END); long size = ftell(f); rewind(f);
  unsigned char *d = malloc((size + 15) & ~15); if (fread(d, 1, size, f) != (size_t)size) return NULL; fclose(f);
  unsigned co = *(unsigned *)(d + 92), ce = *(unsigned *)(d + 96), pv = *(unsigned *)(d + 88);
  if (pv > co && pv < ce) ce = pv;
  if (colInit(w, d + co, ce - co)) return NULL; return d;
}
static int key_eq_box(const ColBox *a, const ColBox *b) { return !memcmp(a->c, b->c, 12) && !memcmp(a->h, b->h, 12) && !memcmp(a->ax, b->ax, 36); }
static int key_eq_cyl(const ColCyl *a, const ColCyl *b) { return !memcmp(a->c, b->c, 12) && a->r == b->r && a->halfLen == b->halfLen && !memcmp(a->axis, b->axis, 12); }
int main(int argc, char **argv) {
  if (argc < 3) return 2;
  if (!load(argv[1], &A) || !load(argv[2], &B)) { printf("не загрузилось\n"); return 2; }
  int other = 0;
  printf("земля: %u/%u треугольников, заборы: %u/%u звеньев, ящики %u/%u, капсулы %u/%u\n", A.ntri, B.ntri, A.nseg, B.nseg, A.nbox, B.nbox, A.ncyl, B.ncyl);
  if (A.ntri != B.ntri || memcmp(A.tri, B.tri, (size_t)A.ntri * sizeof(ColTri))) { printf("ОТЛИЧИЕ: земля\n"); other++; }
  if (A.nseg != B.nseg || memcmp(A.seg, B.seg, (size_t)A.nseg * sizeof(ColSeg))) { printf("ОТЛИЧИЕ: заборы (ColSeg)\n"); other++; }
  int softB = 0, softC = 0, hardToSoftB = 0, hardToSoftC = 0, lost = 0, gainPhantom = 0, unmatched = 0;
  // ящики: сопоставление по ключу, в окрестности того же индекса и общим перебором
  for (unsigned i = 0; i < B.nbox; i++) {
    const ColBox *nb = &B.box[i]; const ColBox *ob = NULL;
    if (i < A.nbox && key_eq_box(&A.box[i], nb)) ob = &A.box[i];
    else for (unsigned j = 0; j < A.nbox; j++) if (key_eq_box(&A.box[j], nb)) { ob = &A.box[j]; break; }
    if (!ob) { unmatched++; if (nb->pad == 1.f) softB++; continue; }
    if (ob->pad == nb->pad) continue;
    if (ob->pad == 0.f && nb->pad == 1.f) { hardToSoftB++; if (argc > 3) printf("  ящик %u c(%.1f %.1f %.1f) h(%.1f %.1f %.1f): твёрдый -> листва\n", i, nb->c[0], nb->c[1], nb->c[2], nb->h[0], nb->h[1], nb->h[2]); }
    else if (ob->pad == 2.f && nb->pad == 1.f) gainPhantom++;   // был невидимым (насквозь), стал листвой: тоже проезжаем
    else { printf("ОТЛИЧИЕ ящик %u: pad %.0f -> %.0f\n", i, ob->pad, nb->pad); other++; }
  }
  for (unsigned i = 0; i < B.ncyl; i++) {
    const ColCyl *nc = &B.cyl[i]; const ColCyl *oc = NULL;
    if (i < A.ncyl && key_eq_cyl(&A.cyl[i], nc)) oc = &A.cyl[i];
    else for (unsigned j = 0; j < A.ncyl; j++) if (key_eq_cyl(&A.cyl[j], nc)) { oc = &A.cyl[j]; break; }
    if (!oc) { unmatched++; if (nc->pad[0] == 1.f) softC++; continue; }
    if (oc->pad[0] == nc->pad[0]) continue;
    if (oc->pad[0] == 0.f && nc->pad[0] == 1.f) { hardToSoftC++; if (argc > 3) printf("  капсула %u c(%.1f %.1f %.1f) r %.1f L %.1f: твёрдая -> листва\n", i, nc->c[0], nc->c[1], nc->c[2], nc->r, 2 * nc->halfLen); }
    else if (oc->pad[0] == 2.f && nc->pad[0] == 1.f) gainPhantom++;
    else { printf("ОТЛИЧИЕ капсула %u: pad %.0f -> %.0f\n", i, oc->pad[0], nc->pad[0]); other++; }
  }
  (void)lost; (void)softB; (void)softC;
  printf("ИТОГ: стало листвой %d ящиков + %d капсул (из невидимых %d); не нашлось пары %d; прочих отличий %d\n", hardToSoftB, hardToSoftC, gainPhantom, unmatched, other);
  return other || unmatched ? 1 : 0;
}
