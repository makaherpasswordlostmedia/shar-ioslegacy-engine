// Что в коллизии вокруг точки: tools/col_census_at.c LEVEL.shr x y z [радиус 6] — твёрдые для машины примитивы в слое [y, y+2,2]: ящики, капсулы, заборы, крутые треугольники,
// опора под точкой. Для разбора «машина стоит в чистом поле» (невидимая стена или нет). Печать: тип, индекс, центр, размеры, верх, материал.
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <string.h>
#include "col.h"
static ColWorld W;
int main(int argc, char **argv) {
  if (argc < 5) return 2;
  FILE *f = fopen(argv[1], "rb"); if (!f) return 2; fseek(f, 0, SEEK_END); long size = ftell(f); rewind(f);
  unsigned char *d = malloc((size + 15) & ~15); if (fread(d, 1, size, f) != (size_t)size) return 2; fclose(f);
  unsigned co = *(unsigned *)(d + 92), ce = *(unsigned *)(d + 96), pv = *(unsigned *)(d + 88); if (pv > co && pv < ce) ce = pv;
  if (colInit(&W, d + co, ce - co)) return 3;
  float px = atof(argv[2]), py = atof(argv[3]), pz = atof(argv[4]), R = argc > 5 ? atof(argv[5]) : 6.f, lo = py - 0.2f, hi = py + 2.2f;
  float g, n[3]; int ok = colGround(&W, px, pz, py + 1.5f, py - 3.f, &g, n);
  printf("точка (%.1f %.1f %.1f): опора %s y %.2f n.y %.2f\n", px, py, pz, ok ? "есть" : "НЕТ", ok ? g : 0.f, ok ? n[1] : 0.f);
  int nb = 0;
  for (unsigned i = 0; i < W.nbox; i++) { const ColBox *B = &W.box[i];
    float r = fabsf(B->ax[0]) * B->h[0] + fabsf(B->ay[0]) * B->h[1] + fabsf(B->az[0]) * B->h[2], rz = fabsf(B->ax[2]) * B->h[0] + fabsf(B->ay[2]) * B->h[1] + fabsf(B->az[2]) * B->h[2], ry = fabsf(B->ax[1]) * B->h[0] + fabsf(B->ay[1]) * B->h[1] + fabsf(B->az[1]) * B->h[2];
    if (B->c[0] + r < px - R || B->c[0] - r > px + R || B->c[2] + rz < pz - R || B->c[2] - rz > pz + R) continue;
    if (B->c[1] + ry < lo || B->c[1] - ry > hi) continue;
    float dx = fmaxf(fabsf(px - B->c[0]) - r, 0.f), dz = fmaxf(fabsf(pz - B->c[2]) - rz, 0.f);
    printf("ящик %u c(%.1f %.1f %.1f) h(%.1f %.1f %.1f) низ %.2f верх %.2f расстояние ~%.1f pad %.0f ay.y %.2f\n", i, B->c[0], B->c[1], B->c[2], B->h[0], B->h[1], B->h[2], B->c[1] - ry, B->c[1] + ry, hypotf(dx, dz), B->pad, B->ay[1]); nb++; }
  for (unsigned i = 0; i < W.ncyl; i++) { const ColCyl *C = &W.cyl[i];
    float ext = C->r + C->halfLen; if (C->c[0] < px - R - ext || C->c[0] > px + R + ext || C->c[2] < pz - R - ext || C->c[2] > pz + R + ext) continue;
    float ey = fabsf(C->axis[1]) * C->halfLen + C->r; if (C->c[1] + ey < lo || C->c[1] - ey > hi) continue;
    float t = (px - C->c[0]) * C->axis[0] + (py - C->c[1]) * C->axis[1] + (pz - C->c[2]) * C->axis[2]; t = fmaxf(-C->halfLen, fminf(C->halfLen, t));
    float qx = C->c[0] + C->axis[0] * t, qy = C->c[1] + C->axis[1] * t, qz = C->c[2] + C->axis[2] * t, dd = sqrtf((px - qx) * (px - qx) + (py - qy) * (py - qy) + (pz - qz) * (pz - qz)) - C->r;
    if (dd > R) continue;
    printf("капсула %u c(%.1f %.1f %.1f) ось(%.2f %.2f %.2f) r %.2f L %.1f расстояние %.1f pad %.0f\n", i, C->c[0], C->c[1], C->c[2], C->axis[0], C->axis[1], C->axis[2], C->r, 2 * C->halfLen, dd, C->pad[0]); nb++; }
  for (unsigned i = 0; i < W.nseg; i++) { const ColSeg *G = &W.seg[i];
    float ex = G->b[0] - G->a[0], ez = G->b[1] - G->a[1], L = sqrtf(ex * ex + ez * ez); if (L < 1e-3f) continue;
    float t = ((px - G->a[0]) * ex + (pz - G->a[1]) * ez) / (L * L); t = fmaxf(0.f, fminf(1.f, t));
    float qx = G->a[0] + ex * t, qz = G->a[1] + ez * t, dd = hypotf(px - qx, pz - qz); if (dd > R) continue;
    float side = (px - G->a[0]) * G->n[0] + (pz - G->a[1]) * G->n[1];
    printf("забор %u (%.1f %.1f)-(%.1f %.1f) n(%.2f %.2f) низ %.1f верх %.1f расстояние %.1f сторона %s\n", i, G->a[0], G->a[1], G->b[0], G->b[1], G->n[0], G->n[1], G->y0, G->y1, dd, side >= 0 ? "лицо" : "изнанка"); nb++; }
  int nt = 0;
  for (unsigned i = 0; i < W.ntri; i++) { const ColTri *T = &W.tri[i]; if (T->n[1] > COL_WALK_NY || T->n[1] < -COL_WALK_NY) continue;
    float mx = (T->a[0] + T->b[0] + T->c[0]) / 3, mz = (T->a[2] + T->b[2] + T->c[2]) / 3; if (hypotf(mx - px, mz - pz) > R) continue;
    float ymn = fminf(T->a[1], fminf(T->b[1], T->c[1])), ymx = fmaxf(T->a[1], fmaxf(T->b[1], T->c[1])); if (ymx < lo || ymn > hi) continue;
    if (nt < 12) printf("стена-треугольник %u центр(%.1f %.1f) y %.2f..%.2f n.y %.2f расстояние %.1f\n", i, mx, mz, ymn, ymx, T->n[1], hypotf(mx - px, mz - pz)); nt++; }
  printf("итого: ящиков/капсул/заборов %d, крутых треугольников %d\n", nb, nt);
  return 0;
}
