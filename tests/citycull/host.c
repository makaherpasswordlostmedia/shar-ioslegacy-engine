// Хост-сверка отсечения города на ME (viewer/citycull.h ccRun, №653): на случайных позах камеры по PVS каждого уровня результат
// «ME + метки, досчитанные главным» обязан совпасть БИТ В БИТ (nd, tk, tp, tf, tcl, regCut) с прежним циклом cullCity (ветка PVS + иерархия
// клеток + цикл по клеткам для кусков дальше pvsRange), записанным здесь буквально. Состояние клеток случайное (часть не загружена),
// запас cullMg 0 и 1,1 м, наборы регионов случайные.
//   cc -O2 -std=c99 -ffp-contract=off -I viewer tests/citycull/host.c -lm -o build/citycull_host && build/citycull_host level.shr [level2.shr ...]
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <stdint.h>
#include "citycull.h"
typedef struct { float bb[6]; int tex, flags, nv, ni, owner; float ox, oy, oz, sc; unsigned off, nf, cell, pad[2]; } Rec;
typedef struct { float bb[6]; unsigned first, n, owner, off, size, pad; int state; } HCell;
static unsigned rnd_s = 777; static float rnd(void) { rnd_s = rnd_s * 1664525u + 1013904223u; return (rnd_s >> 8) / 16777216.f; }
static void planes(float pl[4][3], float fx, float fy, float fz) {
  float rx = -fz, rz = fx, rl = sqrtf(rx * rx + rz * rz); if (rl < 1e-4f) { rx = 1; rz = 0; rl = 1; }
  rx /= rl; rz /= rl; float ux = -rz * fy, uy = rz * fx - rx * fz, uz = rx * fy;
  float tv = tanf(62.f * .5f * 3.14159265f / 180.f) * 1.03f, th = tv * (16.f / 9.f);
  float n[4][3] = {{fx * th - rx, fy * th, fz * th - rz}, {fx * th + rx, fy * th, fz * th + rz}, {fx * tv - ux, fy * tv - uy, fz * tv - uz}, {fx * tv + ux, fy * tv + uy, fz * tv + uz}};
  memcpy(pl, n, sizeof n);
}
// ---- «главный»: переменные и функции как в main_render.h ----
static float pl[4][3], eyeX, eyeY, eyeZ, drawDist, cullMg; static unsigned regEye, regCut; static int nd;
static unsigned short tk[CC_MAXDRAW], tp[CC_MAXDRAW], tcl[CC_MAXDRAW]; static unsigned char tf[CC_MAXDRAW];
static const Rec *pc; static unsigned npc, ncell; static HCell *cl; static CcRec *cr; static unsigned short *crc;
static float boxD2(const float *b) {
  float dx = b[0] - cullMg - eyeX > 0 ? b[0] - cullMg - eyeX : (eyeX - b[3] - cullMg > 0 ? eyeX - b[3] - cullMg : 0);
  float dy = b[1] - cullMg - eyeY > 0 ? b[1] - cullMg - eyeY : (eyeY - b[4] - cullMg > 0 ? eyeY - b[4] - cullMg : 0);
  float dz = b[2] - cullMg - eyeZ > 0 ? b[2] - cullMg - eyeZ : (eyeZ - b[5] - cullMg > 0 ? eyeZ - b[5] - cullMg : 0);
  return dx * dx + dy * dy + dz * dz;
}
static int visBox(const float *b, float ox, float oy, float oz) {
  for (int i = 0; i < 4; i++) {
    float px = (pl[i][0] > 0 ? b[3] + cullMg : b[0] - cullMg) + ox - eyeX, py = (pl[i][1] > 0 ? b[4] + cullMg : b[1] - cullMg) + oy - eyeY, pz = (pl[i][2] > 0 ? b[5] + cullMg : b[2] - cullMg) + oz - eyeZ;
    if (px * pl[i][0] + py * pl[i][1] + pz * pl[i][2] < 0) return 0;
  }
  return 1;
}
#define LOD 50.f
static int optFar = 1;
static void cullPiece(unsigned k) {   // как main_render.h cullPiece; ветка по Piece — то же решение по записи уровня (флаги FARP не моделируем: оба пути одинаковы)
  const Rec *d = &pc[k];
  if (!cr[k].pad && cr[k].cell != 0xFFFFu) {
    const CcRec *h = &cr[k]; unsigned rg = h->rg;
    if (rg && rg <= 16 && !((regEye >> (rg - 1)) & 1u)) { regCut++; return; }
    float d2 = boxD2(h->bb); if (d2 > drawDist * drawDist || !visBox(h->bb, 0, 0, 0)) return;
    int far_ = optFar ? d2 > LOD * LOD : 0; if (nd >= CC_MAXDRAW) return;
    tk[nd] = h->tk; tp[nd] = k; tf[nd] = far_; tcl[nd] = h->tcl; nd++; return;
  }
  { unsigned rg = d->pad[0]; if (rg && rg <= 16 && !((regEye >> (rg - 1)) & 1u)) { regCut++; return; } }
  float d2 = boxD2(d->bb); if (d2 > drawDist * drawDist || !visBox(d->bb, 0, 0, 0)) return;
  int far = d2 > LOD * LOD; if (!optFar) far = 0; if (nd >= CC_MAXDRAW) return;
  int t = d->tex < 0 || d->tex > 510 ? 511 : d->tex;
  tk[nd] = ((d->flags & 3) << 9) | t; tp[nd] = k; tf[nd] = far;
  tcl[nd] = ((d->flags & 2) && !(d->flags & 4)) || d->cell >= 0xFFFFu ? 0xFFFFu : (unsigned short)d->cell; nd++;
}
static int cellClassC(unsigned ci) {
  float bi[6]; memcpy(bi, cl[ci].bb, sizeof bi); if (cullMg > 0.f) { bi[0] -= cullMg; bi[1] -= cullMg; bi[2] -= cullMg; bi[3] += cullMg; bi[4] += cullMg; bi[5] += cullMg; }
  return cl[ci].state == 2 ? chClassify(bi, pl, eyeX, eyeY, eyeZ, drawDist) : 0;
}
static void cullPieceIn(unsigned k, int inside) {
  const CcRec *h = &cr[k]; unsigned rg = h->rg;
  if (rg && rg <= 16 && !((regEye >> (rg - 1)) & 1u)) { regCut++; return; }
  float d2 = boxD2(h->bb);
  if (d2 > drawDist * drawDist || (!inside && !visBox(h->bb, 0, 0, 0))) return;
  int far_ = optFar ? d2 > LOD * LOD : 0; if (nd >= CC_MAXDRAW) return;
  tk[nd] = h->tk; tp[nd] = k; tf[nd] = far_; tcl[nd] = h->tcl; nd++;
}
static void refRun(const unsigned short *pl_, int n, float pr2, float pvsRange) {   // cullCity: ветка PVS + иерархия, затем цикл по клеткам (буквально)
  nd = 0; regCut = 0;
  for (int i = 0; i < n; i++) { unsigned k = pl_[i]; if (k >= npc) continue; unsigned ci = crc[k];
    if (ci != 0xFFFFu && ci < ncell) { int c = cellClassC(ci); if (!c) continue;
      if (!cr[k].pad && boxD2(cr[k].bb) <= pr2) cullPieceIn(k, c == 2);
      else if (cr[k].pad && boxD2(cr[k].bb) <= pr2) cullPiece(k); }
    else if (cr[k].cell == 0xFFFFu && cl[pc[k].cell].state == 2 && boxD2(pc[k].bb) <= pr2) cullPiece(k); }
  if (drawDist > pvsRange)
    for (unsigned i = 0; i < ncell; i++) { HCell *c = &cl[i]; if (c->owner || c->state != 2) continue;
      if (boxD2(c->bb) > drawDist * drawDist || !visBox(c->bb, 0, 0, 0)) continue;
      for (unsigned k = c->first; k < c->first + c->n; k++) if (boxD2(pc[k].bb) > pr2) cullPiece(k); }
}
static CcJob J; static CcCell cc_[CC_MAXCELL]; static unsigned char st_[CC_MAXCELL];
static int meRun(const unsigned short *pl_, int n, float pr2, float pvsRange) {   // ccBegin + ccRun + слияние cullCityEnd
  for (unsigned i = 0; i < ncell; i++) { memcpy(cc_[i].bb, cl[i].bb, sizeof cc_[i].bb); cc_[i].first = cl[i].first; cc_[i].n = cl[i].n; int r = cl[i].state == 2; st_[i] = (unsigned char)(r | ((r && !cl[i].owner) << 1)); }
  memset(&J, 0, sizeof J);
  J.eye[0] = eyeX; J.eye[1] = eyeY; J.eye[2] = eyeZ; J.dd = drawDist; J.mg = cullMg
#ifdef NEG
 + 0.001f
#endif
 ; J.pr2 = pr2; J.lod = LOD; memcpy(J.pl, pl, sizeof J.pl);
  J.flags = (optFar ? CC_F_FAR : 0u) | (drawDist > pvsRange ? CC_F_FARLOOP : 0u); J.n = n; J.ncell = ncell; J.npc = npc; J.regEye = regEye;
  J.list = pl_; J.crc = crc; J.cr = cr; J.cells = cc_; J.state = st_;
  if (!ccRun(&J)) return 0;
  nd = 0; regCut = J.regCut;
  for (unsigned i = 0; i < J.nOut; i++) { unsigned short t = J.otk[i], k = J.otp[i];
    if (t == CC_MK_CALL) cullPiece(k);
    else if (t == CC_MK_CHECK) { if (k < npc && cl[pc[k].cell].state == 2 && boxD2(pc[k].bb) <= pr2) cullPiece(k); }
    else { if (nd >= CC_MAXDRAW) break; tk[nd] = t; tp[nd] = k; tf[nd] = J.otf[i]; tcl[nd] = J.otcl[i]; nd++; } }
  return 1;
}
int main(int argc, char **argv) {
  int bad = 0; long total = 0, marks = 0, ovf = 0;
  for (int a = 1; a < argc; a++) {
    FILE *f = fopen(argv[a], "rb"); if (!f) { printf("%s: нет файла\n", argv[a]); bad++; continue; }
    fseek(f, 0, SEEK_END); long sz = ftell(f); fseek(f, 0, SEEK_SET); unsigned char *b = malloc(sz); if (fread(b, 1, sz, f) != (size_t)sz) { printf("чтение\n"); return 2; } fclose(f);
    npc = *(unsigned *)(b + 8); unsigned ptab = *(unsigned *)(b + 76), ctab = *(unsigned *)(b + 84), pvsOff = *(unsigned *)(b + 88); ncell = *(unsigned *)(b + 80);
    pc = (const Rec *)(b + ptab); if (ncell > CC_MAXCELL) { printf("%s: клеток %u > %d\n", argv[a], ncell, CC_MAXCELL); bad++; continue; }
    cl = calloc(ncell, sizeof *cl); for (unsigned i = 0; i < ncell; i++) memcpy(&cl[i], b + ctab + 48 * i, 48);
    if (!pvsOff || memcmp(b + pvsOff, "PVS1", 4)) { printf("%s: нет PVS1\n", argv[a]); continue; }
    cr = malloc(npc * sizeof *cr); crc = malloc(npc * 2);
    for (unsigned i = 0; i < npc; i++) { const Rec *d = &pc[i]; CcRec *h = &cr[i]; memcpy(h->bb, d->bb, sizeof h->bb); int t = d->tex < 0 || d->tex > 510 ? 511 : d->tex;
      h->tk = (unsigned short)(((d->flags & 3) << 9) | t); h->tcl = ((d->flags & 2) && !(d->flags & 4)) || d->cell >= 0xFFFFu ? 0xFFFFu : (unsigned short)d->cell;
      h->cell = d->cell >= 0xFFFFu ? 0xFFFFu : (unsigned short)d->cell; h->rg = (unsigned char)(d->pad[0] <= 255 ? d->pad[0] : 0); h->pad = d->pad[0] > 255; crc[i] = h->cell; }
    if (getenv("CC_SYN")) for (unsigned i = 0; i < npc; i++) { float r = rnd(); if (r < .03f) cr[i].pad = 1; else if (r < .05f) { cr[i].cell = 0xFFFFu; crc[i] = 0xFFFFu; } }   // синтетика: пути с метками (в данных уровней таких кусков почти нет)
    const float *pf = (const float *)(b + pvsOff + 4); const unsigned *pu = (const unsigned *)(b + pvsOff + 16);
    float ox = pf[0], oz = pf[1], pcell = pf[2]; unsigned W = pu[0], H = pu[1]; float range = (pu[3] >= 115 && pu[3] <= 1000) ? (float)pu[3] : 115.f;
    const unsigned *ent = (const unsigned *)(b + pvsOff + 32); const unsigned short *pool = (const unsigned short *)((const char *)ent + W * H * 8);
    unsigned *cand = malloc(W * H * 4); unsigned nc = 0; for (unsigned i = 0; i < W * H; i++) if (ent[2 * i + 1] != 0xFFFFFFFFu && ent[2 * i + 1]) cand[nc++] = i;
    long poses = 0, mism = 0;
    for (int it = 0; it < 3000 && nc; it++) {
      unsigned e = cand[(unsigned)(rnd() * nc) % nc]; float gx = e % W, gz = e / W;
      eyeX = ox + (gx + rnd()) * pcell; eyeZ = oz + (gz + rnd()) * pcell; eyeY = 1.5f + rnd() * 10.f;
      float yaw = rnd() * 6.2831853f, pit = (rnd() - .35f) * 1.0f, fx = cosf(pit) * cosf(yaw), fy = sinf(pit), fz = cosf(pit) * sinf(yaw);
      drawDist = rnd() < .5f ? 115.f : (rnd() < .5f ? 150.f : 250.f); cullMg = rnd() < .5f ? 0.f : 1.1f; optFar = rnd() < .8f;
      float pr2 = drawDist > range ? range * range : 1e30f; planes(pl, fx, fy, fz);
      regEye = rnd() < .3f ? 0xFFFFu : (unsigned)(rnd() * 65536.f);
      for (unsigned i = 0; i < ncell; i++) { cl[i].state = rnd() < .8f ? 2 : (rnd() < .5f ? 0 : 1); cl[i].owner = rnd() < .03f; }
      const unsigned short *lst = pool + ent[2 * e]; unsigned n = ent[2 * e + 1]; poses++;
      refRun(lst, (int)n, pr2, range);
      static unsigned short rtk[CC_MAXDRAW], rtp[CC_MAXDRAW], rcl[CC_MAXDRAW]; static unsigned char rtf[CC_MAXDRAW]; int rnd_ = nd; unsigned rreg = regCut;
      memcpy(rtk, tk, sizeof tk); memcpy(rtp, tp, sizeof tp); memcpy(rcl, tcl, sizeof tcl); memcpy(rtf, tf, sizeof tf);
      if (!meRun(lst, (int)n, pr2, range)) { ovf++; continue; }
      int ok = nd == rnd_ && regCut == rreg;
      for (int i = 0; ok && i < nd; i++) ok = rtk[i] == tk[i] && rtp[i] == tp[i] && rcl[i] == tcl[i] && rtf[i] == tf[i];
      if (!ok) { if (mism < 3) printf("  не совпало: поза %ld dd=%.0f mg=%.1f nd_ref=%d nd_me=%d reg %u/%u\n", poses, drawDist, cullMg, rnd_, nd, rreg, regCut); mism++; }
      total++; marks += J.nMark;
    }
    printf("%s: поз %ld, расхождений %ld\n", argv[a], poses, mism); bad += mism != 0;
    free(cl); free(cr); free(crc); free(cand); free(b);
  }
  printf("ИТОГ: %s (сверено %ld, меток для главного %ld, переполнений %ld)\n", bad ? "РАСХОЖДЕНИЕ" : "СОВПАЛО БИТ В БИТ", total, marks, ovf);
  return bad ? 1 : 0;
}
