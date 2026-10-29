// №692 (причал L3: «5–7 стоят вокруг машины и смотрят»): машина игрока стоит поперёк пешеходной дорожки; ни один прохожий не должен стоять
// ближе 6 м к ней дольше 2 с подряд (у оригинала проходят мимо). tests/traffic/ped_wait.c LEVEL TRAFFIC X Z [ПЛОСКОСТЬ_РАДИУС_ПУТИ] ;
// -DPED_WAIT_OLD=1 — красный контроль (ждёт сколько угодно)
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "traffic.h"
#include "homer.h"
static ColWorld world; static Traffic T; static Car player;
static const float DT = 1.f / 30.f;
static unsigned char *readAt(FILE *f, unsigned off, unsigned sz) { unsigned char *m = aligned_alloc(64, (sz + 63) & ~63u); fseek(f, off, SEEK_SET); if (fread(m, 1, sz, f) != sz) { free(m); return 0; } return m; }
static int run(float cx, float cz, float hx, int verbose, float secs, int *outMax);
int main(int argc, char **argv) {
  if (argc < 5) return 2;
  FILE *f = fopen(argv[1], "rb"); if (!f) return 2;
  unsigned char hdr[104]; if (fread(hdr, 1, 104, f) != 104 || memcmp(hdr, "SHR7", 4)) return 2;
  unsigned pvsOff = *(unsigned *)(hdr + 88), colOff = *(unsigned *)(hdr + 92), propOff = *(unsigned *)(hdr + 96);
  fseek(f, 0, SEEK_END); unsigned fsize = (unsigned)ftell(f); unsigned end = fsize; if (pvsOff > colOff && pvsOff < end) end = pvsOff; if (propOff > colOff && propOff < end) end = propOff;
  unsigned char *cm = readAt(f, colOff, end - colOff); fclose(f);
  if (!cm || colInit(&world, cm, end - colOff)) return 2;
  FILE *g = fopen(argv[2], "rb"); if (!g) return 2; fseek(g, 0, SEEK_END); unsigned tsize = (unsigned)ftell(g); unsigned char *buf = readAt(g, 0, tsize); fclose(g);
  if (!buf || trafficInitMem(&T, buf, tsize, 0)) return 2;
  if (!strcmp(argv[3], "scan")) {   // каждая середина отрезка пути: где ждут дольше всего
    int worst = 0, hits = 0, n = 0; float wx = 0, wz = 0;
    for (uint32_t p = 0; p < T.hd->nPath; p++) { const TrPath *P = &T.path[p];
      for (uint32_t k = 0; k < P->n; k += (uint32_t)(argc > 5 ? atoi(argv[5]) : 3)) {
        const float *a = T.pathPt + 3 * (P->first + k), *b = T.pathPt + 3 * (P->first + (k + 1) % P->n);
        float mx = (a[0] + b[0]) * .5f, mz = (a[2] + b[2]) * .5f, hx = atan2f(b[2] - a[2], b[0] - a[0]); int mr = 0;
        if (hypotf(mx - T.pathPt[3 * P->first], mz - T.pathPt[3 * P->first + 2]) > 1e5f) continue;
        run(mx, mz, hx, 0, argc > 4 ? (float)atof(argv[4]) : 40.f, &mr); n++;
        if (mr > 60) { hits++; if (mr > worst) { worst = mr; wx = mx; wz = mz; } printf("  (%.1f; %.1f) стояли %.1f с\n", mx, mz, mr / 30.f); } }
    }
    printf("точек %d, со стоянием дольше 2 с: %d, худшая (%.1f; %.1f) %.1f с -> %s\n", n, hits, wx, wz, worst / 30.f, hits ? "FAIL" : "PASS"); return hits != 0; }
  float cx = (float)atof(argv[3]), cz = (float)atof(argv[4]); int mr = 0;
  float best = 1e30f, hx = 0.f; for (uint32_t p = 0; p < T.hd->nPath; p++) { const TrPath *P = &T.path[p];
    for (uint32_t k = 0; k < P->n; k++) { const float *a = T.pathPt + 3 * (P->first + k), *b = T.pathPt + 3 * (P->first + (k + 1) % P->n);
      float mx = (a[0] + b[0]) * .5f - cx, mz = (a[2] + b[2]) * .5f - cz, d = mx * mx + mz * mz; if (d < best) { best = d; hx = atan2f(b[2] - a[2], b[0] - a[0]); } } }
  if (best > 40.f * 40.f) { printf("рядом с (%.1f; %.1f) нет пешеходного пути (ближайший %.1f м)\n", cx, cz, sqrtf(best)); return 2; }
  run(cx, cz, hx, 1, 90.f, &mr); return mr > 60;
}
static int run(float cx, float cz, float hx, int verbose, float secs, int *outMax) {
  trafficReset(&T, &world);
  float gy; colGround(&world, cx, cz, 1e4f, -1e6f, &gy, 0);
  carInit(&player, NULL, &world, cx, gy, cz, hx); player.h = hx;
  float pp[3] = {player.x, player.y, player.z}, eye[3] = {player.x, player.y + 3, player.z - 7}, fw[3] = {0, 0, 1};
  static int runF[64]; memset(runF, 0, sizeof runF); int bad = 0, nearMax = 0, maxRun = 0;
  for (int fr = 0; fr < (int)(30 * secs); fr++) {
    trafficUpdate(&T, &world, &player, 0, pp, eye, fw, DT);
    int nearN = 0;
    for (int i = 0; i < T.maxPeds && i < 64; i++) { const TrPed *e = &T.ped[i];
      int st = e->mode == TRP_STAND && hypotf(e->x - player.x, e->z - player.z) < 6.f;
      runF[i] = st ? runF[i] + 1 : 0; if (st) nearN++; if (runF[i] > maxRun) maxRun = runF[i]; if (runF[i] == 61) bad++; }
    if (nearN > nearMax) nearMax = nearN;
  }
  if (verbose) printf("машина на (%.1f; %.1f), %.0f с: больше всего одновременно стоящих ближе 6 м %d, самое долгое стояние %.1f с, дольше 2 с: %d пешеходов -> %s\n", cx, cz, secs, nearMax, maxRun / 30.f, bad, bad ? "FAIL" : "PASS");
  *outMax = maxRun; return bad != 0;
}
