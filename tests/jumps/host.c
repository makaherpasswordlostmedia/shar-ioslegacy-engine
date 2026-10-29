// Правки Роба 46 и 47 на Маке: зоны прыжка машин (перелёт дома с трамплина) и подкидывающие точки Гомера.
//   tests/jumps/host.sh [level.shr] [homer.shr] [ключи]   — сборка и прогон; итог «jumps: PASS/FAIL», код выхода = число провалов
// Те же модули, что у движка (car.c, col.c, homer.c, skin.c host). Все цели — из данных уровня, координат руками нет:
//   зоны и точки — блок JMP1 секции COL1 (tools/jumps_export.py: Event 48 jumpzone* и Event 6 диска);
//   линия трамплина — build/sandbox/routes-l1.tsv (tools/cartest/routes.py: старт, направление, кромка по данным);
//   дом — ящики COL1 над линией полёта сразу за кромкой (самый высокий верх в 25 м); «крыша» — нарисованная геометрия
//   (куски города level.shr, как в переписи стен tools/cartest/walls.c).
// Проверки:
//   1. JMP1 есть: зоны и точки прочитаны.
//   2. Маршрут «дом» (зона jumpzone17, статичная камера z1_housejump диска снимает перелёт этого дома): веер 60..120 км/ч,
//      курс −5/0/+5°, прицел вбок −2/0/+2 м. Как у оригинала (правка 342, близнец PS2): на 60–70 км/ч машина встаёт у дома
//      (не меньше 80 % заездов), от 100 км/ч перелетает (не меньше 80 %); ударов о стену в полёте ВЫШЕ нарисованного (низ машины
//      над рисунком у точки удара больше 1 м, ABOVE_TOL) — ноль. До правки 342 ожидание было «перелёт на любой скорости».
//   3. Подкидывающие точки: Гомер встаёт в объём каждой точки (на опору внутри объёма), ничего не нажимает; вершина его
//      полёта — у точки локатора: по высоте ±0.35 м, по горизонтали до 0.6 м. Норма: все точки, на которые можно встать.
// Отрицательные контроли (гейт обязан покраснеть): --no-boost (зоны выключены: без разгона зоны дом не перелетается и на 100 км/ч),
// --old47 (прежнее правило правки 47 — подброс до верха зоны: перелёт и на 60 км/ч), --plant-wall (ящик дома поднят на 6 м —
// «стена выше крыши» подложена), --no-pads (подкидывающие точки выключены).
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "homer.h"

extern int carJumpBoostOff, carJumpBoost, homerBounceOff;
static ColWorld W; static unsigned char *file; static long fileSize; static int fails;
static void check(const char *what, float got, float lo, float hi, const char *expect) {
  int ok = got >= lo && got <= hi; if (!ok) fails++;
  printf("%-4s %-58s %8.3f   (%s)\n", ok ? "ok" : "FAIL", what, got, expect);
}

// ---------------------------------------------------------------- рисуемая геометрия (как tools/cartest/walls.c)
typedef struct { float bb[6]; int32_t tex; uint32_t flags, nv, ni, owner; float ox, oy, oz, sc; uint32_t off, nf, cell, pad[2]; } Rec;
typedef struct { float bb[6]; uint32_t first, n, owner, off, size, pad; } CellRec;
static float *T; static unsigned NT; static unsigned *gS, *gL; static int GW, GH; static float GOX, GOZ; static const float GC = 2.f;
static void loadRender(void) {
  uint32_t npc, tableOff, cellOff; memcpy(&npc, file + 8, 4); memcpy(&tableOff, file + 76, 4); memcpy(&cellOff, file + 84, 4);
  const Rec *recs = (const Rec *)(file + tableOff); const CellRec *cells = (const CellRec *)(file + cellOff);
  unsigned cap = 1 << 20; T = malloc(sizeof(float) * 9 * cap);
  for (unsigned i = 0; i < npc; i++) {
    const Rec *r = &recs[i]; if (r->owner != 0 || (r->flags & 4) || !(r->flags & 16)) continue;   // город, не небо, без индексов
    int vs = (r->flags & 32) ? 12 : 16; const uint8_t *b = file + cells[r->cell].off + r->off;
    for (unsigned k = 0; k + 2 < r->ni; k += 3) {
      if (NT == cap) { cap *= 2; T = realloc(T, sizeof(float) * 9 * cap); }
      for (int j = 0; j < 3; j++) {
        const int16_t *q = (const int16_t *)(b + (size_t)(k + j) * vs + (vs == 12 ? 6 : 8));
        T[9 * NT + 3 * j] = r->ox + q[0] * (r->sc / 32768.f); T[9 * NT + 3 * j + 1] = r->oy + q[1] * (r->sc / 32768.f);
        T[9 * NT + 3 * j + 2] = r->oz + q[2] * (r->sc / 32768.f);
      }
      NT++;
    }
  }
  GOX = W.ox; GOZ = W.oz; GW = (int)(W.W * W.cell / GC) + 1; GH = (int)(W.H * W.cell / GC) + 1;
  gS = calloc((size_t)GW * GH + 1, 4);
  for (int pass = 0; pass < 2; pass++) {
    for (unsigned t = 0; t < NT; t++) {
      const float *a = T + 9 * t;
      int cx0 = (int)floorf((fminf(a[0], fminf(a[3], a[6])) - GOX) / GC), cx1 = (int)floorf((fmaxf(a[0], fmaxf(a[3], a[6])) - GOX) / GC);
      int cz0 = (int)floorf((fminf(a[2], fminf(a[5], a[8])) - GOZ) / GC), cz1 = (int)floorf((fmaxf(a[2], fmaxf(a[5], a[8])) - GOZ) / GC);
      if (cx0 < 0) cx0 = 0; if (cz0 < 0) cz0 = 0; if (cx1 >= GW) cx1 = GW - 1; if (cz1 >= GH) cz1 = GH - 1;
      for (int z = cz0; z <= cz1; z++) for (int x = cx0; x <= cx1; x++) { size_t c = (size_t)z * GW + x; if (pass == 0) gS[c + 1]++; else gL[gS[c]++] = t; }
    }
    if (pass == 0) { for (size_t c = 0; c < (size_t)GW * GH; c++) gS[c + 1] += gS[c]; gL = malloc(sizeof(unsigned) * (gS[(size_t)GW * GH] + 1)); }
    else { for (size_t c = (size_t)GW * GH; c > 0; c--) gS[c] = gS[c - 1]; gS[0] = 0; }
  }
}
// верх нарисованного в круге радиуса r вокруг (x, z): вертикальные лучи сверху в центре и по двум кольцам (r/2, r),
// по 8 направлений — самое высокое попадание в нарисованный треугольник (обе стороны)
static float rayDownTri(float x, float z, const float *a, float *y) {
  float x0 = a[0], z0 = a[2], x1 = a[3], z1 = a[5], x2 = a[6], z2 = a[8];
  float d = (z1 - z2) * (x0 - x2) + (x2 - x1) * (z0 - z2); if (fabsf(d) < 1e-9f) return 0;
  float w0 = ((z1 - z2) * (x - x2) + (x2 - x1) * (z - z2)) / d, w1 = ((z2 - z0) * (x - x2) + (x0 - x2) * (z - z2)) / d, w2 = 1.f - w0 - w1;
  if (w0 < -1e-4f || w1 < -1e-4f || w2 < -1e-4f) return 0;
  *y = w0 * a[1] + w1 * a[4] + w2 * a[7]; return 1;
}
static float renderTop(float x, float z, float r) {
  float best = -1e9f;
  for (int ring = 0; ring < 3; ring++) for (int k = 0; k < (ring ? 8 : 1); k++) {
    float rr = r * ring * .5f, px = x + rr * cosf(k * .785398f), pz = z + rr * sinf(k * .785398f);
    int gx = (int)floorf((px - GOX) / GC), gz = (int)floorf((pz - GOZ) / GC);
    if (gx < 0 || gz < 0 || gx >= GW || gz >= GH) continue;
    size_t c = (size_t)gz * GW + gx;
    for (unsigned q = gS[c]; q < gS[c + 1]; q++) { float y; if (rayDownTri(px, pz, T + 9 * gL[q], &y) && y > best) best = y; }
  }
  return best;
}

// «выше нарисованного»: низ машины выше самого высокого нарисованного в круге ABOVE_R у точки удара больше чем на ABOVE_TOL —
// те же полоса и запас, что у правила заборов (tools/psp_export.py FENCE_BAND, FENCE_MARGIN): стенка до 1 м над кустом/крышей
// у линии участка — не «стена до неба»
#define ABOVE_R 1.5f
#define ABOVE_TOL 1.25f   // запас правила 1 м + 0.25 м на разницу выборки (полоса куска 2 м против круга у точки удара, наклон кузова)
static int zoneByName(const char *n) { for (uint32_t i = 0; i < W.nzone; i++) if (!strncmp(W.zone[i].name, n, 16)) return (int)i; return -1; }

int main(int argc, char **argv) {
  const char *lvl = "build/level.shr", *hom = "build/homer.shr", *routes = "build/sandbox/routes-l1.tsv";
  int noBoost = 0, old47 = 0, plant = 0, noPads = 0, pos = 0, verbose = 0;
  for (int i = 1; i < argc; i++) {
    if (!strcmp(argv[i], "--no-boost")) noBoost = 1; else if (!strcmp(argv[i], "--old47")) old47 = 1; else if (!strcmp(argv[i], "--plant-wall")) plant = 1;
    else if (!strcmp(argv[i], "--no-pads")) noPads = 1; else if (!strcmp(argv[i], "-v")) verbose = 1; else if (!strcmp(argv[i], "--routes") && i + 1 < argc) routes = argv[++i];
    else if (pos == 0) { lvl = argv[i]; pos++; } else if (pos == 1) { hom = argv[i]; pos++; }
  }
  carJumpBoostOff = noBoost; carJumpBoost = old47; homerBounceOff = noPads;
  FILE *f = fopen(lvl, "rb"); if (!f) { printf("нет %s\n", lvl); return 1; }
  fseek(f, 0, SEEK_END); fileSize = ftell(f); rewind(f);
  file = aligned_alloc(16, (fileSize + 15) & ~15L); if (fread(file, 1, fileSize, f) != (size_t)fileSize) return 1; fclose(f);
  unsigned pv = *(unsigned *)(file + 88), co = *(unsigned *)(file + 92), po = *(unsigned *)(file + 96), ce = (unsigned)fileSize;
  if (po > co && po < ce) ce = po; if (pv > co && pv < ce) ce = pv;
  if (colInit(&W, file + co, ce - co)) { printf("COL1 не читается\n"); return 1; }
  printf("jumps: %s — зон прыжка %u, подкидывающих точек %u%s%s%s%s\n", lvl, W.nzone, W.npad, noBoost ? " [--no-boost]" : "", old47 ? " [--old47]" : "",
         plant ? " [--plant-wall]" : "", noPads ? " [--no-pads]" : "");
  check("1. JMP1: зон прыжка в данных уровня", (float)W.nzone, 1, 1e9f, "Event 48 jumpzone*, jumps.p3d");
  check("1. JMP1: подкидывающих точек в данных уровня", (float)W.npad, 1, 1e9f, "Event 6: отдушины, пружины");
  loadRender();

  // ---------------- 2. маршрут «дом»: jumpzone17
  int zi = zoneByName("jumpzone17");
  FILE *rt = fopen(routes, "r"); char name[64]; float sx, sy, sz, dx, dz, lx, ly, lz; int glass, found = 0;
  while (rt && fscanf(rt, "%63s %f %f %f %f %f %f %f %f %d", name, &sx, &sy, &sz, &dx, &dz, &lx, &ly, &lz, &glass) == 10)
    if (!strcmp(name, "jumpzone17")) { found = 1; break; }
  if (rt) fclose(rt);
  check("2. маршрут jumpzone17 в routes-l1.tsv и зона в JMP1", (float)(found && zi >= 0), 1, 1, "tools/cartest/routes.py");
  if (found && zi >= 0) {
    // дом: ящики COL1, которые задевает полоса полёта ±1.5 м в 3..25 м за кромкой, — самый высокий верх; дальняя стенка —
    // дальний край этих ящиков вдоль линии полёта
    float houseTop = -1e9f, houseFar = 0.f; int houseBox = -1;
    for (uint32_t i = 0; i < W.nbox; i++) {
      const ColBox *B = &W.box[i]; const float *A[3] = {B->ax, B->ay, B->az};
      float ex = 0, ez = 0, ey = 0; for (int k = 0; k < 3; k++) { ex += fabsf(A[k][0]) * B->h[k]; ey += fabsf(A[k][1]) * B->h[k]; ez += fabsf(A[k][2]) * B->h[k]; }
      float rx = B->c[0] - lx, rz = B->c[2] - lz, along = rx * dx + rz * dz, side = fabsf(rx * dz - rz * dx);
      float halfAlong = fabsf(dx) * ex + fabsf(dz) * ez, halfSide = fabsf(dz) * ex + fabsf(dx) * ez;
      if (along + halfAlong < 3.f || along - halfAlong > 25.f || side - halfSide > 1.5f) continue;
      if (B->c[1] + ey > houseTop) { houseTop = B->c[1] + ey; houseBox = (int)i; }
      if (along + halfAlong > houseFar) houseFar = along + halfAlong;
    }
    if (plant && houseBox >= 0) {   // подложить «стену выше крыши»: ящик дома выше на 6 м (центр +3, полувысота +3 по вертикальной оси)
      ColBox *B = (ColBox *)&W.box[houseBox]; int kv = 0; const float *A[3] = {B->ax, B->ay, B->az};
      for (int k = 1; k < 3; k++) if (fabsf(A[k][1]) > fabsf(A[kv][1])) kv = k;
      B->c[1] += 3.f; B->h[kv] += 3.f; houseTop += 6.f;
    }
    printf("     дом: ящик #%d, верх %.1f м, дальняя стенка в %.1f м за кромкой (%.1f, %.1f); верх зоны %.1f\n", houseBox, houseTop, houseFar,
           lx, lz, colZoneTop(&W.zone[zi]));
    // правка 342: ожидание — как у оригинала (близнец PS2, knowledge/facts/ps2-ramps.yaml): на 50 и 70 км/ч машина встаёт у
    // стены дома, на 102 км/ч (бот отпускает газ на 100) задевает конёк и перелетает, с газом до упора (106 км/ч) перелетает
    // чисто. Было (правка 47, правило порта «подброс до верха зоны»): перелёт на любой скорости 60–120 км/ч не меньше 80 %.
    // «Перелетел» — через 6 с после кромки машина за дальней стенкой дома, ниже крыши, на колёсах, без возврата на надёжное место
    int slowN = 0, slowOver = 0, fastN = 0, fastOver = 0, above = 0, aboveFar = 0, boosted = 0; float worstAbove = 0.f, worstFar = 0.f;
    for (int kmh = 60; kmh <= 120; kmh += 10) for (int hi = -1; hi <= 1; hi++) for (int li = -1; li <= 1; li++) {
      float a = hi * 5.f * 0.0174533f, dl = li * 2.f, run = hypotf(lx - sx, lz - sz);
      float ux = dx * cosf(a) + dz * sinf(a), uz = -dx * sinf(a) + dz * cosf(a), h = atan2f(ux, uz);
      float ax = lx + dz * dl, az = lz - dx * dl, x0 = ax - ux * run, z0 = az - uz * run, gy;
      if (!colGround(&W, x0, z0, sy + 2.f, sy - 3.f, &gy, 0)) continue;
      static Car car; carInit(&car, NULL, &W, x0, gy, z0, h);
      for (int k = 0; k < 10; k++) { CarInput in = {0}; carUpdate(&car, &W, &in, 1 / 60.f); }
      carSetSpeed(&car, kmh / 3.6f);
      int passed = 0, rec0 = car.recoveries, b0 = car.boosts; float tPass = 0.f;
      for (int fr = 0; fr < 20 * 60; fr++) {
        CarInput in = {0}; in.throttle = (!passed && car.v * 3.6f >= kmh) ? 0.f : 1.f;
        carUpdate(&car, &W, &in, 1 / 60.f);
        float along = (car.x - lx) * dx + (car.z - lz) * dz;
        if (!passed && along > 0.f) { passed = 1; tPass = fr / 60.f; }
        if (passed && !car.grounded && car.wallV > 1.f) {   // удар о стену в полёте: выше нарисованного?
          float top = renderTop(car.wallP[0] - car.wallN[0] * .6f, car.wallP[2] - car.wallN[1] * .6f, ABOVE_R), low = car.wallP[1] + car.p.bandLo;   // низ твёрдого слоя кузова в точке удара (с наклоном)
          // считаются удары над домом (до его дальней стенки); дальше — заборы соседних участков, не эта проверка (печать для разбора)
          if (low - top > ABOVE_TOL) { int house = along <= houseFar; if (house) { above++; if (low - top > worstAbove) worstAbove = low - top; }
            else { aboveFar++; if (low - top > worstFar) worstFar = low - top; }
            if (verbose || !house) printf("     удар выше рисунка%s: %d км/ч курс %+d прицел %+.0f: (%.1f %.1f %.1f) %.1f м за кромкой, низ %.1f, рисунок %.1f, примитив тип %d #%u\n",
                                house ? "" : " (за домом, вне проверки)", kmh, hi * 5, dl, car.x, car.y, car.z, along, low, top, car.wallType, car.wallIdx); }
        }
        if (passed && fr / 60.f - tPass > 6.f) break;
        if (!passed && fr > 15 * 60) break;
      }
      float U = 1.f - 2.f * (car.q[1] * car.q[1] + car.q[3] * car.q[3]), along = (car.x - lx) * dx + (car.z - lz) * dz;
      int over = passed && along > houseFar && car.y < houseTop - 2.f && car.recoveries == rec0 && U > .3f;
      if (kmh <= 70) { slowN++; slowOver += over; } else if (kmh >= 100) { fastN++; fastOver += over; }
      if (verbose) printf("     %3d км/ч курс %+d прицел %+.0f: итог %.1f м по линии, y %.1f, %s\n", kmh, hi * 5, dl, along, car.y, over ? "перелетел" : "не перелетел");
      boosted += car.boosts > b0;
    }
    printf("     60–70 км/ч: перелетели %d из %d; 100–120 км/ч: перелетели %d из %d; с разгоном зоны %d; ударов выше нарисованного над домом %d (худший на %.2f м), за домом %d (худший на %.2f м)\n",
           slowOver, slowN, fastOver, fastN, boosted, above, worstAbove, aboveFar, worstFar);
    check("2. дом: 60–70 км/ч встаёт у дома (оригинал 50, 70 км/ч)", slowN ? 1.f - (float)slowOver / slowN : 0.f, .8f, 1.f, ">= 0.8 не перелетели");
    check("2. дом: от 100 км/ч перелетает (оригинал 102–106 км/ч)", fastN ? (float)fastOver / fastN : 0.f, .8f, 1.f, ">= 0.8 перелетели");
    check("2. удары о стену в полёте выше нарисованного, шт", (float)above, 0, 0, "0: нет «стены выше крыши»");
  }

  // ---------------- 3. подкидывающие точки
  SkinModel *m = skinLoad(hom); if (!m) { printf("нет %s\n", hom); return 1; }
  static Homer H; if (homerInit(&H, m)) { printf("homerInit: нет клипов\n"); return 1; }
  int canStand = 0, reached = 0;
  for (uint32_t i = 0; i < W.npad; i++) {
    const ColPad *P = &W.pad[i]; const ColZone *Z = (const ColZone *)P;
    // опора внутри объёма: самая нижняя (отдушина/пружина — внизу объёма, как у sv01/sv02 с объёмом-стенкой в 10 м)
    float top = colZoneTop(Z), bot = 2.f * P->c[1] - top, gy = 0.f, g, yq = top + .3f; int any = 0;
    for (int it = 0; it < 8 && colGround(&W, P->c[0], P->c[2], yq, bot - .5f, &g, 0); it++) {
      if (colZoneContains(Z, P->c[0], g + .3f, P->c[2], HOMER_RADIUS)) { gy = g; any = 1; }
      yq = g - .2f;
    }
    if (!any) { printf("     %-10s не встать (нет опоры внутри объёма)\n", P->name); continue; }
    if (P->apex[1] - gy < .5f) { printf("     %-10s точка у ступней (%.2f м над опорой %.1f) — подброса нет (homer.c: вершина ниже 0.5 м)\n", P->name, P->apex[1] - gy, gy); continue; }
    canStand++;
    homerPlace(&H, &W, P->c[0], gy + .05f, P->c[2], 0.f);
    float maxY = H.y, ax = H.x, az = H.z; int b0 = H.bounces;
    HomerInput in; memset(&in, 0, sizeof in);
    for (int fr = 0; fr < 180; fr++) { homerUpdate(&H, &W, NULL, &in, 1 / 60.f); if (H.y > maxY) { maxY = H.y; ax = H.x; az = H.z; } }
    float dyE = maxY - P->apex[1], dxz = hypotf(ax - P->apex[0], az - P->apex[2]);
    int ok = H.bounces > b0 && fabsf(dyE) <= .35f && dxz <= .6f; reached += ok;
    printf("     %-10s встал на %.1f, вершина %.2f (точка %.2f, %+.2f м), вбок %.2f м -> %s\n", P->name, gy, maxY, P->apex[1], dyE, dxz, ok ? "ok" : "мимо");
  }
  check("3. подкидывающие точки: на которые можно встать", (float)canStand, 1, 1e9f, "есть опора внутри объёма");
  check("3. подкидывающие точки: вершина у точки локатора", canStand ? (float)reached / canStand : 0.f, 1.f, 1.f, "все");

  // ---------------- 4. пыль из-под ног (правка 45): клуб на каждый шаг бега (○), при ходьбе пыли нет
  { float gy = 0.f, sx = 220.f, sz = 172.f; colGround(&W, sx, sz, 50.f, -50.f, &gy, 0);   // улица у дома Симпсонов (спавн уровня)
    int steps[2] = {0, 0}; float cad[2] = {0.f, 0.f};
    for (int run = 0; run < 2; run++) {
      homerPlace(&H, &W, sx, gy + .05f, sz, 1.5708f); HomerEvent e; while (homerPopEvent(&H, &e)) {}   // вдоль улицы (курс спавна)
      HomerInput in; memset(&in, 0, sizeof in); in.my = 1.f; in.camYaw = 1.5708f; in.dash = run == 0;
      float t0 = -1.f, t1 = 0.f;
      for (int fr = 0; fr < 150; fr++) {   // 2.5 с, первые 0.5 с — разгон
        homerUpdate(&H, &W, NULL, &in, 1 / 60.f);
        while (homerPopEvent(&H, &e)) if (e.type == HOMER_EV_STEP && fr >= 30) { steps[run]++; if (t0 < 0.f) t0 = fr / 60.f; t1 = fr / 60.f; }
      }
      cad[run] = steps[run] > 1 ? (t1 - t0) / (steps[run] - 1) : 0.f;
    }
    printf("     бег 2 с: шагов %d (через %.2f с; запись PS2 ~0.3 с), ходьба 2 с: шагов %d\n", steps[0], cad[0], steps[1]);
    check("4. пыль: клубов на шаги бега за 2 с", (float)steps[0], 6, 16, "бег ○: два шага на цикл hom_loco_dash");
    check("4. пыль: клубов при ходьбе", (float)steps[1], 0, 0, "без ○ пыли нет");
  }
  printf("jumps: %s (%d провалов)\n", fails ? "FAIL" : "PASS", fails);
  return fails;
}
