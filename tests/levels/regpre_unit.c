// Хост-гейт гистерезиса REGPRE: путь игрока у границы GATE_PRE_M с шумом скорости и угла (как на первой ходьбе: повороты, торможения), 30 к/с, 40 с.
// Считает ВКЛЮЧЕНИЯ региона в любом окне 10 с. hyst=0 — прежнее (красный: обязан дать > 1), hyst=1 — новое (зелёное: не больше 1).
#include <stdio.h>
#include <stdlib.h>
#include "../../viewer/regpre.h"
static float rnd(void) { return (float)rand() / 2147483647.f; }
static int run(int hyst, int seed, int *tot) {
  srand(seed); float px = 0.f, pz = -120.f; unsigned now = 1000; int prev = 0, n = 0; unsigned rises[4000]; float yaw = 0.f;
  for (int f = 0; f < 30 * 40; f++, now += 33333) {
    float spd = 4.f + 1.2f * (rnd() - .5f) * 2.f;              // скорость гуляет около порога 4 м/с
    yaw += (rnd() - .5f) * 0.9f; if (yaw > 1.2f) yaw = 1.2f; if (yaw < -1.2f) yaw = -1.2f;   // курс виляет около направления на ворота
    float dirx = sinf(yaw), dirz = cosf(yaw);
    px += dirx * spd * (1.f / 30.f) * .5f; pz += dirz * spd * (1.f / 30.f) * .5f;   // медленный дрейф: игрок долго стоит у границы 90 м
    if (pz > -75.f) pz = -120.f;
    int y = regPreYes(0, 0.f - px, 0.f - pz, dirx, dirz, spd, now, hyst);
    if (y && !prev && n < 4000) rises[n++] = now; prev = y;
  }
  int worst = 0; for (int i = 0; i < n; i++) { int c = 0; for (int j = i; j < n && rises[j] - rises[i] < 10000000u; j++) c++; if (c > worst) worst = c; }
  *tot = n; return worst;
}
int main(void) {
  int worstOld = 0, worstNew = 0, totOld = 0, totNew = 0;
  for (int seed = 1; seed <= 20; seed++) { int t; int w = run(0, seed, &t); if (w > worstOld) worstOld = w; totOld += t;
    for (int k = 0; k < 64; k++) regPreT[k] = 0; w = run(1, seed, &t); if (w > worstNew) worstNew = w; totNew += t; for (int k = 0; k < 64; k++) regPreT[k] = 0; }
  printf("REGPRE unit: прежнее: включений %d, максимум за 10 с %d; гистерезис: включений %d, максимум за 10 с %d\n", totOld, worstOld, totNew, worstNew);
  int ok = worstOld > 1 && worstNew <= 1;
  printf("REGPRE-ЮНИТ: %s\n", ok ? "PASS (красный пойман, зелёный чист)" : "FAIL"); return ok ? 0 : 1;
}
