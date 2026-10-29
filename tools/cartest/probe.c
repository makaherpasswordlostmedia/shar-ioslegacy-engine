// Разбор данных столкновений уровня: ящики, звенья и треугольники вокруг точки. Только чтение level.shr.
//   probe level.shr box I [J]            ящики с номерами I..J
//   probe level.shr near X Y Z R         все примитивы в радиусе R от точки
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "col.h"
ColWorld w;
static int loadCol(const char *path) {
  FILE *f = fopen(path, "rb"); if (!f) return -1; fseek(f, 0, SEEK_END); long n = ftell(f); fseek(f, 0, SEEK_SET);
  unsigned char *d = aligned_alloc(16, (n + 15) & ~15); if (fread(d, 1, n, f) != (size_t)n) return -1; fclose(f);
  unsigned pvsOff = *(unsigned *)(d + 88), colOff = *(unsigned *)(d + 92), propOff = *(unsigned *)(d + 96);
  unsigned end = n; if (pvsOff && pvsOff < end && pvsOff > colOff) end = pvsOff; if (propOff && propOff < end && propOff > colOff) end = propOff;
  void *cm = aligned_alloc(16, ((end - colOff) + 15) & ~15); memcpy(cm, d + colOff, end - colOff);
  return colInit(&w, cm, end - colOff);
}
static void pbox(unsigned i) {
  const ColBox *b = &w.box[i];
  printf("box#%u pad=%g c=(%.2f,%.2f,%.2f) h=(%.2f,%.2f,%.2f) ax=(%.2f,%.2f,%.2f) ay=(%.2f,%.2f,%.2f) az=(%.2f,%.2f,%.2f)\n", i, b->pad, b->c[0], b->c[1], b->c[2], b->h[0], b->h[1], b->h[2], b->ax[0], b->ax[1], b->ax[2], b->ay[0], b->ay[1], b->ay[2], b->az[0], b->az[1], b->az[2]);
}
int main(int argc, char **argv) {
  if (argc < 4 || loadCol(argv[1])) { puts("usage: probe level.shr box I [J] | near X Y Z R"); return 2; }
  printf("tri=%u box=%u cyl=%u seg=%u zone=%u pad=%u flags=%u\n", w.ntri, w.nbox, w.ncyl, w.nseg, w.nzone, w.npad, 0u);
  if (!strcmp(argv[2], "ground") && argc >= 7) {   // сетка: высота земли под точкой (сверху вниз), шаг S
    float x0 = atof(argv[3]), z0 = atof(argv[4]), half = atof(argv[5]), st = atof(argv[6]), yT = argc > 7 ? atof(argv[7]) : 60.f;
    for (float z = z0 - half; z <= z0 + half + .01f; z += st) { printf("z=%7.1f:", z); for (float x = x0 - half; x <= x0 + half + .01f; x += st) { float g, n3[3]; if (colGround(&w, x, z, yT, -200.f, &g, n3)) printf(" %6.1f", g); else printf("    ---"); } printf("\n"); }
    return 0; }
  if (!strcmp(argv[2], "death") && argc >= 7) {   // зона DEATH в точках сетки на нескольких высотах
    float x0 = atof(argv[3]), z0 = atof(argv[4]), half = atof(argv[5]), st = atof(argv[6]);
    printf("зон DEATH в уровне: %u\n", w.ndeath);
    for (unsigned i = 0; i < w.ndeath; i++) { const ColPad *d = &w.death[i]; printf("death#%u c=(%.1f,%.1f,%.1f) h=(%.1f,%.1f,%.1f) apex=(%.1f,%.1f,%.1f) %s\n", i, d->c[0], d->c[1], d->c[2], d->h[0], d->h[1], d->h[2], d->apex[0], d->apex[1], d->apex[2], d->name); }
    for (float yy = 4; yy >= -12; yy -= 4) { printf("y=%.0f:\n", yy); for (float z = z0 - half; z <= z0 + half + .01f; z += st) { printf("z=%7.1f:", z); for (float x = x0 - half; x <= x0 + half + .01f; x += st) printf(" %c", colDeathAt(&w, x, yy, z, 0.f) >= 0 ? 'D' : '.'); printf("\n"); } }
    return 0; }
  if (!strcmp(argv[2], "phantoms")) { for (unsigned i = 0; i < w.nbox; i++) if (w.box[i].pad == 2.f) printf("box %u\n", i); for (unsigned i = 0; i < w.ncyl; i++) if (w.cyl[i].pad[0] == 2.f) printf("cyl %u\n", i); return 0; }
  if (!strcmp(argv[2], "flat") && argc >= 6) {   // как поиск выхода №738 (escapeOutEx): точки колец 0,5…8 м; потом ближайшая ровная (n.y ≥ 0,9) до 40 м
    float x = atof(argv[3]), y = atof(argv[4]), z = atof(argv[5]); static const float RR[9] = {.5f, 1.f, 1.5f, 2.f, 3.f, 4.f, 5.f, 6.5f, 8.f};
    int have = 0, flat = 0, tot = 0; float maxny = 0;
    for (int ri = 0; ri < 9; ri++) for (int k = 0; k < 16; k++) { float a = k * 3.14159265f / 8; float qx = x + sinf(a) * RR[ri], qz = z + cosf(a) * RR[ri], g, n3[3]; tot++;
      if (colGround(&w, qx, qz, y + 1.2f, y - 10.f, &g, n3)) { have++; if (n3[1] > maxny) maxny = n3[1]; if (n3[1] >= .9f) flat++; } }
    printf("в кольцах 0,5…8 м: точек %d, с землёй в окне [y−10, y+1,2] %d, ровных (n.y ≥ 0,9) %d, лучший n.y %.2f (уклон %.0f°)\n", tot, have, flat, maxny, acosf(maxny) * 57.2958f);
    float best = -1; for (float r = 8; r <= 40 && best < 0; r += 1) for (int k = 0; k < 32; k++) { float a = k * 3.14159265f / 16, qx = x + sinf(a) * r, qz = z + cosf(a) * r, g, n3[3]; if (colGround(&w, qx, qz, y + 1.2f, y - 10.f, &g, n3) && n3[1] >= .9f) { best = r; printf("ближайшая ровная точка за кольцами: %.0f м, y=%.1f (x=%.1f z=%.1f)\n", r, g, qx, qz); break; } }
    if (best < 0) printf("ровной точки в 40 м в окне высот нет\n");
    return 0; }
  if (!strcmp(argv[2], "box")) { unsigned i = atoi(argv[3]), j = argc > 4 ? atoi(argv[4]) : i; for (; i <= j && i < w.nbox; i++) pbox(i); return 0; }
  if (!strcmp(argv[2], "near") && argc >= 7) {
    float x = atof(argv[3]), y = atof(argv[4]), z = atof(argv[5]), r = atof(argv[6]);
    for (unsigned i = 0; i < w.nbox; i++) { const ColBox *b = &w.box[i]; float d = hypotf(b->c[0] - x, b->c[2] - z); if (d < r + fmaxf(b->h[0], fmaxf(b->h[1], b->h[2])) && fabsf(b->c[1] - y) < r + 6) pbox(i); }
    for (unsigned i = 0; i < w.nseg; i++) { const ColSeg *s = &w.seg[i]; float mx = (s->a[0] + s->b[0]) / 2, mz = (s->a[1] + s->b[1]) / 2; if (hypotf(mx - x, mz - z) < r + hypotf(s->b[0] - s->a[0], s->b[1] - s->a[1]) / 2) printf("seg#%u a=(%.2f,%.2f) b=(%.2f,%.2f) n=(%.2f,%.2f) y0=%.1f y1=%.1f\n", i, s->a[0], s->a[1], s->b[0], s->b[1], s->n[0], s->n[1], s->y0, s->y1); }
    for (unsigned i = 0; i < w.ncyl; i++) { const ColCyl *c = &w.cyl[i]; if (hypotf(c->c[0] - x, c->c[2] - z) < r + c->halfLen + c->r) printf("cyl#%u c=(%.2f,%.2f,%.2f) axis=(%.2f,%.2f,%.2f) r=%.2f halfLen=%.2f flat=%u\n", i, c->c[0], c->c[1], c->c[2], c->axis[0], c->axis[1], c->axis[2], c->r, c->halfLen, c->flat); }
    unsigned nt = 0; for (unsigned i = 0; i < w.ntri; i++) { const ColTri *t = &w.tri[i]; float mx = (t->a[0] + t->b[0] + t->c[0]) / 3, mz = (t->a[2] + t->b[2] + t->c[2]) / 3, my = (t->a[1] + t->b[1] + t->c[1]) / 3; if (hypotf(mx - x, mz - z) < r && fabsf(my - y) < r) { if (nt++ < 40) printf("tri#%u a=(%.2f,%.2f,%.2f) b=(%.2f,%.2f,%.2f) c=(%.2f,%.2f,%.2f) n=(%.2f,%.2f,%.2f)\n", i, t->a[0], t->a[1], t->a[2], t->b[0], t->b[1], t->b[2], t->c[0], t->c[1], t->c[2], t->n[0], t->n[1], t->n[2]); } }
    printf("треугольников в радиусе: %u\n", nt);
  }
  return 0;
}
