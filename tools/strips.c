// Полосы треугольников для кусков города (К4, ПЛАН_ОПТИМИЗАЦИЙ 17.10 п.1). Последний шаг сборки уровня (после tools/pvs, tools/wind, tools/shr_order.py):
// переписывает блобы клеток, заменяя список треугольников (флаг 16, без индексов) непрозрачных кусков города неиндексными полосами meshoptimizer
// (restart, каждая полоса — своя команда PRIM). Остальное в файле не меняется: клетки лежат в конце файла (порядок shr_order), таблицы кусков и клеток правятся на месте.
//   strips in.shr out.shr         (SHR_STRIPS=1 в tools/build_level.sh)
// Кусок-полоса: флаг F_STRIP = 1<<26, Rec.nv/ni/nf прежние (длины СПИСКОВ, чтобы все счётчики и проверки остались верными), Rec.off — новый.
// Блоб куска (16-выравнен): u32 nsvN, nsN, nsvF, nsF | вершины ближней версии (nsvN*vs) | длины полос u16[nsN] (до 4 Б) | вершины дальней (nsvF*vs) | длины u16[nsF] (до 4 Б).
// Берём куски: owner 0, флаг 16, без 1|2|4 (альфа, полупрозрачное, небо) и без F_ADDITIVE (1<<24), ni, nf <= 65535, ni % 3 == 0. Остальные копируются как есть.
// Сборка: tools/strips.sh (meshoptimizer 1.3, MIT).
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include "meshoptimizer.h"
typedef struct { float bb[6]; int32_t tex; uint32_t flags, nv, ni, owner; float ox, oy, oz, sc; uint32_t off, nf, cell, pad[2]; } Rec;
typedef struct { float bb[6]; uint32_t first, n, owner, off, size, pad; } CellRec;
_Static_assert(sizeof(Rec) == 80, "Rec"); _Static_assert(sizeof(CellRec) == 48, "CellRec");
#define F_STRIP (1u << 26)
#define F_ADD (1u << 24)
static uint64_t hb(const uint8_t *p, size_t n) { uint64_t h = 1469598103934665603ull; for (size_t i = 0; i < n; i++) { h ^= p[i]; h *= 1099511628211ull; } return h; }
static size_t weld(const uint8_t *b, size_t nv, size_t vs, unsigned *idx, unsigned **firstOut) {
  size_t cap = 1; while (cap < nv * 2) cap <<= 1; int32_t *tab = malloc(cap * 4); memset(tab, 0xff, cap * 4);
  unsigned *first = malloc(nv * 4 + 4); size_t nu = 0;
  for (size_t i = 0; i < nv; i++) {
    uint64_t h = hb(b + i * vs, vs); size_t s = h & (cap - 1);
    for (;;) { int32_t t = tab[s];
      if (t < 0) { tab[s] = (int32_t)nu; first[nu] = (unsigned)i; idx[i] = (unsigned)nu++; break; }
      if (!memcmp(b + (size_t)first[t] * vs, b + i * vs, vs)) { idx[i] = (unsigned)t; break; }
      s = (s + 1) & (cap - 1); }
  }
  free(tab); *firstOut = first; return nu;
}
// список вершин b[nv] -> полосы: вершины в out (nsv*vs), длины в lens; возвращает число полос
static size_t stripify(const uint8_t *b, size_t nv, size_t vs, uint8_t **out, size_t *nsv, uint16_t **lens) {
  unsigned *idx = malloc(nv * 4 + 4), *o1 = malloc(nv * 4 + 4), *st = malloc(meshopt_stripifyBound(nv) * 4 + 4), *first;
  size_t nu = weld(b, nv, vs, idx, &first);
  meshopt_optimizeVertexCacheStrip(o1, idx, nv, nu);
  size_t n = meshopt_stripify(st, o1, nv, nu, ~0u), ns = 0, tot = 0, run = 0;
  for (size_t k = 0; k < n; k++) { if (st[k] == ~0u) { if (run) { ns++; tot += run; } run = 0; } else run++; } if (run) { ns++; tot += run; }
  *out = malloc(tot * vs + 4); *lens = malloc(ns * 2 + 4); *nsv = tot; size_t o = 0, m = 0; run = 0;
  for (size_t k = 0; k < n; k++) {
    if (st[k] == ~0u) { if (run) (*lens)[m++] = (uint16_t)run; run = 0; }
    else { memcpy(*out + o * vs, b + (size_t)first[st[k]] * vs, vs); o++; run++; }
  }
  if (run) (*lens)[m++] = (uint16_t)run;
  free(idx); free(o1); free(st); free(first); return ns;
}
static int cmpU(const void *a, const void *b) { const uint32_t *x = a, *y = b; return x[1] < y[1] ? -1 : x[1] > y[1]; }   // (кусок, off)
int main(int argc, char **argv) {
  if (argc < 3) { fprintf(stderr, "strips in.shr out.shr\n"); return 1; }
  FILE *f = fopen(argv[1], "rb"); if (!f) { perror(argv[1]); return 1; }
  fseek(f, 0, SEEK_END); size_t fs = ftell(f); fseek(f, 0, SEEK_SET); uint8_t *file = malloc(fs); if (fread(file, 1, fs, f) != fs) return 1; fclose(f);
  if (memcmp(file, "SHR7", 4)) { fprintf(stderr, "не SHR7\n"); return 1; }
  uint32_t npc, ncell, tOff, cOff, pvsOff; memcpy(&npc, file + 8, 4); memcpy(&tOff, file + 76, 4); memcpy(&ncell, file + 80, 4); memcpy(&cOff, file + 84, 4); memcpy(&pvsOff, file + 88, 4);
  Rec *R = (Rec *)(file + tOff); CellRec *C = (CellRec *)(file + cOff);
  uint32_t cmin = 0xFFFFFFFFu, cmax = 0; uint32_t align = 4096;
  for (uint32_t i = 0; i < ncell; i++) { if (C[i].off < cmin) cmin = C[i].off; if (C[i].off + C[i].size > cmax) cmax = C[i].off + C[i].size; while (C[i].off % align) align >>= 1; }
  if (!pvsOff || cmin <= pvsOff) { fprintf(stderr, "клетки должны лежать после PVS1 (tools/shr_order.py)\n"); return 1; }
  if (cmax > fs) { fprintf(stderr, "блобы за концом файла\n"); return 1; }
  for (uint32_t i = 0; i < npc; i++) if (R[i].flags & F_STRIP) { fprintf(stderr, "уже в полосах\n"); return 1; }
  // порядок клеток в файле
  uint32_t *ord = malloc(ncell * 8); for (uint32_t i = 0; i < ncell; i++) { ord[2 * i] = i; ord[2 * i + 1] = C[i].off; } qsort(ord, ncell, 8, cmpU);
  uint8_t *outTail = malloc(fs + (fs >> 2) + 65536); size_t tl = 0; size_t base = cmin;
  long long nStripP = 0, nPieces = 0, vOld = 0, vNew = 0, nStr = 0;
  for (uint32_t oi = 0; oi < ncell; oi++) {
    uint32_t ci = ord[2 * oi]; CellRec *c = &C[ci]; const uint8_t *blob = file + c->off;
    while ((base + tl) % align) outTail[tl++] = 0;
    size_t cellStart = tl;
    uint32_t np = c->n; uint32_t *po = malloc(np * 8 + 8);
    for (uint32_t k = 0; k < np; k++) { po[2 * k] = c->first + k; po[2 * k + 1] = R[c->first + k].off; } qsort(po, np, 8, cmpU);
    size_t cur = 0;   // позиция в исходном блобе (для копии зазоров)
    for (uint32_t k = 0; k < np; k++) {
      Rec *r = &R[po[2 * k]]; size_t vs = (r->flags & 32) ? 12 : 16; nPieces++;
      size_t ext = (r->flags & 16) ? (size_t)r->nv * vs : (((size_t)r->nv * 16 + 15) & ~15ull) + (((size_t)r->ni * 2 + 15) & ~15ull) + (size_t)r->nf * 2;
      if (r->off < cur) { fprintf(stderr, "куски перекрываются в клетке %u\n", ci); return 1; }
      if (r->off + ext > c->size) { fprintf(stderr, "кусок %u выходит за клетку\n", po[2 * k]); return 1; }
      // зазор перед куском (выравнивание) копируем как есть
      memcpy(outTail + tl, blob + cur, r->off - cur); tl += r->off - cur;
      int ok = r->owner == 0 && (r->flags & 16) && !(r->flags & (1 | 2 | 4)) && !(r->flags & F_ADD) && r->ni >= 3 && r->ni % 3 == 0 && r->ni <= 65535 && r->nf <= 65535 && r->nf % 3 == 0 && r->nv == r->ni + r->nf;
      size_t newOff = tl - cellStart;
      if (!ok) { memcpy(outTail + tl, blob + r->off, ext); tl += ext; r->off = (uint32_t)newOff; cur = (size_t)po[2 * k + 1] + ext; continue; }
      const uint8_t *vb = blob + r->off; uint8_t *sN, *sF = NULL; uint16_t *lN, *lF = NULL; size_t nsvN, nsvF = 0, nsN, nsF = 0;
      nsN = stripify(vb, r->ni, vs, &sN, &nsvN, &lN);
      if (r->nf) nsF = stripify(vb + (size_t)r->ni * vs, r->nf, vs, &sF, &nsvF, &lF);
      if (getenv("STRIPS_RED")) { size_t po_ = vs == 12 ? 6 : 8; for (size_t q = 0; q < nsvN; q++) { int16_t *x = (int16_t *)(sN + q * vs + po_); int v = *x + 2500; *x = (int16_t)(v > 32767 ? 32767 : v); } }   // красный контроль гейта: сдвиг вершин (картинка обязана разойтись)
      uint32_t h[4] = {(uint32_t)nsvN, (uint32_t)nsN, (uint32_t)nsvF, (uint32_t)nsF}; size_t st = tl;
      memcpy(outTail + tl, h, 16); tl += 16;
      memcpy(outTail + tl, sN, nsvN * vs); tl += nsvN * vs; memcpy(outTail + tl, lN, nsN * 2); tl += nsN * 2; while (tl & 3) outTail[tl++] = 0;
      if (r->nf) { memcpy(outTail + tl, sF, nsvF * vs); tl += nsvF * vs; memcpy(outTail + tl, lF, nsF * 2); tl += nsF * 2; while (tl & 3) outTail[tl++] = 0; }
      while ((tl - st) & 15) outTail[tl++] = 0;
      vOld += (long long)(r->ni + r->nf); vNew += (long long)(nsvN + nsvF); nStr += (long long)(nsN + nsF); nStripP++;
      free(sN); free(lN); free(sF); free(lF);
      r->off = (uint32_t)newOff; r->flags |= F_STRIP; cur = (size_t)po[2 * k + 1] + ext;
      (void)st;
    }
    // хвост клетки после последнего куска (если есть) копируем
    if (cur < c->size) { memcpy(outTail + tl, blob + cur, c->size - cur); tl += c->size - cur; }
    c->off = (uint32_t)(base + cellStart); c->size = (uint32_t)(tl - cellStart); free(po);
  }
  size_t newSize = base + tl; uint8_t *outFile = malloc(newSize); memcpy(outFile, file, base);
  // таблицы Rec/Cell правились в file, а они лежат до base: копия выше уже содержит правки
  memcpy(outFile + base, outTail, tl);
  FILE *o = fopen(argv[2], "wb"); if (!o) { perror(argv[2]); return 1; } fwrite(outFile, 1, newSize, o); fclose(o);
  printf("strips: кусков в клетках %lld, в полосах %lld; вершин %lld -> %lld (%.1f%%), полос %lld; файл %zu -> %zu Б (%.2f МБ)\n", nPieces, nStripP, vOld, vNew, vOld ? 100.0 * vNew / vOld : 0.0, nStr, fs, newSize, ((double)fs - (double)newSize) / 1048576.0);
  return 0;
}
