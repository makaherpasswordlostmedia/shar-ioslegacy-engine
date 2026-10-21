// Горбы-капсулы (тупик миссии m0, миссионер Б2 28.09): зарытая пологая капсула поперёк дороги не стена — колёса въезжают.
// Тот же код машины и коллизии, что на PSP (viewer/car.c, col.c), уровень build/level.shr. Случаи из данных, без координат
// в движке: сами места находятся по COL1 (капсулы не-кусты, лежащие под полом, с пологим верхом над дорогой).
//   A) common_gens51 у x 129 z 140..165 (тупик m0 на пути к Kwik-E-Mart): машина с востока на 5/10/15/20 м/с, курс ±10°
//      обязана переехать (x < 124 за 6 с)
//   B) не пропускать лишнего: те же заезды в высокую капсулу-не-куст (верх выше пола + 0.75 м) — остановка
//   (кусты — свои правила, tests/foliage; правило горба их не касается)
//   D) правка Роба 200 (03.10): тот же горб медленно (2–4 м/с, как едет Роб «через арку к стеклу»), разные z и курсы: машина
//      обязана переехать (x < 124 за 14 с) без толчков вбок — сдвиг кузова сверх скорости поперёк курса за кадр не больше 0,1 м,
//      вдоль — не больше 0,5 м (было: центр перевалил ось — капсула под машиной становилась стеной, срез толстым концом
//      выталкивал кузов вдоль изгороди до 5 м за кадр; оригинал, близнец arch.py, переезжает ровно)
//   E) правка 200, остаток сверки tests/humps/sweep.c (03.10): углы заборов. У острого выпуклого угла (твёрдый клин уже 85°) толстая
//      полоса звена за линией выходит на лицо соседа: машина, огибающая угол вдоль соседа, получала толчок вдоль забора (L1 Landmrk
//      у АЭС 1,7 м/кадр, L3 1,3). По данным, все острые выпуклые углы заборов уровня (кроме изгородей): машина 3 м/с вдоль лица каждого
//      звена к углу и за угол (зазор 0,4 м); толчок вбок от самих звеньев угла (тот же кадр без них — не толкает) не больше 0,1 м/кадр
//   G) правка 200, остаток сверки (03.10): все горбы уровня наискось. Решение «горб/стена» по одной точке пола перескакивало у кузова
//      с креном, и срез капсулы, уже под кузовом, толкал его вдоль изгороди (L1 bushesShape1 0,53, common_gens51 0,19, L2 common306
//      0,96 м/кадр). По данным: каждая лежачая длинная капсула-не-куст, 5 мест вдоль оси, с горбатой стороны (верх над землёй не
//      выше COL_HUMP), 2 и 4 м/с, курс 0 и ±20°, старт не за забором; толчок от самой капсулы (тот же кадр без неё — не толкает)
//      вбок не больше 0,1 м/кадр, вперёд — не больше 0,5
//   H) стены остаются стенами (правка 200, остаток сверки): тот же горб со стороны-стены (верх выше земли больше COL_HUMP) и звенья
//      острых углов заборов в лоб, 5 и 10 м/с (засчитываются заезды, где машина разогналась до стены не меньше 3 м/с и не упала с
//      уступа): машина остаётся со своей стороны, не разгоняется (после удара не быстрее подъезда и заданной скорости + 0,5 м/с: газ держит до неё) и не подлетает (вверх
//      не больше 3 м/с) — память горба и правило угла не делают стену проходимой или пружиной
//   Красные: -DFENCE_BEYOND_FRONT=1 (E), -DHUMP_NO_KEEP=1 (G), прежние col.c/car.c (CAR_C, COL_C) — обе
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "car.h"
static ColWorld W; static int fails;
// HUMPS_CAR=имя: те же случаи на параметрах другой машины из .con (без переменной — машина по умолчанию, как раньше)
static CarParams carP; static const CarParams *carPP;
static void check(const char *n, int ok) { printf("%s %s\n", ok ? "ok" : "FAIL", n); fails += !ok; }
static int drive(float x, float z, float h, float v, float secs, float *ex, float *ez) {
  Car c; float g; if (!colGround(&W, x, z, 50, -50, &g, 0)) return -1;
  carInit(&c, carPP, &W, x, g, z, h); for (int k = 0; k < 20; k++) { CarInput in = {0}; carUpdate(&c, &W, &in, 1 / 60.f); }
  carSetSpeed(&c, v);
  for (int f = 0; f < (int)(secs * 60); f++) { CarInput in = {1, 0, 0}; if (c.v > v) in.throttle = 0; carUpdate(&c, &W, &in, 1 / 60.f); }
  *ex = c.x; *ez = c.z; return 0;
}
static float maxPush, maxFwd;   // D: наибольший сдвиг кузова за кадр сверх скорости: поперёк курса и вдоль (м)
static int driveSlow(float x, float z, float h, float v, float secs, float *ex, float *ez) {
  Car c; float g; if (!colGround(&W, x, z, 50, -50, &g, 0)) return -1;
  carInit(&c, carPP, &W, x, g, z, h); for (int k = 0; k < 20; k++) { CarInput in = {0}; carUpdate(&c, &W, &in, 1 / 60.f); }
  carSetSpeed(&c, v); maxPush = maxFwd = 0.f;
  for (int f = 0; f < (int)(secs * 60); f++) {
    CarInput in = {1, 0, 0}; if (c.v > v) in.throttle = 0;
    float px = c.x, pz = c.z, vx = c.vel[0], vz = c.vel[2];
    carUpdate(&c, &W, &in, 1 / 60.f);
    float dx = c.x - px - vx / 60.f, dz = c.z - pz - vz / 60.f, fx = sinf(c.h), fz = cosf(c.h);
    float ds = fabsf(-fz * dx + fx * dz), dfw = fabsf(fx * dx + fz * dz);   // поперёк курса и вдоль
    if (c.x < 124.f) break;                                   // переехал — дальше не меряем (склон к улице)
    if (ds > maxPush) maxPush = ds; if (dfw > maxFwd) maxFwd = dfw;
    if (getenv("HUMPS_TRACE") && (ds > .1f || dfw > .3f)) printf("    t %.2f pos %.2f %.2f %.2f v %.2f %.2f %.2f толчок %.2f (%.2f %.2f) ct %d wallV %.1f prim %d#%u reverts %d recov %d\n", f / 60.f,
      c.x, c.y, c.z, c.vel[0], c.vel[1], c.vel[2], ds, dx, dz, c.contacts, c.wallV, c.wallV > 0 ? c.wallType : -1, c.wallV > 0 ? c.wallIdx : 0, c.reverts, c.recoveries);
  }
  *ex = c.x; *ez = c.z; return 0;
}
// старт за забором (в пределах звена, забор в слое кузова у земли, не изгородь) — место недостижимо ездой по земле
static int behindFence(float x, float z, float y) {
  for (unsigned i = 0; i < W.nseg; i++) {
    const ColSeg *G = &W.seg[i]; float dx = G->b[0] - G->a[0], dz = G->b[1] - G->a[1], L = sqrtf(dx * dx + dz * dz);
    if (L < 1e-4f || G->y1 < y + 0.5f || G->y0 > y + 1.5f || G->y0 < COL_SEG_FOL_Y0) continue;
    float ox = x - G->a[0], oz = z - G->a[1], t = (ox * dx + oz * dz) / L, u = ox * G->n[0] + oz * G->n[1];
    if (t >= 0.f && t <= L && u < 0.f && u > -10.f) return 1;
  }
  return 0;
}
// заезд с абляцией: v м/с, кадров fr; на каждом кадре со сдвигом кузова сверх скорости больше 0,1 вбок (или 0,5 вперёд) тот же кадр
// повторяется без примитивов off() — толчок их, если без них сдвига нет. Возврат: наибольший их толчок вбок (*fw — вперёд)
typedef void (*Toggle)(int on);
// Толчок на стеновой стороне капсулы (откос выше порога горба, замеры col.c humpSide) — не езда по горбу: стена по замыслу
// (col.c: «с одной стороны горб 0.3–0.5 м, с другой откос 2–3 м, там стена остаётся»). Прохождение уступа колесом (6d018af) уводит
// заезд с горбовой стороны на другую (сверзился с террасы к подножию насыпи) — такой толчок считается отдельно, не как горб.
typedef int (*SideFn)(const Car *k);
static int gWallJolts;
static float driveAbl(float x, float z, float h, float v, int frames, Toggle off, float *fw, int *rev, SideFn wall) {
  Car c; float g; *fw = 0.f; *rev = 0;
  if (!colGround(&W, x, z, 1e6f, -1e6f, &g, 0)) return -1.f;
  carInit(&c, carPP, &W, x, g, z, h); for (int k = 0; k < 20; k++) { CarInput in = {0}; carUpdate(&c, &W, &in, 1 / 60.f); }
  carSetSpeed(&c, v); int r0 = c.reverts + c.recoveries; float mx = 0.f;
  for (int f = 0; f < frames; f++) {
    CarInput in = {1, 0, 0}; if (c.v > v) in.throttle = 0;
    float px = c.x, pz = c.z, vx = c.vel[0], vz = c.vel[2]; Car prev = c;
    if (getenv("HUMPS_G")) printf("== f %d pos %.3f %.3f %.3f vel %.2f %.2f %.2f h %.2f wh %d body %d ct %d rev %d\n", f, c.x, c.y, c.z, c.vel[0], c.vel[1], c.vel[2], c.h, c.wheels, c.bodyHit, c.contacts, c.reverts);
    carUpdate(&c, &W, &in, 1 / 60.f);
    float dx = c.x - px - vx / 60.f, dz = c.z - pz - vz / 60.f, fx = sinf(c.h), fz = cosf(c.h);
    float lat = fabsf(-fz * dx + fx * dz), lon = fabsf(fx * dx + fz * dz);
    if (getenv("HUMPS_G") && (lat > .1f || lon > .5f)) printf("  G jolt f %d lat %.3f lon %.3f -> pos %.3f %.3f %.3f wh %d body %d ct %d revWhy %d pen %.3f\n", f, lat, lon, c.x, c.y, c.z, c.wheels, c.bodyHit, c.contacts, c.revWhy, c.pen);
    if (f >= 3 && (lat > .1f || lon > .5f)) {
      Car k = prev; off(1); carUpdate(&k, &W, &in, 1 / 60.f); off(0);
      float ex = k.x - px - vx / 60.f, ez = k.z - pz - vz / 60.f, lat2 = fabsf(-fz * ex + fx * ez), lon2 = fabsf(fx * ex + fz * ez);
      if (lat2 > .1f) lat = 0.f; if (lon2 > .5f) lon = 0.f;   // и без них толкает — не их толчок
      if ((lat > .1f || lon > .5f) && wall && wall(&prev)) { gWallJolts++; continue; }   // толкает только капсула, но со стеновой стороны
      if (lat > mx) mx = lat; if (lon > *fw) *fw = lon;
    }
  }
  *rev = c.reverts + c.recoveries != r0;
  return mx;
}
static unsigned offA, offB; static float offY[4];   // E: звенья угла выводятся из слоя кузова
static void offFence(int on) {
  ColSeg *A = (ColSeg *)&W.seg[offA], *B = (ColSeg *)&W.seg[offB];
  if (on) { offY[0] = A->y0; offY[1] = A->y1; offY[2] = B->y0; offY[3] = B->y1; A->y0 = B->y0 = 1e9f; A->y1 = B->y1 = 1e9f + 1.f; }
  else { A->y0 = offY[0]; A->y1 = offY[1]; B->y0 = offY[2]; B->y1 = offY[3]; }
}
static unsigned offC; static float offR[2];          // G: капсула без радиуса и длины
static void offCyl(int on) {
  ColCyl *C = (ColCyl *)&W.cyl[offC];
  if (on) { offR[0] = C->r; offR[1] = C->halfLen; C->r = 0.f; C->halfLen = 0.f; } else { C->r = offR[0]; C->halfLen = offR[1]; }
}

#ifndef HUMPS_G_WALLSIDE_OLD
#define HUMPS_G_WALLSIDE_OLD 0
#endif
static int cylWallSide(const Car *k) {   // машина (центр) на стороне капсулы offC, где верх торчит над землёй выше порога горба
  const ColCyl *C = &W.cyl[offC]; float axl = hypotf(C->axis[0], C->axis[2]); if (axl < 1e-4f) return 0;
  float ux = C->axis[0] / axl, uz = C->axis[2] / axl, L = 2.f * C->halfLen * axl;
  float t = (k->x - (C->c[0] - ux * L * .5f)) * ux + (k->z - (C->c[2] - uz * L * .5f)) * uz; if (t < 0.f) t = 0.f; if (t > L) t = L;
  float top = C->c[1] + C->axis[1] * ((t - L * .5f) / axl) + C->r, g;
  if (!colGround(&W, k->x, k->z, k->y + 1.f, -1e6f, &g, 0)) return 0;
  return top - g > fminf(COL_HUMP, C->r * (1.f - COL_WALK_NY));
}
int main(int argc, char **argv) {
  if (argc < 2) return 2;
  FILE *f = fopen(argv[1], "rb"); if (!f) return 2; fseek(f, 0, SEEK_END); long n = ftell(f); rewind(f);
  unsigned char *d = aligned_alloc(16, (n + 15) & ~15); if (fread(d, 1, n, f) != (size_t)n) return 2; fclose(f);
  unsigned co = *(unsigned *)(d + 92), po = *(unsigned *)(d + 96), pv = *(unsigned *)(d + 88), ce = (unsigned)n;
  if (po > co && po < ce) ce = po; if (pv > co && pv < ce) ce = pv;
  if (colInit(&W, d + co, ce - co)) return 2;
  { const char *e = getenv("HUMPS_CAR"); if (e && *e) { if (!carParamsFor(e, &carP)) { printf("FAIL: нет машины %s\n", e); return 2; } carPP = &carP; printf("машина: %s\n", e); } }
  // A: горб m0 — заезд с востока (курс −x = −π/2), старт в 14 м от оси капсулы
  int passA = 0, totA = 0;
  for (int vi = 0; vi < 4; vi++) for (int ai = -1; ai <= 1; ai++) {
    float v = 5.f + 5.f * vi, h = -1.5708f + ai * .1745f, ex, ez;
    if (drive(143.f, 160.2f, h, v, 6.f, &ex, &ez)) continue;
    totA++; passA += ex < 124.f;   // центр машины за дальним краем капсулы (x 127.1) с запасом корпуса
    printf("  горб m0: %2.0f м/с курс %+3.0f° -> x %.1f %s\n", v, ai * 10.f, ex, ex < 124.f ? "переехал" : "СТОИТ");
  }
  check("A: горб-капсула common_gens51 переезжается на всех скоростях и курсах", totA == 12 && passA == totA);
  // B и C: по данным — ближайшие к дороге капсулы: высокая не-куст и куст; заезд перпендикулярно оси на 10 м/с
  const float *best[2] = {0, 0}; float bestTop[2] = {0, 0}; int bestI[2] = {-1, -1};   // [0] — высокая не-куст
  for (unsigned i = 0; i < W.ncyl; i++) {
    const ColCyl *C = &W.cyl[i]; if (fabsf(C->axis[1]) > .3f || C->halfLen < 1.f) continue;
    int bush = C->pad[0] == 1.f; float g; if (!colGround(&W, C->c[0] + C->axis[2] * 6.f, C->c[2] - C->axis[0] * 6.f, C->c[1] + 3.f, C->c[1] - 6.f, &g, 0)) continue;
    float top = C->c[1] + C->r - g; if (top < (bush ? .8f : 1.2f) || top > 3.f) continue;   // B: верх выше пола + 1.2 м
    if (bestI[bush] < 0) { bestI[bush] = (int)i; best[bush] = C->c; bestTop[bush] = top; }
  }
  for (int k = 0; k < 1; k++) {
    if (bestI[k] < 0) { check(k ? "C: куст найден" : "B: высокая капсула найдена", 0); continue; }
    const ColCyl *C = &W.cyl[bestI[k]]; float px = -C->axis[2], pz = C->axis[0];   // поперёк оси
    float sx = C->c[0] + px * 8.f, sz = C->c[2] + pz * 8.f, h = atan2f(-px, -pz), ex, ez;
    drive(sx, sz, h, 10.f, 3.f, &ex, &ez);
    float across = (ex - C->c[0]) * px + (ez - C->c[2]) * pz;   // > 0 — осталась со своей стороны
    printf("  %s капсула %d, верх над полом %.2f м: сторона после заезда %.2f\n", k ? "куст" : "высокая", bestI[k], bestTop[k], across);
    check(k ? "C: куст сбоку не проезжается насквозь" : "B: высокая капсула держит машину", across > 0.f);
  }
  // D: правка 200 — медленно через горб к стеклу (x 127.4 z 158.1)
  int passD = 0, totD = 0; float worst = 0.f, worstF = 0.f;
  const float zs[4] = {157.5f, 158.5f, 159.5f, 161.f};
  for (int vi = 0; vi < 3; vi++) for (int zi = 0; zi < 4; zi++) for (int ai = -1; ai <= 1; ai++) {
    float v = 2.f + vi, h = -1.5708f + ai * .0873f, ex, ez;
    { const char *tr = getenv("HUMPS_ONLY"); if (tr) { float tv, tz, ta; if (sscanf(tr, "%f,%f,%f", &tv, &tz, &ta) == 3 && (tv != v || tz != zs[zi] || ta != ai)) continue; } }
    if (driveSlow(143.f, zs[zi], h, v, 14.f, &ex, &ez)) continue;
    int ok = ex < 124.f && maxPush <= .1f && maxFwd <= .5f; totD++; passD += ok; if (maxPush > worst) worst = maxPush; if (maxFwd > worstF) worstF = maxFwd;
    if (!ok || getenv("HUMPS_V")) printf("  горб медленно: %.0f м/с z %.1f курс %+2.0f° -> x %.1f z %.1f, толчок вбок %.2f, вперёд %.2f м/кадр %s\n", v, zs[zi], ai * 5.f,
                                         ex, ez, maxPush, maxFwd, ok ? "ok" : (ex < 124.f ? "ТОЛЧОК" : "СТОИТ"));
  }
  printf("  горб медленно: %d из %d, наибольший толчок вбок %.2f, вперёд %.2f м/кадр\n", passD, totD, worst, worstF);
  check("D: горб медленно (2–4 м/с) переезжается без толчков вбок (правка 200)", totD == 36 && passD == totD);
  // E: острые выпуклые углы заборов
  { int runs = 0, bad = 0, rv = 0; float worstE = 0.f; const float hl = 2.7f, hw = 1.45f;   // кузов машины уровня с запасом
    for (unsigned i = 0; i < W.nseg; i++) for (int ei = 0; ei < 2; ei++) {
      const ColSeg *A = &W.seg[i]; float Px = ei ? A->b[0] : A->a[0], Pz = ei ? A->b[1] : A->a[1];
      float ax = A->b[0] - A->a[0], az = A->b[1] - A->a[1], la = hypotf(ax, az); if (la < 1e-3f || A->y0 < COL_SEG_FOL_Y0) continue;
      float dix = ei ? -ax / la : ax / la, diz = ei ? -az / la : az / la;   // от угла внутрь звена i (по нему едет машина)
      for (unsigned j = 0; j < W.nseg; j++) for (int ej = 0; ej < 2; ej++) {
        const ColSeg *B = &W.seg[j]; float Qx = ej ? B->b[0] : B->a[0], Qz = ej ? B->b[1] : B->a[1];
        if (j == i || fabsf(Qx - Px) > 2e-3f || fabsf(Qz - Pz) > 2e-3f || B->y0 < COL_SEG_FOL_Y0) continue;
        float bx = B->b[0] - B->a[0], bz = B->b[1] - B->a[1], lb = hypotf(bx, bz); if (lb < 1e-3f) continue;
        float djx = ej ? -bx / lb : bx / lb, djz = ej ? -bz / lb : bz / lb, sx = dix + djx, sz = diz + djz;
        if (hypotf(sx, sz) < 0.02f || sx * (A->n[0] + B->n[0]) + sz * (A->n[1] + B->n[1]) > 0.f) continue;   // прямой стык, вогнутый
        if (dix * djx + diz * djz < cosf(85.f * 0.0174533f)) continue;                                       // клин не острый
        float Sx = Px + dix * (hl + 6.f) + A->n[0] * (hw + 0.4f), Sz = Pz + diz * (hl + 6.f) + A->n[1] * (hw + 0.4f), g;
        if (!colGround(&W, Sx, Sz, 1e6f, -1e6f, &g, 0)) continue;
        if (A->y1 < g + 0.5f || A->y0 > g + 1.4f || B->y1 < g + 0.5f || B->y0 > g + 1.4f || behindFence(Sx, Sz, g)) continue;
        offA = i; offB = j; float fw; int rev;
        float mx = driveAbl(Sx, Sz, atan2f(-dix, -diz), 3.f, 300, offFence, &fw, &rev, 0);
        if (mx < 0.f) continue;
        runs++; rv += rev; if (mx > .1f) { bad++; printf("  угол %.0f° звенья %u/%u (%.1f, %.1f): толчок вбок от угла %.2f м/кадр\n",
                                               acosf(dix * djx + diz * djz) * 57.2958f, i, j, Px, Pz, mx); }
        if (mx > worstE) worstE = mx;
      }
    }
    printf("  углы заборов: заездов %d, толчок вбок от звеньев угла > 0,1 м/кадр: %d (наибольший %.2f), с отменой/возвратом %d\n", runs, bad, worstE, rv);
    check("E: острые углы заборов — без толчка вдоль забора у угла (правка 200, остаток сверки)", bad == 0); }
  // G: все горбы уровня наискось
  { int runs = 0, bad = 0, rv = 0; float worstG = 0.f, worstGf = 0.f; gWallJolts = 0;
    for (unsigned i = 0; i < W.ncyl; i++) {
      const ColCyl *C = &W.cyl[i]; float axl = hypotf(C->axis[0], C->axis[2]);
      if (C->pad[0] == 1.f || C->halfLen <= 0.f || fabsf(C->axis[1]) > .3f || axl < 1e-4f || 2.f * C->halfLen * axl < COL_HUMP_LEN) continue;
      float ux = C->axis[0] / axl, uz = C->axis[2] / axl;
      for (int st = 1; st <= 5; st++) for (int side = -1; side <= 1; side += 2) {
        float t = (st / 6.f - .5f) * 2.f * C->halfLen, ax = C->c[0] + C->axis[0] * t, az = C->c[2] + C->axis[2] * t, top = C->c[1] + C->axis[1] * t + C->r;
        float px = -uz * side, pz = ux * side, sx = ax + px * (C->r + 5.f), sz = az + pz * (C->r + 5.f), g;
        if (!colGround(&W, sx, sz, top + 1.f, top - 6.f, &g, 0) || top - g > COL_HUMP || behindFence(sx, sz, g)) continue;
        for (int vi = 0; vi < 2; vi++) for (int ai = -1; ai <= 1; ai++) {
          offC = i; float fw; int rev;
          { const char *g = getenv("HUMPS_G");   // 388/377: один заезд G — HUMPS_G=cyl,место,сторона,м/с,курс° (разбор с -DCOL_DEBUG)
            if (g) { unsigned gi; int gst, gside, gv, ga;
              if (sscanf(g, "%u,%d,%d,%d,%d", &gi, &gst, &gside, &gv, &ga) == 5 && (gi != i || gst != st || gside != side || gv != (vi ? 4 : 2) || ga != ai * 20)) continue;
#ifdef COL_DEBUG
              { extern int colDebug; colDebug = 1; }
#endif
            } }
          float mx = driveAbl(sx, sz, atan2f(-px, -pz) + ai * 20.f * 0.0174533f, vi ? 4.f : 2.f, 360, offCyl, &fw, &rev, HUMPS_G_WALLSIDE_OLD ? 0 : cylWallSide);
#ifdef COL_DEBUG
          { extern int colDebug; colDebug = 0; }
#endif
          if (mx < 0.f) continue;
          runs++; rv += rev; if (mx > worstG) worstG = mx; if (fw > worstGf) worstGf = fw;
          if (mx > .1f || fw > .5f) { bad++; printf("  горб cyl %u место %d сторона %+d, %d м/с курс %+d°: толчок от капсулы вбок %.2f, вперёд %.2f м/кадр\n",
                                                 i, st, side, vi ? 4 : 2, ai * 20, mx, fw); }
        }
      }
    }
    printf("  горбы наискось: заездов %d, с толчком от самой капсулы: %d (вбок до %.2f, вперёд до %.2f м/кадр), с отменой/возвратом %d; толчков на стеновой стороне (откос, не горб): %d\n", runs, bad, worstG, worstGf, rv, gWallJolts);
    check("G: горбы уровня наискось (2–4 м/с, ±20°) — капсула под кузовом не толкает (правка 200, остаток сверки)", bad == 0); }
  // H: стены держат — сторона-стена горбов и звенья острых углов в лоб
  { int runs = 0, bad = 0; float gainW = -9.f, vyW = -9.f;
    for (int pass = 0; pass < 2; pass++) for (unsigned i = 0; i < (pass ? W.nseg : W.ncyl); i++) {
      float tx[5], tz[5], nx, nz; int nt = 0;   // точки удара и нормаль «к машине»
      if (!pass) {
        const ColCyl *C = &W.cyl[i]; float axl = hypotf(C->axis[0], C->axis[2]);
        if (C->pad[0] == 1.f || C->halfLen <= 0.f || fabsf(C->axis[1]) > .3f || axl < 1e-4f || 2.f * C->halfLen * axl < COL_HUMP_LEN) continue;
        float ux = C->axis[0] / axl, uz = C->axis[2] / axl;
        for (int side = -1; side <= 1; side += 2) for (int st = 1; st <= 3; st++) {
          float t = (st / 4.f - .5f) * 2.f * C->halfLen, ax = C->c[0] + C->axis[0] * t, az = C->c[2] + C->axis[2] * t, top = C->c[1] + C->axis[1] * t + C->r;
          float px = -uz * side, pz = ux * side, sx = ax + px * (C->r + 7.f), sz = az + pz * (C->r + 7.f), g;
          float gn, hx = ax + px * (C->r + .3f), hz = az + pz * (C->r + .3f);   // сторона-стена — как у humpFlags: земля в r + 0,3 м от оси
          if (!colGround(&W, hx, hz, top + 1.f, top - 6.f, &gn, 0) || (top - gn <= COL_HUMP + .1f && top - gn <= C->r * (1.f - COL_WALK_NY) + .1f)) continue;   // + 0,1 м: явная стена, не порог
          if (!colGround(&W, sx, sz, top + 1.f, top - 8.f, &g, 0) || top - g > 3.f || behindFence(sx, sz, g)) continue;
          for (int vi = 0; vi < 2; vi++) {
            float v = vi ? 10.f : 5.f; Car c; carInit(&c, carPP, &W, sx, g, sz, atan2f(-px, -pz));
            int selH = 0;   // 388/377: один заезд H — HUMPS_H=cyl,место,сторона,м/с (покадровая печать; с -DCOL_DEBUG — контакты)
            { const char *hs = getenv("HUMPS_H"); if (hs) { unsigned hi; int hst, hside, hv;
                if (sscanf(hs, "%u,%d,%d,%d", &hi, &hst, &hside, &hv) == 4 && (hi != i || hst != st || hside != side || hv != (int)v)) continue; selH = 1; } }
#ifdef COL_DEBUG
            { extern int colDebug; colDebug = selH; }
#endif
            for (int k = 0; k < 20; k++) { CarInput in = {0}; carUpdate(&c, &W, &in, 1 / 60.f); }
            carSetSpeed(&c, v); float hit = 0.f, after = 0.f, vy = -9.f, y0 = c.y, ymin = c.y; int touched = 0;
            for (int f = 0; f < 240; f++) {
              CarInput in = {1, 0, 0}; if (c.v > v) in.throttle = 0;
              if (selH) printf("== f %d pos %.3f %.3f %.3f vel %.2f %.2f %.2f h %.2f roll %.0f pitch %.0f wh %d body %d ct %d pen %.3f rev %d comp %.2f %.2f %.2f %.2f wallV %.1f %d#%u\n", f, c.x, c.y, c.z, c.vel[0], c.vel[1], c.vel[2], c.h, c.roll * 57.3f, c.pitch * 57.3f, c.wheels, c.bodyHit, c.contacts, c.pen, c.reverts, c.comp[0], c.comp[1], c.comp[2], c.comp[3], c.wallV, c.wallV > 0 ? c.wallType : -1, c.wallV > 0 ? c.wallIdx : 0);
              carUpdate(&c, &W, &in, 1 / 60.f);
              float sp = hypotf(c.vel[0], c.vel[2]); if (c.contacts) touched = 1;
              if (!touched) hit = sp; else { if (sp > after) after = sp; if (c.vel[1] > vy) vy = c.vel[1]; }
              if (c.y < ymin) ymin = c.y;
            }
            float across = (c.x - ax) * px + (c.z - az) * pz;
            if (!touched || hit < 3.f || ymin < y0 - 1.5f) continue;   // не доехал до стены разогнавшись / упал с уступа у старта
            runs++;
            int ok = across > 0.f && after <= fmaxf(hit, v) + .5f && vy <= 3.f;
            if (touched && after - hit > gainW) gainW = after - hit; if (vy > vyW) vyW = vy;
            if (!ok) { bad++; printf("  стена горба cyl %u место %d сторона %+d, %.0f м/с: сторона %.2f, скорость %.1f -> %.1f, вверх %.1f\n", i, st, side, v, across, hit, after, vy); }
          }
        }
        continue;
      }
      const ColSeg *A = &W.seg[i]; float ax = A->b[0] - A->a[0], az = A->b[1] - A->a[1], la = hypotf(ax, az);
      if (la < 1e-3f || A->y0 < COL_SEG_FOL_Y0) continue;
      for (int ei = 0; ei < 2; ei++) {   // острый выпуклый угол у конца ei
        float Px = ei ? A->b[0] : A->a[0], Pz = ei ? A->b[1] : A->a[1], dix = ei ? -ax / la : ax / la, diz = ei ? -az / la : az / la; int acute = 0;
        for (unsigned j = 0; j < W.nseg && !acute; j++) for (int ej = 0; ej < 2; ej++) {
          const ColSeg *B = &W.seg[j]; float Qx = ej ? B->b[0] : B->a[0], Qz = ej ? B->b[1] : B->a[1];
          if (j == i || fabsf(Qx - Px) > 2e-3f || fabsf(Qz - Pz) > 2e-3f) continue;
          float bx = B->b[0] - B->a[0], bz = B->b[1] - B->a[1], lb = hypotf(bx, bz); if (lb < 1e-3f) continue;
          float djx = ej ? -bx / lb : bx / lb, djz = ej ? -bz / lb : bz / lb, sx = dix + djx, sz = diz + djz;
          if (hypotf(sx, sz) >= 0.02f && sx * (A->n[0] + B->n[0]) + sz * (A->n[1] + B->n[1]) <= 0.f && dix * djx + diz * djz >= cosf(85.f * 0.0174533f)) acute = 1;
        }
        if (acute && nt < 5) { float o = fminf(1.f, la * .5f); tx[nt] = Px + dix * o; tz[nt] = Pz + diz * o; nt++; }
      }
      nx = A->n[0]; nz = A->n[1];
      for (int k = 0; k < nt; k++) {
        float sx = tx[k] + nx * 7.f, sz = tz[k] + nz * 7.f, g;
        if (!colGround(&W, sx, sz, 1e6f, -1e6f, &g, 0) || A->y1 < g + 0.5f || A->y0 > g + 1.4f || behindFence(sx, sz, g)) continue;
        for (int vi = 0; vi < 2; vi++) {
          float v = vi ? 10.f : 5.f; Car c; carInit(&c, carPP, &W, sx, g, sz, atan2f(-nx, -nz));
          for (int q = 0; q < 20; q++) { CarInput in = {0}; carUpdate(&c, &W, &in, 1 / 60.f); }
          carSetSpeed(&c, v); float hit = 0.f, after = 0.f, vy = -9.f, y0 = c.y, ymin = c.y; int touched = 0;
          for (int f = 0; f < 180; f++) {
            CarInput in = {1, 0, 0}; if (c.v > v) in.throttle = 0;
            carUpdate(&c, &W, &in, 1 / 60.f);
            float sp = hypotf(c.vel[0], c.vel[2]); if (c.contacts) touched = 1;
            if (!touched) hit = sp; else { if (sp > after) after = sp; if (c.vel[1] > vy) vy = c.vel[1]; }
            if (c.y < ymin) ymin = c.y;
          }
          float u = (c.x - A->a[0]) * nx + (c.z - A->a[1]) * nz, t = ((c.x - A->a[0]) * ax + (c.z - A->a[1]) * az) / la;
          if (!touched || hit < 3.f || ymin < y0 - 1.5f) continue;
          runs++;
          int ok = !(u < -.3f && t >= 0.f && t <= la) && after <= fmaxf(hit, v) + .5f && vy <= 3.f;
          if (touched && after - hit > gainW) gainW = after - hit; if (vy > vyW) vyW = vy;
          if (!ok) { bad++; printf("  звено %u у острого угла, %.0f м/с: за линией %.2f, скорость %.1f -> %.1f, вверх %.1f\n", i, v, u, hit, after, vy); }
        }
      }
    }
    printf("  стены: заездов %d (сторона-стена горбов и звенья острых углов в лоб 5/10 м/с), прошли или разогнались %d; прибавка скорости до %.2f м/с, вверх до %.2f м/с\n", runs, bad, gainW, vyW);
    check("H: стены горбов и звенья углов держат, без разгона и подброса (правка 200, остаток сверки)", bad == 0); }
  printf("RESULT: %s (%d failures)\n", fails ? "FAIL" : "OK", fails);
  return fails != 0;
}
