// Близнецы · сторона «Порт, лёгкий» (docs/handoff/БЛИЗНЕЦЫ_2026-10-01.md §1): та же логика, что EBOOT, без экрана — мир ботов
// tools/bots/world.c (сам мир не меняется; это отдельный вход, как tools/bots/game_headless.c).
//   port_light LEVEL HOMER [--msn FILE] [--place X Y Z H] [--frames N] [--every K]
// --place — машина в точку (оси и курс порта, как goto сценария; y — откуда искать землю вниз), без ввода N кадров по 1/60 с.
// Выход: по строке JSON на кадр 0, каждые K кадров и последний: всё, что знает мир без экрана (поза, скорость, пешком, комната,
// трафик, lift машины, отпечаток мира). Камеры, загрузок, памяти у мира ботов нет — их сторона не выдумывает.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "world.h"

static void out(BotWorld *w, int f) {
  int foot = gameOnFoot(&w->G), tc = -1, tp = -1, tk = -1;
  if (!bwTrafficCounts(&tc, &tp, &tk)) tc = tp = tk = -1;
  float px = foot ? w->homer.x : w->car.x, py = foot ? w->homer.y : w->car.y, pz = foot ? w->homer.z : w->car.z;
  printf("{\"frame\":%d,\"car\":[%.5f,%.5f,%.5f],\"h\":%.6f,\"vel\":[%.5f,%.5f,%.5f],\"v\":%.5f,\"onfoot\":%d,\"player\":[%.5f,%.5f,%.5f],"
         "\"room\":%d,\"lift\":%.5f,\"grounded\":%d,\"cars\":%d,\"peds\":%d,\"parked\":%d,\"coins\":%u,\"hnr\":%.4f,\"hash\":\"%016llx\"}\n",
         f, w->car.x, w->car.y, w->car.z, w->car.h, w->car.vel[0], w->car.vel[1], w->car.vel[2], w->car.v, foot, px, py, pz,
         bwRoomAt(px, py, pz), w->lift, w->car.grounded, tc, tp, tk, w->st.coins, w->hnrHeat, (unsigned long long)bwHash(w));
}

int main(int argc, char **argv) {
  if (argc < 3) { fprintf(stderr, "usage: port_light LEVEL HOMER [--msn FILE] [--place X Y Z H] [--frames N] [--every K]\n"); return 2; }
  const char *msn = 0; int frames = 120, every = 0, place = 0; float x = 0, y = 0, z = 0, h = 0;
  for (int i = 3; i < argc; i++) {
    if (!strcmp(argv[i], "--msn") && i + 1 < argc) msn = argv[++i];
    else if (!strcmp(argv[i], "--frames") && i + 1 < argc) frames = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--every") && i + 1 < argc) every = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--place") && i + 4 < argc) { x = (float)atof(argv[i + 1]); y = (float)atof(argv[i + 2]); z = (float)atof(argv[i + 3]); h = (float)atof(argv[i + 4]); place = 1; i += 4; }
    else { fprintf(stderr, "port_light: непонятный ключ %s\n", argv[i]); return 2; }
  }
  if (bwData(argv[1], argv[2], msn)) { fprintf(stderr, "port_light: нет данных уровня/Гомера/миссий\n"); return 2; }
  static BotWorld w;
  if (bwNew(&w)) { fprintf(stderr, "port_light: мир без коллизии\n"); return 2; }
  if (place) bwPlace(&w, x, y, z, h);
  out(&w, 0);
  for (int f = 1; f <= frames; f++) { bwStep(&w, 0, 0.f, 0.f); if ((every > 0 && f % every == 0) || f == frames) out(&w, f); }
  return 0;
}
