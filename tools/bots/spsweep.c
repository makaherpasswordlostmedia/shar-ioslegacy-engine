// spsweep — заезды на стейтпропы (кусты, будки, барьеры, ящики...) со всех сторон и на разных скоростях (ночь 11.10, пункты Роба:
// «кусты проезжаются/перелетаются мягко», барьеры, будка). Мир один (снимок), на каждый случай — загрузка снимка, машина в 25 м от
// предмета, курсом на его центр, держит скорость; смотрим 6 с. Ничего в игре не меняет.
//   spsweep LEVEL HOMER MSN [--speeds 10,22,30] [--angles 8] [--cls N] [--max N]
// Разбор 11.10 (КОЛЛИЗИИ_НОЧЬ_РАЗБОР): каждый заезд идёт ДВАЖДЫ — с предметом и БЕЗ него (экземпляр отключён): «застряла/подбросило» без предмета —
// вина окружения (стена, склон, бордюр на разгоне), только с предметом — вина предмета. Строки SP2: предмет, тип, cls, x, z, угол°, скорость,
// исход С, исход БЕЗ, макс.vy с/без, подъём с/без, скорость после, расстояние в конце, состояние изменилось, полуразмеры типа h x y z, масса; итог SP2SUM: cls, случаев, застряла с,
// застряла без, застряла только с предметом, подбросило с, подбросило без, подбросило только с предметом, перевернулась.
// (прежнее описание, строки SP — в ночном tools/bots/spsweep.c ветки night-final)
// Строки: SP<TAB>предмет<TAB>тип<TAB>cls<TAB>atc<TAB>x<TAB>z<TAB>угол°<TAB>скорость<TAB>исход<TAB>макс.vy<TAB>макс.подъём<TAB>скорость_после<TAB>состояние_изменилось<TAB>дистанция_конец
// исход: ok (проехала/ушла дальше 8 м за предмет), застряла (стоит < 1,5 м/с дольше 1,2 с у предмета), подбросило (подъём над ездой > 1,2 м или vy > 4),
// перевернулась (крен > 70°), мимо (не дошла: стена на пути), нет_опоры. Итог: SPSUM<TAB>cls<TAB>случаев<TAB>застряла<TAB>подбросило<TAB>перевернулась
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "world.h"
static BotWorld W;
typedef struct { const char *res; float maxVy, maxUp, vAfter, endDist; int changed; float minD; int passed; } Res;
// один заезд (скорость v, курс a, предмет i), без предмета — тот же заезд с отключённым экземпляром: застревание из-за окружения, а не предмета
// «без предмета» убирает и его собственные объёмы COL1 (кусты, фонари, изгороди лежат в COL1 отдельно от SPR1): коробка или цилиндр, которые
// касаются круга предмета (радиус rad, центр c; расстояние от центра до ящика по его осям / до цилиндра по горизонтали меньше rad + 0.3 м). Чужие
// стены рядом (перила моста, заборы) остаются: иначе контроль снимал бы окружение. mode 1 — обнулить размеры, 0 — вернуть
#define CARVE_MAX 256
static struct { int kind; unsigned idx; float h[3], r, hl; } carved[CARVE_MAX]; static int ncarved;
static float boxDist(const ColBox *b, const float c[3]) {
  float d[3] = {c[0] - b->c[0], c[1] - b->c[1], c[2] - b->c[2]}, s2 = 0.f; const float *ax[3] = {b->ax, b->ay, b->az};
  for (int k = 0; k < 3; k++) { float u = d[0] * ax[k][0] + d[1] * ax[k][1] + d[2] * ax[k][2], e = fabsf(u) - b->h[k]; if (e > 0.f) s2 += e * e; }
  return sqrtf(s2);
}
static void carve(const float c[3], float rad, int mode) {
  ColWorld *w = (ColWorld *)bwCol();
  if (mode) {
    ncarved = 0;
    for (uint32_t j = 0; j < w->nbox && ncarved < CARVE_MAX; j++) { ColBox *b = (ColBox *)&w->box[j]; if (boxDist(b, c) < rad + .3f) {
        if (getenv("SP_DBG")) fprintf(stderr, "  box %u c=(%.1f,%.1f,%.1f) h=(%.1f,%.1f,%.1f) mat=%u\n", j, b->c[0], b->c[1], b->c[2], b->h[0], b->h[1], b->h[2], (unsigned)b->pad); carved[ncarved].kind = 0; carved[ncarved].idx = j; memcpy(carved[ncarved].h, b->h, sizeof b->h); memset(b->h, 0, sizeof b->h); ncarved++; } }
    for (uint32_t j = 0; j < w->ncyl && ncarved < CARVE_MAX; j++) { ColCyl *q = (ColCyl *)&w->cyl[j]; if (hypotf(q->c[0] - c[0], q->c[2] - c[2]) < q->r + rad + .3f && fabsf(q->c[1] - c[1]) < q->halfLen + rad + 1.f) {
        if (getenv("SP_DBG")) fprintf(stderr, "  cyl %u c=(%.1f,%.1f,%.1f) r=%.1f hl=%.1f\n", j, q->c[0], q->c[1], q->c[2], q->r, q->halfLen); carved[ncarved].kind = 1; carved[ncarved].idx = j; carved[ncarved].r = q->r; carved[ncarved].hl = q->halfLen; q->r = 0.f; q->halfLen = 0.f; ncarved++; } }
    if (getenv("SP_DBG")) fprintf(stderr, "carve rad %.1f at %.1f %.1f: %d volumes\n", rad, c[0], c[2], ncarved);
  } else for (int k = 0; k < ncarved; k++) {
    if (carved[k].kind == 0) memcpy(((ColBox *)&w->box[carved[k].idx])->h, carved[k].h, sizeof carved[k].h);
    else { ColCyl *q = (ColCyl *)&w->cyl[carved[k].idx]; q->r = carved[k].r; q->halfLen = carved[k].hl; }
  }
}
static float rad_; static int ctrlMode = 3;   // SP_CTRL=1 — убрать только SPR1-экземпляр, 2 — только объёмы COL1, 3 (по умолчанию) — оба
static Res runCase(BotSnap *snap, unsigned i, float c[3], float a, float v, int without) {
  Res R = {"ok", 0, 0, 0, 0, 0, 1e9f, 0};
  float dx = sinf(a), dz = cosf(a), D = 25.f, sx = c[0] - dx * D, sz = c[2] - dz * D, gy;
  bwLoad(&W, snap);
  if (without) { if (ctrlMode & 1) { W.sp.run[i].alive = 0; W.sp.run[i].colOn = 0; } if (ctrlMode & 2) carve(c, rad_, 1); }
  if (!colGround(bwCol(), sx, sz, c[1] + 3.f, c[1] - 6.f, &gy, 0)) { R.res = "нет_опоры"; if (without && (ctrlMode & 2)) carve(c, rad_, 0); return R; }
  { float p0[3] = {sx, gy + .8f, sz}, p1[3] = {c[0] - dx * 3.f, gy + .8f, c[2] - dz * 3.f}, q0[3] = {sx, gy + 1.4f, sz}, q1[3] = {p1[0], gy + 1.4f, p1[2]};
    if (colRayFrac(bwCol(), p0, p1, 0) < 1.f || colRayFrac(bwCol(), q0, q1, 0) < 1.f) { R.res = "мимо"; if (without && (ctrlMode & 2)) carve(c, rad_, 0); return R; } }
  bwPlace(&W, sx, gy + .3f, sz, a); carSetSpeed(&W.car, v * .6f);
  unsigned char st0 = W.sp.run[i].state; float baseY = gy, stillT = 0.f;
  for (int f = 0; f < 360; f++) {
    bwStep(&W, 0, 0.f, W.car.v < v ? -1.f : 0.f);
    float d = hypotf(W.car.x - c[0], W.car.z - c[2]), along = (W.car.x - c[0]) * dx + (W.car.z - c[2]) * dz;
    if (d < R.minD) R.minD = d; if (along > 8.f) R.passed = 1;
    if (fabsf(W.car.vy) > R.maxVy) R.maxVy = fabsf(W.car.vy);
    float up = W.car.y - baseY; if (d < 12.f && up > R.maxUp) R.maxUp = up;
    if (d < 10.f && fabsf(W.car.v) < 1.5f && W.car.x == W.car.x) stillT += 1.f / 60.f; else if (fabsf(W.car.v) >= 1.5f) stillT = 0.f;
    if (stillT > 1.2f && !R.passed) { R.res = R.minD < 4.f ? "застряла" : "мимо"; break; }
    if (W.sp.run[i].state != st0) R.changed = 1;
    R.endDist = d; R.vAfter = W.car.v;
  }
  if (strcmp(R.res, "ok") == 0) { if (R.maxUp > 1.2f || R.maxVy > 4.f) R.res = "подбросило"; if (W.car.roll > 1.22f || W.car.roll < -1.22f) R.res = "перевернулась"; if (!R.passed && R.minD > 6.f) R.res = "мимо"; }
  if (W.sp.run[i].state != st0) R.changed = 1;
  if (without && (ctrlMode & 2)) carve(c, rad_, 0);
  return R;
}
int main(int argc, char **argv) {
  if (argc < 4 || bwData(argv[1], argv[2], argv[3])) { fprintf(stderr, "spsweep: нет данных\n"); return 2; }
  float speeds[8] = {10.f, 22.f, 30.f}; int nsp = 3, nang = 8, onlyCls = -1, maxInst = 100000;
  for (int i = 4; i < argc; i++) {
    if (!strcmp(argv[i], "--speeds") && i + 1 < argc) { nsp = 0; for (char *p = strtok(argv[++i], ","); p && nsp < 8; p = strtok(0, ",")) speeds[nsp++] = (float)atof(p); }
    else if (!strcmp(argv[i], "--angles") && i + 1 < argc) nang = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--cls") && i + 1 < argc) onlyCls = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--max") && i + 1 < argc) maxInst = atoi(argv[++i]);
  }
  if (getenv("SP_CTRL")) ctrlMode = atoi(getenv("SP_CTRL"));
  bwNew(&W); if (!W.haveSP) { printf("SPSUM\t-\t0\t0\t0\t0\n"); return 0; }
  BotSnap snap; bwSaveAlloc(&W, &snap); bwSave(&W, &snap);
  // SP2: предмет, тип, cls, x, z, угол, скорость, исход С предметом, исход БЕЗ предмета, максимальный vy/подъём с предметом и без, скорость после, расстояние в конце, предмет изменил состояние
  long sum[16][8]; memset(sum, 0, sizeof sum);   // 0 случаев, 1 застряла с, 2 застряла без, 3 застряла только с, 4 подбросило с, 5 подбросило без, 6 подбросило только с, 7 перевернулась с
  for (unsigned i = 0; i < W.sp.ninst && (int)i < maxInst; i++) {
    const SpType *T = &W.sp.type[W.sp.inst[i].type]; int cls = T->cls; if (onlyCls >= 0 && cls != onlyCls) continue;
    float c[3], rad; spBounds(&W.sp, i, c, &rad); rad_ = rad;
    for (int ai = 0; ai < nang; ai++) for (int si = 0; si < nsp; si++) {
      float a = ai * 6.2831853f / nang, v = speeds[si];
      Res w = runCase(&snap, i, c, a, v, 0);
      if (!strcmp(w.res, "мимо") || !strcmp(w.res, "нет_опоры")) continue;
      Res o = runCase(&snap, i, c, a, v, 1);
      if (cls >= 0 && cls < 16) { long *S = sum[cls]; S[0]++; int sw = !strcmp(w.res, "застряла"), so = !strcmp(o.res, "застряла"), lw = !strcmp(w.res, "подбросило"), lo = !strcmp(o.res, "подбросило");
        S[1] += sw; S[2] += so; S[3] += sw && !so; S[4] += lw; S[5] += lo; S[6] += lw && !lo; S[7] += !strcmp(w.res, "перевернулась"); }
      if (strcmp(w.res, "ok"))
        printf("SP2\t%u\t%u\t%d\t%.1f\t%.1f\t%.0f\t%.0f\t%s\t%s\t%.1f\t%.1f\t%.2f\t%.2f\t%.1f\t%.1f\t%d\t%.1f %.1f %.1f\t%.0f\n", i, W.sp.inst[i].type, cls, c[0], c[2], a * 57.2958f, v, w.res, o.res, w.maxVy, o.maxVy, w.maxUp, o.maxUp, w.vAfter, w.endDist, w.changed, T->h[0], T->h[1], T->h[2], T->mass);
    }
  }
  for (int k = 0; k < 16; k++) if (sum[k][0]) printf("SP2SUM\t%d\t%ld\t%ld\t%ld\t%ld\t%ld\t%ld\t%ld\t%ld\n", k, sum[k][0], sum[k][1], sum[k][2], sum[k][3], sum[k][4], sum[k][5], sum[k][6], sum[k][7]);
  return 0;
}
