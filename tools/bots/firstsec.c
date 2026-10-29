// firstsec — №537: стоимость кадров сразу после старта миссии (машины ИИ миссии, первая перепланировка, постановка на дорогу).
//   firstsec LEVEL PLAYER MSN MISSION_ID [FRAMES] [REPS]   MISSION_ID — строка id ("sr3"); ввод пустой; печатает мкс покадрово (среднее по REPS) блоками и пики
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "world.h"
static BotWorld W;
static double now(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec * 1e6 + t.tv_nsec / 1e3; }
int main(int argc, char **argv) {
  if (argc < 5 || bwData(argv[1], argv[2], argv[3])) { fprintf(stderr, "usage: firstsec LEVEL PLAYER MSN MISSION_ID [FRAMES] [REPS]\n"); return 2; }
  int frames = argc > 5 ? atoi(argv[5]) : 600, reps = argc > 6 ? atoi(argv[6]) : 5; bwNew(&W); if (!W.haveMsn) return 3;
  const MsnFile *F = &W.msn.f; int mi = -1;
  for (unsigned i = 0; i < F->nmissions; i++) if (!strcmp(msn_str(F, F->missions[i].id), argv[4])) mi = (int)i;
  if (mi < 0) { fprintf(stderr, "нет миссии %s\n", argv[4]); return 3; }
  if (F->missions[mi].flags & (MSN_MF_BONUS | MSN_MF_STREETRACE | MSN_MF_GAMBLE | MSN_MF_BONUSMISSION)) msn_start_bonus(&W.msn.rt, mi); else msn_start_mission(&W.msn.rt, mi, 0);
  BotSnap s; bwSaveAlloc(&W, &s); bwSave(&W, &s);
  typedef struct { unsigned b; float ax, ay; } Fr; Fr *in = 0; int nin = 0;
  if (getenv("FS_IN")) { FILE *fi = fopen(getenv("FS_IN"), "r"); char ln[256]; int cap = 0; while (fi && fgets(ln, sizeof ln, fi)) { if (ln[0] == '#') continue; int k; unsigned b; float ax, ay;
      if (sscanf(ln, "%d %x %f %f", &k, &b, &ax, &ay) != 4) continue; for (int i = 0; i < k; i++) { if (nin == cap) { cap = cap ? cap * 2 : 4096; in = realloc(in, sizeof(Fr) * (size_t)cap); } in[nin++] = (Fr){b, ax, ay}; } } if (fi) fclose(fi); }
  if (getenv("FS_FROM")) {   // профиль окна кадров: дойти до FROM, снять снимок, крутить окно FROM..TO много раз (для sample)
    int from = atoi(getenv("FS_FROM")), to = atoi(getenv("FS_TO")), reps2 = atoi(getenv("FS_REPS"));
    for (int f = 0; f < from; f++) { if (f < nin) bwStep(&W, in[f].b, in[f].ax, in[f].ay); else bwStep(&W, 0, 0.f, 0.f); }
    BotSnap s2; bwSaveAlloc(&W, &s2); bwSave(&W, &s2); double a = now();
    for (int r = 0; r < reps2; r++) { bwLoad(&W, &s2); for (int f = from; f < to; f++) { if (f < nin) bwStep(&W, in[f].b, in[f].ax, in[f].ay); else bwStep(&W, 0, 0.f, 0.f); } }
    printf("окно %d..%d x %d: %.1f мкс на кадр\n", from, to, reps2, (now() - a) / ((double)reps2 * (to - from))); return 0; }
  double *t = calloc((size_t)frames, sizeof(double)); int ncar0 = 0; int *pl = calloc((size_t)frames, sizeof(int)); int maxpl = 0, maxplf = -1, plTot = 0;
  for (int r = 0; r < reps; r++) {
    bwLoad(&W, &s);
    for (int f = 0; f < frames; f++) { unsigned rp0 = 0; for (int c = 0; c < W.msn.cars.n; c++) rp0 += W.msn.cars.c[c].replans; double a = now(); if (f < nin) bwStep(&W, in[f].b, in[f].ax, in[f].ay); else bwStep(&W, 0, 0.f, 0.f); double b = now() - a; if (r == 0 || b < t[f]) t[f] = b; if (r == 0) { unsigned rp1 = 0; for (int c = 0; c < W.msn.cars.n; c++) rp1 += W.msn.cars.c[c].replans; pl[f] = (int)(rp1 - rp0); plTot += pl[f]; if (pl[f] > maxpl) { maxpl = pl[f]; maxplf = f; } } /* минимум по повторам: без шума планировщика */
      if (r == 0 && getenv("FS_CARS") && (f == 5 || f % 300 == 299 || f == frames - 1)) { printf("  кадр %d:", f); for (int c = 0; c < W.msn.cars.n; c++) if (W.msn.cars.c[c].on) printf(" %s/%s v%.2f x%.2f z%.2f", W.msn.cars.c[c].name, mcModeName[W.msn.cars.c[c].mode], W.msn.cars.c[c].car.v, W.msn.cars.c[c].car.x, W.msn.cars.c[c].car.z); printf(" | игрок пешком %d\n", gameOnFoot(&W.G)); }
      if (r == 0 && f == frames - 1) for (int c = 0; c < W.msn.cars.n; c++) ncar0 += W.msn.cars.c[c].on; }
  }
  double tot[8] = {0}; int nb = 0;
  printf("миссия %s (индекс %d), машин миссии в конце %d, мкс на кадр (минимум из %d повторов), блоки по 15 кадров:\n", argv[4], mi, ncar0, reps);
  for (int f = 0; f < frames; f += 15) { double m = 0, mx = 0; int n = 0; for (int k = f; k < f + 15 && k < frames; k++) { m += t[k]; n++; if (t[k] > mx) mx = t[k]; }
    if (f < 180 || f % 60 == 0) printf("  кадры %3d–%3d: среднее %6.0f, максимум %6.0f\n", f, f + n - 1, m / n, mx); }
  { int idx[12] = {0}; for (int q = 0; q < 12; q++) { double bm = -1; for (int k = 0; k < frames; k++) { int used = 0; for (int z = 0; z < q; z++) used |= idx[z] == k; if (!used && t[k] > bm) { bm = t[k]; idx[q] = k; } } }
    printf("самые долгие кадры:"); for (int q = 0; q < 12; q++) printf(" %d(%.0f)", idx[q], t[idx[q]]); printf("\n");
    for (int sec = 0; sec * 60 < frames && sec < 30; sec++) { double m = 0; int n = 0; for (int k = sec * 60; k < (sec + 1) * 60 && k < frames; k++) { m += t[k]; n++; } printf("  сек %2d: среднее %.0f\n", sec, m / n); } }
  printf("перепланировок всего %d, больше всего в кадр: %d (кадр %d)\n", plTot, maxpl, maxplf);
  double first = 0, rest = 0; for (int k = 0; k < 60 && k < frames; k++) first += t[k]; for (int k = 120; k < frames; k++) rest += t[k];
  printf("ИТОГ: первая секунда (кадры 0–59) %.0f мкс/кадр, с 3-й секунды %.0f мкс/кадр\n", first / (frames < 60 ? frames : 60), frames > 120 ? rest / (frames - 120) : 0.0);
  (void)tot; (void)nb; return 0;
}
