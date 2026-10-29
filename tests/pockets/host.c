// Правка Роба 339 (05.10, L1 F4-8 у электростанции): «выступы и места, куда можно попасть и не выехать». Тот же код машины и коллизии,
// что на PSP (viewer/car.c, col.c), уровни build/level.shr и build/levels/l2..l7/level.shr. Случаи — из данных COL1, без координат в движке.
// Причина F4-8: внутренний забор (правка 47, верх = земля Intersect в полосе + до 3 м) ниже проезжей опоры, которая через него идёт:
// верх труб l1z6 (видимая земля и цилиндры, y −4,3) над забором 510 (верх −4,85). Машина по трубам переезжает линию оригинала и падает
// в щель между трубой 570 и стеной площадки (выезда нет: труба 3,6 м, у стены — край мира). Правило (col.h CarBox.fsup): машине на опоре
// внутренний забор не ниже опоры + 2,5 м; в полёте — верх из данных. Прежнее — colFenceSupOff = 1 (красный).
//   host LEVEL f48     A) маршрут F4-8: с труб (−163, −302) курсом на юг, газ с рулём вправо 0…0,6 (в щель). Зелёный: центр не за линией 510
//                         и машина возвращается к старту. Красный: в щели и не вернуться (карман) хотя бы в одном заезде
//   host LEVEL census  B) все внутренние заборы уровня (конечный верх, не изгородь), через линию которых идёт опора выше верха (кузов на ней
//                         проходит над забором): в каждой такой точке машина на опоре в 6 м с лица, курсом на линию, газ 3 с. Прежнее:
//                         сколько переехали и сколько из них не могут вернуться к месту старта (карман: 64 случайные цепочки ввода);
//                         новое: переехавших 0, в кармане ни одна из тех, кого прежнее запирало (у непереехавших — проба тупика роя)
//                      C) скольжение: те же точки наискось (25°) на 8 м/с — у нового без толчков стены: сдвиг сверх скорости за кадр
//                         ≤ 0,3 м; где прежнее тоже упиралось — по нормали забора не больше прежнего + 0,1 и без подброса (вертикальная
//                         скорость после касания не выше прежней + 0,5 м/с); без пересечения линии там, где прежнее не пересекало.
//                         09.10 (решение владельца «как в оригинале», сверка стен по PS2): прежний критерий «после касания не быстрее
//                         подъезда + 0,5 м/с» заложил трение кузова о забор 0,2 (правило порта). У PS2 машина на газу у забора с лица
//                         наискось едет вдоль него 2,6–6,1 м/с (пробы teleport000_Af, fence_f007_Af, fence_f001_Bf, car.c
//                         CAR_WALL_FRICTION_OLD) — разгон вдоль забора под газом не толчок; меряем толчок поперёк, подброс и пересечение
//                      D) стоит поперёк линии (центр в 0,3 м перед линией, нос за ней): за 1 с без ввода не уходит за линию в карман —
//                         центр за ней глубже 0,3 м (где прежнее не уходило) и не может вернуться к месту (pocketAt, 64 цепочки ввода). 09.10: прежний критерий «сдвиг не больше прежнего + 0,6 м»
//                         мерил и качение: с правилом покоя по PS2 (car.c CAR_SLOPE_HOLD_OLD) машина на скате 18° (забор 368 L1, крыша
//                         12,8 м) скатывается на 1,19 м — у PS2 на 17–20° машина тоже катится (lawn003, wall005). Карман — это уход за линию
// Выход: строка на случай и итог «RESULT: OK/FAIL»; код возврата — число провалов. POCKETS_TRACE=1 — подробности; POCKETS_OLD=1 — красный
// флагом (новое = прежнее); красный прежним кодом — tests/pockets/gate.sh (car.c/col.c базы + shim_old.c)
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "car.h"

extern int colFenceSupOff;   // viewer/col.c (правка 339); для прежнего кода — tests/pockets/shim_old.c
extern int carCrashPopOld;   // viewer/car.c (правка 346): подброс при ударе краша
static ColWorld W; static int fails;
static int forceOld;          // POCKETS_OLD=1 — «новое» тоже прежним (красный флагом: проверки обязаны упасть)
#define SUPOFF(v) (colFenceSupOff = carCrashPopOld = forceOld ? 1 : (v))   // прежнее = обе правки (339, 346) выключены
static void check(const char *n, int ok) { printf("%s %s\n", ok ? "ok" : "FAIL", n); fails += !ok; }
#define DT (1.f / 60.f)
static void step(Car *c, float thr, float brk, float st) { CarInput in = {thr, brk, st, 0}; carUpdate(c, &W, &in, DT); }
// проба тупика (как tools/bots/explorer.c carTrapped): 8 заходов по 150 кадров из одного состояния — газ прямо/влево/вправо,
// назад прямо/влево/вправо, назад 0,75 с и газ с рулём в обе стороны; хоть один отъехал на 3 м — не заперта
static int trappedAt(const Car *c0) {
  static const float steer[8] = {0, -1, 1, 0, -1, 1, -1, 1};
  for (int d = 0; d < 8; d++) {
    Car c = *c0;
    for (int f = 0; f < 150; f++) { int rev = d >= 3 && d < 6 ? 1 : d >= 6 && f < 45; float st = d >= 6 && f < 45 ? -steer[d] : steer[d];
      step(&c, rev ? 0.f : 1.f, rev ? 1.f : 0.f, st); }
    if (c.destroyed || hypotf(c.x - c0->x, c.z - c0->z) > 3.f) return 0;
  }
  return 1;
}
// выезд из места падения (15.10, разбор «pockets A красный у базы»): машина, свалившаяся с трубы на землю ниже старта, — не в кармане, если хоть один из 8 заходов (как trappedAt) за 8 с уходит от места на 15 м.
// Критерий «вернуться к старту» (pocketAt) для падения с трубы не годится: старт на 3,6 м выше, на трубу не взобраться даже из открытого поля; настоящий карман — когда уйти некуда
static int escapeAt(const Car *c0) {
  static const float steer[8] = {0, -1, 1, 0, -1, 1, -1, 1};
  for (int d = 0; d < 8; d++) {
    Car c = *c0;
    for (int f = 0; f < 480; f++) { int rev = d >= 3 && d < 6 ? 1 : d >= 6 && f < 45; float st = d >= 6 && f < 45 ? -steer[d] : steer[d];
      step(&c, rev ? 0.f : 1.f, rev ? 1.f : 0.f, st); if (c.destroyed) break;
      if (hypotf(c.x - c0->x, c.z - c0->z) > 15.f) return 1; }
  }
  return 0;
}
// карман: из состояния c0 не вернуться к месту старта (в 4 м по плоскости и 1,5 м по высоте) ни одной из 64 случайных цепочек ввода
// (до 3 макросов по 1,5–3 с: газ или назад, руль −1…1; ГПСЧ с постоянным зерном — одинаково на прежнем и новом). Возврат страховкой
// машины (recover: сидит на днище 2 с и т.п. — телепорт на надёжное место) выездом не считается: цепочка обрывается
static int pocketAt(const Car *c0, float sx, float sy, float sz) {
  unsigned r = 12345u;
  for (int k = 0; k < 64; k++) {
    Car c = *c0;
    for (int m = 0; m < 3; m++) {
      r ^= r << 13; r ^= r >> 17; r ^= r << 5; int fr = 90 + (int)(r % 91u);
      r ^= r << 13; r ^= r >> 17; r ^= r << 5; int rev = (r >> 3) & 1; float st = (float)((int)(r % 201u) - 100) / 100.f;
      for (int f = 0; f < fr; f++) {
        step(&c, rev ? 0.f : 1.f, rev ? 1.f : 0.f, st);
        if (c.recoveries != c0->recoveries || c.destroyed) break;   // возврат страховкой (телепорт на надёжное место) — не выезд
        if (hypotf(c.x - sx, c.z - sz) < 4.f && fabsf(c.y - sy) < 1.5f) return 0;
      }
      if (c.recoveries != c0->recoveries || c.destroyed) break;
    }
  }
  return 1;
}
static int placeOn(Car *c, float x, float s, float z, float h) {   // на опору s (верхний слой не выше s + 0,5)
  float g; if (!colGround(&W, x, z, s + .5f, s - 1.f, &g, 0)) return 0;
  carInit(c, NULL, &W, x, g, z, h); for (int k = 0; k < 20; k++) step(c, 0, 0, 0);
  return fabsf(c->y - g) < .6f;
}
static float side(const ColSeg *G, float x, float z) { return (x - G->a[0]) * G->n[0] + (z - G->a[1]) * G->n[1]; }

// ------------------------------------------------------------------ A: F4-8
#ifndef POCKETS_C_OLD
#define POCKETS_C_OLD 0   // 1 — прежние критерии C (красен у базы: звенья 45 и 810 L1): vy до удара вместо vy в кадре первого контакта, выталкивание только на уровне опоры, порог сдвига не ниже прежнего
#endif
#ifndef POCKETS_A_RETURN_OLD
#define POCKETS_A_RETURN_OLD 0   // 1 — прежний критерий A «вернуться к месту старта» (красен на падении с трубы: gate A красный у базы)
#endif
static int f48(void) {
  int seg = -1;   // забор 510 по данным: звено, ближайшее к (−162.9, −310.2) с конечным верхом
  float bd = 1e9f;
  for (unsigned i = 0; i < W.nseg; i++) { const ColSeg *G = &W.seg[i]; if (G->y1 > 1e5f) continue;
    float mx = (G->a[0] + G->b[0]) * .5f, mz = (G->a[1] + G->b[1]) * .5f, d = hypotf(mx + 162.86f, mz + 310.23f); if (d < bd) { bd = d; seg = (int)i; } }
  if (seg < 0 || bd > 1.f) { check("A: забор у щели F4-8 найден в данных", 0); return 0; }
  const ColSeg *G = &W.seg[seg];
  printf("  забор %d (%.2f %.2f)-(%.2f %.2f) верх %.2f\n", seg, G->a[0], G->a[1], G->b[0], G->b[1], G->y1);
  int crossed = 0, trapped = 0, runs = 0;
  for (int k = 0; k <= 4; k++) {
    float st = k * .15f; Car c;
    if (!placeOn(&c, -163.f, -4.3f, -302.f, 3.1416f)) { check("A: старт на трубах", 0); return 0; }
    float minU = 1e9f;
    for (int f = 0; f < 240; f++) { step(&c, 1.f, 0.f, st); float u = side(G, c.x, c.z); if (u < minU) minU = u; }
    for (int f = 0; f < 60; f++) step(&c, 0.f, 0.f, 0.f);
    int tr = trappedAt(&c), pk = pocketAt(&c, -163.f, -4.3f, -302.f), behind = side(G, c.x, c.z) < -.6f && c.y < -6.f;   // в щели: за линией и на дне (−7,9)
    int stuck = !escapeAt(&c);   // уйти из этой точки на 15 м некуда: настоящий карман. pk (вернуться к старту) — справка: после падения с трубы на землю ниже старта не вернуться и из открытого поля
    runs++; crossed += behind; trapped += POCKETS_A_RETURN_OLD ? pk : stuck;
    printf("  руль %.2f: конец (%.2f %.2f %.2f), центр за линией до %.2f м, %s; проба роя: %s; назад к старту: %s\n", st, c.x, c.y, c.z, minU < 0 ? -minU : 0.f,
           behind ? "В ЩЕЛИ" : "на трубах", tr ? "ЗАПЕРТА" : "сдвинулась на 3 м", pk ? (stuck ? "НЕ ВЕРНУТЬСЯ, ВЫЕХАТЬ НЕКУДА (карман)" : "не к старту (ниже), но уехать может") : "вернулась");
  }
  printf("  итог A: заездов %d, в щели %d, не вернуться %d\n", runs, crossed, trapped);
  return crossed * 100 + trapped;
}

// ------------------------------------------------------------------ B, C, D: все «утопленные» внутренние заборы уровня
typedef struct { int seg; float px, pz, s, drop; } Cand;   // drop: на сколько за линией (в 0,5…2 м) земля ниже опоры; >= POCKETS_EDGE_DROP — край площадки, не проезд по опоре
#ifndef POCKETS_EDGE_DROP
#define POCKETS_EDGE_DROP 1.5f   // за линией обрыв не меньше: машина падает с края опоры вниз, а не едет по опоре сквозь забор (16.10, разбор Физики: L1/L4/L7 (337,1; -369,4))
#endif
#ifndef POCKETS_EDGE_OLD
#define POCKETS_EDGE_OLD 0       // 1 — прежнее: любой переезд линии центром считается дырой
#endif
static Cand cand[20000]; static int nc;
static int layers(float x, float z, float top, float bot, float *ys) {
  int k = 0; float n3[3];
  while (k < 8 && colGround(&W, x, z, top, bot, &ys[k], n3)) { if (n3[1] < .7f) { top = ys[k] - .3f; continue; } top = ys[k] - .3f; k++; }
  return k;
}
static void census(void) {
  int fin = 0;
  for (unsigned i = 0; i < W.nseg && nc < 20000; i++) {
    const ColSeg *G = &W.seg[i];
    if (G->y1 > 1e5f || G->y0 < COL_SEG_FOL_Y0) continue;   // граница карты; изгородь (правка 173 — проезд сквозь)
    fin++;
    float dx = G->b[0] - G->a[0], dz = G->b[1] - G->a[1], L = hypotf(dx, dz); if (L < 2.f) continue;
    float last = -1e9f;
    for (float t = 1.f; t <= L - 1.f; t += 1.f) {
      float px = G->a[0] + dx / L * t, pz = G->a[1] + dz / L * t, ys[8];
      int k = layers(px, pz, G->y1 + 6.f, G->y1 - 3.f, ys);
      for (int j = 0; j < k; j++) {
        float s = ys[j]; if (s + .35f < G->y1 - .02f) continue;   // кузов на этой опоре ниже верха — забор держит и так
        float yf[8], yb[8]; int ok = 0, kf = layers(px + G->n[0] * 6.f, pz + G->n[1] * 6.f, s + .8f, s - .8f, yf);
        int kb = layers(px - G->n[0] * 2.f, pz - G->n[1] * 2.f, s + .8f, s - 40.f, yb);
        for (int q = 0; q < kf; q++) if (fabsf(yf[q] - s) < .8f) ok = 1;
        if (!ok || !kb) continue;   // с лица на 6 м — та же опора (подъезд по ней), за линией — есть куда
        if (t - last < 4.f) continue;
        float drop = 1e9f;   // обрыв за линией: самая высокая земля не выше опоры + 0,8 на расстоянии 0,5…2 м за линией
        for (float dd = .5f; dd <= 2.01f; dd += .5f) { float yz[8]; int kz = layers(px - G->n[0] * dd, pz - G->n[1] * dd, s + .8f, s - 40.f, yz); if (kz && s - yz[0] < drop) drop = s - yz[0]; }
        last = t; cand[nc++] = (Cand){(int)i, px, pz, s, drop}; break;
      }
    }
  }
  printf("  внутренних заборов (конечный верх, не изгородь) %d; точек, где опора выше верха и подъезд по ней с лица: %d\n", fin, nc);
}
typedef struct { int crossed, trapped, air; float pop, popSide, vGain, popN, vyUp, yCross, yEnd; } Run;   // crossed: центр перешёл линию в пределах звена; air — в полёте
static Run approach(const Cand *k, float angDeg, float v0, float secs) {
  const ColSeg *G = &W.seg[k->seg]; Run r = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0}; Car c;
  float a = angDeg * 3.14159265f / 180.f, ux = G->b[0] - G->a[0], uz = G->b[1] - G->a[1], L = hypotf(ux, uz); ux /= L; uz /= L;
  float dxh = -G->n[0] * cosf(a) + ux * sinf(a), dzh = -G->n[1] * cosf(a) + uz * sinf(a);   // курс на линию (наискось — вдоль ux)
  float sx = k->px - dxh * 6.f, sz = k->pz - dzh * 6.f;
  if (!placeOn(&c, sx, k->s, sz, atan2f(dxh, dzh)) || !c.grounded || c.contacts || c.reverts) { r.crossed = -1; return r; }   // старт не встал чисто
  if (v0 > 0.f) carSetSpeed(&c, v0);
  float vin = 0.f, vy0 = 0.f, vyPrev = 0.f; int touched = 0;
  for (int f = 0; f < (int)(secs * 60); f++) {
    float px = c.x, pz = c.z, vx = c.vel[0], vz = c.vel[2]; int gr = c.grounded; float u0 = side(G, px, pz); vyPrev = c.vel[1];
#ifdef COL_DEBUG
    { extern int colDebug; const char *e_ = getenv("POCKETS_DBGF"); colDebug = e_ && f == atoi(e_) && angDeg > 0.f && !colFenceSupOff; }   // разбор кадра: какой слой двигает кузов (сборка с -DCOL_DEBUG)
#endif
    step(&c, v0 > 0.f && hypotf(c.vel[0], c.vel[2]) > v0 ? 0.f : 1.f, 0.f, 0.f);
    float u = side(G, c.x, c.z), t = (c.x - G->a[0]) * ux + (c.z - G->a[1]) * uz;
    if (u0 >= 0.f && u < 0.f && t > -.5f && t < L + .5f && !r.crossed) { r.crossed = 1; r.air = !gr; r.yCross = c.y; }   // перешла линию звена (не продолжения)
    float ddx = c.x - px - vx * DT, ddz = c.z - pz - vz * DT, pop = hypotf(ddx, ddz), ps = fabsf(ddx * ux + ddz * uz);
    int onSup = POCKETS_C_OLD || c.y >= k->s - 0.8f;   // сдвиг считаем, пока машина на уровне опоры: после схода с края площадки ящик под ней даёт выталкивание, к забору оно не относится
    if (onSup && pop > r.pop) r.pop = pop;
    if (getenv("POCKETS_FRAMES") && angDeg > 0.f && f >= 18 && f <= 30) printf("    [%s] f%d v %.2f vy %.3f ct %d side %.2f touched %d vyPrev %.3f\n", colFenceSupOff ? "прежнее" : "новое", f, hypotf(c.vel[0], c.vel[2]), c.vel[1], c.contacts, side(G, c.x, c.z), touched, vyPrev);
    if (getenv("POCKETS_APPTRACE") && (pop > (getenv("POCKETS_APPTHR") ? (float)atof(getenv("POCKETS_APPTHR")) : .25f) || (c.vel[1] - vy0 > .5f && touched))) printf("    [%s] кадр %d: сдвиг %.2f (по нормали %.2f) pos %.2f %.2f %.2f v %.2f vy %.2f gr %d wh %d ct %d типы %d %d\n", angDeg > 0 ? "C" : "B", f, pop, fabsf(ddx * G->n[0] + ddz * G->n[1]), c.x, c.y, c.z, hypotf(c.vel[0], c.vel[2]), c.vel[1], c.grounded, c.wheels, c.contacts, c.ctype[0], c.ctype[1]);
    if (ps > r.popSide) r.popSide = ps;
    float pn = fabsf(ddx * G->n[0] + ddz * G->n[1]); if (pn > r.popN) r.popN = pn;   // толчок по нормали забора
    float sp = hypotf(c.vel[0], c.vel[2]);
    if (!touched && (c.contacts || (!POCKETS_C_OLD && v0 > 0.f && sp < v0 - 1.f))) { touched = 1;   // удар: контакт ИЛИ потеря скорости > 1 м/с (флаг контакта в первом кадре удара не всегда стоит)
      vin = hypotf(vx, vz); vy0 = POCKETS_C_OLD ? c.vel[1] : vyPrev; }   // vy до удара: подскок от удара виден у прежнего и нового одинаково (в кадре, где контакт отмечен впервые, vy уже вырос)
    if (touched && sp - vin > r.vGain) r.vGain = sp - vin;
    if (touched && c.vel[1] - vy0 > r.vyUp) r.vyUp = c.vel[1] - vy0;
  }
  r.yEnd = c.y;
  if (secs >= 3.f) { for (int f = 0; f < 60; f++) step(&c, 0, 0, 0); r.trapped = r.crossed ? ((!POCKETS_EDGE_OLD && k->drop >= POCKETS_EDGE_DROP) ? !escapeAt(&c) : pocketAt(&c, sx, k->s, sz)) : trappedAt(&c); }   // упала с края площадки: запертость = некуда уехать на 15 м (вернуться наверх падая нельзя, как в A)
  return r;
}

int main(int argc, char **argv) {
  if (argc < 3) { fprintf(stderr, "usage: host LEVEL f48|census\n"); return 2; }
  FILE *f = fopen(argv[1], "rb"); if (!f) return 2; fseek(f, 0, SEEK_END); long n = ftell(f); rewind(f);
  unsigned char *d = aligned_alloc(16, (n + 15) & ~15); if (fread(d, 1, n, f) != (size_t)n) return 2; fclose(f);
  unsigned co = *(unsigned *)(d + 92), po = *(unsigned *)(d + 96), pv = *(unsigned *)(d + 88), ce = (unsigned)n;
  if (po > co && po < ce) ce = po; if (pv > co && pv < ce) ce = pv;
  if (colInit(&W, d + co, ce - co)) return 2;
  int trace = getenv("POCKETS_TRACE") != NULL; forceOld = getenv("POCKETS_OLD") != NULL;
  if (!strcmp(argv[2], "f48")) {
    SUPOFF(1); printf("прежнее (colFenceSupOff = 1):\n"); int old = f48();
    SUPOFF(0); printf("новое:\n"); int now = f48();
    check("A: прежнее — машина с труб падает в щель F4-8 и не возвращается (красный пойман)", old / 100 > 0 && old % 100 > 0);
    check("A: новое — машина не заходит за забор (в щели 0) и нигде не заперта: упав с боковой стороны трубы, уезжает на 15 м (карманов 0)", now == 0);
  } else if (!strcmp(argv[2], "census")) {
    census();
    int oc = 0, ot = 0, ncr = 0, ntr = 0, nair = 0, nbad = 0, nedge = 0, nedgefall = 0, skip = 0, slid = 0, sbad = 0, dbad = 0, dn = 0; float popMax = 0, popOld = 0;
    for (int i = 0; i < nc; i++) {
      const Cand *k = &cand[i]; const ColSeg *G = &W.seg[k->seg];
      if (getenv("POCKETS_ONLY") && k->seg != atoi(getenv("POCKETS_ONLY"))) continue;   // отладка: только это звено (остальные прогоны не влияют на состояние)
      SUPOFF(1); Run o = approach(k, 0.f, 0.f, 3.f);
      SUPOFF(0); Run w = approach(k, 0.f, 0.f, 3.f);
      if (o.crossed < 0 || w.crossed < 0) { skip++; continue; }
      oc += o.crossed && !o.air; ot += o.crossed && !o.air && o.trapped; ncr += w.crossed && !w.air; ntr += w.crossed && w.trapped; nair += w.crossed && w.air;
      int edge = !POCKETS_EDGE_OLD && k->drop >= POCKETS_EDGE_DROP;   // край площадки: за линией опоры нет, переезд = падение вниз, это не дыра забора (наблюдение)
      int bad = (w.crossed && !w.air && !edge) || (o.crossed && !o.air && o.trapped && w.trapped);   // по опоре — правило; в полёте — верх из данных, как было
      nbad += bad; nedge += edge; nedgefall += edge && w.crossed && !w.air;
      if (edge && w.crossed && !w.air) printf("  КРАЙ  забор %d у (%.1f %.1f) верх %.2f опора %.2f: за линией земля ниже на %.2f м, машина упала с края через линию: при пересечении y %.2f, через 3 с y %.2f (наблюдение, не дыра забора)\n", k->seg, k->px, k->pz, G->y1, k->s, k->drop, w.yCross, w.yEnd);
      if (getenv("POCKETS_DROPS")) printf("  точка забор %d у (%.1f %.1f) опора %.2f обрыв за линией %.2f м %s\n", k->seg, k->px, k->pz, k->s, k->drop, edge ? "КРАЙ" : "по опоре");
      if (trace || bad || (o.crossed && o.trapped))
        printf("  %s забор %d у (%.1f %.1f) верх %.2f опора %.2f: прежнее %s%s, новое %s%s\n", bad ? "ПЛОХО" : "  ", k->seg, k->px, k->pz, G->y1, k->s,
               o.crossed ? (o.air ? "перелетела" : "переехала") : "держит", o.crossed && o.trapped ? " и ЗАПЕРТА" : "",
               w.crossed ? (w.air ? "перелетела" : "ПЕРЕЕХАЛА") : "держит", w.crossed && w.trapped ? " ЗАПЕРТА" : "");
      // C: наискось 25°, 8 м/с
      SUPOFF(1); Run so = approach(k, 25.f, 8.f, 2.f);
      SUPOFF(0); Run sw = approach(k, 25.f, 8.f, 2.f);
      if (so.crossed >= 0 && sw.crossed >= 0) {
        slid++; if (sw.pop > popMax) popMax = sw.pop; if (so.pop > popOld) popOld = so.pop;
        int same = so.crossed <= 0;   // прежнее тоже упёрлось: сравниваем толчок и подброс; прежнее переехало, новое держит — упор правила 339
        int b2 = sw.pop > (POCKETS_C_OLD ? .3f : fmaxf(.3f, so.pop)) || (same && (sw.popN > so.popN + .1f || sw.vyUp > so.vyUp + .5f)) || (sw.crossed > 0 && so.crossed <= 0);
        if (b2 || trace) { sbad += b2; printf("  %s забор %d у (%.1f %.1f) опора %.2f: наискось новое сдвиг %.2f м/кадр (по нормали %.2f, прежнее %.2f), вверх +%.2f (прежнее +%.2f) м/с, перешла %d/%d; вдоль прибавка %.2f м/с (справка)\n",
                                 b2 ? "ТОЛЧОК" : "  ", k->seg, k->px, k->pz, k->s, sw.pop, sw.popN, so.popN, sw.vyUp, so.vyUp, sw.crossed, so.crossed, sw.vGain); }
      }
      // D: поперёк линии (кузов вдоль линии, центр в 0,3 м перед ней), 1 с без ввода
      { Car c; float ux = G->b[0] - G->a[0], uz = G->b[1] - G->a[1], L = hypotf(ux, uz); ux /= L; uz /= L;
        float cx = k->px + G->n[0] * .3f, cz = k->pz + G->n[1] * .3f;
        float mvs[2] = {0, 0}, us[2] = {0, 0}; int okp = 1, pk = 0;
        for (int o = 0; o < 2 && okp; o++) {   // прежнее и новое: само место может катить (склон, край крыши) — сравниваем
          SUPOFF(!o);
          if (!placeOn(&c, cx, k->s, cz, atan2f(-G->n[0], -G->n[1]))) { okp = 0; break; }   // кузов поперёк линии: нос за ней, центр перед
          float x0 = c.x, z0 = c.z; for (int q = 0; q < 60; q++) step(&c, 0, 0, 0);
          mvs[o] = hypotf(c.x - x0, c.z - z0); us[o] = side(G, c.x, c.z);
          if (o == 1 && us[1] < -.3f) pk = pocketAt(&c, cx, k->s, cz);   // ушла за линию: может ли вернуться
        }
        SUPOFF(0);
        if (okp) { dn++;
          if (us[1] < -.3f && us[0] >= -.3f && pk) { dbad++; printf("  В КАРМАН забор %d у (%.1f %.1f): стоявшая поперёк за 1 с ушла за линию на %.2f м (прежнее %.2f) и не возвращается, сдвиг %.2f м (прежнее %.2f)\n", k->seg, k->px, k->pz, -us[1], -us[0], mvs[1], mvs[0]); }
          else if ((trace || us[1] < -.3f) && mvs[1] > mvs[0] + .6f) printf("     забор %d у (%.1f %.1f): поперёк линии катится %.2f м (прежнее %.2f), центр перед линией %.2f м\n", k->seg, k->px, k->pz, mvs[1], mvs[0], us[1]); }
      }
    }
    printf("  B: точек %d (старт не встал чисто %d): прежнее — переехали по опоре %d, из них в кармане %d; новое — переехали по опоре %d, "
           "перелетели (верх из данных, как было) %d, за линией в кармане %d; плохих %d; край площадки (обрыв за линией >= %.1f м) %d точек, упали через линию %d (наблюдение)\n", nc - skip, skip, oc, ot, ncr, nair, ntr, nbad, POCKETS_EDGE_DROP, nedge, nedgefall);
    printf("  C: наискось %d: наибольший сдвиг за кадр новое %.2f м (прежнее %.2f), толчков %d\n", slid, popMax, popOld, sbad);
    printf("  D: поперёк линии %d: выталкиваний %d\n", dn, dbad);
    check("B: новое — по опоре через внутренний забор не переезжает ни одна; кого прежнее оставляло в кармане — не оставляет", nbad == 0);
    check("C: новое — у забора на опоре скольжение без толчков, подброса и пересечения", sbad == 0);
    check("D: новое — стоящая поперёк линии не уходит за линию в карман", dbad == 0);
    printf("ИТОГ %s: точек %d, прежнее переехали по опоре %d (в кармане %d), новое переехали по опоре %d\n", argv[1], nc - skip, oc, ot, ncr);
  } else if (!strcmp(argv[2], "points") && argc >= 4) {   // points FILE: строки «код x y z» (тупики роя) — разбор: 16 курсов в точке,
    // запертых пробой роя; из них выезжают манёвром (64 случайные цепочки по 3 хода, отъехать на 8 м) или карман; что держит
    FILE *pf = fopen(argv[3], "r"); char ln[256];
    while (pf && fgets(ln, sizeof ln, pf)) {
      char code[32]; float x, y, z; if (sscanf(ln, "%31s %f %f %f", code, &x, &y, &z) != 4) continue;
      for (int o = 0; o < 2; o++) {
        SUPOFF(!o); int tr = 0, pk = 0, n = 0; unsigned hold[8] = {0};
        for (int hi = 0; hi < 16; hi++) {
          Car c; float g; if (!colGround(&W, x, z, y + 1.5f, y - 3.f, &g, 0)) continue;
          carInit(&c, NULL, &W, x, g, z, hi * 6.2831853f / 16); for (int k = 0; k < 30; k++) step(&c, 0, 0, 0);
          n++; if (!trappedAt(&c)) continue; tr++;
          { Car q = c; for (int f = 0; f < 60; f++) { step(&q, 1, 0, 0); for (int i = 0; i < q.contacts && i < 4; i++) hold[q.ctype[i] & 7]++; } }
          // выезд манёвром: 64 цепочки (ГПСЧ с постоянным зерном), успех — центр в 8 м от точки
          unsigned r = 777u; int esc = 0;
          for (int kk = 0; kk < 64 && !esc; kk++) { Car q = c;
            for (int m = 0; m < 3 && !esc; m++) {
              r ^= r << 13; r ^= r >> 17; r ^= r << 5; int fr = 90 + (int)(r % 91u);
              r ^= r << 13; r ^= r >> 17; r ^= r << 5; int rev = (r >> 3) & 1; float st = (float)((int)(r % 201u) - 100) / 100.f;
              for (int f = 0; f < fr; f++) { step(&q, rev ? 0.f : 1.f, rev ? 1.f : 0.f, st);
                if (q.recoveries != c.recoveries) break;
                if (hypotf(q.x - c.x, q.z - c.z) > 8.f) { esc = 1; break; } }
              if (q.recoveries != c.recoveries) break; } }
          pk += !esc;
        }
        printf("%s\t%s\tкурсов %d\tзаперта пробой роя %d\tиз них карман (манёвром не выехать) %d\tдержит: стены %u ящики %u цилиндры %u заборы %u\n",
               code, o ? "новое" : "прежнее", n, tr, pk, hold[COL_TRI], hold[COL_BOX], hold[COL_CYL], hold[COL_SEG]);
      }
    }
    if (pf) fclose(pf);
  } else if (!strcmp(argv[2], "hit") && argc >= 8) {   // hit X Z H V [кадров]: машина в (X, Z) курсом H со скоростью V м/с, газ; по кадрам
    float x = atof(argv[3]), z = atof(argv[4]), h = atof(argv[5]), v = atof(argv[6]); int nf = atoi(argv[7]);
    for (int o = 0; o < 2; o++) {
      SUPOFF(!o); Car c; float g; if (!colGround(&W, x, z, 50.f, -50.f, &g, 0)) return 2;
      carInit(&c, NULL, &W, x, g, z, h); for (int k = 0; k < 20; k++) step(&c, 0, 0, 0); carSetSpeed(&c, v);
      printf("%s:\n", o ? "новое" : "прежнее");
      for (int f = 0; f < nf; f++) { step(&c, 1, 0, 0);
        if (f % 4 == 3) printf("  %3d pos %.2f %.2f %.2f v %.1f vy %.2f gr %d wh %d bodyHit %d ct %d type %d idx %u hitV %.1f rev %d why %d\n", f, c.x, c.y, c.z,
          hypotf(c.vel[0], c.vel[2]), c.vel[1], c.grounded, c.wheels, c.bodyHit, c.contacts, c.contacts ? c.ctype[0] : -1, c.wallIdx, c.wallV, c.reverts, c.revWhy); }
    }
  } else if (!strcmp(argv[2], "ram") && argc >= 4) {   // ram SEG [SEG…]: заезды в забор на 17/22/28 м/с под 0/±30/±60° к нормали, с лица в 12 м
    for (int ai = 3; ai < argc; ai++) {
      int si = atoi(argv[ai]); const ColSeg *G = &W.seg[si];
      float ux = G->b[0] - G->a[0], uz = G->b[1] - G->a[1], L = hypotf(ux, uz); ux /= L; uz /= L;
      for (int o = 0; o < 2; o++) {
        SUPOFF(!o); int nrun = 0, ontop = 0, behind = 0, back = getenv("RAM_BACK") != NULL; float sg = back ? -1.f : 1.f;   // RAM_BACK=1 — с изнанки
        static const float ANG[9] = {-80, -70, -60, -30, 0, 30, 60, 70, 80};   // к нормали забора: ±80° — почти вдоль (касательный)
        for (float t = 1.f; t < L - .5f; t += 2.f) for (int a = 0; a < 9; a++) for (int vi = 0; vi < 3; vi++) {
          float ang = ANG[a] * 3.14159265f / 180.f, v = vi == 0 ? 17.f : vi == 1 ? 22.f : 28.f;
          float px = G->a[0] + ux * t, pz = G->a[1] + uz * t;
          float dx = -sg * G->n[0] * cosf(ang) + ux * sinf(ang), dz = -sg * G->n[1] * cosf(ang) + uz * sinf(ang);
          float sx = px - dx * 12.f, sz = pz - dz * 12.f, g0, gl; Car c;
          if (!colGround(&W, sx, sz, G->y1 + 2.f, G->y1 - 12.f, &g0, 0)) continue;
          if (!colGround(&W, px + sg * G->n[0] * 1.5f, pz + sg * G->n[1] * 1.5f, g0 + 3.f, g0 - 5.f, &gl, 0)) gl = g0;   // земля у линии со стороны заезда
          carInit(&c, NULL, &W, sx, g0, sz, atan2f(dx, dz)); for (int k = 0; k < 20; k++) step(&c, 0, 0, 0);
          if (!c.grounded || c.contacts) continue;
          carSetSpeed(&c, v); nrun++;
          for (int f = 0; f < 180; f++) step(&c, 1, 0, 0);
          for (int f = 0; f < 60; f++) step(&c, 0, 0, 0);
          float u = side(G, c.x, c.z), tt = (c.x - G->a[0]) * ux + (c.z - G->a[1]) * uz;
          int top = fabsf(u) < 1.5f && c.y > gl + 1.f && tt > -1.f && tt < L + 1.f, beh = sg * u < -1.5f && tt > -1.f && tt < L + 1.f && c.y > gl - 3.f;
          ontop += top; behind += beh;
          if ((top || beh) && getenv("POCKETS_TRACE")) printf("    t %.1f угол %+.0f v %.0f: конец (%.2f %.2f %.2f) сторона %.2f %s\n", t, ANG[a], v, c.x, c.y, c.z, u, top ? "НА ЗАБОРЕ" : "ЗА");
        }
        printf("  забор %d (%.1f %.1f)-(%.1f %.1f) верх %.2f, %s: заездов %d, на заборе %d, за ним %d\n", si, G->a[0], G->a[1], G->b[0], G->b[1], G->y1, o ? "новое" : "прежнее", nrun, ontop, behind);
      }
    }
  } else if (!strcmp(argv[2], "ram1") && argc >= 6) {   // ram1 SEG ANG V [T]: одиночный таран, конец и состояние по t вдоль звена
    int si = atoi(argv[3]); const ColSeg *G = &W.seg[si]; float angd = atof(argv[4]), v = atof(argv[5]);
    float ux = G->b[0] - G->a[0], uz = G->b[1] - G->a[1], L = hypotf(ux, uz); ux /= L; uz /= L;
    for (float t = 1.f; t < L - .5f; t += (argc >= 7 ? 100.f : 2.f)) {
      float tt0 = argc >= 7 ? atof(argv[6]) : t; float ang = angd * 3.14159265f / 180.f;
      float px = G->a[0] + ux * tt0, pz = G->a[1] + uz * tt0, dx = -G->n[0] * cosf(ang) + ux * sinf(ang), dz = -G->n[1] * cosf(ang) + uz * sinf(ang), sx = px - dx * 12.f, sz = pz - dz * 12.f, g0; Car c;
      if (!colGround(&W, sx, sz, G->y1 + 2.f, G->y1 - 12.f, &g0, 0)) continue;
      carInit(&c, NULL, &W, sx, g0, sz, atan2f(dx, dz)); for (int k = 0; k < 20; k++) step(&c, 0, 0, 0);
      if (!c.grounded || c.contacts) continue;
      carSetSpeed(&c, v);
      for (int f = 0; f < 180; f++) { step(&c, 1, 0, 0); if (getenv("R1TRACE") && f % 6 == 0) printf("   f%3d pos %.2f %.2f %.2f v %.1f rev %d why %d rec %d\n", f, c.x, c.y, c.z, hypotf(c.vel[0], c.vel[2]), c.reverts, c.revWhy, c.recoveries); }
      for (int f = 0; f < 60; f++) step(&c, 0, 0, 0);
      printf("t=%.1f старт (%.1f %.1f) конец (%.2f %.2f %.2f) v %.1f reverts %d why %d trapped %d\n", tt0, sx, sz, c.x, c.y, c.z, hypotf(c.vel[0], c.vel[2]), c.reverts, c.revWhy, trappedAt(&c));
      if (getenv("RAM_RESET")) { float wx = c.x, wz = c.z; carResetNearby(&c, &W); for (int f = 0; f < 30; f++) step(&c, 0, 0, 0);
        printf("   RESET CAR: в %.1f м от места, на (%.2f %.2f %.2f), колёс %d, trapped %d\n", hypotf(c.x - wx, c.z - wz), c.x, c.y, c.z, c.wheels, trappedAt(&c)); }
      if (argc >= 7) break;
    }
  } else if (!strcmp(argv[2], "ramall")) {   // ramall: все внутренние заборы уровня (конечный верх, не изгородь), заезды с лица на 17 и 28 м/с
    // под 0/±45/±75° к нормали через каждые 3 м звена; итог — где машина осталась НА заборе (центр у линии и выше земли у неё на 1 м)
    // и ЗА ним (по земле или перелетев); прежнее и новое
    static const float ANG[5] = {-75, -45, 0, 45, 75};
    int tot[2] = {0, 0}, top[2] = {0, 0}, beh[2] = {0, 0};
    for (unsigned si = 0; si < W.nseg; si++) {
      const ColSeg *G = &W.seg[si]; if (G->y1 > 1e5f || G->y0 < COL_SEG_FOL_Y0) continue;
      float ux = G->b[0] - G->a[0], uz = G->b[1] - G->a[1], L = hypotf(ux, uz); if (L < 1.f) continue; ux /= L; uz /= L;
      for (float t = .5f * fmodf(L, 3.f) + .5f; t < L; t += 3.f) for (int a = 0; a < 5; a++) for (int vi = 0; vi < 2; vi++) {
        float ang = ANG[a] * 3.14159265f / 180.f, v = vi ? 28.f : 17.f, px = G->a[0] + ux * t, pz = G->a[1] + uz * t;
        float dx = -G->n[0] * cosf(ang) + ux * sinf(ang), dz = -G->n[1] * cosf(ang) + uz * sinf(ang), sx = px - dx * 12.f, sz = pz - dz * 12.f, g0, gl;
        if (!colGround(&W, sx, sz, G->y1 + 2.f, G->y1 - 12.f, &g0, 0)) continue;
        if (!colGround(&W, px + G->n[0] * 1.5f, pz + G->n[1] * 1.5f, g0 + 3.f, g0 - 5.f, &gl, 0)) gl = g0;
        int res[2] = {0, 0}; float ex[2], ey[2], ez[2];
        for (int o = 0; o < 2; o++) {
          SUPOFF(!o); Car c; carInit(&c, NULL, &W, sx, g0, sz, atan2f(dx, dz)); for (int k = 0; k < 20; k++) step(&c, 0, 0, 0);
          if (!c.grounded || c.contacts) { res[o] = -1; continue; }
          carSetSpeed(&c, v); for (int f = 0; f < 150; f++) step(&c, 1, 0, 0); for (int f = 0; f < 90; f++) step(&c, 0, 0, 0);
          float u = side(G, c.x, c.z), tt = (c.x - G->a[0]) * ux + (c.z - G->a[1]) * uz; int in = tt > -1.f && tt < L + 1.f;
          res[o] = in && fabsf(u) < 1.5f && c.y > gl + 1.f && c.recoveries == 0 ? 1 : in && u < -1.5f && c.recoveries == 0 ? 2 : 0;
          ex[o] = c.x; ey[o] = c.y; ez[o] = c.z;
        }
        if (res[0] < 0 || res[1] < 0) continue;
        for (int o = 0; o < 2; o++) { tot[o]++; top[o] += res[o] == 1; beh[o] += res[o] == 2; }
        if (res[0] || res[1]) {
          static const char LET[] = "ABCDEFGHJKLM"; int cx = (int)floorf((px + 700.f) / 100.f), cz = (int)floorf((pz + 700.f) / 100.f);
          int sxi = (int)floorf(((px + 700.f) / 100.f - cx) * 3.f), szi = (int)floorf(((pz + 700.f) / 100.f - cz) * 3.f);
          printf("  %c%d-%d забор %u у (%.1f %.1f) верх %.2f земля %.2f, %+3.0f° %2.0f м/с: прежнее %s (%.1f %.1f %.1f), новое %s (%.1f %.1f %.1f)\n",
                 cx >= 0 && cx < 12 ? LET[cx] : '?', cz + 1, 1 + sxi + 3 * szi, si, px, pz, G->y1, gl, ANG[a], v,
                 res[0] == 1 ? "НА ЗАБОРЕ" : res[0] == 2 ? "ЗА" : "у забора", ex[0], ey[0], ez[0], res[1] == 1 ? "НА ЗАБОРЕ" : res[1] == 2 ? "ЗА" : "у забора", ex[1], ey[1], ez[1]);
        }
      }
    }
    printf("ИТОГ таран: заездов %d; прежнее — на заборе %d, за ним %d; новое — на заборе %d, за ним %d\n", tot[0], top[0], beh[0], top[1], beh[1]);
  } else if (!strcmp(argv[2], "walls")) {   // walls [X Z R]: правка 346 — внутренние заборы со стеной-гребнем (верх стены у линии выше земли с
    // лица на 1,2…4 м, в 3,5 м за линией опора снова ниже верха на 0,8 м: кирпичная/каменная стена, не ступень двора). Таран с лица на 17/22/28 м/с (60–100 км/ч) под 0/±30/±60/±75° через каждые 2 м.
    // «Въехал на забор» — колёса (начало машины) у линии выше верха стены или в конце стоит на ней; «за» — в конце за линией. Прежнее и новое
    float fx0 = argc >= 6 ? (float)atof(argv[3]) : 0.f, fz0 = argc >= 6 ? (float)atof(argv[4]) : 0.f, fr = argc >= 6 ? (float)atof(argv[5]) : 1e9f;
    static const float ANG[7] = {-75, -60, -30, 0, 30, 60, 75};
    int tot = 0, nw = 0, up[2] = {0, 0}, top[2] = {0, 0}, beh[2] = {0, 0}, frozen[2] = {0, 0}; float maxUp[2] = {-9, -9};
    for (unsigned si = 0; si < W.nseg; si++) {
      const ColSeg *G = &W.seg[si]; if (G->y1 > 1e5f || G->y0 < COL_SEG_FOL_Y0) continue;
      float ux = G->b[0] - G->a[0], uz = G->b[1] - G->a[1], L = hypotf(ux, uz); if (L < 1.f) continue; ux /= L; uz /= L;
      for (float t = .5f * fmodf(L, 2.f) + .5f; t < L; t += 2.f) {
        float px = G->a[0] + ux * t, pz = G->a[1] + uz * t, gf, wt = -1e9f, ys[8];
        if (hypotf(px - fx0, pz - fz0) > fr) continue;
        if (!colGround(&W, px + G->n[0] * 2.f, pz + G->n[1] * 2.f, G->y1, G->y1 - 12.f, &gf, 0)) continue;   // земля с лица у линии
        for (float d = 0.f; d <= 1.5f; d += .5f) { int k = layers(px - G->n[0] * d, pz - G->n[1] * d, gf + 4.2f, gf + .6f, ys); if (k && ys[0] > wt) wt = ys[0]; }
        if (wt < gf + 1.2f || wt > gf + 4.f) continue;   // нет стены за линией (ниже 1,2 м — ступень двора, бордюр, не стена)
        { float yb[8]; int kb = layers(px - G->n[0] * 3.5f, pz - G->n[1] * 3.5f, wt - .8f, gf - 3.f, yb);   // стена — гребень: за ней снова ниже
          if (!kb) continue; }
        nw++;
        if (getenv("WALLS_DEBUG")) printf("    точка забор %u (%.1f %.1f) земля %.2f стена %.2f\n", si, px, pz, gf, wt);
        for (int a = 0; a < 7; a++) for (int vi = 0; vi < 3; vi++) {
          float ang = ANG[a] * 3.14159265f / 180.f, v = vi == 0 ? 17.f : vi == 1 ? 22.f : 28.f;
          float dx = -G->n[0] * cosf(ang) + ux * sinf(ang), dz = -G->n[1] * cosf(ang) + uz * sinf(ang), sx = px - dx * 12.f, sz = pz - dz * 12.f, g0;
          if (!colGround(&W, sx, sz, gf + 1.5f, gf - 3.f, &g0, 0) || fabsf(g0 - gf) > 1.5f) continue;   // разгон по той же земле, что у стены
          int res[2][3] = {{0}}; float mu[2] = {-9, -9}; int okr = 1; int fz[2] = {0, 0}; Car endC[2];
          for (int o = 0; o < 2 && okr; o++) {
            SUPOFF(!o); Car c; carInit(&c, NULL, &W, sx, g0, sz, atan2f(dx, dz)); for (int k = 0; k < 20; k++) step(&c, 0, 0, 0);
            if (!c.grounded || c.contacts) { okr = 0; break; }
            carSetSpeed(&c, v); int rv0 = 0;
            for (int f = 0; f < 240; f++) { if (f == 180) rv0 = c.reverts; step(&c, f < 150 ? 1.f : 0.f, 0.f, 0.f); float u = side(G, c.x, c.z), tt = (c.x - G->a[0]) * ux + (c.z - G->a[1]) * uz;
              if (fabsf(u) < 3.5f && tt > -1.f && tt < L + 1.f && c.recoveries == 0 && c.y - wt > mu[o]) mu[o] = c.y - wt; }   // начало машины в 2,3 м за носом
            float u = side(G, c.x, c.z), tt = (c.x - G->a[0]) * ux + (c.z - G->a[1]) * uz; int in = tt > -1.f && tt < L + 1.f && c.recoveries == 0;
            res[o][0] = mu[o] > -.05f; res[o][1] = in && fabsf(u) < 1.5f && c.y > wt - .4f; res[o][2] = in && u < -1.5f;
            if (c.reverts - rv0 > 50) { frozen[o]++; fz[o] = 1; }   // последнюю секунду почти каждый подшаг отменён — машина замерла (подвисла на линии)
            endC[o] = c;
          }
          if (!okr) continue;
          if (getenv("POCKETS_FROZEN") && (fz[0] || fz[1])) {   // разбор «замерла» по точкам: кто замер, где, уезжает ли машина за 2,5 с (trappedAt: газ/назад/руль, 8 заходов, 3 м)
            int tr0 = fz[0] ? trappedAt(&endC[0]) : -1, tr1 = fz[1] ? trappedAt(&endC[1]) : -1, es1 = fz[1] ? escapeAt(&endC[1]) : -1;
            printf("  ЗАМЕРЛА забор %u (%.1f %.1f) стена %.2f %+3.0f° %2.0f м/с: прежнее %s, новое %s | конец нового (%.2f %.2f %.2f) сторона %.2f; escapeAt(8 с, 15 м): %d\n", si, px, pz, wt, ANG[a], v,
                   fz[0] ? (tr0 ? "замерла И ЗАПЕРТА" : "замерла, уезжает") : "едет", fz[1] ? (tr1 ? "замерла И ЗАПЕРТА" : "замерла, уезжает") : "едет",
                   endC[1].x, endC[1].y, endC[1].z, side(G, endC[1].x, endC[1].z), es1);
          }
          if (getenv("POCKETS_FROZEN") && ((res[1][2] && !res[0][2]) || (res[1][1] && !res[0][1]))) {   // новое «за ней»/«на стене», прежнее нет: уезжает ли машина из конца заезда
            int tr1 = trappedAt(&endC[1]), es1 = escapeAt(&endC[1]);
            printf("  НОВОЕ %s забор %u (%.1f %.1f) стена %.2f %+3.0f° %2.0f м/с: конец (%.2f %.2f %.2f) сторона %.2f; trappedAt(2,5 с, 3 м): %s; escapeAt(8 с, 15 м): %s\n", res[1][2] ? "ЗА" : "НА СТЕНЕ", si, px, pz, wt, ANG[a], v,
                   endC[1].x, endC[1].y, endC[1].z, side(G, endC[1].x, endC[1].z), tr1 ? "ЗАПЕРТА" : "уезжает", es1 ? "уезжает" : "ЗАПЕРТА");
          }
          tot++;
          for (int o = 0; o < 2; o++) { up[o] += res[o][0]; top[o] += res[o][1]; beh[o] += res[o][2]; if (mu[o] > maxUp[o]) maxUp[o] = mu[o]; }
          if (res[0][0] || res[0][1] || res[0][2] || res[1][0] || res[1][1] || res[1][2]) {
            static const char LET[] = "ABCDEFGHJKLM"; int cx = (int)floorf((px + 700.f) / 100.f), cz = (int)floorf((pz + 700.f) / 100.f);
            int sxi = (int)floorf(((px + 700.f) / 100.f - cx) * 3.f), szi = (int)floorf(((pz + 700.f) / 100.f - cz) * 3.f);
            if (getenv("POCKETS_TRACE") || res[1][0] || res[1][1] || res[1][2])
              printf("  %c%d-%d забор %u у (%.1f %.1f) стена %.2f над землёй %.2f, %+3.0f° %2.0f м/с: прежнее %+.2f%s%s, новое %+.2f%s%s\n",
                     cx >= 0 && cx < 12 ? LET[cx] : '?', cz + 1, 1 + sxi + 3 * szi, si, px, pz, wt, wt - gf, ANG[a], v, mu[0], res[0][1] ? " НА СТЕНЕ" : "",
                     res[0][2] ? " ЗА" : "", mu[1], res[1][1] ? " НА СТЕНЕ" : "", res[1][2] ? " ЗА" : "");
          }
        }
      }
    }
    printf("ИТОГ стены: точек со стеной-гребнем %d, таранов %d; прежнее — выше верха стены %d (до %+.2f м), на стене %d, за ней %d, замерла %d; "
           "новое — выше %d (до %+.2f м), на стене %d, за ней %d, замерла %d\n", nw, tot, up[0], maxUp[0], top[0], beh[0], frozen[0], up[1], maxUp[1], top[1], beh[1], frozen[1]);
    if (argc >= 6) { check("E: прежнее — таран выносит колёса выше верха стены (красный пойман)", up[0] > 0);
                     check("E: новое — ни выше верха стены, ни на ней, ни за ней", up[1] == 0 && top[1] == 0 && beh[1] == 0); }
    // F (вся семья, все уровни) — суммой по уровням в tests/pockets/gate.sh: новое не хуже прежнего по каждому счёту (уровень по отдельности
    // может разойтись на 1–2 заезда: хаотичная траектория после другого удара)
    printf("WALLS\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\n", up[0], top[0], beh[0], frozen[0], up[1], top[1], beh[1], frozen[1]);
  } else if (!strcmp(argv[2], "wallcase") && argc >= 8) {   // wallcase SEG PX PZ ANG V: таран из walls по кадрам (прежнее и новое)
    const ColSeg *G = &W.seg[atoi(argv[3])]; float px = atof(argv[4]), pz = atof(argv[5]), ang = atof(argv[6]) * 3.14159265f / 180.f, v = atof(argv[7]);
    float ux = G->b[0] - G->a[0], uz = G->b[1] - G->a[1], L = hypotf(ux, uz); ux /= L; uz /= L;
    float dx = -G->n[0] * cosf(ang) + ux * sinf(ang), dz = -G->n[1] * cosf(ang) + uz * sinf(ang), sx = px - dx * 12.f, sz = pz - dz * 12.f, g0, gf;
    if (!colGround(&W, px + G->n[0] * 2.f, pz + G->n[1] * 2.f, G->y1, G->y1 - 12.f, &gf, 0)) return 2;   // как в walls: земля с лица у линии
    for (int o = 0; o < 2; o++) {
      SUPOFF(!o); Car c; if (!colGround(&W, sx, sz, gf + 1.5f, gf - 3.f, &g0, 0)) return 2;
      carInit(&c, NULL, &W, sx, g0, sz, atan2f(dx, dz)); for (int k = 0; k < 20; k++) step(&c, 0, 0, 0); carSetSpeed(&c, v);
      printf("%s: старт (%.2f %.2f %.2f)\n", o ? "новое" : "прежнее", c.x, c.y, c.z);
      for (int f = 0; f < 240; f++) { step(&c, f < 150 ? 1.f : 0.f, 0, 0);
        if (f % 8 == 7) printf("  %3d pos %.2f %.2f %.2f сторона %.2f v %.1f vy %.2f gr %d wh %d ct %d type %d idx %u crash %d rec %d rev %d why %d\n", f, c.x, c.y, c.z, side(G, c.x, c.z),
          hypotf(c.vel[0], c.vel[2]), c.vel[1], c.grounded, c.wheels, c.contacts, c.contacts ? c.ctype[0] : -1, c.wallIdx, c.crashes, c.recoveries, c.reverts, c.revWhy); }
    }
  } else if (!strcmp(argv[2], "slide") && argc >= 7) {   // slide SEG PX PZ S: заезд C (25°, 8 м/с) по кадрам, прежнее и новое
    Cand k = {atoi(argv[3]), (float)atof(argv[4]), (float)atof(argv[5]), (float)atof(argv[6])}; const ColSeg *G = &W.seg[k.seg];
    float a = 25.f * 3.14159265f / 180.f, ux = G->b[0] - G->a[0], uz = G->b[1] - G->a[1], L = hypotf(ux, uz); ux /= L; uz /= L;
    float dxh = -G->n[0] * cosf(a) + ux * sinf(a), dzh = -G->n[1] * cosf(a) + uz * sinf(a);
    for (int o = 0; o < 2; o++) {
      SUPOFF(!o); Car c; printf("%s: верх %.2f\n", o ? "новое" : "прежнее", G->y1);
      if (!placeOn(&c, k.px - dxh * 6.f, k.s, k.pz - dzh * 6.f, atan2f(dxh, dzh))) continue;
      carSetSpeed(&c, 8.f); float vyMax = -1e9f; int vyF = 0;
      for (int f = 0; f < 120; f++) { float px = c.x, pz = c.z, vx = c.vel[0], vz = c.vel[2];
        step(&c, hypotf(c.vel[0], c.vel[2]) > 8.f ? 0.f : 1.f, 0, 0);
        float pop = hypotf(c.x - px - vx * DT, c.z - pz - vz * DT);
        if (pop > .1f || f % 10 == 9) printf("  %3d pos %.2f %.2f %.2f сторона %.2f v %.2f gr %d wh %d ct %d type %d idx %u rev %d why %d толчок %.2f\n", f, c.x, c.y, c.z,
          side(G, c.x, c.z), hypotf(c.vel[0], c.vel[2]), c.grounded, c.wheels, c.contacts, c.contacts ? c.ctype[0] : -1, c.wallIdx, c.reverts, c.revWhy, pop); }
    }
  } else if (!strcmp(argv[2], "trace") && argc >= 7) {   // trace SEG PX PZ S: заезд B по кадрам, прежнее и новое
    Cand k = {atoi(argv[3]), (float)atof(argv[4]), (float)atof(argv[5]), (float)atof(argv[6])}; const ColSeg *G = &W.seg[k.seg];
    for (int o = 0; o < 2; o++) {
      SUPOFF(!o); Car c; float sx = k.px + G->n[0] * 6.f, sz = k.pz + G->n[1] * 6.f;
      printf("%s: забор (%.2f %.2f)-(%.2f %.2f) верх %.2f\n", o ? "новое" : "прежнее", G->a[0], G->a[1], G->b[0], G->b[1], G->y1);
      if (!placeOn(&c, sx, k.s, sz, atan2f(-G->n[0], -G->n[1]))) { printf("  старт не встал\n"); continue; }
      for (int f = 0; f < 180; f++) { step(&c, 1, 0, 0);
        if (f % 6 == 5) printf("  %3d pos %.2f %.2f %.2f сторона %.2f gr %d wh %d ct %d rev %d why %d rec %d\n", f, c.x, c.y, c.z, side(G, c.x, c.z), c.grounded, c.wheels, c.contacts, c.reverts, c.revWhy, c.recoveries); }
    }
  } else if (!strcmp(argv[2], "c25") && argc >= 7) {   // c25 SEG PX PZ S: заезд C (25°, 8 м/с) по кадрам, прежнее и новое
    Cand k = {atoi(argv[3]), (float)atof(argv[4]), (float)atof(argv[5]), (float)atof(argv[6])}; const ColSeg *G = &W.seg[k.seg];
    for (int o = 0; o < 2; o++) {
      SUPOFF(!o); Car c; float a = 25.f * 3.14159265f / 180.f, ux = G->b[0] - G->a[0], uz = G->b[1] - G->a[1], L = hypotf(ux, uz); ux /= L; uz /= L;
      float dxh = -G->n[0] * cosf(a) + ux * sinf(a), dzh = -G->n[1] * cosf(a) + uz * sinf(a), sx = k.px - dxh * 6.f, sz = k.pz - dzh * 6.f;
      printf("%s: забор (%.2f %.2f)-(%.2f %.2f) верх %.2f опора %.2f\n", o ? "новое" : "прежнее", G->a[0], G->a[1], G->b[0], G->b[1], G->y1, k.s);
      if (!placeOn(&c, sx, k.s, sz, atan2f(dxh, dzh))) { printf("  старт не встал\n"); continue; }
      carSetSpeed(&c, 8.f); float vyMax = -1e9f; int vyF = 0;
      for (int f = 0; f < 120; f++) { float px = c.x, pz = c.z, vx = c.vel[0], vz = c.vel[2];
        step(&c, hypotf(c.vel[0], c.vel[2]) > 8.f ? 0.f : 1.f, 0, 0);
        float pop = hypotf(c.x - px - vx * DT, c.z - pz - vz * DT);
        if (c.vel[1] > vyMax) { vyMax = c.vel[1]; vyF = f; }
        if (c.contacts || pop > .15f || f % 20 == 0) printf("  %3d pos %.2f %.2f %.2f сторона %.2f v %.2f vy %.2f gr %d wh %d ct %d(типы %d %d) pop %.2f\n", f, c.x, c.y, c.z, side(G, c.x, c.z), hypotf(c.vel[0], c.vel[2]), c.vel[1], c.grounded, c.wheels, c.contacts, c.ctype[0], c.ctype[1], pop); }
      printf("  макс. vy %.2f на кадре %d\n", vyMax, vyF);
    }
  } else return 2;
  printf("RESULT: %s (%d failures)\n", fails ? "FAIL" : "OK", fails);
  return fails;
}
