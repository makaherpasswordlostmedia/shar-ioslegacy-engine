// Граф дорог уровня, A* и водитель по опорным точкам (боты Б1–Б2): общий код навигатора (tools/bots/nav.c) и миссионера
// (tools/bots/missioner.c). Подключается как исходник (#include), в одну единицу трансляции с миром (tools/bots/world.c).
#ifndef NAVGRAPH_H
#define NAVGRAPH_H
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include "world.h"

// ------------------------------------------------------------------ граф дорог
typedef struct { float ax, ay, az, bx, by, bz, hw; } Road;
static Road *roads; static int nroad;
typedef struct { float x, y, z; } P3;
static P3 *node; static int nnode; static int *adj, *adjStart; static float *adjW;
// прямая между узлами проезжая: земля через каждые 2 м, перепад соседних проб до 0.6 м, забор не пересекается
static int clearLine(P3 a, P3 b) {
  const ColWorld *cw = bwCol(); float d = hypotf(b.x - a.x, b.z - a.z), py = a.y; int n = (int)(d / 2.f) + 1;
  if (colCrossFence(cw, a.x, a.z, b.x, b.z, 0, 0) || colCrossFence(cw, b.x, b.z, a.x, a.z, 0, 0)) return 0;
  for (int k = 1; k <= n; k++) { float t = (float)k / n, x = a.x + (b.x - a.x) * t, z = a.z + (b.z - a.z) * t, g;
    if (!colGround(cw, x, z, py + .8f, py - 1.5f, &g, 0) || fabsf(g - py) > .6f) return 0; py = g; }
  return 1;
}
static int nodeOf(float x, float y, float z) {
  for (int i = 0; i < nnode; i++) if (fabsf(node[i].x - x) < 1.5f && fabsf(node[i].z - z) < 1.5f && fabsf(node[i].y - y) < 2.f) return i;
  node[nnode] = (P3){x, y, z}; return nnode++;
}
static void loadRoads(const char *path) {
  FILE *f = fopen(path, "rb"); if (!f) { fprintf(stderr, "nav: нет %s\n", path); exit(2); }
  fseek(f, 0, SEEK_END); long n = ftell(f); rewind(f);
  roads = malloc((size_t)n); if (fread(roads, 1, (size_t)n, f) != (size_t)n) exit(2); fclose(f); nroad = (int)(n / sizeof(Road));
  node = malloc(sizeof(P3) * (size_t)nroad * 2);
  int *ea = malloc(sizeof(int) * (size_t)nroad * 2 * 24), ne = 0;   // пары рёбер (u, v)
  for (int i = 0; i < nroad; i++) {
    Road *r = &roads[i]; int a = nodeOf(r->ax, r->ay, r->az), b = nodeOf(r->bx, r->by, r->bz);
    ea[2 * ne] = a; ea[2 * ne + 1] = b; ne++;
  }
  for (int i = 0; i < nnode; i++) for (int j = i + 1; j < nnode; j++) {   // перекрёстки: концы ближе 12 м, или до 25 м, если между ними
    float dx = node[i].x - node[j].x, dz = node[i].z - node[j].z, d2 = dx * dx + dz * dz;   // проезжая земля без ступеней и заборов
    if (d2 >= 625.f || fabsf(node[i].y - node[j].y) >= 3.f || ne >= nroad * 2 * 24 - 1) continue;
    if (d2 >= 144.f && !clearLine(node[i], node[j])) continue;
    ea[2 * ne] = i; ea[2 * ne + 1] = j; ne++;
  }
  adjStart = calloc((size_t)nnode + 1, sizeof(int)); adj = malloc(sizeof(int) * (size_t)ne * 2); adjW = malloc(sizeof(float) * (size_t)ne * 2);
  for (int e = 0; e < ne; e++) { adjStart[ea[2 * e] + 1]++; adjStart[ea[2 * e + 1] + 1]++; }
  for (int i = 0; i < nnode; i++) adjStart[i + 1] += adjStart[i];
  int *fill = calloc((size_t)nnode, sizeof(int));
  for (int e = 0; e < ne; e++) for (int k = 0; k < 2; k++) {
    int u = ea[2 * e + k], v = ea[2 * e + 1 - k], at = adjStart[u] + fill[u]++;
    adj[at] = v; adjW[at] = hypotf(node[u].x - node[v].x, node[u].z - node[v].z);
  }
  free(ea); free(fill);
}
static int nearestNode(float x, float y, float z) {
  int best = -1; float bd = 1e18f;
  for (int i = 0; i < nnode; i++) { float dx = node[i].x - x, dz = node[i].z - z, dy = node[i].y - y, d = dx * dx + dz * dz + 4.f * dy * dy; if (d < bd) { bd = d; best = i; } }
  return best;
}
// места, где бот застрял: рёбра ближе 10 м к ним дороже (объезд, как сделал бы игрок)
static float avoidXZ[64][2]; static int navAvoidN;
static void navAvoid(float x, float z) { if (navAvoidN < 64) { avoidXZ[navAvoidN][0] = x; avoidXZ[navAvoidN][1] = z; navAvoidN++; } }
static float avoidCost(const P3 *a, const P3 *b) {
  float c = 0;
  for (int k = 0; k < navAvoidN; k++) {
    float px = avoidXZ[k][0], pz = avoidXZ[k][1], dx = b->x - a->x, dz = b->z - a->z, l2 = dx * dx + dz * dz + 1e-6f;
    float t = ((px - a->x) * dx + (pz - a->z) * dz) / l2; t = t < 0 ? 0 : t > 1 ? 1 : t;
    if (hypotf(a->x + dx * t - px, a->z + dz * t - pz) < 10.f) c += 1e4f;
  }
  return c;
}
// A*: путь узлов от s к g; -> число узлов (0 — нет пути)
static int astar(int s, int g, int *out, int cap) {
  float *gs = malloc(sizeof(float) * nnode); int *from = malloc(sizeof(int) * nnode); char *closed = calloc((size_t)nnode, 1);
  for (int i = 0; i < nnode; i++) { gs[i] = 1e30f; from[i] = -1; }
  gs[s] = 0; int n = 0;
  for (;;) {
    int u = -1; float bf = 1e30f;
    for (int i = 0; i < nnode; i++) if (!closed[i] && gs[i] < 1e29f) { float f = gs[i] + hypotf(node[i].x - node[g].x, node[i].z - node[g].z); if (f < bf) { bf = f; u = i; } }
    if (u < 0) break; if (u == g) { for (int v = g; v >= 0 && n < cap; v = from[v]) out[n++] = v; break; }
    closed[u] = 1;
    for (int k = adjStart[u]; k < adjStart[u + 1]; k++) { int v = adj[k]; float c = gs[u] + adjW[k] + (navAvoidN ? avoidCost(&node[u], &node[v]) : 0.f); if (c < gs[v]) { gs[v] = c; from[v] = u; } }
  }
  for (int i = 0; i < n / 2; i++) { int t = out[i]; out[i] = out[n - 1 - i]; out[n - 1 - i] = t; }
  free(gs); free(from); free(closed); return n;
}

static void navLoad(const char *roadsPath) { loadRoads(roadsPath); }
// опорные точки от A до B: A, узлы пути A* (не больше cap-2, прорежены), B; -> число точек
static int navPlan(float ax, float ay, float az, float bx, float by, float bz, P3 *q, int cap) {
  int s = nearestNode(ax, ay, az), g = nearestNode(bx, by, bz), path[1024], n = astar(s, g, path, 1024), k = 0;
  q[k++] = (P3){ax, ay, az};
  if (n) { int step = n > cap - 3 ? (n + cap - 4) / (cap - 3) : 1; for (int i = 0; i < n && k < cap - 1; i += step) q[k++] = node[path[i]]; }
  q[k++] = (P3){bx, by, bz};
  return k;
}
// ------------------------------------------------------------------ водитель по опорным точкам
// par: 0 упреждение базовое м, 1 упреждение на м/с, 2 скорость на прямой м/с, 3 скорость в повороте м/с, 4 торможение: запас по скорости,
//      5 усиление руля, 6 угол ошибки для ручника (рад)
#define NPAR 7
#define MAXWP 96   // опорных точек пути не больше
static const float PAR0[NPAR] = {5.f, .35f, 26.f, 11.f, 3.f, 2.2f, 1.2f}, PARLO[NPAR] = {2.f, .1f, 8.f, 5.f, 0.f, .8f, .6f}, PARHI[NPAR] = {14.f, .9f, 40.f, 30.f, 10.f, 5.f, 3.2f};
// кадр водителя: точка прицела — первая опорная дальше упреждения; газ/тормоз по целевой скорости, руль по ошибке курса
static void navSteer(const P3 *q, int n, int *segp, const Car *c, const float *par, unsigned *bp, float *axp) {
  int seg = *segp; float v = c->v, L = par[0] + par[1] * fabsf(v);
  while (seg < n - 1 && hypotf(q[seg + 1].x - c->x, q[seg + 1].z - c->z) < L) seg++;
  P3 t = q[seg < n - 1 ? seg + 1 : n - 1];
  float e = atan2f(t.x - c->x, t.z - c->z) - c->h; while (e > 3.14159f) e -= 6.28318f; while (e < -3.14159f) e += 6.28318f;
  float turn = 0.f;   // резкость поворота впереди
  if (seg + 2 < n) { float a1 = atan2f(q[seg + 1].x - q[seg].x, q[seg + 1].z - q[seg].z), a2 = atan2f(q[seg + 2].x - q[seg + 1].x, q[seg + 2].z - q[seg + 1].z), d = a2 - a1;
    while (d > 3.14159f) d -= 6.28318f; while (d < -3.14159f) d += 6.28318f; turn = fabsf(d); }
  float vt = turn > .5f && hypotf(q[seg + 1 < n ? seg + 1 : n - 1].x - c->x, q[seg + 1 < n ? seg + 1 : n - 1].z - c->z) < 30.f ? par[3] : par[2];
  if (fabsf(e) > .6f) vt = fminf(vt, par[3]);
  unsigned b = 0; float ax = fmaxf(-1.f, fminf(1.f, -e * par[5]));
  if (v < vt) b |= GP_R; else if (v > vt + par[4]) b |= GP_L;
  if (fabsf(e) > par[6] && v > 8.f) b |= GP_SQUARE;
  *segp = seg; *bp = b; *axp = ax;
}
#endif
