// №738 (Роб 17.10: «застрял в ящике и у стены дома — переносить на дорогу рядом»): машина в тесном ящике (стены со всех сторон, ровный пол).
// Сцена «ящик»: газ 1,5 с, задний ход 1,5 с, по кругу 8 с — машина обязана выйти (ушла от места > 2 м, стоит на земле, не в стене).
// Контроль «стена»: машина у стены только газом 8 с — не трогаем (уход < 1 м). tests/wedge738/host.sh; EXTRA=-DWEDGE738_OLD=1 — красный
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "car.h"
static int fails;
static void check(const char *n, int ok) { printf("%s %s\n", ok ? "OK" : "FAIL", n); fails += !ok; }
static struct { ColHdr h; ColTri t[64]; unsigned start[2], refs[64]; } g;
static int nt;
static void tri(float ax, float ay, float az, float bx, float by, float bz, float cx, float cy, float cz) {
  float ux = bx - ax, uy = by - ay, uz = bz - az, vx = cx - ax, vy = cy - ay, vz = cz - az, n[3] = {uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx};
  float l = sqrtf(n[0] * n[0] + n[1] * n[1] + n[2] * n[2]); g.t[nt] = (ColTri){{ax, ay, az}, {bx, by, bz}, {cx, cy, cz}, {n[0] / l, n[1] / l, n[2] / l}}; nt++; }
static void wall(float x0, float z0, float x1, float z1, float h) {   // две стороны (видно с обеих)
  tri(x0, 0, z0, x1, 0, z1, x1, h, z1); tri(x0, 0, z0, x1, h, z1, x0, h, z0); tri(x0, 0, z0, x1, h, z1, x1, 0, z1); tri(x0, 0, z0, x0, h, z0, x1, h, z1); }
static void world(ColWorld *w, int box) {
  memset(&g, 0, sizeof g); nt = 0; memcpy(g.h.magic, "COL1", 4); g.h.ox = g.h.oz = -100; g.h.cell = 200; g.h.W = g.h.H = 1;
  tri(-100, 0, -100, 100, 0, 100, 100, 0, -100); tri(-100, 0, -100, -100, 0, 100, 100, 0, 100);
  if (box) { wall(-1.5f, -3.1f, 1.5f, -3.1f, 1.2f); wall(1.5f, -3.1f, 1.5f, 3.1f, 1.2f); wall(1.5f, 3.1f, -1.5f, 3.1f, 1.2f); wall(-1.5f, 3.1f, -1.5f, -3.1f, 1.2f); }
  else wall(-10, -3.0f, 10, -3.0f, 4.f);
  g.h.ntri = nt; g.h.nref = nt;
  static unsigned char buf[sizeof g]; size_t o = 0; unsigned st[2] = {0, (unsigned)nt};   // COL1: заголовок, треугольники подряд, начала клеток, ссылки
  memcpy(buf, &g.h, sizeof g.h); o += sizeof g.h; memcpy(buf + o, g.t, nt * sizeof(ColTri)); o += nt * sizeof(ColTri);
  memcpy(buf + o, st, sizeof st); o += sizeof st; for (int i = 0; i < nt; i++) { unsigned r = (unsigned)i; memcpy(buf + o, &r, 4); o += 4; }
  if (colInit(w, buf, o)) printf("colInit fail\n");
}
static float run(int box) {
  ColWorld w; world(&w, box); Car c; const float dt = 1 / 60.f;
  carInit(&c, NULL, &w, 0, 0, 0, box ? 0.f : 3.14159f);   // в ящике — вдоль z; у стены — носом к стене (−z)
  for (int k = 0; k < 30; k++) { CarInput in = {0}; carUpdate(&c, &w, &in, dt); }
  float x0 = c.x, z0 = c.z;
  for (int t = 0; t < 600; t++) { CarInput in = {0}; if (!box || (t / 90) % 2 == 0) in.throttle = 1.f; else in.brake = 1.f; carUpdate(&c, &w, &in, dt); }
  float d = hypotf(c.x - x0, c.z - z0);
  printf("%s: ушла на %.2f м, (%.2f %.2f %.2f) на земле %d\n", box ? "ящик" : "стена", d, c.x, c.y, c.z, c.grounded);
  return d;
}
int main(void) {
  float a = run(1), b = run(0);
  check("зажатая в ящике машина (вперёд и назад) выходит рядом", a > 2.f);
  check("машина, давящая газом в стену, остаётся на месте", b < 1.f);
  printf("RESULT: %s\n", fails ? "FAIL" : "OK"); return fails ? 1 : 0;
}
