// fallhunt — охота на выпадения Гомера за мир вокруг одного места (разбор ночи 11.10, «КОЛЛИЗИИ_НОЧЬ_РАЗБОР»): те же макросы, что у
// explorer (выйти из машины, бег с прыжками), но старты — случайные опоры (ВСЕ слои над точкой) в радиусе R вокруг места, и на каждое
// падение (ниже самой низкой коллизии на 5 м) пишется след последних 150 кадров. Без эмулятора, процессор Мака, повтор по seed.
//   fallhunt LEVEL PLAYER X Z R TRIALS SEED
// Строки: F<TAB>проба<TAB>старт x y z<TAB>последняя опора x y z<TAB>состояние Гомера<TAB>падение x y z<TAB>макрос a b кадры<TAB>цепочка;
//   T<TAB>проба<TAB>кадр<TAB>x y z<TAB>на_опоре<TAB>состояние<TAB>vx vy vz — след; итог S<TAB>проб<TAB>падений
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "world.h"
static BotWorld W; static BotSnap S0; static uint32_t rs = 1;
static uint32_t xr(void) { rs ^= rs << 13; rs ^= rs >> 17; rs ^= rs << 5; return rs; }
enum { M_WALK, M_JUMP };
static void macroInput(int kind, int a, int b, int f, unsigned *bt, float *ax, float *ay) {
  *bt = 0; *ax = 0; *ay = 0;
  if (kind == M_WALK) { if (f == 0) *bt = GP_TRIANGLE; else { *bt = GP_CIRCLE; *ax = cosf(b * .0245f) * .99f; *ay = -sinf(b * .0245f) * .99f; if (f % 50 == 25 && a > 0) *bt |= GP_CROSS; } }
  else { if (f == 0) *bt = GP_TRIANGLE; else { *bt = GP_CIRCLE; *ax = cosf(b * .0245f); *ay = -sinf(b * .0245f); if (f % 40 == 5 || f % 40 == 15) *bt |= GP_CROSS; } }
}
typedef struct { float x, y, z; int g, st; float vx, vy, vz; } Tr;
int main(int argc, char **argv) {
  if (argc < 8) { fprintf(stderr, "fallhunt LEVEL PLAYER X Z R TRIALS SEED\n"); return 2; }
  if (bwData(argv[1], argv[2], 0)) { fprintf(stderr, "fallhunt: нет данных\n"); return 2; }
  float X = atof(argv[3]), Z = atof(argv[4]), R = atof(argv[5]); int trials = atoi(argv[6]); rs = (uint32_t)atoi(argv[7]) | 1;
  float minY = 1e9f; { const ColWorld *cw = bwCol(); for (uint32_t i = 0; i < cw->ntri; i++) { const ColTri *T = &cw->tri[i]; float m = fminf(T->a[1], fminf(T->b[1], T->c[1])); if (m < minY) minY = m; } }
  bwNew(&W); bwSaveAlloc(&W, &S0); bwSave(&W, &S0);
  static Tr ring[150]; int falls = 0, shown = 0;
  for (int t = 0; t < trials; t++) {
    float sx = X + ((int)(xr() % 2001) - 1000) / 1000.f * R, sz = Z + ((int)(xr() % 2001) - 1000) / 1000.f * R;
    float tops[8], top = 120.f; int nl = 0, gy;
    for (; nl < 8; nl++) { float g; if (!colGround(bwCol(), sx, sz, top, -120.f, &g, 0)) break; tops[nl] = g; top = g - .5f; }
    if (!nl) continue; gy = (int)(xr() % (unsigned)nl); float y0 = tops[gy] + .05f, h = (xr() % 628) / 100.f;
    bwLoad(&W, &S0); bwPlace(&W, sx, y0, sz, h); for (int f = 0; f < 30; f++) bwStep(&W, 0, 0, 0);
    float lg[3] = {sx, y0, sz}; int lgst = 0, fell = 0, rn = 0, rh = 0, nmac = 1 + (int)(xr() % 4);
    char chain[160] = ""; int lk = 0, la = 0, lb = 0, lf = 0;
    for (int m = 0; m < nmac && !fell; m++) {
      int kind = (int)(xr() % 2), a = (int)(xr() % 201) - 100, b = (int)(xr() % 256), fr = 120 + (int)(xr() % 181);
      lk = kind; la = a; lb = b; lf = fr; char tmp[40]; snprintf(tmp, sizeof tmp, "%d:%d:%d:%d ", kind, a, b, fr); if (strlen(chain) + strlen(tmp) < sizeof chain) strcat(chain, tmp);
      for (int f = 0; f < fr; f++) {
        unsigned bt; float ax, ay; macroInput(kind, a, b, f, &bt, &ax, &ay); bwStep(&W, bt, ax, ay);
        int ft = gameOnFoot(&W.G); float px = ft ? W.homer.x : W.car.x, py = ft ? W.homer.y : W.car.y, pz = ft ? W.homer.z : W.car.z;
        ring[rn % 150] = (Tr){px, py, pz, ft ? W.homer.grounded : W.car.grounded, ft ? W.homer.state : -1, W.homer.vx, W.homer.vy, W.homer.vz}; rn++; if (rh < 150) rh++;
        if (py < minY - 5.f) { fell = 1; break; }
        if (ft ? W.homer.grounded : W.car.grounded) { lg[0] = px; lg[1] = py; lg[2] = pz; lgst = ft ? W.homer.state : -1; }
      }
    }
    if (!fell) continue;
    falls++;
    printf("F\t%d\t%.2f %.2f %.2f\t%.2f %.2f %.2f\t%d\t%.2f %.2f %.2f\t%d %d %d %d\t%s\n", t, sx, y0, sz, lg[0], lg[1], lg[2], lgst, ring[(rn - 1) % 150].x, ring[(rn - 1) % 150].y, ring[(rn - 1) % 150].z, lk, la, lb, lf, chain);
    if (shown < 4) { shown++; for (int i = 0; i < rh; i++) { Tr *q = &ring[(rn - rh + i) % 150]; if (i % 3 == 0 || i > rh - 40) printf("T\t%d\t%d\t%.2f %.2f %.2f\t%d\t%d\t%.2f %.2f %.2f\n", t, i, q->x, q->y, q->z, q->g, q->st, q->vx, q->vy, q->vz); } }
  }
  printf("S\t%d\t%d\n", trials, falls);
  return 0;
}
