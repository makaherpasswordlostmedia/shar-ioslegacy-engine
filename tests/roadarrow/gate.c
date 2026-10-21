// Гейт №606 (стрелки на дороге): на настоящих данных уровня (коллизия COL1 + дороги трафика) набор зелёных стрелок (viewer/roadarrow.h — тот же код, что в игре)
// не прячется под дорогу. Точки пути берутся у игры: trafficRouteArrow на сетке положений игрока по дорогам и нескольких целях.
// «Подложенный провал» (--sink М): узел дороги ниже асфальта на М метров (реальные уровни дают такое на склонах и мостах) — прежний путь (--old) стрелку теряет, новый нет.
//   gate LEVEL.shr HOMER.shr [--old] [--sink 0.5]     RESULT: PASS|FAIL (--old: PASS = красный пойман, т.е. прежний путь потерял стрелки)
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <math.h>
#include "world.h"
#include "traffic.h"
#include "roadarrow.h"
static int gAt(float x, float z, float yHi, float yLo, float *out) { float n[3]; return colGround(bwCol(), x, z, yHi, yLo, out, n); }
int main(int argc, char **argv) {
  if (argc < 3 || bwData(argv[1], argv[2], 0)) { fprintf(stderr, "usage\n"); return 2; }
  int old = 0; float sink = 0.f;
  for (int i = 3; i < argc; i++) { if (!strcmp(argv[i], "--old")) old = 1; else if (!strcmp(argv[i], "--sink") && i + 1 < argc) sink = (float)atof(argv[++i]); }
  static BotWorld w; if (bwNew(&w)) return 2;
  const Traffic *t = (const Traffic *)bwTraffic(); if (!t) { printf("нет трафика\nRESULT: FAIL\n"); return 1; }
  const float tg[6][2] = {{220, 172}, {-150, -300}, {300, -100}, {-300, 200}, {0, 0}, {100, 350}};
  int n = 0, buried = 0, noGround = 0; float worstDepth = 0;
  for (float px = -600; px <= 600; px += 20) for (float pz = -600; pz <= 600; pz += 20) for (float ph = 0; ph < 6.2f; ph += 1.57f) for (int g = 0; g < 6; g++) {
    float p[3], h;
    if (!trafficRouteArrow(t, px, pz, ph, tg[g][0], tg[g][1], 70.f, p, &h)) continue;
    p[1] -= sink; n++;
    float top = raTop(gAt, p, h); if (top < -1e8f) { noGround++; continue; }
    float y = old ? p[1] : raLiftedY(gAt, p, h);
    // стрелки лежат на асфальте (+0,02 м в данных набора): закрыты, если их высота ниже самой высокой коллизии под набором
    if (y + 0.02f < top - 0.005f) { buried++; if (top - y > worstDepth) worstDepth = top - y; }
  }
  printf("точек маршрута %d, без земли под набором %d, закрыто дорогой %d (%.1f%%), худшая глубина %.2f м, режим %s, провал узла %.2f м\n", n, noGround, buried, n ? 100.0 * buried / n : 0.0, worstDepth, old ? "прежний" : "новый", sink);
  int ok = n >= 5 && (old ? buried > 0 : buried == 0);
  printf("RESULT: %s\n", ok ? "PASS" : "FAIL");
  return ok ? 0 : 1;
}
