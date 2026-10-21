// scene.h — рисуемая геометрия города и предметы уровня для офлайн-проверок (worldscan, tests/shadow522): треугольники кусков (без неба, с флагом альфа/смешивание),
// сетка 2 м для лучей, луч «обе стороны», нарисованная земля под точкой, список предметов. Только чтение level.shr; нужны col.h, props.h, stateprops.h.
#ifndef SHAR_SCENE_H
#define SHAR_SCENE_H
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <stdint.h>
#include "col.h"
#include "props.h"
#include "stateprops.h"
static ColWorld W; static unsigned char *file; static unsigned fileSize; static int LV;
typedef struct { float bb[6]; int32_t tex; uint32_t flags, nv, ni, owner; float ox, oy, oz, sc; uint32_t off, nf, cell, pad[2]; } Rec;
typedef struct { float bb[6]; uint32_t first, n, owner, off, size, pad; } CellRec;
static float *T; static unsigned char *TF; static short *TX; static unsigned NT;   // TX — индекс текстуры треугольника (Rec.tex)
static unsigned *gStart, *gList; static int GW, GH; static float GOX, GOZ; static const float GC = 2.f;
static float *propXZ; static unsigned nProp;

// ---------------------------------------------------------------- рисуемая геометрия и предметы
static void loadRender(void) {
  uint32_t npc, tableOff, cellOff; memcpy(&npc, file + 8, 4); memcpy(&tableOff, file + 76, 4); memcpy(&cellOff, file + 84, 4);
  const Rec *recs = (const Rec *)(file + tableOff); const CellRec *cells = (const CellRec *)(file + cellOff);
  unsigned cap = 1 << 20; T = malloc(sizeof(float) * 9 * cap); TF = malloc(cap); TX = malloc(sizeof(short) * cap);
  for (unsigned i = 0; i < npc; i++) {
    const Rec *r = &recs[i]; if (r->owner != 0 || (r->flags & 4) || !(r->flags & 16)) continue;   // город, не небо, с индексами
    int vs = (r->flags & 32) ? 12 : 16; const uint8_t *b = file + cells[r->cell].off + r->off;
    for (unsigned k = 0; k + 2 < r->ni; k += 3) {
      if (NT == cap) { cap *= 2; T = realloc(T, sizeof(float) * 9 * cap); TF = realloc(TF, cap); TX = realloc(TX, sizeof(short) * cap); }
      for (int j = 0; j < 3; j++) {
        const int16_t *q = (const int16_t *)(b + (size_t)(k + j) * vs + (vs == 12 ? 6 : 8));
        T[9 * NT + 3 * j] = r->ox + q[0] * (r->sc / 32768.f); T[9 * NT + 3 * j + 1] = r->oy + q[1] * (r->sc / 32768.f); T[9 * NT + 3 * j + 2] = r->oz + q[2] * (r->sc / 32768.f);
      }
      TF[NT] = (unsigned char)(r->flags & 3);   // 1 альфа, 2 смешивание: листва, стекло, вывески — проезд по замыслу не проверяем
      TX[NT] = (short)r->tex;
      NT++;
    }
  }
  GOX = W.ox; GOZ = W.oz; GW = (int)(W.W * W.cell / GC) + 1; GH = (int)(W.H * W.cell / GC) + 1;
  gStart = calloc((size_t)GW * GH + 1, 4);
  for (int pass = 0; pass < 2; pass++) {
    for (unsigned t = 0; t < NT; t++) {
      const float *a = T + 9 * t;
      float x0 = fminf(a[0], fminf(a[3], a[6])), x1 = fmaxf(a[0], fmaxf(a[3], a[6])), z0 = fminf(a[2], fminf(a[5], a[8])), z1 = fmaxf(a[2], fmaxf(a[5], a[8]));
      int cx0 = (int)floorf((x0 - GOX) / GC), cx1 = (int)floorf((x1 - GOX) / GC), cz0 = (int)floorf((z0 - GOZ) / GC), cz1 = (int)floorf((z1 - GOZ) / GC);
      if (cx0 < 0) cx0 = 0; if (cz0 < 0) cz0 = 0; if (cx1 >= GW) cx1 = GW - 1; if (cz1 >= GH) cz1 = GH - 1;
      for (int z = cz0; z <= cz1; z++) for (int x = cx0; x <= cx1; x++) { size_t c = (size_t)z * GW + x; if (pass == 0) gStart[c + 1]++; else gList[gStart[c]++] = t; }
    }
    if (pass == 0) { for (size_t c = 0; c < (size_t)GW * GH; c++) gStart[c + 1] += gStart[c]; gList = malloc(sizeof(unsigned) * (gStart[(size_t)GW * GH] + 1)); }
    else { for (size_t c = (size_t)GW * GH; c > 0; c--) gStart[c] = gStart[c - 1]; gStart[0] = 0; }
  }
}
static Props gProps; static StateProps gSP;
static void loadProps(void) {
  unsigned po = *(unsigned *)(file + 96); if (!po || po + 64 > fileSize) return;
  unsigned size = *(unsigned *)(file + po + 40);
  if (propsInit(&gProps, file + po, size) || spInit(&gSP, gProps.spr, gProps.sprSize)) return;
  propXZ = malloc(sizeof(float) * 3 * (gProps.ninst + gSP.ninst + 1));
  for (unsigned i = 0; i < gProps.ninst; i++) { propXZ[3 * nProp] = gProps.def[i].x; propXZ[3 * nProp + 1] = gProps.def[i].y; propXZ[3 * nProp + 2] = gProps.def[i].z; nProp++; }
  for (unsigned i = 0; i < gSP.ninst; i++) { propXZ[3 * nProp] = gSP.inst[i].x; propXZ[3 * nProp + 1] = gSP.inst[i].y; propXZ[3 * nProp + 2] = gSP.inst[i].z; nProp++; }
}
static int nearProp(float x, float y, float z, float r) {
  for (unsigned i = 0; i < nProp; i++) { float dx = propXZ[3 * i] - x, dz = propXZ[3 * i + 2] - z; if (dx * dx + dz * dz < r * r && fabsf(propXZ[3 * i + 1] - y) < 8.f) return 1; }
  return 0;
}
static float rayTri(const float *o, const float *d, const float *a) {   // обе стороны треугольника
  float e1[3] = {a[3] - a[0], a[4] - a[1], a[5] - a[2]}, e2[3] = {a[6] - a[0], a[7] - a[1], a[8] - a[2]};
  float p[3] = {d[1] * e2[2] - d[2] * e2[1], d[2] * e2[0] - d[0] * e2[2], d[0] * e2[1] - d[1] * e2[0]};
  float det = e1[0] * p[0] + e1[1] * p[1] + e1[2] * p[2]; if (fabsf(det) < 1e-9f) return -1;
  float inv = 1.f / det, s[3] = {o[0] - a[0], o[1] - a[1], o[2] - a[2]};
  float u = (s[0] * p[0] + s[1] * p[1] + s[2] * p[2]) * inv; if (u < 0 || u > 1) return -1;
  float q[3] = {s[1] * e1[2] - s[2] * e1[1], s[2] * e1[0] - s[0] * e1[2], s[0] * e1[1] - s[1] * e1[0]};
  float v = (d[0] * q[0] + d[1] * q[1] + d[2] * q[2]) * inv; if (v < 0 || u + v > 1) return -1;
  return (e2[0] * q[0] + e2[1] * q[1] + e2[2] * q[2]) * inv;
}
static float rayCast(const float *o, const float *d, float tmax, int skipAlpha) {
  float ex = o[0] + d[0] * tmax, ez = o[2] + d[2] * tmax, best = -1;
  int cx0 = (int)floorf((fminf(o[0], ex) - GOX) / GC), cx1 = (int)floorf((fmaxf(o[0], ex) - GOX) / GC), cz0 = (int)floorf((fminf(o[2], ez) - GOZ) / GC), cz1 = (int)floorf((fmaxf(o[2], ez) - GOZ) / GC);
  if (cx0 < 0) cx0 = 0; if (cz0 < 0) cz0 = 0; if (cx1 >= GW) cx1 = GW - 1; if (cz1 >= GH) cz1 = GH - 1;
  for (int z = cz0; z <= cz1; z++) for (int x = cx0; x <= cx1; x++) {
    size_t c = (size_t)z * GW + x;
    for (unsigned k = gStart[c]; k < gStart[c + 1]; k++) { if (skipAlpha && TF[gList[k]]) continue; float t = rayTri(o, d, T + 9 * gList[k]); if (t >= 0 && t <= tmax && (best < 0 || t < best)) best = t; }
  }
  return best;
}

static float renderGround(float x, float z, float yTop, float depth) {   // нарисованная земля под (x, yTop) в пределах depth или -1e9
  float o[3] = {x, yTop, z}, d[3] = {0, -1, 0}, t = rayCast(o, d, depth, 0); return t < 0 ? -1e9f : yTop - t;
}
// чтение level.shr в память и COL1; 0 — ок
static int sceneLoad(const char *path) {
  FILE *f = fopen(path, "rb"); if (!f) return 1;
  fseek(f, 0, SEEK_END); fileSize = (unsigned)ftell(f); rewind(f); file = aligned_alloc(16, (fileSize + 15) & ~15u);
  if (fread(file, 1, fileSize, f) != fileSize) { fclose(f); return 2; } fclose(f);
  uint32_t pv = *(uint32_t *)(file + 88), co = *(uint32_t *)(file + 92), po = *(uint32_t *)(file + 96), end = fileSize; if (po > co && po < end) end = po; if (pv > co && pv < end) end = pv;
  return colInit(&W, file + co, end - co) ? 3 : 0;
}
#endif
