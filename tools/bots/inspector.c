// Инспектор полигона v2 (план Роба docs/ПОЛИГОН_ПЛАН_2026-10-05.md: «инспектор — обход каждой клетки машиной, пешком, прыжками»):
// не случайный рой, а обход списка точек (клетки, где побывал рой, tools/polygon/roles.py points) тем же кодом мира, что EBOOT
// (tools/bots/world.c). Из каждой точки — пробы из одного снимка, мир после пробы тот же:
//   машина (car): поставить (как goto смоука), 0.5 с покоя, 8 заходов по 2.5 с (газ прямо/влево/вправо, назад прямо/влево/вправо,
//                 назад и газ с рулём) — как carTrapped исследователя; ни один не отъехал на 3 м -> car_trapped;
//   пешком (foot): выйти (△), 8 сторон бегом по 1.5 с; прыжки (jump): 8 сторон бегом с двойным прыжком; никуда не ушёл на 1.5 м и
//                 △ не сажает в машину за 3 с -> foot_trapped;
//   в любой пробе: ниже самой низкой коллизии уровня на 5 м -> fall; скачок > 10 м за кадр -> death_move (перенос DEATH, obj — зона);
//   удары машины о стену мира (car.wallV > 3 м/с: точка, примитив COL1, материал) -> hits.tsv — регистратор сверяет с видимой
//   геометрией («невидимая стена»); след проб (раз в 10 кадров) -> trace.bin — регистратор ищет проход сквозь видимую стену.
// Взаимодействия (--interact): каждый гэг города (collect-l<N>.shr) и каждая дверь комнаты (interiors-l<N>.bin): машина в 6 м от
// него на опору той же высоты, выйти, дойти стиком (относительно камеры, как missioner), у цели △ (гэг по действию); гэг
// заиграл (gagSt != 0) / дверь впустила (комната = её) за 8 с -> ok, иначе interact_fail. Стейтпропы — не покрыто (пишется).
//   inspector LEVEL PLAYER POINTS [--modes car,foot,jump] [--part K/N] [--interact] --out DIR
//   inspector LEVEL PLAYER --one X Y Z H [--modes ...] --out DIR      одна точка (повтор места из очереди сверки)
// POINTS — строки "x y z h" (курс движка, вперёд = (sin h, cos h)); # — комментарий. Выход DIR/events.tsv (формат cellsout.h:
// вид x y z время слой объект пешком + номер точки), DIR/hits.tsv, DIR/trace.bin (int32 точка, int32 проба, float x y z),
// DIR/interact.tsv, DIR/done.txt (точек пройдено — продолжение после остановки: --resume). Повтор побайтный: ни часов, ни случайности
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "world.h"

#define HIT_V 3.f        // м/с: удар о стену, который пишем
#define JUMP_D 10.f      // м за кадр: перенос (DEATH, сброс), не езда
static BotWorld W; static BotSnap S0, P0, P1; static float minY = 1e9f;
static FILE *fEv, *fHit, *fTr, *fIa; static int curPt, curProbe;

static void ev(const char *kind, float x, float y, float z, int foot, const char *obj) {
  int nl; char o[16]; int layer = bwWhere(x, y, z, 1.2f, &nl, o);
  fprintf(fEv, "%s\t%.2f\t%.2f\t%.2f\t0\t%d\t%s\t%d\t%d\n", kind, x, y, z, layer, obj && *obj ? obj : o, foot, curPt);
}
static void pos(float p[3]) { int f = gameOnFoot(&W.G); p[0] = f ? W.homer.x : W.car.x; p[1] = f ? W.homer.y : W.car.y; p[2] = f ? W.homer.z : W.car.z; }
static void trace(void) { float p[3]; pos(p); int32_t h[2] = {curPt, curProbe}; fwrite(h, 4, 2, fTr); fwrite(p, 4, 3, fTr); }

// один кадр пробы: удар, перенос, провал. 1 — проба кончилась (провал)
static int stepProbe(unsigned bt, float ax, float ay, int f) {
  float a[3]; pos(a); int zone = gameDeathAt(&W.G), foot = gameOnFoot(&W.G);
  bwStep(&W, bt, ax, ay);
  float b[3]; pos(b);
  if (!foot && W.car.wallV > HIT_V)
    fprintf(fHit, "%.2f\t%.2f\t%.2f\t%.2f\t%d\t%u\t%d\t%.3f\t%.3f\t%d\t%d\n", W.car.wallP[0], W.car.wallP[1], W.car.wallP[2], W.car.wallV,
            W.car.wallType, W.car.wallIdx, W.car.wallMat, W.car.wallN[0], W.car.wallN[1], curPt, curProbe);
  if (hypotf(b[0] - a[0], b[2] - a[2]) > JUMP_D || fabsf(b[1] - a[1]) > JUMP_D) {
    char o[16]; snprintf(o, sizeof o, zone >= 0 ? "Z%d" : "-", zone); ev("death_move", a[0], a[1], a[2], foot, o); return 1; }
  if (b[1] < minY - 5.f) { ev("fall", a[0], a[1], a[2], foot, 0); return 1; }
  if (f % 10 == 9) trace();
  return 0;
}

static int probeCar(float x, float y, float z, float h) {   // -> 1 машина заперта
  bwLoad(&W, &S0); bwPlace(&W, x, y, z, h);
  for (int f = 0; f < 30; f++) bwStep(&W, 0, 0, 0);
  if (W.car.y < minY - 5.f) { ev("fall", x, y, z, 0, "place"); return 0; }
  bwSave(&W, &P0); float x0 = W.car.x, z0 = W.car.z; int freeDir = 0;
  static const float steer[8] = {0, -1, 1, 0, -1, 1, -1, 1};
  for (int d = 0; d < 8; d++) {   // все 8: и свободная точка даёт удары и след для регистратора
    bwLoad(&W, &P0); curProbe = d; int end = 0;
    for (int f = 0; f < 150 && !end; f++) { unsigned bt = d < 3 ? GP_R : d < 6 ? GP_L : (f < 45 ? GP_L : GP_R);
      float ax = d >= 6 && f < 45 ? -steer[d] : steer[d]; end = stepProbe(bt, ax, 0.f, f); }
    if (end || gameOnFoot(&W.G) || W.car.destroyed || hypotf(W.car.x - x0, W.car.z - z0) > 3.f) freeDir = 1;
  }
  if (!freeDir) ev("car_trapped", x0, W.car.y, z0, 0, 0);
  return !freeDir;
}

static int probeFoot(float x, float y, float z, float h, int run, int jump) {   // -> 1 Гомер заперт
  bwLoad(&W, &S0); bwPlace(&W, x, y, z, h);
  for (int f = 0; f < 30; f++) bwStep(&W, 0, 0, 0);
  for (int f = 0; f < 90; f++) bwStep(&W, f == 5 ? GP_TRIANGLE : 0, 0, 0);   // выйти
  if (!gameOnFoot(&W.G)) return 0;   // не вышел (зажат у стены) — пешком отсюда не проверить
  bwSave(&W, &P1); float x0 = W.homer.x, z0 = W.homer.z; int freeDir = 0;
  for (int d = 0; d < 16; d++) {
    int j = d >= 8; if ((j && !jump) || (!j && !run)) continue;
    bwLoad(&W, &P1); curProbe = 8 + d; float a = (d & 7) * .785398f; int end = 0;
    for (int f = 0; f < 90 && !end; f++) end = stepProbe(GP_CIRCLE | (j && (f == 5 || f == 15) ? GP_CROSS : 0), cosf(a), -sinf(a), f);
    if (end || !gameOnFoot(&W.G) || hypotf(W.homer.x - x0, W.homer.z - z0) > 1.5f) freeDir = 1;
  }
  if (!freeDir) {   // △ — сесть в машину за 3 с (зажат машиной у стены — не тупик)
    bwLoad(&W, &P1); for (int f = 0; f < 180; f++) bwStep(&W, f == 5 ? GP_TRIANGLE : 0, 0, 0);
    if (!gameOnFoot(&W.G)) freeDir = 1;
  }
  if (!freeDir) ev(jump && !run ? "foot_trapped_jump" : "foot_trapped", x0, W.homer.y, z0, 1, 0);
  return !freeDir;
}

// ------------------------------------------------------------------ взаимодействия
// машина в 6 м от цели на опору не дальше 1.5 м по высоте (8 сторон), выйти; 0 — подойти неоткуда
static int approach(float tx, float ty, float tz) {
  const ColWorld *cw = bwCol();
  for (int d = 0; d < 8; d++) {
    float a = d * .785398f, x = tx + 6.f * sinf(a), z = tz + 6.f * cosf(a), gy, n3[3];
    if (!colGround(cw, x, z, ty + 1.5f, ty - 1.5f, &gy, n3) || n3[1] < .7f) continue;
    bwLoad(&W, &S0); bwPlace(&W, x, gy, z, a + 1.5708f);   // боком к цели: выход со стороны водителя не в неё
    for (int f = 0; f < 30; f++) bwStep(&W, 0, 0, 0);
    for (int f = 0; f < 90; f++) bwStep(&W, f == 5 ? GP_TRIANGLE : 0, 0, 0);
    if (gameOnFoot(&W.G) && W.homer.state == HS_FOOT) return 1;
  }
  return 0;
}
static int walkTo(float tx, float tz, int act, int (*done)(int), int arg) {   // 8 с: шаг к цели, у цели △ раз в 0.5 с
  for (int f = 0; f < 480; f++) {
    float d = hypotf(tx - W.homer.x, tz - W.homer.z), r = atan2f(tx - W.homer.x, tz - W.homer.z) - W.homer.camYaw;
    unsigned b = act && d < 1.6f && f % 30 == 0 ? GP_TRIANGLE : 0;
    if (d > .4f) bwStep(&W, b, -sinf(r), -cosf(r)); else bwStep(&W, b, 0, 0);
    if (done(arg)) return 1;
  }
  return 0;
}
static int gagDone(int g) { return W.haveColl && (W.coll.st.gagSt[g] != 0); }
static int doorDone(int r) { return W.room == r; }

static void interact(void) {
  int ngag = W.haveColl ? (int)W.coll.ngag : 0, nroom = bwRooms(), nst = W.haveSP ? 1 : 0;
  for (int g = 0; g < ngag; g++) {
    const CollGag *G = &W.coll.gag[g]; if (G->room >= 0) continue;   // гэги комнат — из комнаты (не покрыто)
    curPt = 100000 + g; int ok = approach(G->x, G->y, G->z) ? walkTo(G->x, G->z, G->trig == COLL_ACTION, gagDone, g) : -1;
    fprintf(fIa, "gag\t%d\t%.16s\t%.2f\t%.2f\t%.2f\t%d\n", g, G->name, G->x, G->y, G->z, ok);
    if (ok == 0) { char o[16]; snprintf(o, sizeof o, "gag:%.11s", G->name); ev("interact_fail", G->x, G->y, G->z, 1, o); }
  }
  for (int r = 0; r < nroom; r++) {
    float p[3]; if (!bwRoomDoor(r, p)) continue;
    curPt = 200000 + r; int ok = approach(p[0], p[1], p[2]) ? walkTo(p[0], p[2], 1, doorDone, r) : -1;
    fprintf(fIa, "door\t%d\t-\t%.2f\t%.2f\t%.2f\t%d\n", r, p[0], p[1], p[2], ok);
    if (ok == 0) { char o[16]; snprintf(o, sizeof o, "door:%d", r); ev("interact_fail", p[0], p[1], p[2], 1, o); }
  }
  fprintf(fIa, "# стейтпропы: %s — проба не покрыта (нужен удар машиной по каждому; следующий шаг)\n", nst ? "есть" : "нет");
}

int main(int argc, char **argv) {
  if (argc < 3) { fprintf(stderr, "usage: inspector LEVEL PLAYER POINTS|--one X Y Z H [--modes car,foot,jump] [--part K/N] [--interact] [--resume] --out DIR\n"); return 2; }
  const char *out = 0, *modes = "car,foot,jump", *pts = 0; int pk = 0, pn = 1, inter = 0, resume = 0, one = 0; float o4[4] = {0};
  for (int i = 3; i < argc; i++) {
    if (!strcmp(argv[i], "--out") && i + 1 < argc) out = argv[++i];
    else if (!strcmp(argv[i], "--modes") && i + 1 < argc) modes = argv[++i];
    else if (!strcmp(argv[i], "--part") && i + 1 < argc) { if (sscanf(argv[++i], "%d/%d", &pk, &pn) != 2 || pn < 1) pn = 1; }
    else if (!strcmp(argv[i], "--interact")) inter = 1;
    else if (!strcmp(argv[i], "--resume")) resume = 1;
    else if (!strcmp(argv[i], "--one") && i + 4 < argc) { one = 1; for (int k = 0; k < 4; k++) o4[k] = (float)atof(argv[++i]); }
    else if (i == 3 && argv[i][0] != '-') pts = argv[i];
  }
  if (!out || (!pts && !one && !inter)) { fprintf(stderr, "inspector: нужны POINTS или --one, и --out\n"); return 2; }
  if (bwData(argv[1], argv[2], 0)) { fprintf(stderr, "inspector: нет данных уровня\n"); return 2; }
  { const ColWorld *cw = bwCol(); for (uint32_t i = 0; i < cw->ntri; i++) { const ColTri *T = &cw->tri[i];
      float m = fminf(T->a[1], fminf(T->b[1], T->c[1])); if (m < minY) minY = m; } }
  bwNew(&W); bwSaveAlloc(&W, &S0); bwSaveAlloc(&W, &P0); bwSaveAlloc(&W, &P1); bwSave(&W, &S0);
  char p[600]; int skip = 0;
  if (resume) { snprintf(p, sizeof p, "%s/done.txt", out); FILE *f = fopen(p, "r"); if (f) { if (fscanf(f, "%d", &skip) != 1) skip = 0; fclose(f); } }
  const char *am = resume && skip ? "a" : "w";
  snprintf(p, sizeof p, "%s/events.tsv", out); fEv = fopen(p, am);
  snprintf(p, sizeof p, "%s/hits.tsv", out); fHit = fopen(p, am);
  snprintf(p, sizeof p, "%s/trace.bin", out); fTr = fopen(p, resume && skip ? "ab" : "wb");
  snprintf(p, sizeof p, "%s/interact.tsv", out); fIa = fopen(p, "w");
  if (!fEv || !fHit || !fTr || !fIa) { fprintf(stderr, "inspector: не пишется %s\n", out); return 2; }
  if (!skip) { fprintf(fEv, "# вид\tx\ty\tz\tвремя\tслой\tобъект\tпешком\tточка\n");
    fprintf(fHit, "# x\ty\tz\tv\tтип\tпримитив\tматериал\tnx\tnz\tточка\tпроба\n"); }
  fprintf(fIa, "# что\tномер\tимя\tx\ty\tz\tok (1 сработало, 0 нет, -1 не подошёл)\n");
  int car = strstr(modes, "car") != 0, foot = strstr(modes, "foot") != 0, jump = strstr(modes, "jump") != 0, n = 0, done = 0, nt = 0;
  if (one) { curPt = 0; if (car) nt += probeCar(o4[0], o4[1], o4[2], o4[3]); if (foot || jump) nt += probeFoot(o4[0], o4[1], o4[2], o4[3], foot, jump); done = 1; }
  else if (pts) {
    FILE *f = fopen(pts, "r"); if (!f) { fprintf(stderr, "inspector: нет %s\n", pts); return 2; }
    char ln[256]; float x, y, z, h;
    while (fgets(ln, sizeof ln, f)) {
      if (ln[0] == '#' || sscanf(ln, "%f %f %f %f", &x, &y, &z, &h) != 4) continue;
      if (n++ % pn != pk) continue;
      if (done++ < skip) continue;
      curPt = n - 1;
      if (car) nt += probeCar(x, y, z, h);
      if (foot || jump) nt += probeFoot(x, y, z, h, foot, jump);
      if (done % 50 == 0) { fflush(fEv); fflush(fHit); fflush(fTr);   // продолжение после остановки (круг полигона прерывается STOP)
        snprintf(p, sizeof p, "%s/done.txt", out); FILE *d = fopen(p, "w"); if (d) { fprintf(d, "%d\n", done); fclose(d); } }
    }
    fclose(f);
  }
  if (inter) interact();
  snprintf(p, sizeof p, "%s/done.txt", out); FILE *d = fopen(p, "w"); if (d) { fprintf(d, "%d\nend\n", done); fclose(d); }
  fclose(fEv); fclose(fHit); fclose(fTr); fclose(fIa);
  fprintf(stderr, "inspector: точек %d, запертых проб %d -> %s\n", done, nt, out);
  return 0;
}
