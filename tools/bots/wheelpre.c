// wheelpre — гейт предотсева colWheelWallContacts (COL_WHEEL_PRE_OLD): новый и прежний расчёт обязаны совпасть побитно.
//   wheelpre LEVEL HOMER MSN [--n 400000] [--seed S]
// Точки: у случайных треугольников (над плоскостью и сбоку), у ящиков и цилиндров, радиусы 0.2..0.6; всего --n запросов.
// Совпадение: число контактов, p, n, depth, ref каждого. Красный контроль: сборка с -DCOL_WHEEL_PRE_BREAK=0.25f обязана дать расхождения.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "world.h"
#include "col.h"
static BotWorld W;
static unsigned long long rs = 88172645463325252ULL;
static float rnd(void) { rs ^= rs << 13; rs ^= rs >> 7; rs ^= rs << 17; return (float)((rs >> 11) & 0xffffff) / 16777216.f; }
int main(int argc, char **argv) {
  if (argc < 4 || bwData(argv[1], argv[2], argv[3])) { fprintf(stderr, "wheelpre: нет данных\n"); return 2; }
  long n = 400000;
  for (int i = 4; i < argc; i++) { if (!strcmp(argv[i], "--n") && i + 1 < argc) n = atol(argv[++i]); else if (!strcmp(argv[i], "--seed") && i + 1 < argc) rs ^= (unsigned long long)atoll(argv[++i]) * 0x9e3779b97f4a7c15ULL; }
  bwNew(&W); const ColWorld *w = bwCol(); long bad = 0, withContact = 0, total = 0, nodiff = 0;
  for (long q = 0; q < n; q++) {
    float p[3], r = .2f + .4f * rnd(); unsigned kind = (unsigned)(rnd() * 3.f);
    if (kind == 0 && w->ntri) { const ColTri *T = &w->tri[(unsigned)(rnd() * (float)w->ntri) % w->ntri]; float u = rnd(), v = rnd(); if (u + v > 1.f) { u = 1.f - u; v = 1.f - v; }
      float s = (rnd() - .35f) * 2.2f * r; for (int k = 0; k < 3; k++) p[k] = T->a[k] + (T->b[k] - T->a[k]) * u + (T->c[k] - T->a[k]) * v + T->n[k] * s; p[0] += (rnd() - .5f) * r; p[2] += (rnd() - .5f) * r; }
    else if (kind == 1 && w->nbox) { const ColBox *B = &w->box[(unsigned)(rnd() * (float)w->nbox) % w->nbox]; for (int k = 0; k < 3; k++) p[k] = B->c[k] + B->ax[k] * (rnd() * 2.f - 1.f) * (B->h[0] + r) + B->ay[k] * (rnd() * 2.f - 1.f) * (B->h[1] + r) + B->az[k] * (rnd() * 2.f - 1.f) * (B->h[2] + r); }
    else if (w->ncyl) { const ColCyl *C = &w->cyl[(unsigned)(rnd() * (float)w->ncyl) % w->ncyl]; for (int k = 0; k < 3; k++) p[k] = C->c[k] + (rnd() * 2.f - 1.f) * (C->r + r + C->halfLen); }
    else continue;
    ColSphereContact a[4], b[4]; memset(a, 0, sizeof a); memset(b, 0, sizeof b);
    colWheelPreOld = 1; int na = colWheelWallContacts(w, p, r, a, 4); colWheelPreOld = 0; int nb = colWheelWallContacts(w, p, r, b, 4);
    total++; withContact += na > 0; int same = na == nb;
    for (int i = 0; same && i < na; i++) same = !memcmp(a[i].p, b[i].p, 12) && !memcmp(a[i].n, b[i].n, 12) && a[i].depth == b[i].depth && a[i].ref == b[i].ref;
    if (!same) { if (bad < 5) printf("РАСХОЖДЕНИЕ запрос %ld: p %.3f %.3f %.3f r %.2f: прежних контактов %d, новых %d\n", q, p[0], p[1], p[2], r, na, nb); bad++; } else nodiff++;
  }
  printf("wheelpre: запросов %ld, с контактом %ld (%.1f%%), расхождений %ld -> %s\n", total, withContact, 100.0 * (double)withContact / (double)(total ? total : 1), bad, bad ? "FAIL" : "PASS");
  return bad ? 1 : 0;
}
