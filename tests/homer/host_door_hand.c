// Роб 17.10 (видео IMG_7282 3:21.2–3:21.4): «рука Гомера проходит сквозь дверь машины» при посадке. Замер на Маке: где кисть относительно борта
// на каждом кадре посадки при разных отступах точки у двери (homerSetDoorOut). Борт — плоскость −halfW машины; «в двери» — кисть ближе к оси машины,
// чем борт, пока дверь почти закрыта (open < 0,3). tests/homer/door_hand.sh [level.shr] [homer.shr]
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <ctype.h>
#include "homer.h"
static ColWorld world; static Car car; static float doorOpen;
static void onDoor(void *u, float o) { (void)u; doorOpen = o; }
static void onDone(void *u, int in) { (void)u; (void)in; }
static unsigned char *readAt(FILE *f, unsigned off, unsigned sz) {
  unsigned char *p = (unsigned char *)malloc(sz); if (!p) return 0;
  fseek(f, (long)off, SEEK_SET); if (fread(p, 1, sz, f) != sz) { free(p); return 0; } return p;
}
#define DT (1.f / 60.f)
static void stepCar(float dt) { CarInput ci = {0, 0, 0, 1}; carUpdate(&car, &world, &ci, dt); }
static int ieq(const char *a, const char *b) { for (; *a && *b; a++, b++) if (tolower((unsigned char)*a) != tolower((unsigned char)*b)) return 0; return !*a && !*b; }
int main(int argc, char **argv) {
  const char *lvl = argc > 1 ? argv[1] : "build/level.shr", *hom = argc > 2 ? argv[2] : "build/homer.shr";
  FILE *f = fopen(lvl, "rb"); if (!f) { printf("no %s\n", lvl); return 1; }
  unsigned char hdr[104]; if (fread(hdr, 1, 104, f) != 104 || memcmp(hdr, "SHR7", 4)) { printf("bad level\n"); return 1; }
  const float *hd = (const float *)(hdr + 12); float spx = hd[6], spy = hd[7], spz = hd[8], sph = hd[9];
  unsigned pvsOff = *(unsigned *)(hdr + 88), colOff = *(unsigned *)(hdr + 92), propOff = *(unsigned *)(hdr + 96);
  fseek(f, 0, SEEK_END); unsigned end = (unsigned)ftell(f); if (pvsOff > colOff && pvsOff < end) end = pvsOff; if (propOff > colOff && propOff < end) end = propOff;
  unsigned char *cm = readAt(f, colOff, end - colOff); fclose(f);
  if (!cm || colInit(&world, cm, end - colOff)) { printf("COL1 failed\n"); return 1; }
  SkinModel *m = skinLoad(hom); if (!m) { printf("no %s\n", hom); return 1; }
  static Homer H; if (homerInit(&H, m)) { printf("homerInit failed\n"); return 1; }
  int nj = (int)m->h->nJoints, jr = -1, jl = -1;
  for (int j = 0; j < nj; j++) { const char *n = m->j[j].name; if (strstr(n, "and") || strstr(n, "rist")) printf("  сустав %d %s\n", j, n);
    if (ieq(n, "Hand_R") || ieq(n, "R_Hand") || ieq(n, "RightHand") || ieq(n, "Wrist_R")) jr = j; if (ieq(n, "Hand_L") || ieq(n, "L_Hand") || ieq(n, "Wrist_L")) jl = j; }
  if (argc > 3) jr = atoi(argv[3]);
  if (jr < 0) { printf("правая кисть не найдена — укажите номер сустава третьим аргументом\n"); return 1; }
  printf("кисть: правая %d (%s), левая %d\n", jr, m->j[jr].name, jl);
  static const float offs[] = {0.f, .10f, .12f, .15f, .20f};
  for (int oi = 0; oi < 5; oi++) {
    homerSetDoorOut(offs[oi]);
    carInit(&car, NULL, &world, spx, spy, spz, sph); for (int i = 0; i < 120; i++) stepCar(DT);
    float fx = sinf(car.h), fz = cosf(car.h), rx = -fz, rz = fx, hw = car.p.halfW;
    HomerCar hc; homerCarFrom(&hc, &car, .62f);
    homerPlace(&H, &world, car.x - rx * 2.6f, car.y + 1.f, car.z - rz * 2.6f, car.h);   // слева от машины (сторона водителя), подходит сам
    HomerCarCb cb = {onDoor, onDone, 0}; doorOpen = 0.f;
    if (!homerEnterCar(&H, &hc, &cb)) { printf("отступ %.2f: не садится\n", offs[oi]); continue; }
    float t = 0.f, worst = -9.f, worstT = 0.f, worstAlong = 0.f, worstUp = 0.f, worstOpen = 0.f, minSide = 9.f; int nIn = 0, n = 0;
    while (H.state != HS_IN_CAR && t < 8.f) {
      HomerInput in; memset(&in, 0, sizeof in); in.camYaw = car.h;
      homerCarFrom(&hc, &car, .62f); homerUpdate(&H, &world, &hc, &in, DT); homerPose(&H); t += DT;
      if (H.state != HS_GET_IN || H.phase != 0) continue;   // открывание двери снаружи (фаза 0); закрывание изнутри — кисть в салоне по делу
      ScePspFMatrix4 pal[SKIN_MAXJ], wj[SKIN_MAXJ]; skinPalette(m, H.xf, pal, wj);
      for (int s = 0; s < 2; s++) { int j = s ? jl : jr; if (j < 0) continue;
        float mx = wj[j].w.x, my = wj[j].w.y, mz = wj[j].w.z;
        float wx = H.place.x.x * mx + H.place.y.x * my + H.place.z.x * mz + H.place.w.x, wy = H.place.x.y * mx + H.place.y.y * my + H.place.z.y * mz + H.place.w.y,
              wz = H.place.x.z * mx + H.place.y.z * my + H.place.z.z * mz + H.place.w.z;
        float dx = wx - car.x, dz = wz - car.z, side = dx * rx + dz * rz, along = dx * fx + dz * fz, up = wy - car.y;
        float pen = side + hw;   // > 0 — кисть ближе к оси машины, чем борт (слева борт на −hw)
        if (getenv("DH_TRACE") && s == 0 && oi == 0) printf("    t %.2f дверь %.2f кисть: борт %+.3f вдоль %.2f высота %.2f\n", t, doorOpen, pen, along, up);
        if (doorOpen < .3f && up > .2f && up < 1.6f && fabsf(along) < 1.6f) { n++; if (pen > 0.f) nIn++; if (pen > worst) { worst = pen; worstT = t; worstAlong = along; worstUp = up; worstOpen = doorOpen; } }
        if (side < minSide) minSide = side; }
    }
    printf("отступ %.2f м: кадров с почти закрытой дверью %d, кисть внутри борта %d, глубже всего %.3f м (t %.2f, вдоль %.2f, высота %.2f, дверь %.2f); посадка %s\n",
           offs[oi], n, nIn, worst, worstT, worstAlong, worstUp, worstOpen, H.state == HS_IN_CAR ? "дошла" : "НЕ дошла");
  }
  return 0;
}
