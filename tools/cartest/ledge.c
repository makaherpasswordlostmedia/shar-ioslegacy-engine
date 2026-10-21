// Уступы на срезах и дорогах (правка Роба 486, вопрос В92): те же пробы, что viewer/msncar.c probeLedge, но в обе стороны хода
// и с сверкой по рисуемой геометрии (как tools/cartest/walls.c). Статический замер COL1 и рисунка, машины не ездят.
//   ledge --level L.shr --roads roads-lN.bin [--meta roads-lN.meta.tsv] [--up 0.8]
// Строка L: отрезок, ход (0 по отрезку a->b, 1 против), shortcut, x y z (где опора кончается), prev (опора до), g (опора после),
//   rise = g - prev, draw0 = рисуемая земля у prev (|draw0 - prev| <= 0.5: под коллизией «выше» рисунок продолжается на старом уровне,
//   значит опора выше — крыша/эстакада над дорогой, а не стена), drawG = рисуемая земля у g (есть ли нарисованный верх уступа),
//   класс: low (rise <= tol: заезжается), wall (рисунок верха есть, внизу его нет: настоящий уступ), over (рисунок у prev продолжается: опора
//   выше — эстакада/козырёк, уступа нет), ghost (рисунка нет ни там, ни там: невидимая опора выше).
//   cc -std=c99 -O2 -I viewer tools/cartest/ledge.c viewer/col.c viewer/car.c viewer/props.c viewer/stateprops.c viewer/coins.c -lm -o build/ledge
#define WALLS_NO_MAIN 1
#include "walls.c"

static int shortcutOf[4096];
int main(int argc, char **argv) {
  const char *level = 0, *road = 0, *meta = 0; float up = .8f, tol = .43f;
  for (int i = 1; i < argc; i++) {
    if (!strcmp(argv[i], "--level") && i + 1 < argc) level = argv[++i];
    else if (!strcmp(argv[i], "--roads") && i + 1 < argc) road = argv[++i];
    else if (!strcmp(argv[i], "--meta") && i + 1 < argc) meta = argv[++i];
    else if (!strcmp(argv[i], "--up") && i + 1 < argc) up = atof(argv[++i]);
    else if (!strcmp(argv[i], "--tol") && i + 1 < argc) tol = atof(argv[++i]);
    else { fprintf(stderr, "unknown argument %s\n", argv[i]); return 2; }
  }
  if (!level || !road) { fprintf(stderr, "usage: ledge --level L.shr --roads roads.bin [--meta roads.meta.tsv]\n"); return 2; }
  staticOnly = 1; loadLevel(level); loadRoads(road); loadRender();
  if (meta) { FILE *m = fopen(meta, "r"); char ln[512]; int i = 0;
    if (m) { while (fgets(ln, sizeof ln, m)) { if (ln[0] == '#') continue; char seg[128], rd[128]; int mc, sp, it, sc;
        if (sscanf(ln, "%127s %127s %d %d %d %d", seg, rd, &mc, &sp, &it, &sc) == 6 && i < 4096) shortcutOf[i++] = sc; } fclose(m); } }
  int cnt[2][4] = {{0}}, nseg[2] = {0};
  for (int r = 0; r < nroad; r++) {
    for (int d = 0; d < 2; d++) {
      const Road *R = &roads[r];
      float ax = d ? R->bx : R->ax, ay = d ? R->by : R->ay, az = d ? R->bz : R->az, bx = d ? R->ax : R->bx, by = d ? R->ay : R->by, bz = d ? R->az : R->bz;
      float dx = bx - ax, dz = bz - az, L = sqrtf(dx * dx + dz * dz); if (L < 1.f) continue;
      float prev = 0, g; int have = 0, found = 0;
      for (float u = 0.f; u < L && !found; u += 1.f) {
        float x = ax + dx * u / L, y = ay + (by - ay) * u / L, z = az + dz * u / L;
        if (!have) { if (colGround(&W, x, z, y + 1.5f, y - 3.f, &g, 0)) { prev = g; have = 1; } continue; }
        if (colGround(&W, x, z, prev + up, prev - 6.f, &g, 0)) { prev = g; continue; }
        if (colGround(&W, x, z, prev + 6.f, prev + up, &g, 0)) {
          float d0 = renderGround(x, z, prev + .6f), dG = renderGround(x, z, g + .3f);
          const char *cls; float rise = g - prev;
          int draw0 = d0 > -1e8f && fabsf(d0 - prev) <= .5f, drawG = dG > -1e8f && fabsf(dG - g) <= .5f;
          if (rise <= tol) cls = "low"; else if (draw0) cls = "over"; else if (drawG) cls = "wall"; else cls = "ghost";
          int ci = !strcmp(cls, "low") ? 0 : !strcmp(cls, "over") ? 1 : !strcmp(cls, "wall") ? 2 : 3;
          cnt[d][ci]++; nseg[d]++; found = 1;
          printf("L\t%d\t%d\t%d\t%.1f\t%.1f\t%.1f\t%.2f\t%.2f\t%.2f\t%.2f\t%.2f\t%s\n", r, d, r < 4096 ? shortcutOf[r] : -1, x, y, z, prev, g, rise,
                 d0 > -1e8f ? d0 - prev : -9.f, dG > -1e8f ? dG - g : -9.f, cls);
        }
      }
    }
  }
  fprintf(stderr, "отрезков %d; по ходу: low %d over %d wall %d ghost %d; против хода: low %d over %d wall %d ghost %d\n", nroad,
          cnt[0][0], cnt[0][1], cnt[0][2], cnt[0][3], cnt[1][0], cnt[1][1], cnt[1][2], cnt[1][3]);
  return 0;
}
