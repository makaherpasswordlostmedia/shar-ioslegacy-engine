// Стенд «ловушка или бот»: одно и то же место, четыре модели, 8 курсов, набор манёвров игрока. Только процессор Мака.
//   trap --level L.shr --lvl N [--roads R.bin] L:x:z[:y] ...   (или --tsv кластеры.tsv --kind stuck --top 12)
// Для каждой модели и курса машина ставится на землю в точке, 0,5 с стоит, затем из этого состояния пробуются манёвры
// (вперёд прямо/влево/вправо, назад прямо/влево/вправо, таран-бот, дикий бот). Выбралась = ушла от точки на ESC метров
// или игра сама вернула её на надёжное место (recovery). Место «ловушка», если не выбралась ни одна пара модель×курс×манёвр.
#define SANDBOX_NO_MAIN
#include <stdarg.h>
#include "sandbox.c"

#define ESC 8.f
#define MAN_N 8
static const char *MAN[MAN_N] = {"вперёд", "вперёд-влево", "вперёд-вправо", "назад", "назад-влево", "назад-вправо", "таран-бот", "дикий-бот"};
static const char *MODELS[4] = {"famil_v", "sportsa", "pickupa", "schoolbu"};
typedef struct { int lvl; float x, y, z; int n; float h; int model, hasH; } Spot;

static int placeCar(Car *c, const CarParams *p, float x, float y, float z, float h) {
  carInit(c, p, &W, x, y, z, h);
  CarBox b; carBox(c, &b); colProbeCar(&W, &b);
  return sane(c) && b.maxDepth <= .05f && c->grounded && c->wheels >= 3;
}
static int run(const Car *start, int man, uint32_t seed, int *recov, float *far) {
  Car c = *start; Bot bot; memset(&bot, 0, sizeof bot); bot.mode = man == 7 ? 1 : 2;
  bot.lastX = c.x; bot.lastZ = c.z;
  rng = seed ? seed : 1; CarBox prev; carBox(&c, &prev);
  float sx = c.x, sz = c.z; int rc0 = c.recoveries; *far = 0;
  for (int t = 0; t < 6 * 60; t++) {
    CarInput in = {0};
    switch (man) {
    case 0: in.throttle = 1; break;
    case 1: in.throttle = 1; in.steer = -1; break;
    case 2: in.throttle = 1; in.steer = 1; break;
    case 3: in.brake = 1; break;
    case 4: in.brake = 1; in.steer = -1; break;
    case 5: in.brake = 1; in.steer = 1; break;
    default: botStep(&bot, &c, &in, t / 60.f); break;
    }
    carUpdate(&c, &W, &in, 1.f / 60);
    if (!sane(&c)) return 0;
    propsHitCar(&objects, &W, &c, &prev); spHitCar(&stateObjects, &W, &c, 0); carBox(&c, &prev);
    float d = hypotf(c.x - sx, c.z - sz); if (d > *far) *far = d;
    if (d >= ESC) return 1;
    if (c.recoveries > rc0) { *recov = 1; return 1; }
  }
  return 0;
}

int main(int argc, char **argv) {
  const char *level = 0, *road = 0, *tsv = 0, *kind = "stuck"; int top = 12, lvl = 1; Spot spots[64]; int ns = 0;
  for (int i = 1; i < argc; i++) {
    if (!strcmp(argv[i], "--level") && i + 1 < argc) level = argv[++i];
    else if (!strcmp(argv[i], "--roads") && i + 1 < argc) road = argv[++i];
    else if (!strcmp(argv[i], "--lvl") && i + 1 < argc) lvl = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--tsv") && i + 1 < argc) tsv = argv[++i];
    else if (!strcmp(argv[i], "--kind") && i + 1 < argc) kind = argv[++i];
    else if (!strcmp(argv[i], "--poses") && i + 1 < argc) {   // позы из bots_swarm --poses: уровень x y z курс модель ...
      FILE *f = fopen(argv[++i], "r"); char ln[400];
      while (f && fgets(ln, sizeof ln, f) && ns < 64) { Spot s = {0, 0, 0, 0, 1, 0, 0, 1}; float pi_, ro; if (sscanf(ln, "%d\t%f\t%f\t%f\t%f\t%d\t%f\t%f", &s.lvl, &s.x, &s.y, &s.z, &s.h, &s.model, &pi_, &ro) >= 6 && s.lvl == lvl) spots[ns++] = s; }
      if (f) fclose(f); }
    else if (!strcmp(argv[i], "--top") && i + 1 < argc) top = atoi(argv[++i]);
    else if (ns < 64) { Spot s = {lvl, 0, 1e9f, 0, 0, 0, 0, 0}; if (sscanf(argv[i], "%f:%f:%f", &s.x, &s.z, &s.y) >= 2) spots[ns++] = s; }
  }
  if (!level) { fprintf(stderr, "usage: trap --level L.shr --lvl N [--roads R.bin] x:z[:y] ...  |  --tsv clusters.tsv --kind stuck --top 12\n"); return 2; }
  if (tsv) {   // кластеры этого уровня из clusters.tsv (уровень x y z тип повторов ...)
    FILE *f = fopen(tsv, "r"); char ln[1200];
    while (f && fgets(ln, sizeof ln, f) && ns < top) { Spot s; char k[32]; if (ln[0] == '#') continue;
      if (sscanf(ln, "%d\t%f\t%f\t%f\t%31s\t%d", &s.lvl, &s.x, &s.y, &s.z, k, &s.n) == 6 && s.lvl == lvl && !strcmp(k, kind)) spots[ns++] = s; }
    if (f) fclose(f);
  }
  if (!freopen("/dev/null", "w", stdout)) return 2;
  loadLevel(level); loadObjects(); if (road) loadRoads(road);
  for (int si = 0; si < ns; si++) {
    Spot *s = &spots[si]; float g, n3[3];
    if (!colGround(&W, s->x, s->z, s->y < 1e8f ? s->y + 3.f : 10000.f, s->y < 1e8f ? s->y - 6.f : -1e5f, &g, n3)) { fprintf(stderr, "L%d x=%.0f z=%.0f: земли нет\n", s->lvl, s->x, s->z); continue; }
    float slope = acosf(fminf(1.f, fmaxf(-1.f, n3[1]))) * 180.f / PI;
    int placed[4] = {0}, total[4] = {0}, esc[4][MAN_N] = {{0}}, escAny[4] = {0}, recov[4] = {0}, tries[4] = {0}; float bestFar[4] = {0};
    for (int m = 0; m < 4; m++) {
      CarParams p; if (!carParamsFor(MODELS[m], &p)) { fprintf(stderr, "нет параметров %s\n", MODELS[m]); return 2; }
      for (int hi = 0; hi < 8; hi++) {
        Car c; float h = s->hasH ? s->h + (hi % 2 ? 1 : -1) * (hi / 2) * 0.35f : hi * PI / 4;   // по позе: курс застрявшей ± 0,35 рад; иначе 8 курсов
        total[m]++;
        int okp = 0; for (int k = 0; k < 8 && !okp; k++) okp = placeCar(&c, &p, s->x, g + .15f * k, s->z, h);
        if (!okp) continue;
        placed[m]++;
        CarInput z = {0}; CarBox prev; carBox(&c, &prev);
        for (int t = 0; t < 30; t++) { carUpdate(&c, &W, &z, 1.f / 60); propsHitCar(&objects, &W, &c, &prev); carBox(&c, &prev); }
        int any = 0;
        for (int man = 0; man < MAN_N; man++) {
          int rc = 0; float far; tries[m]++;
          int ok = run(&c, man, 1234567u + (uint32_t)hi * 7919u + (uint32_t)man, &rc, &far);
          if (ok) { esc[m][man]++; any = 1; if (rc) recov[m]++; }
          if (far > bestFar[m]) bestFar[m] = far;
        }
        escAny[m] += any;
      }
    }
    fprintf(stderr, "L%d x=%.1f y=%.1f z=%.1f (повторов у ботов %d), уклон земли %.0f°\n", s->lvl, s->x, g, s->z, s->n, slope);
    int trapAll = 1;
    for (int m = 0; m < 4; m++) {
      fprintf(stderr, "  %-8s поставлено %d/8 курсов; выбралась хоть чем-то: %d; игра вернула сама: %d; по манёврам:", MODELS[m], placed[m], escAny[m], recov[m]);
      for (int man = 0; man < MAN_N; man++) fprintf(stderr, " %s=%d", MAN[man], esc[m][man]);
      fprintf(stderr, " | дальше всего ушла %.1f м\n", bestFar[m]);
      if (escAny[m]) trapAll = 0;
    }
    int placedAny = placed[0] + placed[1] + placed[2] + placed[3];
    fprintf(stderr, "  ВЕРДИКТ: %s\n", !placedAny ? "не удалось поставить ни одну машину (место внутри стены)" : trapAll ? "ЛОВУШКА: не выбралась ни одна модель ни одним манёвром" : "не ловушка: игрок выбирается");
  }
  propsFree(&objects); spFree(&stateObjects); colFree(&W);
  return 0;
}
