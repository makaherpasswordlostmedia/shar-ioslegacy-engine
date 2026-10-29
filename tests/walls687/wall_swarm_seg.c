// №687 (Роб, L2 C1-5): ровная бетонная стена на трассе останавливает машину; по ровной стене можно прислониться и ехать быстро.
// Рой заездов вдоль настоящих стен уровня (ящики и вертикальные треугольники коллизии длиной от 6 м, ≥1,2 м высотой, твёрдые): машина стартует
// у стены под углом 5/15/30° к ней, на 10 и 25 м/с, в обе стороны вдоль, с обеих сторон, держит газом скорость, руль 0. Скользящий контакт по ровной
// стене скорость сохраняет (наклон отскока и трение дают потерю, но не остановку): конец заезда — через 30 м вдоль стены или 7 с.
// Провал: прошла вдоль стены < 22 м за 7 с или скорость в конце < 0,45·v·cosθ (после контакта).
// cc -std=c11 -O2 -I viewer tools/cartest/wall_swarm.c viewer/car.c viewer/col.c -lm -o wall_swarm ; ./wall_swarm level.shr [max_граней] [seed]
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "car.h"
#include "col.h"
typedef struct { float cx, cz, tx, tz, nx, nz, len, ht; int kind, idx; } Face;
static Face *F; static int nF, capF;
static void add(float cx, float cz, float tx, float tz, float nx, float nz, float len, float ht, int kind, int idx) {
  if (nF == capF) { capF = capF ? capF * 2 : 4096; F = realloc(F, capF * sizeof *F); }
  F[nF++] = (Face){cx, cz, tx, tz, nx, nz, len, ht, kind, idx};
}
static ColWorld w;
int main(int argc, char **argv) {
  FILE *f = fopen(argv[1], "rb"); if (!f) return 2; fseek(f, 0, SEEK_END); unsigned n = ftell(f); rewind(f); unsigned char *b = malloc(n);
  if (fread(b, 1, n, f) != n) return 2; fclose(f);
  unsigned co = *(unsigned *)(b + 92), po = *(unsigned *)(b + 96), pv = *(unsigned *)(b + 88), end = n;
  if (po > co && po < end) end = po; if (pv > co && pv < end) end = pv;
  if (colInit(&w, b + co, end - co)) return 2;
  int maxF = argc > 2 ? atoi(argv[2]) : 400; unsigned seed = argc > 3 ? atoi(argv[3]) : 1; srand(seed);
  for (unsigned i = 0; i < w.nbox; i++) {   // боковые грани твёрдых ящиков
    const ColBox *B = &w.box[i]; if (B->pad == 1.f) continue;
    const float *ax[3] = {B->ax, B->ay, B->az};
    for (int a = 0; a < 3; a++) {   // a — ось нормали грани (горизонтальная), v — вертикальная, t — вдоль
      if (fabsf(ax[a][1]) > 0.1f) continue;
      for (int v = 0; v < 3; v++) { if (v == a || fabsf(ax[v][1]) < 0.9f) continue;
        int t = 3 - a - v; float len = 2 * B->h[t], ht = 2 * B->h[v]; if (len < 6.f || ht < 1.2f) continue;
        for (int s = -1; s <= 1; s += 2) {
          float nx = ax[a][0] * s, nz = ax[a][2] * s, l = hypotf(nx, nz); nx /= l; nz /= l;
          add(B->c[0] + nx * B->h[a] * l, B->c[2] + nz * B->h[a] * l, ax[t][0], ax[t][2], nx, nz, len, ht, 1, (int)i); }
      }
    }
  }
  for (unsigned i = 0; i < w.ntri; i++) {   // вертикальные треугольники: по самому длинному горизонтальному ребру
    const ColTri *T = &w.tri[i]; if (fabsf(T->n[1]) > 0.1f) continue;
    float hy = fmaxf(T->a[1], fmaxf(T->b[1], T->c[1])) - fminf(T->a[1], fminf(T->b[1], T->c[1])); if (hy < 1.2f) continue;
    const float *P[3] = {T->a, T->b, T->c}; float best = 0; int bi = 0;
    for (int e = 0; e < 3; e++) { float l = hypotf(P[(e + 1) % 3][0] - P[e][0], P[(e + 1) % 3][2] - P[e][2]); if (l > best) { best = l; bi = e; } }
    if (best < 6.f) continue;
    float tx = (P[(bi + 1) % 3][0] - P[bi][0]) / best, tz = (P[(bi + 1) % 3][2] - P[bi][2]) / best, nl = hypotf(T->n[0], T->n[2]);
    add((P[bi][0] + P[(bi + 1) % 3][0]) * .5f, (P[bi][2] + P[(bi + 1) % 3][2]) * .5f, tx, tz, T->n[0] / nl, T->n[2] / nl, best, hy, 2, (int)i);
  }
  if (!getenv("WSW_NOSEG")) for (unsigned i = 0; i < w.nseg; i++) {   // №687: стены-отрезки COL1 (заборы, ограждения трасс): граница полосы, нормаль в сторону проезда
    const ColSeg *S = &w.seg[i]; float dx = S->b[0] - S->a[0], dz = S->b[1] - S->a[1], l = hypotf(dx, dz); if (l < 6.f || S->y1 - S->y0 < 1.2f) continue;
    add((S->a[0] + S->b[0]) * .5f, (S->a[1] + S->b[1]) * .5f, dx / l, dz / l, S->n[0], S->n[1], l, 3.f, 3, (int)i);
  }
  { const char *rg = getenv("WSW_REG"); if (rg) { float x0, x1, z0, z1; sscanf(rg, "%f,%f,%f,%f", &x0, &x1, &z0, &z1); int k = 0;
      for (int i = 0; i < nF; i++) if (F[i].cx >= x0 && F[i].cx <= x1 && F[i].cz >= z0 && F[i].cz <= z1) F[k++] = F[i]; nF = k; } }
  fprintf(stderr, "граней-кандидатов: %d (ящики+треугольники)\n", nF);
  if (nF > maxF) for (int i = 0; i < maxF; i++) { int j = i + rand() % (nF - i); Face t = F[i]; F[i] = F[j]; F[j] = t; }
  const char *one = getenv("WSW_ONE"); int o_fi = -1, o_ia = 0, o_iv = 0, o_d = 1; if (one) sscanf(one, "%d,%d,%d,%d", &o_fi, &o_ia, &o_iv, &o_d);
  int nrun = nF < maxF ? nF : maxF, fail = 0, runs = 0;
  const float angs[3] = {5, 15, 30}, vts[2] = {10, 25}; CarParams p; carParamsFor("famil_v", &p);
  printf("face\tkind\tidx\tcx\tcz\tang\tvt\tdir\tprog_m\tt_s\tv_end\tvmin_after\tstate\tlat_end\tu_end\tx_end\tz_end\n");
  for (int fi = 0; fi < nrun; fi++) {
    if (one && fi != o_fi) continue;
    const Face *q = &F[fi]; if (q->len < 10.f) continue;
    for (int d = -1; d <= 1; d += 2) for (int iv = 0; iv < 2; iv++) {
      if (one && (d != o_d || iv != o_iv)) continue;
      float tx = q->tx * d, tz = q->tz * d, vt = vts[iv], need = q->len * .8f, tmax = (q->len + 8.f) / (vt * .4f) + 3.f;
      for (int ia = -1; ia < 3; ia++) {
        if (one && ia >= 0 && ia != o_ia) continue; int dbg = one && ia >= 0;   // ia = -1 — контроль: параллельно стене в 2,5 м (проходимость коридора), без контакта
        float th = ia < 0 ? 0.f : angs[ia] * 0.0174533f;
        float fx = tx * cosf(th) - q->nx * sinf(th), fz = tz * cosf(th) - q->nz * sinf(th);
        float off = ia < 0 ? 2.5f : 1.4f + 10.f * tanf(th);   // вбок от стены: так, чтобы к началу стены ещё не касаться
        float sx = q->cx - tx * (q->len * .5f + 6.f + (ia < 0 ? 0.f : 3.f / (sinf(th) > .1f ? sinf(th) : .1f) * cosf(th) * 0.f)) + q->nx * off, sz = q->cz - tz * (q->len * .5f + 6.f) + q->nz * off;
        float g; if (!colGround(&w, sx, sz, 12, -12, &g, 0)) { if (ia < 0) goto nextrun; continue; }
        Car c; carInit(&c, &p, &w, sx, g, sz, atan2f(fx, fz));
        for (int i = 0; i < 30; i++) carUpdate(&c, &w, &(CarInput){0}, 1.f / 60);
        if (hypotf(c.x - sx, c.z - sz) > 1.f || c.y > g + 1.f) { if (ia < 0) goto nextrun; continue; }
        carSetSpeed(&c, vt); float x0 = c.x, z0 = c.z; int hit = 0, flip = 0, lt = -1; unsigned li = 0; float vmin = 1e9, prog = 0, t = 0, u0 = -q->len * .5f + 4.f, u1 = -q->len * .5f + fminf(q->len - 3.f, 14.f);
        for (; t < tmax && prog < need; t += 1.f / 60) {
          CarInput in = {0}; in.throttle = c.v < vt ? 1.f : 0.f; carUpdate(&c, &w, &in, 1.f / 60);
          float along = (c.x - x0) * tx + (c.z - z0) * tz; if (along > prog) prog = along;
          if (!hit && c.wallV > .3f) hit = 1; if (c.wallV > .3f) { lt = c.wallType; li = c.wallIdx; }
          float u = (c.x - q->cx) * tx + (c.z - q->cz) * tz; if (hit && u > u0 && u < u1) { float vv = hypotf(c.vel[0], c.vel[2]); if (vv < vmin) vmin = vv; }
          if (dbg) printf("  t=%.2f u=%.1f x=%.2f z=%.2f v=%.1f wallV=%.1f lat=%.2f rev=%d why=%d wheels=%d y=%.2f\n", t, u, c.x, c.z, hypotf(c.vel[0], c.vel[2]), c.wallV, (c.x - q->cx) * q->nx + (c.z - q->cz) * q->nz, c.reverts, c.revWhy, c.wheels, c.y);
          if (u > u1 + 1.f) break;
          if (fabsf(c.roll) > 1.0f || fabsf(c.pitch) > 1.0f) flip = 1;
        }
        float vend = hypotf(c.vel[0], c.vel[2]);
        if (ia < 0) { if (((c.x - q->cx) * tx + (c.z - q->cz) * tz) < u1 + .5f || flip) goto nextrun; continue; }   // коридор непроходим и без стены — грань не годится
        runs++; if (!hit) continue;
        int bad = (vmin < .45f * vt * cosf(th)) || (((c.x - q->cx) * tx + (c.z - q->cz) * tz) < u1 + .5f && t >= tmax - .02f);
        if (bad && !flip) fail++;
        if (bad) printf("%d\t%d\t%d\t[%d:%u]\t%.1f\t%.1f\t%.0f\t%.0f\t%d\t%.1f\t%.1f\t%.1f\t%.1f\t%s\t%.2f\t%.1f\t%.2f\t%.2f\n", fi, q->kind, q->idx, lt, li, q->cx, q->cz, angs[ia], vt, d, prog, t, vend, vmin, flip ? "перевернулась" : "СТОП", (c.x - q->cx) * q->nx + (c.z - q->cz) * q->nz, (c.x - q->cx) * tx + (c.z - q->cz) * tz, c.x, c.z);
      }
      nextrun:;
    }
  }
  fprintf(stderr, "заездов с контактом/всего: провалов %d из %d (граней %d)\n", fail, runs, nrun);
  printf("RESULT fail=%d runs=%d faces=%d\n", fail, runs, nrun);
  return fail ? 1 : 0;
}
