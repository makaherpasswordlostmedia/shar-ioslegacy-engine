// Гейт «машина уровня в движке» (tests/cars/cars.sh), часть 2: езда, выход и посадка на машине уровня в мире ботов
// (tools/bots/world.c — тот же код логики, что EBOOT: car.c, homer.c, game.c). Уровень без трафика, карточек и комнат
// (BW_NO_*), чтобы мерить только машину и Гомера.
//   drive_host LEVEL.shr HOMER.shr МАШИНА   -> строки отчёта, последняя «PASS»/«FAIL …»; код 0/1
// Сценарий: старт уровня за рулём -> 3 с газ (X) -> тормоз до остановки -> △ выход -> △ посадка -> 2 с газ.
// Провал: машина мира не та (CAR1 не прочитан или чужое имя); за 3 с газа проехала < 5 м или быстрее своей TopSpeed;
// выход дольше 4 с; посадка дольше 4 с (Гомер не дошёл до двери — через 4 с движок сажает «как есть») или с выбросом;
// Гомер в машине не внутри коробки кузова; после посадки машина не едет.
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "world.h"

static int frames(BotWorld *w, int n, unsigned b) { for (int i = 0; i < n; i++) bwStep(w, b, 0.f, 0.f); return n; }

int main(int argc, char **argv) {
  if (argc < 4) { fprintf(stderr, "drive_host LEVEL.shr HOMER.shr МАШИНА\n"); return 2; }
  setenv("BW_NO_TRAFFIC", "1", 1); setenv("BW_NO_COLLECT", "1", 1); setenv("BW_NO_ROOMS", "1", 1);
  if (bwData(argv[1], argv[2], NULL)) { printf("FAIL: мир не загрузился (%s)\n", argv[1]); return 1; }
  int bad = 0;
  printf("машина мира: %s (CAR1: %d)\n", bwCarName(), bwCarSource());
  if (bwCarSource() != 1 || strcmp(bwCarName(), argv[3])) { printf("  ПРОВАЛ: машина мира %s, ждали %s\n", bwCarName(), argv[3]); bad++; }
  static BotWorld W; BotWorld *w = &W;
  if (bwNew(w) || !w->haveCol || !w->haveHomer) { printf("FAIL: новая игра без коллизии или Гомера\n"); return 1; }
  const CarParams *P = &w->car.p;
  printf("параметры: %s масса %.0f, TopSpeed %.1f км/ч, кузов %.2f x %.2f, дверь (%.3f, %.3f), якорь (%.3f, %.3f)\n", P->name, P->mass,
         P->topSpeed * 3.6f, 2 * P->halfW, 2 * P->halfL, P->doorX, P->doorZ, P->seatAx, P->seatAz);
  // 1 — газ 3 с. Меряется машина, а не старт: если курс старта упирается в стену ближе 5 м (так у уровня 3 — отдельный
  // вопрос к старту, печатается), тот же разгон со старта курсом +90°, -90°, 180°
  float sx, sy, sz, sh; bwSpawn(&sx, &sy, &sz, &sh);
  static const float turn[4] = {0.f, 1.5707963f, -1.5707963f, 3.1415927f};
  float d1 = 0.f, vmax = 0.f; int k = 0;
  for (; k < 4; k++) {
    if (k) { bwNew(w); bwPlace(w, sx, sy, sz, sh + turn[k]); }
    float x0 = w->car.x, z0 = w->car.z; vmax = 0.f;
    for (int i = 0; i < 180; i++) { bwStep(w, GP_CROSS, 0.f, 0.f); if (w->car.v > vmax) vmax = w->car.v; }
    d1 = hypotf(w->car.x - x0, w->car.z - z0);
    if (d1 >= 5.f) break;
    printf("старт курсом %+.2f рад: за 3 с газа %.1f м — впереди стена (%.1f м/с)\n", turn[k], d1, w->st.maxWallV);
  }
  if (k == 4) k = 3;
  printf("газ 3 с%s: %.1f м, до %.1f км/ч (TopSpeed %.1f)\n", k ? " (курс старта повёрнут)" : "", d1, vmax * 3.6f, P->topSpeed * 3.6f);
  if (d1 < 5.f || vmax > P->topSpeed * 1.05f) { printf("  ПРОВАЛ: езда\n"); bad++; }
  for (int i = 0; i < 300 && fabsf(w->car.v) > .3f; i++) bwStep(w, GP_CIRCLE, 0.f, 0.f);
  frames(w, 30, 0);
  // 2 — выход
  int t = 0; bwStep(w, GP_TRIANGLE, 0.f, 0.f); t++;
  while (t < 240 && !gameOnFoot(&w->G)) { bwStep(w, 0, 0.f, 0.f); t++; }
  while (t < 240 && w->homer.state != HS_FOOT) { bwStep(w, 0, 0.f, 0.f); t++; }
  float cx = w->car.x, cz = w->car.z, fx = sinf(w->car.h), fz = cosf(w->car.h);
  float lat = (w->homer.x - cx) * fz - (w->homer.z - cz) * fx, lon = (w->homer.x - cx) * fx + (w->homer.z - cz) * fz;
  printf("выход: %.2f с, Гомер %s, через верх %d, сбоку %+.2f м, вдоль %+.2f м\n", t / 60.f, w->homer.state == HS_FOOT ? "пешком" : "не вышел",
         w->homer.overTop, lat, lon);
  if (t >= 240) { printf("  ПРОВАЛ: выход дольше 4 с\n"); bad++; }
  frames(w, 20, 0);
  // 3 — посадка
  int iris0 = w->homer.irisSeat, ej0 = w->homer.ejected; t = 0;
  bwStep(w, GP_TRIANGLE, 0.f, 0.f); t++;
  int started = w->homer.state == HS_TO_DOOR || w->homer.state == HS_GET_IN;
  while (t < 600 && w->homer.state != HS_IN_CAR) { bwStep(w, 0, 0.f, 0.f); t++; }
  int sat = t; frames(w, 10, 0);                             // поза «сидит» ставится в кадре HS_IN_CAR (кадр посадки — ещё корень клипа)
  CarBox b; carBox(&w->car, &b);
  float ex = w->homer.x - b.x, ez = w->homer.z - b.z, a = ex * b.fx + ez * b.fz, s = -ex * b.fz + ez * b.fx;
  int inBody = fabsf(a) <= b.hl && fabsf(s) <= b.hw;
  printf("посадка: %s за %.2f с, ирисом %d, Гомер в машине: вдоль %+.2f из ±%.2f, сбоку %+.2f из ±%.2f\n",
         w->homer.state == HS_IN_CAR ? "сел" : "не сел", sat / 60.f, w->homer.irisSeat - iris0, a, b.hl, s, b.hw);
  if (!started || w->homer.state != HS_IN_CAR || sat > 240 || w->homer.irisSeat != iris0 || w->homer.ejected != ej0) { printf("  ПРОВАЛ: посадка\n"); bad++; }
  if (!inBody) { printf("  ПРОВАЛ: Гомер в машине вне кузова\n"); bad++; }
  // 4 — снова газ 2 с
  float x0 = w->car.x, z0 = w->car.z; frames(w, 120, GP_CROSS);
  float d2 = hypotf(w->car.x - x0, w->car.z - z0);
  printf("после посадки газ 2 с: %.1f м\n", d2);
  if (d2 < 2.f) {   // правки 164/187: машина оригинала гасит удар на месте и остаётся у стены (не отскакивает) — впереди стена,
    x0 = w->car.x; z0 = w->car.z; frames(w, 120, GP_CIRCLE);   // тогда управляемость — задний ход («кружок»), как сделал бы игрок
    d2 = hypotf(w->car.x - x0, w->car.z - z0);
    printf("  впереди стена — назад 2 с: %.1f м\n", d2);
  }
  if (d2 < 2.f) { printf("  ПРОВАЛ: после посадки не едет\n"); bad++; }
  printf(bad ? "FAIL (%d)\n" : "PASS\n", bad);
  return bad ? 1 : 0;
}
