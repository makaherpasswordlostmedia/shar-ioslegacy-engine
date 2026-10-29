// Длинный мир (пункт 10б, гейт «стекло после возврата снова бьётся»): один непрерывный мир игры без экрана, без телепорта.
// 1) повтор каскадёра (файл нажатий .in, старт в первой строке) доводит машину до удара — предмет разбит;
// 2) водитель навигатора (A* по дорогам + водитель по опорным точкам) уезжает к узлу дороги в 80–150 м от предмета;
// 3) ждёт, пока предмет вернётся на место (правило порта props.c: игрок дальше 60 м и предмет 5 с вне вида), до 40 с;
// 4) едет назад и въезжает в предмет с разгона (заход на 25 м по той же линии, что в повторе) — предмет обязан разбиться снова.
// Застрял (медленнее 1 м/с 3 с) — START (RESET CAR), как игрок. Итог в stdout, код 0 — разбит дважды.
//   longworld LEVEL HOMER ROADS REPRO.in PROP
// Отрицательный контроль гейта: BW_NO_RESPAWN=1 (возврат предметов в игре без экрана выключен) — предмет не возвращается,
// повторно не бьётся, тест обязан провалиться именно на шаге 3/4 («не вернулся», «НЕ разбит»).
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "world.h"
#include "navgraph.h"

static BotWorld W;
static int hidden(int i) { return W.haveProps && (unsigned)i < W.props.ninst && W.props.st[i].hidden; }
// ехать по опорным точкам до последней (ближе R) не дольше secs; застревание -> START; -> 1 доехал
static int drive(P3 *q, int n, float R, float secs, int prop, int *broke) {
  int seg = 0, tries = 0; float slow = 0, backT = 0, backAx = 0; float par[NPAR]; memcpy(par, PAR0, sizeof par);
  for (int f = 0; f < (int)(secs * 60); f++) {
    unsigned b; float ax; navSteer(q, n, &seg, &W.car, par, &b, &ax);
    if (backT > 0) { b = GP_L; ax = backAx; backT -= BW_DT; }   // сдать назад с обратным рулём, как игрок
    else if (slow > 1.5f) { if (++tries % 4 == 0) b = GP_START; else { backT = 1.2f; backAx = -ax; } slow = 0; }   // каждая 4-я — RESET CAR
    bwStep(&W, b, ax, 0.f);
    if (getenv("LW_TRACE") && f % 300 == 0) fprintf(stderr, "  %.0f с: машина %.1f %.1f %.1f v %.1f\n", f / 60.f, W.car.x, W.car.y, W.car.z, W.car.v);
    if (fabsf(W.car.v) < 1.f) slow += BW_DT; else slow = 0;
    if (broke && hidden(prop)) { *broke = 1; return 1; }
    if (hypotf(W.car.x - q[n - 1].x, W.car.z - q[n - 1].z) < R) return 1;
  }
  return 0;
}

int main(int argc, char **argv) {
  if (argc < 6) { fprintf(stderr, "usage: longworld LEVEL HOMER ROADS REPRO.in PROP [--no-wait]\n"); return 2; }
  if (bwData(argv[1], argv[2], 0)) return 2;
  navLoad(argv[3]);
  int prop = atoi(argv[5]), noWait = 0;
  FILE *in = fopen(argv[4], "r"); if (!in) return 2;
  char ln[1024]; float sx = 0, sy = 0, sz = 0, sh = 0; bwNew(&W);
  if (fgets(ln, sizeof ln, in)) { char *p = strstr(ln, "--start"); if (p) sscanf(p + 7, "%f %f %f %f", &sx, &sy, &sz, &sh); }
  bwPlace(&W, sx, sy, sz, sh);
  float hx = 0, hz = 0, lastX = W.car.x, lastZ = W.car.z;   // линия захода: откуда машина ехала в последнюю секунду до удара
  int fr = 0;
  while (fgets(ln, sizeof ln, in)) { int n; unsigned b; float ax, ay; if (ln[0] == '#' || sscanf(ln, "%d %x %f %f", &n, &b, &ax, &ay) != 4) continue;
    for (int k = 0; k < n; k++, fr++) { if (fr % 60 == 0) { lastX = W.car.x; lastZ = W.car.z; } bwStep(&W, b, ax, ay); } }
  fclose(in);
  if (!hidden(prop)) { printf("1) повтор не разбил предмет %d — FAIL\n", prop); return 1; }
  const PropState *s = &W.props.st[prop]; float gx = s->home[0], gy = s->home[1], gz = s->home[2];
  hx = gx - lastX; hz = gz - lastZ; { float l = hypotf(hx, hz) + 1e-3f; hx /= l; hz /= l; }
  printf("1) разбит на кадре %d (%.1f с), предмет у %.1f %.1f\n", fr, fr / 60.f, gx, gz);
  // 2) уехать к узлу дороги в 80–150 м
  int far = -1; float bd = 1e9f;
  for (int i = 0; i < nnode; i++) { float d = hypotf(node[i].x - gx, node[i].z - gz), dc = hypotf(node[i].x - W.car.x, node[i].z - W.car.z);
    if (d > 80.f && d < 150.f && dc < bd) { bd = dc; far = i; } }
  P3 q[MAXWP]; int n = navPlan(W.car.x, W.car.y, W.car.z, node[far].x, node[far].y, node[far].z, q, MAXWP);
  int ok = drive(q, n, 8.f, 90.f, prop, 0); float dAway = hypotf(W.car.x - gx, W.car.z - gz);
  printf("2) уехал: %s, до предмета %.0f м\n", ok ? "доехал" : "не доехал за 90 с", dAway);
  // 3) ждать возврата
  int back = 0, wf = 0;
  if (!noWait) for (; wf < 40 * 60 && !back; wf++) { bwStep(&W, W.car.v > .5f ? GP_L : W.car.v < -.5f ? GP_R : 0, 0, 0); back = !hidden(prop);   // гасить скорость в обе стороны (L при нуле — задний ход)
    if (getenv("LW_TRACE") && wf % 300 == 0) { const PropState *t = &W.props.st[prop]; float fx = sinf(W.car.h), fz = cosf(W.car.h), cx = W.car.x - fx * 7.5f, cz = W.car.z - fz * 7.5f;
      float dx = t->home[0] - cx, dz = t->home[2] - cz, d = hypotf(dx, dz);
      fprintf(stderr, "  ждём %.0f с: до дома предмета %.0f м, косинус к взгляду %.2f, away %.1f, спрятан %d, сейчас у %.1f %.1f\n", wf / 60.f, d, (dx * fx + dz * fz) / d, t->away, t->hidden, t->x, t->z); } }
  printf("3) %s\n", noWait ? "не ждал (контроль)" : back ? "предмет вернулся на место" : "предмет не вернулся за 40 с");
  // 4) назад и въехать с разгона по линии захода
  float ax0 = gx - hx * 25.f, az0 = gz - hz * 25.f;
  n = navPlan(W.car.x, W.car.y, W.car.z, ax0, gy, az0, q, MAXWP);
  int reach = drive(q, n, 6.f, 120.f, prop, 0);
  P3 line[2] = {{ax0, gy, az0}, {gx + hx * 10.f, gy, gz + hz * 10.f}}; int broke = 0;
  if (reach && !hidden(prop)) drive(line, 2, 2.f, 15.f, prop, &broke);   // «разбит снова» — только переход «на месте -> разбит»
  printf("4) заход: %s; предмет %s\n", reach ? "на линии" : "не вышел на линию", broke ? "разбит снова" : "НЕ разбит");
  int pass = broke && back;
  printf("RESULT: %s (длинный мир %.0f с игры)\n", pass ? "OK" : "FAIL", W.st.frames / 60.f);
  return pass ? 0 : 1;
}
