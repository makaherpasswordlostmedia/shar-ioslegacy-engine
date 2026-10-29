// Гейт правки 354 (колёса): синтетическая машина CAR1 (суставы w0..w3 по углам + кузов), без данных игры. Проверки:
//  A — скрытые колёса по правилу SLES 0x27a140: honor_v (и HONOR_V) — все 4 сустава колёс не рисуются, rocke_v — только w2, w3,
//      famil_v — все рисуются (carVisSetCar / carVisJointHidden);
//  B — трафик и машины миссий (trafficDrawModel): у honor_v куски колёс 1..4 не уходят в отрисовку, кузов — уходит; у famil_v — все;
//  C — ход подвески вверх (carvis jointXf): при полном сжатии колесо не выше запаса wheelUp; без запаса — до lim − eq, как прежде;
//  D — таблицы правила совпадают: viewer/carwheels.h = tools/traffic_export.HIDDEN_WHEELS = tools/wheel_clear.HIDDEN (run.sh).
// Красный: -DCARWHEELS_OLD=1 (прежнее: заглушки рисуются) обязан упасть на A и B.
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "carvis.h"
#include "traffic.h"
#include "carwheels.h"
static int fails;
static void check(const char *n, int ok) { printf("%s %s\n", ok ? "ok" : "FAIL", n); fails += !ok; }

static unsigned char sec[4096];
static unsigned mkCar1(void) {   // CAR1 v1: 5 суставов (кузов + w0..w3, у famil_v w3 — левое переднее), без шарниров
  static const char *nm[5] = {"body", "w0", "w1", "w2", "w3"};
  static const float xyz[5][3] = {{0, 0, 0}, {.8f, .35f, 1.3f}, {-.8f, .35f, 1.3f}, {.8f, .35f, -1.3f}, {-.8f, .35f, -1.3f}};
  memset(sec, 0, sizeof sec); memcpy(sec, "CAR1", 4);
  unsigned *u = (unsigned *)(sec + 4); u[0] = 1; u[1] = 5;
  float *f = (float *)(sec + 32); f[0] = .7f; f[1] = .7f; f[2] = .37f; f[3] = .5f;
  unsigned char *p = sec + 80;
  for (int j = 0; j < 5; j++, p += 28) { memcpy(p, nm[j], strlen(nm[j])); memcpy(p + 12, xyz[j], 12); }
  return (unsigned)(p - sec);
}
static int drawn[16], ndrawn;
static void fn(void *user, const TrPiece *p, const void *v, const float m[16]) { (void)user; (void)v; (void)m; if (ndrawn < 16) drawn[ndrawn++] = (int)p->wheel; }

int main(void) {
  CarVis v; unsigned n = mkCar1();
  if (carVisInit(&v, sec, n)) { printf("FAIL carVisInit\n"); return 2; }
  // A
  carVisSetCar(&v, "honor_v"); int h = 0; for (int j = 1; j <= 4; j++) h += carVisJointHidden(&v, j);
  check("A1: honor_v — все 4 колеса-заглушки не рисуются", h == 4 && !carVisJointHidden(&v, 0));
  carVisSetCar(&v, "HONOR_V"); h = 0; for (int j = 1; j <= 4; j++) h += carVisJointHidden(&v, j);
  check("A2: имя без учёта регистра (HONOR_V)", h == 4);
  carVisSetCar(&v, "rocke_v");
  check("A3: rocke_v — скрыты только w2, w3", !carVisJointHidden(&v, 1) && !carVisJointHidden(&v, 2) && carVisJointHidden(&v, 3) && carVisJointHidden(&v, 4));
  carVisSetCar(&v, "famil_v"); h = 0; for (int j = 0; j <= 4; j++) h += carVisJointHidden(&v, j);
  check("A4: famil_v — все колёса рисуются", h == 0);
  // B
  TrModel M; memset(&M, 0, sizeof M); TrPiece pc[5]; memset(pc, 0, sizeof pc);
  for (int i = 0; i < 5; i++) { pc[i].wheel = (uint32_t)i; pc[i].sc = 1.f; pc[i].ni = 3; }
  M.firstPiece = 0; M.nPiece = 5; M.lift = .7f;
  Car c; memset(&c, 0, sizeof c); c.q[0] = 1.f;
  strcpy(M.name, "honor_v"); ndrawn = 0; trafficDrawModel(&M, pc, (const unsigned char *)sec, &c, 0.f, 0, fn, 0, 0);
  check("B1: трафик honor_v — рисуется только кузов", ndrawn == 1 && drawn[0] == 0);
  strcpy(M.name, "rocke_v"); ndrawn = 0; trafficDrawModel(&M, pc, (const unsigned char *)sec, &c, 0.f, 0, fn, 0, 0);
  check("B2: трафик rocke_v — кузов и задние w0, w1", ndrawn == 3);
  strcpy(M.name, "famil_v"); ndrawn = 0; trafficDrawModel(&M, pc, (const unsigned char *)sec, &c, 0.f, 0, fn, 0, 0);
  check("B3: трафик famil_v — все 5 кусков", ndrawn == 5);
  // C: полное сжатие подвески; колесо FL (wheelJ[0])
  carVisSetCar(&v, "famil_v"); c.eq = .05f; c.lim = .25f; for (int i = 0; i < 4; i++) c.comp[i] = c.lim;
  int j = v.wheelJ[0]; float m[16];
  carVisPieceMatrix(&v, &c, j, 0, 0, 0, 0, 1, m); float y0 = m[13] - v.lift - v.joint[j].y;
  check("C1: без запаса в таблице — ход вверх до lim − eq (как прежде)", fabsf(y0 - (c.lim - c.eq)) < 1e-4f);
  v.wheelUp[0] = .08f;   // запас модели (tools/wheel_clear.py), меньше lim − eq
  carVisPieceMatrix(&v, &c, j, 0, 0, 0, 0, 1, m); float y1 = m[13] - v.lift - v.joint[j].y;
  check("C2: колесо не выше запаса модели", fabsf(y1 - .08f) < 1e-4f);
  for (int i = 0; i < 4; i++) c.comp[i] = 0.f;
  carVisPieceMatrix(&v, &c, j, 0, 0, 0, 0, 1, m); float y2 = m[13] - v.lift - v.joint[j].y;
  check("C3: вниз (колесо в воздухе) — как прежде, −eq", fabsf(y2 + c.eq) < 1e-4f);
  // таблица для D (run.sh сверяет с питоном)
  for (int i = 0; i < CAR_WHEEL_CONS; i++) if (carWheelCons[i].hide) printf("HIDE %s 0x%X\n", carWheelCons[i].name, carWheelCons[i].hide);
  printf("RESULT %s (%d провалов)\n", fails ? "FAIL" : "PASS", fails);
  return fails ? 1 : 0;
}
