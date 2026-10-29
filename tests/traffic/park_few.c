// №стоящие (Sonnet-PS2, ps2-parked-cars-count-l1.yaml): у оригинала на L1 стоят 2 машины (модели пула с флагом стоянки, leveli.mfk:195-199), порт занимал
// ВСЕ места данных (L1 10). Гейт: занятых мест = min(моделей пула с флагом стоянки, мест) на каждом уровне, обе модели присутствуют (если мест хватает),
// пустые места без машины (вне мира, gone=1). Замер: вокруг 44 перекрёстков (глаз на центре, без отсечения по кадру, дальность 90 м) — стоящих рисуется, вызовов и
// треугольников на кадр. Красный: -DTRAFFIC_PARK_FEW_OLD=1 (все места заняты) обязан упасть.   park_few level.shr traffic.shr [ожидаемо занято, -1 = по правилу]
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "traffic.h"
static ColWorld world; static Traffic T;
static unsigned char *readAt(FILE *f, unsigned off, unsigned sz) { unsigned char *m = aligned_alloc(64, (sz + 63) & ~63u); fseek(f, off, SEEK_SET); if (fread(m, 1, sz, f) != sz) { free(m); return 0; } return m; }
static int calls;
static void count(void *u, const TrPiece *p, const void *v, const float m[16]) { (void)u; (void)p; (void)v; (void)m; calls++; }
int main(int argc, char **argv) {
  if (argc < 3) return 2;
  FILE *f = fopen(argv[1], "rb"); if (!f) return 2; unsigned char hdr[104]; if (fread(hdr, 1, 104, f) != 104) return 2;
  unsigned pvsOff = *(unsigned *)(hdr + 88), colOff = *(unsigned *)(hdr + 92), propOff = *(unsigned *)(hdr + 96);
  fseek(f, 0, SEEK_END); unsigned end = (unsigned)ftell(f); if (pvsOff > colOff && pvsOff < end) end = pvsOff; if (propOff > colOff && propOff < end) end = propOff;
  unsigned char *cm = readAt(f, colOff, end - colOff); fclose(f); if (!cm || colInit(&world, cm, end - colOff)) return 2;
  FILE *g = fopen(argv[2], "rb"); if (!g) return 2; fseek(g, 0, SEEK_END); unsigned ts = (unsigned)ftell(g); unsigned char *buf = readAt(g, 0, ts); fclose(g);
  if (!buf || trafficInitMem(&T, buf, ts, 0)) return 2;
  trafficReset(&T, &world);
  int slotsPark = 0; for (unsigned i = 0; i < T.hd->nSlot; i++) slotsPark += T.slot[i].park ? 1 : 0;
  int occ = 0, models = 0, seen[TR_MAXMODEL] = {0}, bad = 0;
  for (int i = 0; i < T.npark; i++) {
    int off = T.park[i].off;
    if (!off) { occ++; int m = T.parkd[i].model; if (m < TR_MAXMODEL && !seen[m]) { seen[m] = 1; models++; } }
    if (off && (T.park[i].car.x < 1e6f || !T.park[i].gone)) bad++;   // пустое место: машины нет, gone=1
  }
  int want = argc > 3 ? atoi(argv[3]) : -1; if (want < 0) want = slotsPark < T.npark ? slotsPark : T.npark;
  int parkModels = 0; { int s2[TR_MAXMODEL] = {0}; for (int i = 0; i < T.npark; i++) { int m = T.parkd[i].model; if (m < TR_MAXMODEL && !s2[m]) { s2[m] = 1; parkModels++; } } }
  int needModels = want < parkModels ? want : parkModels;
  T.drawDist = 90.f; double sp = 0, st = 0, sc = 0; int mp = 0, mt = 0, mc = 0, n = 0;
  for (unsigned j = 0; j < T.hd->nJunc; j++) {
    float eye[3] = {T.junc[j].x, T.junc[j].y + 3.f, T.junc[j].z}; T.drawnPark = 0; T.drawnTris = 0; calls = 0;
    trafficDrawCars(&T, eye, 0, count, 0);
    sp += T.drawnPark; st += T.drawnTris; sc += calls; if (T.drawnPark > mp) mp = T.drawnPark; if (T.drawnTris > mt) mt = T.drawnTris; if (calls > mc) mc = calls; n++;
  }
  printf("мест %d, моделей с флагом стоянки в пуле %d, занято %d (ожидалось %d), разных моделей %d (нужно >= %d), пустых с машиной %d\n", T.npark, slotsPark, occ, want, models, needModels, bad);
  printf("вокруг %d перекрёстков (90 м, без отсечения по кадру): стоящих в среднем %.2f (макс %d), вызовов %.1f (макс %d), треугольников %.0f (макс %d)\n", n, sp / n, mp, sc / n, mc, st / n, mt);
  int ok = occ == want && models >= needModels && !bad;
  printf("RESULT %s\n", ok ? "PASS" : "FAIL"); return ok ? 0 : 1;
}
