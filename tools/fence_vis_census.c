// Перепись заборов коллизии без рисунка (слово дирижёра 15.10: «ударяюсь о прозрачное», класс №581): для каждого звена ColSeg с конечным верхом идём по нему шагом 0,5 м;
// участок «покрыт», если рядом (по плану не дальше COVER_R = 0,6 м) есть видимый треугольник города не-земли (|n.y| < 0,85 — стены, наклонные; или любой выше земли на 0,4 м)
// с высотой, пересекающей полосу [земля+0,3 .. min(верх звена, земля+2,2)], либо точка пропа/стейтпропа (рисуются отдельно от города) ближе PROP_R = 2,0 м.
// Не покрытые участки длиннее MIN_GAP = 2 м — в таблицу: уровень, звено, начало-конец вдоль, длина, сектор. Бесконечные звенья (край мира) считаются отдельно (их рисунка у воды нет по замыслу).
//   fence_vis_census LEVEL.shr vis.bin [ex.txt] [--all]    ex.txt — точки пропов «x z» по строке
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "col.h"
#include "placecode.h"
#define COVER_R 0.6f
#define PROP_R 2.0f
#define MIN_GAP 2.0f
#define CELL 2.0f
static ColWorld W;
typedef struct { float v[9], ny; } Tri;
static Tri *T; static unsigned NT; static int GX, GZ; static float GX0, GZ0; static unsigned *cellS, *cellL;
static float pdist(float px, float pz, float ax, float az, float bx, float bz) { float ex = bx - ax, ez = bz - az, l = ex * ex + ez * ez, t = l > 1e-12f ? ((px - ax) * ex + (pz - az) * ez) / l : 0.f; t = fmaxf(0.f, fminf(1.f, t)); return hypotf(px - (ax + ex * t), pz - (az + ez * t)); }
static float triDist(const Tri *t, float px, float pz) {
  float ax = t->v[0], az = t->v[2], bx = t->v[3], bz = t->v[5], cx = t->v[6], cz = t->v[8];
  float d1 = (px - bx) * (az - bz) - (ax - bx) * (pz - bz), d2 = (px - cx) * (bz - cz) - (bx - cx) * (pz - cz), d3 = (px - ax) * (cz - az) - (cx - ax) * (pz - az);
  int neg = (d1 < 0) || (d2 < 0) || (d3 < 0), pos = (d1 > 0) || (d2 > 0) || (d3 > 0); if (!(neg && pos)) return 0.f;
  return fminf(pdist(px, pz, ax, az, bx, bz), fminf(pdist(px, pz, bx, bz, cx, cz), pdist(px, pz, cx, cz, ax, az)));
}
int main(int argc, char **argv) {
  if (argc < 3) return 2; int all = 0; for (int i = 3; i < argc; i++) if (!strcmp(argv[i], "--all")) all = 1;
  FILE *f = fopen(argv[1], "rb"); if (!f) return 2; fseek(f, 0, SEEK_END); long size = ftell(f); rewind(f);
  unsigned char *d = malloc((size + 15) & ~15); if (fread(d, 1, size, f) != (size_t)size) return 2; fclose(f);
  unsigned co = *(unsigned *)(d + 92), ce = *(unsigned *)(d + 96), pv = *(unsigned *)(d + 88); if (pv > co && pv < ce) ce = pv;
  if (colInit(&W, d + co, ce - co)) return 3;
  FILE *vf = fopen(argv[2], "rb"); if (!vf) return 2; fseek(vf, 0, SEEK_END); long vs = ftell(vf); rewind(vf); NT = (unsigned)(vs / sizeof(Tri)); T = malloc(vs); if (fread(T, 1, vs, vf) != (size_t)vs) return 2; fclose(vf);
  float *EX = NULL; int nex = 0;
  if (argc > 3 && argv[3][0] != '-') { FILE *ef = fopen(argv[3], "r"); if (ef) { EX = malloc(sizeof(float) * 2 * 8192); float x, z; while (nex < 8192 && fscanf(ef, "%f %f", &x, &z) == 2) { EX[nex * 2] = x; EX[nex * 2 + 1] = z; nex++; } fclose(ef); } }
  // сетка по плану: берём только стены/наклонные (|n.y| < 0.85) и всё, что не лежит на земле (проверка по высоте — на лету)
  float xmin = 1e30f, zmin = 1e30f, xmax = -1e30f, zmax = -1e30f;
  for (unsigned i = 0; i < NT; i++) for (int k = 0; k < 3; k++) { float x = T[i].v[k * 3], z = T[i].v[k * 3 + 2]; if (x < xmin) xmin = x; if (x > xmax) xmax = x; if (z < zmin) zmin = z; if (z > zmax) zmax = z; }
  GX0 = xmin - 2; GZ0 = zmin - 2; GX = (int)((xmax - xmin + 4) / CELL) + 1; GZ = (int)((zmax - zmin + 4) / CELL) + 1;
  unsigned *cnt = calloc((size_t)GX * GZ + 1, 4); size_t tot = 0;
  for (int pass = 0; pass < 2; pass++) {
    if (pass) { cellS = malloc(((size_t)GX * GZ + 1) * 4); cellL = malloc(tot * 4); size_t a = 0; for (size_t c = 0; c < (size_t)GX * GZ; c++) { cellS[c] = (unsigned)a; a += cnt[c]; cellS[(size_t)GX * GZ] = (unsigned)a; } memset(cnt, 0, ((size_t)GX * GZ + 1) * 4); }
    for (unsigned i = 0; i < NT; i++) {
      float x0 = fminf(T[i].v[0], fminf(T[i].v[3], T[i].v[6])) - COVER_R, x1 = fmaxf(T[i].v[0], fmaxf(T[i].v[3], T[i].v[6])) + COVER_R;
      float z0 = fminf(T[i].v[2], fminf(T[i].v[5], T[i].v[8])) - COVER_R, z1 = fmaxf(T[i].v[2], fmaxf(T[i].v[5], T[i].v[8])) + COVER_R;
      if ((x1 - x0) * (z1 - z0) > 4000.f) continue;   // огромные плиты (земля/подложка) — не рисунок забора
      int cx0 = (int)((x0 - GX0) / CELL), cx1 = (int)((x1 - GX0) / CELL), cz0 = (int)((z0 - GZ0) / CELL), cz1 = (int)((z1 - GZ0) / CELL);
      for (int cz = cz0; cz <= cz1; cz++) for (int cx = cx0; cx <= cx1; cx++) { size_t c = (size_t)cz * GX + cx; if (!pass) { cnt[c]++; tot++; } else cellL[cellS[c] + cnt[c]++] = i; }
    }
  }
  int nf = 0, ninf = 0, ngap = 0, nland = 0; float landGap = 0.f; float gapLen = 0.f, fenceLen = 0.f, infLen = 0.f, infGap = 0.f;
  for (unsigned s = 0; s < W.nseg; s++) {
    const ColSeg *G = &W.seg[s]; int inf = G->y1 > 1e5f; if (G->y0 < -1.5e6f) continue;   // изгородь-листва (мягкая) — не стена
    float ex = G->b[0] - G->a[0], ez = G->b[1] - G->a[1], L = sqrtf(ex * ex + ez * ez); if (L < 0.3f) continue;
    if (inf) { ninf++; infLen += L; } else { nf++; fenceLen += L; }
    int ns = (int)(L / 0.5f) + 1; float gs = -1.f; int run = 0, landRun = 0;
    for (int k = 0; k <= ns; k++) {
      float t = (float)k / ns, px = G->a[0] + ex * t, pz = G->a[1] + ez * t, g = 0.f; int cov = 0;
      float top = inf ? 1e9f : G->y1;
      int okg = colGround(&W, px, pz, (inf ? 200.f : G->y1 + 1.f), -300.f, &g, 0);
      if (!okg) g = inf ? 0.f : G->y1 - 3.f;
      float lo = g + 0.3f, hi = fminf(top, g + 2.2f);
      int cx = (int)((px - GX0) / CELL), cz = (int)((pz - GZ0) / CELL);
      for (int dz = -1; dz <= 1 && !cov; dz++) for (int dx = -1; dx <= 1 && !cov; dx++) {
        int x = cx + dx, z = cz + dz; if (x < 0 || z < 0 || x >= GX || z >= GZ) continue; size_t c = (size_t)z * GX + x;
        for (unsigned q = cellS[c]; q < cellS[c + 1]; q++) { const Tri *tr = &T[cellL[q]];
          float ymn = fminf(tr->v[1], fminf(tr->v[4], tr->v[7])), ymx = fmaxf(tr->v[1], fmaxf(tr->v[4], tr->v[7]));
          if (ymx < lo || ymn > hi) continue; if (fabsf(tr->ny) > 0.85f && ymn < g + 0.4f) continue;   // почти горизонтальное на земле — земля
          if (triDist(tr, px, pz) <= COVER_R) { cov = 1; break; } } }
      for (int e = 0; e < nex && !cov; e++) if (hypotf(EX[e * 2] - px, EX[e * 2 + 1] - pz) <= PROP_R) cov = 1;
      int land = okg;
      if (okg) { float nx = G->n[0], nz = G->n[1], g1, g2; land = colGround(&W, px + nx * 1.5f, pz + nz * 1.5f, g + 1.2f, g - 1.2f, &g1, 0) && colGround(&W, px - nx * 1.5f, pz - nz * 1.5f, g + 1.2f, g - 1.2f, &g2, 0); }
      if (!cov) { if (!run) gs = t * L; run++; landRun += land; }
      if ((cov || k == ns) && run) { float ge = (cov ? t : 1.f) * L, len = ge - gs;
        int isLand = run > 0 && landRun * 10 >= run * 8;   // 80 % отсчётов участка — ровная земля по обе стороны
        if (len >= MIN_GAP && (all || !inf)) { float mx = G->a[0] + ex * ((gs + ge) * .5f / L), mz = G->a[1] + ez * ((gs + ge) * .5f / L); char pc[12]; placeCode(mx, mz, pc, sizeof pc);
          printf("GAP seg %u %s длина %.1f из %.1f вдоль %.1f..%.1f середина(%.1f %.1f) верх %s земля-по-обе-стороны %s сектор %s\n", s, inf ? "бесконечное" : "конечное", len, L, gs, ge, mx, mz, inf ? "-" : "есть", isLand ? "да" : "нет", pc); }
        if (!inf) { gapLen += len >= MIN_GAP ? len : 0.f; ngap += len >= MIN_GAP; if (len >= MIN_GAP && isLand) { landGap += len; nland++; } } else if (len >= MIN_GAP) infGap += len; run = 0; landRun = 0; }
    }
  }
  printf("ИТОГ: заборов конечных %d (%.0f м), без рисунка участков >%.0f м: %d (%.0f м, %.0f%%; из них над ровной землёй по обе стороны %d участков, %.0f м); бесконечных (край мира) %d (%.0f м), без рисунка %.0f м\n", nf, fenceLen, MIN_GAP, ngap, gapLen, fenceLen > 0 ? 100 * gapLen / fenceLen : 0, nland, landGap, ninf, infLen, infGap);
  return 0;
}
