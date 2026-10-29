// Стенд, 17.10: оценка (ничего не пишет в данные) двух идей из ОПТИМИЗАТОРЫ_РЕСЁРЧ_2026-10-17.md.
//  (1) К4: куски города без индексов (флаг 16) -> неиндексные полосы meshopt_stripify (отдельные полосы, restart): вершины и байты до/после.
//  (2) К6: PVS1 по клеткам 40 м вместо кусков: размер секции до/после + сколько лишних непрозрачных треугольников рисуется.
// Сборка: tools/strip_probe.sh (meshoptimizer 1.3, MIT, из ~/_backups/.../research-2026-09-27/sources/meshoptimizer/src). Запуск: strip_probe level.shr [таблица.tsv]
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include "meshoptimizer.h"

typedef struct { float bb[6]; int32_t tex; uint32_t flags, nv, ni, owner; float ox, oy, oz, sc; uint32_t off, nf, cell, pad[2]; } Rec;
typedef struct { float bb[6]; uint32_t first, n, owner, off, size, pad; } CellRec;
_Static_assert(sizeof(Rec) == 80, "Rec");
_Static_assert(sizeof(CellRec) == 48, "CellRec");

static uint64_t hb(const uint8_t *p, size_t n) { uint64_t h = 1469598103934665603ull; for (size_t i = 0; i < n; i++) { h ^= p[i]; h *= 1099511628211ull; } return h; }

// сварить вершины по байтам: возвращает число уникальных, idx[nv] -> уникальный номер
static size_t weld(const uint8_t *b, size_t nv, size_t vs, unsigned *idx, unsigned **firstOut) {
  size_t cap = 1; while (cap < nv * 2) cap <<= 1; int32_t *tab = malloc(cap * 4); memset(tab, 0xff, cap * 4);
  unsigned *first = malloc(nv * 4); size_t nu = 0;
  for (size_t i = 0; i < nv; i++) {
    uint64_t h = hb(b + i * vs, vs); size_t s = h & (cap - 1);
    for (;;) {
      int32_t t = tab[s];
      if (t < 0) { tab[s] = (int32_t)nu; first[nu] = (unsigned)i; idx[i] = (unsigned)nu++; break; }
      if (!memcmp(b + (size_t)first[t] * vs, b + i * vs, vs)) { idx[i] = (unsigned)t; break; }
      s = (s + 1) & (cap - 1);
    }
  }
  free(tab); if (firstOut) *firstOut = first; else free(first); return nu;
}


static void proc(const uint8_t *b, size_t nv, size_t vs, long long *tot, long long *ns, long long *sew, long long *uniq) {
  if (!nv) return;
  unsigned *idx = malloc(nv * 4), *o1 = malloc(nv * 4), *st = malloc(meshopt_stripifyBound(nv) * 4);
  size_t nu = weld(b, nv, vs, idx, NULL); *uniq += nu;
  meshopt_optimizeVertexCacheStrip(o1, idx, nv, nu);
  size_t n = meshopt_stripify(st, o1, nv, nu, ~0u), run = 0;
  for (size_t k = 0; k < n; k++) { if (st[k] == ~0u) { if (run) { (*ns)++; *tot += run; } run = 0; } else run++; }
  if (run) { (*ns)++; *tot += run; }
  *sew += meshopt_stripify(st, o1, nv, nu, 0);
  free(idx); free(o1); free(st);
}

// ---- тестовый файл для тура на железе (stripbench.bin): те же куски в трёх видах (список / отдельные полосы / одна полоса с вырожденными) ----
// 'SBN1', u32 nrec | запись: u32 piece, u32 flags, i32 tex, u32 vs, f32 ox,oy,oz,sc, u32 nList, u32 nStripV, u32 nStrips, u32 nSew, f32 bb[6]
//   | список (nList*vs Б) | вершины полос (nStripV*vs Б) | длины полос u16[nStrips] (выровнять 4) | одна полоса (nSew*vs Б) | выравнивание 16
static void emitPiece(FILE *o, uint32_t pi, const Rec *r, const uint8_t *b) {
  size_t vs = (r->flags & 32) ? 12 : 16, nv = r->ni;
  unsigned *idx = malloc(nv * 4), *o1 = malloc(nv * 4), *st = malloc(meshopt_stripifyBound(nv) * 4), *first = NULL;
  size_t nu = weld(b, nv, vs, idx, &first);
  meshopt_optimizeVertexCacheStrip(o1, idx, nv, nu);
  size_t n = meshopt_stripify(st, o1, nv, nu, ~0u); size_t tot = 0, ns = 0, run = 0;
  for (size_t k = 0; k < n; k++) { if (st[k] == ~0u) { if (run) { ns++; tot += run; } run = 0; } else run++; } if (run) { ns++; tot += run; }
  unsigned *sw = malloc(meshopt_stripifyBound(nv) * 4); size_t nsw = meshopt_stripify(sw, o1, nv, nu, 0);
  uint32_t h[8 + 4 + 6] = {pi, r->flags, (uint32_t)r->tex, (uint32_t)vs}; float ff[4] = {r->ox, r->oy, r->oz, r->sc}; memcpy(h + 4, ff, 16);
  h[8] = (uint32_t)nv; h[9] = (uint32_t)tot; h[10] = (uint32_t)ns; h[11] = (uint32_t)nsw; memcpy(h + 12, r->bb, 24);
  fwrite(h, 4, 18, o); fwrite(b, vs, nv, o);
  for (size_t k = 0; k < n; k++) if (st[k] != ~0u) fwrite(b + (size_t)first[st[k]] * vs, vs, 1, o);
  { uint16_t *ln = malloc(ns * 2 + 4); size_t m = 0; run = 0; for (size_t k = 0; k < n; k++) { if (st[k] == ~0u) { if (run) ln[m++] = (uint16_t)run; run = 0; } else run++; } if (run) ln[m++] = (uint16_t)run;
    fwrite(ln, 2, m, o); if (m & 1) { uint16_t z = 0; fwrite(&z, 2, 1, o); } free(ln); }
  for (size_t k = 0; k < nsw; k++) fwrite(b + (size_t)first[sw[k]] * vs, vs, 1, o);
  { long pos = ftell(o); while (pos & 15) { fputc(0, o); pos++; } }
  free(idx); free(o1); free(st); free(sw); free(first);
}

int main(int argc, char **argv) {
  const char *emitPath = NULL; int emitK = 4, na = 0; char *av[8];
  for (int i = 1; i < argc && na < 8; i++) { if (!strcmp(argv[i], "--emit") && i + 1 < argc) emitPath = argv[++i]; else if (!strcmp(argv[i], "--cells") && i + 1 < argc) emitK = atoi(argv[++i]); else av[na++] = argv[i]; }
  if (na < 1) { fprintf(stderr, "strip_probe level.shr [out.tsv] [--emit stripbench.bin --cells K]\n"); return 1; }
  argc = na + 1; argv = av - 1;
  FILE *f = fopen(argv[1], "rb"); if (!f) { perror(argv[1]); return 1; }
  fseek(f, 0, SEEK_END); size_t fs = ftell(f); fseek(f, 0, SEEK_SET);
  uint8_t *file = malloc(fs); if (fread(file, 1, fs, f) != fs) return 1; fclose(f);
  if (memcmp(file, "SHR7", 4)) { fprintf(stderr, "не SHR7\n"); return 1; }
  uint32_t npc, ncell, tOff, cOff, pvsOff; memcpy(&npc, file + 8, 4); memcpy(&tOff, file + 76, 4); memcpy(&ncell, file + 80, 4); memcpy(&cOff, file + 84, 4); memcpy(&pvsOff, file + 88, 4);
  const Rec *R = (const Rec *)(file + tOff); const CellRec *C = (const CellRec *)(file + cOff);
  printf("файл %zu Б, кусков %u, клеток %u, PVS1 @%u\n", fs, npc, ncell, pvsOff);

  if (emitPath) {   // K самых плотных клеток (по непрозрачным треугольникам ближней версии), все их непрозрачные куски
    long long *ct = calloc(ncell + 1, 8); for (uint32_t i = 0; i < npc; i++) if (R[i].owner == 0 && !(R[i].flags & 3) && (R[i].flags & 16)) ct[R[i].cell] += R[i].ni / 3;
    FILE *o = fopen(emitPath, "wb"); uint32_t nrec = 0; fwrite("SBN1", 1, 4, o); fwrite(&nrec, 4, 1, o); long long totTri = 0; char *used = calloc(ncell + 1, 1);
    for (int kk = 0; kk < emitK; kk++) { uint32_t best = 0; long long bv = -1; for (uint32_t c = 0; c < ncell; c++) if (!used[c] && ct[c] > bv) { bv = ct[c]; best = c; } used[best] = 1;
      for (uint32_t i = 0; i < npc; i++) { const Rec *r = &R[i]; if (r->owner == 0 && r->cell == best && !(r->flags & 3) && (r->flags & 16) && r->ni) { emitPiece(o, i, r, file + C[r->cell].off + r->off); nrec++; totTri += r->ni / 3; } }
      printf("  клетка %u: %lld непрозрачных треугольников\n", best, bv); }
    fseek(o, 4, SEEK_SET); fwrite(&nrec, 4, 1, o); fclose(o); printf("emit: %u кусков, %lld треугольников -> %s\n", nrec, totTri, emitPath);
  }
  // ---------- (1) полосы ----------
  long long nc = 0, nnoidx = 0, nidx = 0;
  long long tri = 0, vOld = 0, vStrip = 0, vSew = 0, strips = 0, bOld = 0, bNew = 0, bOldNoidx = 0, bNewNoidx = 0, uniq = 0, farv = 0;
  long long ftri = 0, fOld = 0, fStrip = 0, fSew = 0, fStrips = 0, bOldF = 0, bNewF = 0; long long perTexVOld[1] = {0};
  (void)perTexVOld;
  for (uint32_t i = 0; i < npc; i++) {
    const Rec *r = &R[i]; if (r->owner != 0) continue; nc++;
    size_t vs = (r->flags & 32) ? 12 : 16;
    if (!(r->flags & 16)) { nidx++; continue; }
    nnoidx++;
    const uint8_t *b = file + C[r->cell].off + r->off;
    farv += r->nf;
    long long t1 = 0, s1 = 0, w1 = 0, u1 = 0;
    proc(b, r->ni, vs, &t1, &s1, &w1, &u1);
    tri += r->ni / 3; vOld += r->ni; vStrip += t1; vSew += w1; strips += s1; uniq += u1; bOldNoidx += (long long)r->ni * vs; bNewNoidx += t1 * vs;
    long long t2 = 0, s2 = 0, w2 = 0, u2 = 0;
    proc(b + (size_t)r->ni * vs, r->nf, vs, &t2, &s2, &w2, &u2);
    ftri += r->nf / 3; fOld += r->nf; fStrip += t2; fSew += w2; fStrips += s2; bOldF += (long long)r->nf * vs; bNewF += t2 * vs;
  }
  printf("\n(1) куски города: %lld, без индексов (флаг 16): %lld, с индексами: %lld; вершин дальних версий (nf): %lld\n", nc, nnoidx, nidx, farv);
  printf("    треугольников %lld; вершин: список %lld | отдельные полосы %lld (%.1f%%) | одна полоса с вырожденными %lld (%.1f%%); полос %lld, вершин на полосу %.1f, вершин на треугольник %.2f\n",
    tri, vOld, vStrip, 100.0 * vStrip / vOld, vSew, 100.0 * vSew / vOld, strips, (double)vStrip / strips, (double)vStrip / tri);
  printf("    байт вершин: было %.2f МБ | стало %.2f МБ | выгода %.2f МБ; (уникальных вершин по байтам %lld, %.1f%% от списка)\n",
    bOldNoidx / 1048576.0, bNewNoidx / 1048576.0, (bOldNoidx - bNewNoidx) / 1048576.0, uniq, 100.0 * uniq / vOld);
  printf("    дальние версии (nf): треугольников %lld; вершин: список %lld | отдельные полосы %lld (%.1f%%) | одна полоса %lld (%.1f%%); полос %lld; байт: было %.2f МБ | стало %.2f МБ | выгода %.2f МБ\n",
    ftri, fOld, fStrip, 100.0 * fStrip / (fOld ? fOld : 1), fSew, 100.0 * fSew / (fOld ? fOld : 1), fStrips, bOldF / 1048576.0, bNewF / 1048576.0, (bOldF - bNewF) / 1048576.0);
  printf("    ВСЕГО вершины города: было %.2f МБ | стало %.2f МБ | выгода %.2f МБ; команд PRIM: %lld (по 4 Б в листах GE: +%.2f МБ)\n",
    (bOldNoidx + bOldF) / 1048576.0, (bNewNoidx + bNewF) / 1048576.0, (bOldNoidx + bOldF - bNewNoidx - bNewF) / 1048576.0, strips + fStrips, (strips + fStrips) * 4 / 1048576.0);
  { long long cellBytes = 0; for (uint32_t i = 0; i < ncell; i++) if (C[i].owner == 0) cellBytes += C[i].size; printf("    блобы клеток города сейчас %.2f МБ (в них вершины и выравнивание)\n", cellBytes / 1048576.0); }

  // ---------- (2) PVS по клеткам ----------
  if (pvsOff && !memcmp(file + pvsOff, "PVS1", 4)) {
    float ox, oz, cs; uint32_t W, H, pool, pad; memcpy(&ox, file + pvsOff + 4, 4); memcpy(&oz, file + pvsOff + 8, 4); memcpy(&cs, file + pvsOff + 12, 4);
    memcpy(&W, file + pvsOff + 16, 4); memcpy(&H, file + pvsOff + 20, 4); memcpy(&pool, file + pvsOff + 24, 4); memcpy(&pad, file + pvsOff + 28, 4);
    const uint32_t *ent = (const uint32_t *)(file + pvsOff + 32); const uint16_t *pl = (const uint16_t *)(file + pvsOff + 32 + (size_t)W * H * 8);
    size_t secBytes = 32 + (size_t)W * H * 8 + (size_t)pool * 2;
    printf("\n(2) PVS1: сетка %ux%u шаг %.1f м, пул %u u16, секция %.1f КБ (в файле до следующей секции может быть выравнивание)\n", W, H, cs, pool, secBytes / 1024.0);
    // кусок -> клетка города; только непрозрачные идут в список клеток, полупрозрачные (flags&3) остаются списком кусков
    uint16_t *list = malloc(65536 * 2); uint8_t *seen = calloc(ncell + 1, 1);
    long long nEnt = 0, oldN = 0, newCellN = 0, newTrN = 0, oldTr = 0, newTr = 0, oldOpaqueN = 0, noData = 0, transN = 0;
    // дедупликация одинаковых списков (как в pvs.c): считаем пул «после» с и без неё
    typedef struct { uint64_t h; uint32_t n; } HE; HE *he = malloc(sizeof(HE) * (size_t)W * H); size_t nhe = 0; long long newPoolDedup = 0, oldPoolDedup = 0;
    HE *ho = malloc(sizeof(HE) * (size_t)W * H); size_t nho = 0;
    long long *cellTri = calloc(ncell + 1, 8);
    for (uint32_t i = 0; i < npc; i++) if (R[i].owner == 0 && (R[i].flags & 3) == 0) cellTri[R[i].cell] += R[i].ni / 3;
    for (size_t e = 0; e < (size_t)W * H; e++) {
      uint32_t st = ent[e * 2], cnt = ent[e * 2 + 1]; if (cnt == 0xFFFFFFFFu) { noData++; continue; }
      nEnt++; oldN += cnt;
      uint16_t nl[4096]; size_t nn = 0, nt = 0; uint16_t tl[4096]; long long otr = 0;
      for (uint32_t k = 0; k < cnt; k++) {
        uint16_t pi = pl[st + k]; const Rec *r = &R[pi]; if (r->owner != 0) continue;
        if ((r->flags & 3) == 0) { oldOpaqueN++; otr += r->ni / 3; if (!seen[r->cell]) { seen[r->cell] = 1; nl[nn++] = (uint16_t)r->cell; } }
        else { tl[nt++] = pi; transN++; }
      }
      long long ntr = 0; for (size_t k = 0; k < nn; k++) { ntr += cellTri[nl[k]]; seen[nl[k]] = 0; }
      oldTr += otr; newTr += ntr; newCellN += nn;
      // хэши списков
      uint64_t h1 = 1469598103934665603ull, h2 = 1469598103934665603ull;
      for (uint32_t k = 0; k < cnt; k++) { h1 ^= pl[st + k]; h1 *= 1099511628211ull; }
      // после: список клеток (отсортируем) + список прозрачных
      for (size_t a = 1; a < nn; a++) { uint16_t v = nl[a]; size_t b2 = a; while (b2 && nl[b2 - 1] > v) { nl[b2] = nl[b2 - 1]; b2--; } nl[b2] = v; }
      for (size_t k = 0; k < nn; k++) { h2 ^= nl[k]; h2 *= 1099511628211ull; } for (size_t k = 0; k < nt; k++) { h2 ^= tl[k] + 65536u; h2 *= 1099511628211ull; }
      int dup = 0; for (size_t k = 0; k < nho; k++) if (ho[k].h == h1 && ho[k].n == cnt) { dup = 1; break; } if (!dup) { ho[nho].h = h1; ho[nho++].n = cnt; oldPoolDedup += cnt; }
      uint32_t nnew = (uint32_t)(nn + nt);
      dup = 0; for (size_t k = 0; k < nhe; k++) if (he[k].h == h2 && he[k].n == nnew) { dup = 1; break; } if (!dup) { he[nhe].h = h2; he[nhe++].n = nnew; newPoolDedup += nnew; }
      (void)transN; (void)nEnt;
    }
    long long newPool = newCellN + transN;
    printf("    записей с данными %lld (без данных %lld); в среднем в записи: кусков было %.1f (непрозрачных %.1f, прозрачных %.1f) -> клеток %.1f + прозрачных %.1f\n",
      nEnt, noData, (double)oldN / nEnt, (double)oldOpaqueN / nEnt, (double)transN / nEnt, (double)newCellN / nEnt, (double)transN / nEnt);
    printf("    пул (u16): было %u | стало %lld (%.1f%%); таблица записей 8 Б * %u без изменений (%.1f КБ; при u16 start + u8 count можно меньше)\n", pool, newPool, 100.0 * newPool / pool, W * H, W * H * 8 / 1024.0);
    printf("    с общими одинаковыми списками (оценка, точное совпадение): пул было %lld | стало %lld\n", oldPoolDedup, newPoolDedup);
    printf("    секция: было %.1f КБ | стало ~%.1f КБ | выгода ~%.2f МБ (без дедупликации в обоих; пул u16)\n", secBytes / 1024.0, (32 + (size_t)W * H * 8 + (size_t)newPool * 2) / 1024.0, ((double)pool - newPool) * 2 / 1048576.0);
    printf("    цена: непрозрачных треугольников в записи: было %.0f | станет %.0f (%.2fx)\n", (double)oldTr / nEnt, (double)newTr / nEnt, (double)newTr / oldTr);
    if (argc > 2) { FILE *o = fopen(argv[2], "w"); fprintf(o, "показатель\tбыло\tстало\n"); fprintf(o, "вершин город без индексов (список -> отдельные полосы)\t%lld\t%lld\n", vOld, vStrip); fprintf(o, "то же, одна полоса с вырожденными\t%lld\t%lld\n", vOld, vSew); fprintf(o, "байт вершин МБ\t%.2f\t%.2f\n", bOldNoidx / 1048576.0, bNewNoidx / 1048576.0); fprintf(o, "полос\t0\t%lld\n", strips); fprintf(o, "PVS1 пул u16\t%u\t%lld\n", pool, newPool); fprintf(o, "PVS1 секция КБ\t%.1f\t%.1f\n", secBytes / 1024.0, (32 + (size_t)W * H * 8 + (size_t)newPool * 2) / 1024.0); fprintf(o, "непрозрачных треугольников на запись PVS\t%.0f\t%.0f\n", (double)oldTr / nEnt, (double)newTr / nEnt); fclose(o); }
  }
  return 0;
}
