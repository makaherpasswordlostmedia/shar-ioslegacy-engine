// Близнецы · набор «постановка машины» (tools/twins/placement.py): сторона «Порт, лёгкий» пачкой — мир ботов tools/bots/world.c
// (та же логика машины и коллизии, что EBOOT), без экрана, детерминированно: каждая проба начинается с одного снимка мира.
//   placement_light LEVEL HOMER [--msn FILE] probe            stdin: "id x z" (оси порта) -> опоры над точкой
//   placement_light LEVEL HOMER [--msn FILE] dump             заборы (ColSeg) и ящики (ColBox) коллизии уровня, сетка
//   placement_light LEVEL HOMER [--msn FILE] run [--every K]
//                                                             stdin: "id x y z h N M f|r" (оси порта; y — от какой высоты искать
//                                                             опору вниз; N кадров покоя, M кадров газа: f — газ X, r — назад ○)
// probe: опоры сверху вниз (как bwWhere: слипшиеся в 1 м — одна), у каждой — высота, наклон n.y, материал (0 твёрдое, 1 куст),
//        глубина кузова машины 1,8×4,4 м на этой опоре при курсе 0 и 90° (colProbeCar: > 0 — внутри стены/дома)
// run:   проба = снимок мира -> bwPlace (как goto) -> N кадров без ввода («дали физике») -> M кадров газа (X) или назад (○) прямо
//        -> строка JSON: где поставлена, где после покоя, где после газа (поза, скорость, на земле, опора bwWhere, урон, пешком)
// Сам мир не меняется; отличия от EBOOT — как у мира ботов (world.h): без рисования, звука, интерфейса.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "world.h"
#include "col.h"

static void pose(const char *tag, BotWorld *w) {
  char obj[16]; int nl = 0;
  int layer = bwWhere(w->car.x, w->car.y, w->car.z, 1.f, &nl, obj);
  printf("\"%s\":{\"x\":%.4f,\"y\":%.4f,\"z\":%.4f,\"h\":%.5f,\"v\":%.4f,\"vel\":[%.4f,%.4f,%.4f],\"grounded\":%d,\"wheels\":%d,"
         "\"pitch\":%.4f,\"roll\":%.4f,\"damage\":%.4f,\"destroyed\":%d,\"onfoot\":%d,\"layer\":%d,\"nlayers\":%d,\"obj\":\"%s\","
         "\"contacts\":%d,\"foliage\":%d}",
         tag, w->car.x, w->car.y, w->car.z, w->car.h, w->car.v, w->car.vel[0], w->car.vel[1], w->car.vel[2], w->car.grounded, w->car.wheels,
         w->car.pitch, w->car.roll, w->car.damage, w->car.destroyed, gameOnFoot(&w->G), layer, nl, obj, w->car.contacts, colFoliageHits());
}

static int probe(void) {
  const ColWorld *cw = bwCol(); char id[64]; float x, z;
  while (scanf("%63s %f %f", id, &x, &z) == 3) {
    float ys[16], ns[16], n3[3], top = 1e4f; int mats[16], k = 0;
    while (k < 16 && colGroundMat(cw, x, z, top, -1e4f, &ys[k], n3, &mats[k])) { ns[k] = n3[1]; top = ys[k] - 1.f; k++; }
    printf("{\"id\":\"%s\",\"x\":%.3f,\"z\":%.3f,\"layers\":[", id, x, z);
    for (int i = 0; i < k; i++) {
      float dep[2];
      for (int a = 0; a < 2; a++) {
        CarBox b; memset(&b, 0, sizeof b); b.x = x; b.z = z; b.fx = a ? 1.f : 0.f; b.fz = a ? 0.f : 1.f; b.hw = .9f; b.hl = 2.2f;
        b.y = ys[i]; b.lo = .35f; b.hi = 1.6f; colProbeCar(cw, &b); dep[a] = b.maxDepth;
      }
      char obj[16]; int nl = 0; bwWhere(x, ys[i], z, 1.f, &nl, obj);
      printf("%s[%.3f,%.3f,%d,%.3f,%.3f,\"%s\"]", i ? "," : "", ys[i], ns[i], mats[i], dep[0], dep[1], obj);
    }
    printf("]}\n");
  }
  return 0;
}

static int dump(void) {   // заборы и ящики коллизии (для выбора точек «забор» и «у стены»), границы сетки
  const ColWorld *cw = bwCol();
  printf("{\"grid\":[%.3f,%.3f,%.3f,%d,%d],\"ntri\":%u,\"nbox\":%u,\"ncyl\":%u,\"nseg\":%u}\n", cw->ox, cw->oz, cw->cell, cw->W, cw->H, cw->ntri, cw->nbox, cw->ncyl, cw->nseg);
  for (uint32_t i = 0; i < cw->nseg; i++) { const ColSeg *g = &cw->seg[i];
    printf("{\"seg\":%u,\"a\":[%.3f,%.3f],\"b\":[%.3f,%.3f],\"n\":[%.4f,%.4f],\"y0\":%.3g,\"y1\":%.3g}\n", i, g->a[0], g->a[1], g->b[0], g->b[1], g->n[0], g->n[1], g->y0, g->y1); }
  for (uint32_t i = 0; i < cw->nbox; i++) { const ColBox *b = &cw->box[i];
    printf("{\"box\":%u,\"c\":[%.3f,%.3f,%.3f],\"ax\":[%.4f,%.4f,%.4f],\"ay\":[%.4f,%.4f,%.4f],\"az\":[%.4f,%.4f,%.4f],\"h\":[%.3f,%.3f,%.3f],\"mat\":%.0f}\n",
           i, b->c[0], b->c[1], b->c[2], b->ax[0], b->ax[1], b->ax[2], b->ay[0], b->ay[1], b->ay[2], b->az[0], b->az[1], b->az[2], b->h[0], b->h[1], b->h[2], b->pad); }
  return 0;
}

static int run(BotWorld *w, int every) {
  static BotSnap snap; bwSaveAlloc(w, &snap); bwSave(w, &snap);
  char id[64], mode[8]; float x, y, z, h; int settle, gas;
  while (scanf("%63s %f %f %f %f %d %d %7s", id, &x, &y, &z, &h, &settle, &gas, mode) == 8) {
    unsigned btn = mode[0] == 'r' ? GP_CIRCLE : GP_CROSS;
    bwLoad(w, &snap);
    bwPlace(w, x, y, z, h);
    int deathZone = gameDeathAt(&w->G);
    const ColWorld *deathWorld = bwCol();
    printf("{\"id\":\"%s\",\"ask\":[%.4f,%.4f,%.4f,%.5f,%d,%d,\"%s\"],\"lift\":%.4f,", id, x, y, z, h, settle, gas, mode, w->lift);
    printf("\"placed_death_zone\":%d,", deathZone);
    if (deathZone >= 0 && (unsigned)deathZone < deathWorld->ndeath) {
      const float *a = deathWorld->death[deathZone].apex;
      printf("\"placed_death_apex\":[%.4f,%.4f,%.4f],", a[0], a[1], a[2]);
    }
    pose("placed", w); printf(",\"trace\":[");
    int n = 0, settleDeath = -1, deathFrame = -1;
    for (int f = 1; f <= settle + gas; f++) {
      bwStep(w, f > settle ? btn : 0u, 0.f, 0.f);
      if (f <= settle && bwLastDeathZone >= 0 && deathFrame < 0) { settleDeath = bwLastDeathZone; deathFrame = f; }
      if (every > 0 && f % every == 0) { printf("%s[%d,%.3f,%.3f,%.3f,%.4f,%.3f]", n++ ? "," : "", f, w->car.x, w->car.y, w->car.z, w->car.h, w->car.v); }
      if (f == settle) { printf("],"); pose("settled", w); printf(",\"trace2\":["); n = 0; }
    }
    printf("],"); pose("gassed", w);
    printf(",\"settle_death_zone\":%d,\"settle_death_frame\":%d", settleDeath, deathFrame);
    if (settleDeath >= 0 && (unsigned)settleDeath < deathWorld->ndeath) {
      const float *a = deathWorld->death[settleDeath].apex;
      printf(",\"settle_death_apex\":[%.4f,%.4f,%.4f]", a[0], a[1], a[2]);
      printf(",\"settle_death_name\":\"%.16s\"", deathWorld->death[settleDeath].name);
    }
    printf("}\n"); fflush(stdout);
  }
  return 0;
}

int main(int argc, char **argv) {
  if (argc < 4) { fprintf(stderr, "usage: placement_light LEVEL HOMER [--msn FILE] probe|run [--every K]\n"); return 2; }
  const char *msn = 0, *mode = 0; int every = 6;
  for (int i = 3; i < argc; i++) {
    if (!strcmp(argv[i], "--msn") && i + 1 < argc) msn = argv[++i];
    else if (!strcmp(argv[i], "--every") && i + 1 < argc) every = atoi(argv[++i]);
    else if (!strcmp(argv[i], "probe") || !strcmp(argv[i], "run") || !strcmp(argv[i], "dump")) mode = argv[i];
    else { fprintf(stderr, "placement_light: непонятный ключ %s\n", argv[i]); return 2; }
  }
  if (!mode) { fprintf(stderr, "placement_light: нужен режим probe или run\n"); return 2; }
  if (bwData(argv[1], argv[2], msn)) { fprintf(stderr, "placement_light: нет данных уровня/Гомера/миссий\n"); return 2; }
  static BotWorld w;
  if (bwNew(&w)) { fprintf(stderr, "placement_light: мир без коллизии\n"); return 2; }
  if (!strcmp(mode, "probe")) return probe();
  if (!strcmp(mode, "dump")) return dump();
  return run(&w, every);
}
