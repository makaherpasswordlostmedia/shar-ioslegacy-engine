// Догонялки, самоигра (пункт Б4, docs/БОТЫ-ИГРОКИ_2026-09-28.md §3.3): беглец — игрок в игре без экрана (BotWorld, тот же C-код,
// что EBOOT), погоня — вторая машина на том же car.c (carUpdate + удар машин carHitCar с миром, порядок как в полигоне). Раунд 60 с.
// ПРАВИЛА БОТА, не игры (в данных диска их нет; пометка в STATE.md): поимка — погоня ближе 4.5 м, на одном этаже (перепад < 2 м)
// и без стены между машинами (bwReachable, Т1.1), беглец медленнее 3 м/с 1.5 с подряд; погоня едет на параметрах famil_v
// (машина полиции из данных — позже). Сборка -DCHASE_FLAT_CATCH=1 — отрицательный контроль: поимка только по плоскости, как до Т1.1.
// Мозги — правила с числами, числа подбираются коэволюцией: поколение беглецов играет против погонь того же поколения, лучшие
// обеих сторон скрещиваются и мутируют. Беглец: едет к своему укрытию (ген — узел дорог), стоит, при приближении погони удирает
// к узлу подальше от неё. Погоня: A* по дорогам к беглецу (раз в секунду), вблизи — прямо с упреждением, таран; застряла — назад.
// Выход (stdout): "G" — поколение (среднее и лучшее время до поимки, доля поимок); "X" — кластеры (вид + клетка 8 м + слой + объект):
//   eternal_corner — беглец не пойман, стоял ≥ 20 с до конца раунда, из них ≥ 10 с погоня была ближе 25 м (подъехала и не достала),
//                    и подтверждение: беглец стоит там же, погоня (те же гены) заходит 8 раз с разных сторон по 30 с и 9-й раз по следу
//                    самого беглеца (куда он проехал, туда проедет и она) — ни разу не поймала;
//   pursuer_stuck  — погоня ≥ 15 с медленнее 1 м/с, беглец дальше 15 м (погоня застряла навсегда).
// Повтор: файл раунда (гены обеих сторон, старты) -> chase ... --replay FILE: тот же исход в тот же кадр.
//   chase LEVEL HOMER ROADS [--gens 20] [--pop 16] [--rounds 4] [--seed S] [--out DIR] [--region X Z R] [--plant-corner X Z R]
//   chase LEVEL HOMER ROADS --catch-probe FX FY FZ CX CY CZ: беглец в F, погоня в C, оба стоят 3 с -> «ПОЙМАН» / «не пойман» (гейт Т1.1)
//   --plant-corner: контроль гейта — «вечный угол»: круг, куда погоне въезд запрещён (она останавливается у края), —
//                   детектор обязан показать eternal_corner в этом месте. Сборка -DCHASE_BREAK_DETECT=1 — детектор сломан нарочно.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "world.h"
#include "navgraph.h"

#define ROUND_S 60.f
#define CATCH_R 4.5f
#define TRAIL_R 40.f   // погоня ближе этого к беглецу и прямой путь перекрыт — едет обходом по следу
#define CATCH_GAP .8f   // кузова ближе — тоже «рядом» (см. catchNear)
#ifndef CHASE_BREAK_DETECT
#define CORNER_PARK_S 20.f
#define CORNER_NEAR_S 10.f
#else
#define CORNER_NEAR_S 1e9f
#define CORNER_PARK_S 1e9f   // сломано нарочно: детектор «вечного угла» никогда не срабатывает
#endif
static int catchNear(const Car *f, const Car *c, float d) {   // беглец f рядом с погоней c: можно ловить
#ifdef CHASE_FLAT_CATCH
  return d < CATCH_R && fabsf(f->v) < 3.f;
#else
  if (fabsf(f->v) >= 3.f) return 0;
#ifndef CHASE_OLD_PURSUIT
  // Правило бота (группа corners-roads, 01.10; решено терминалом): «рядом» — центры ближе 4.5 м ИЛИ кузова ближе 0.8 м.
  // Разбор угла 154 592 ночи 30.09: беглец стоит носом/кормой к погоне, кузова упёрлись бампер в бампер, а центры в 4.6–5.5 м
  // (две полудлины машины 2.3 + 2.3 больше 4.5) — по старому правилу такой упор не ловится никогда.
  if (d >= CATCH_R) {
    CarBox a, b; carBox(f, &a); carBox(c, &b); float ux = (c->x - f->x) / (d + 1e-4f), uz = (c->z - f->z) / (d + 1e-4f);
    float ea = fabsf(ux * a.fx + uz * a.fz) * a.hl + fabsf(-ux * a.fz + uz * a.fx) * a.hw, eb = fabsf(ux * b.fx + uz * b.fz) * b.hl + fabsf(-ux * b.fz + uz * b.fx) * b.hw;
    if (d - ea - eb >= CATCH_GAP) return 0;
  }
#else
  if (d >= CATCH_R) return 0;
#endif
  return bwReachable(f->x, f->y, f->z, c->x, c->y, c->z);
#endif
}
static uint32_t rs = 1;
static uint32_t xr(void) { rs ^= rs << 13; rs ^= rs >> 17; rs ^= rs << 5; return rs; }
static float fr(void) { return (xr() >> 8) * (1.f / 16777216.f); }
static float gauss(void) { float u = fr() + 1e-7f, v = fr(); return sqrtf(-2.f * logf(u)) * cosf(6.2831853f * v); }
static float clampf(float v, float a, float b) { return v < a ? a : v > b ? b : v; }

// ------------------------------------------------------------------ гены
// беглец: водитель (NPAR, как у навигатора), укрытие (узел), дистанция тревоги (м), скорость сближения для тревоги (м/с)
// погоня: водитель (NPAR), упреждение цели (с), дистанция «прямо на беглеца» (м), время тарана задним ходом (с)
typedef struct { float par[NPAR]; int dest; float alarm, closing; } Fug;
typedef struct { float par[NPAR]; float lead, direct, backT; } Cop;
static float regX, regZ, regR = 1e9f; static int plant; static float plX, plZ, plR;
static int inRegion(int n) { return hypotf(node[n].x - regX, node[n].z - regZ) <= regR; }
static unsigned char *nodeFree;   // узел дороги, где машина стоит свободно (не внутри коллизии): старты только с них
static void markFreeNodes(void) {
  nodeFree = calloc((size_t)nnode, 1); int bad = 0;
  for (int i = 0; i < nnode; i++) { Car c; carInit(&c, NULL, bwCol(), node[i].x, node[i].y, node[i].z, 0.f); CarBox b; carBox(&c, &b); colProbeCar(bwCol(), &b);
    nodeFree[i] = b.maxDepth < .3f; bad += !nodeFree[i]; }
  fprintf(stderr, "chase: узлов дорог %d, внутри коллизии %d — старты не с них\n", nnode, bad);
}
static int randNodeNear(float x, float z, float r0, float r1) {   // случайный свободный узел на расстоянии r0..r1 (или ближайший к кольцу)
  for (int k = 0; k < 400; k++) { int n = (int)(xr() % (unsigned)nnode); float d = hypotf(node[n].x - x, node[n].z - z); if (d >= r0 && d <= r1 && (!nodeFree || nodeFree[n])) return n; }
  return nearestNode(x + r1, 0, z);
}
static void mutPar(float *p) { for (int k = 0; k < NPAR; k++) if (fr() < .4f) p[k] = clampf(p[k] + gauss() * .12f * (PARHI[k] - PARLO[k]), PARLO[k], PARHI[k]); }
static Fug fugNew(void) {
  Fug f; for (int k = 0; k < NPAR; k++) f.par[k] = PARLO[k] + fr() * (PARHI[k] - PARLO[k]);
  do f.dest = (int)(xr() % (unsigned)nnode); while (!inRegion(f.dest));
  f.alarm = 10.f + fr() * 50.f; f.closing = fr() * 6.f; return f;
}
static Cop copNew(void) { Cop c; for (int k = 0; k < NPAR; k++) c.par[k] = PARLO[k] + fr() * (PARHI[k] - PARLO[k]); c.lead = fr() * 1.5f; c.direct = 10.f + fr() * 30.f; c.backT = .6f + fr() * 1.4f; return c; }

// ------------------------------------------------------------------ раунд
static BotWorld W; static BotSnap S0; static Car cop;
typedef struct { float fx, fy, fz, fh, cx, cy, cz, ch; } Starts;
typedef struct { float survive; int caught; int corner, stuck; float kx, ky, kz, sx, sy, sz, kh; } Result;
static P3 trail[256]; static int ntrail;          // след беглеца раунда (раз в 0.5 с) — для подтверждения угла
static const P3 *copTrail; static int copTrailN;   // подтверждение: погоня едет по этому следу (как ехал беглец)
static float trailV[256]; static const float *copTrailV;   // скорость беглеца в точке следа (обход: погоня не быстрее него)
static void aimDirect(const Car *c, float tx, float tz, const float *par, unsigned *b, float *ax) {
  P3 q[2] = {{c->x, c->y, c->z}, {tx, c->y, tz}}; int seg = 0; navSteer(q, 2, &seg, c, par, b, ax);
}
#ifndef CHASE_OLD_PURSUIT
static int wideSee(const Car *a, P3 b) {   // видно кузовом: три луча bwReachable — по оси и по бортам (±0.8 м поперёк линии)
  float dx = b.x - a->x, dz = b.z - a->z, l = hypotf(dx, dz) + 1e-4f, ox = -dz / l * .8f, oz = dx / l * .8f;
  return bwReachable(a->x, a->y, a->z, b.x, b.y, b.z) && bwReachable(a->x + ox, a->y, a->z + oz, b.x + ox, b.y, b.z + oz) &&
         bwReachable(a->x - ox, a->y, a->z - oz, b.x - ox, b.y, b.z - oz);
}
#endif
static Result playRoundT(const Fug *F, const Cop *C, const Starts *st, int trace, float secs, int stay) {
  uint32_t keepRs = rs, h = 2166136261u; const unsigned char *sb = (const void *)st;   // свой генератор раунда: исход — функция генов и стартов
  for (size_t k = 0; k < sizeof *st; k++) h = (h ^ sb[k]) * 16777619u;
  rs = h | 1;
  bwLoad(&W, &S0); bwPlace(&W, st->fx, st->fy, st->fz, st->fh);
  carInit(&cop, NULL, bwCol(), st->cx, st->cy, st->cz, st->ch);
  P3 fq[MAXWP], cq[MAXWP]; int fn = navPlan(W.car.x, W.car.y, W.car.z, node[F->dest].x, node[F->dest].y, node[F->dest].z, fq, MAXWP), fseg = 0, cn = 0, cseg = 0;
  int mode = 0;   // беглец: 0 к укрытию, 1 стоит, 2 удирает
  int blocked = 0, cmode = 0, tkAt = 0, noTrail = 0; (void)blocked; (void)cmode; (void)tkAt; (void)noTrail;   // погоня: прямой путь к беглецу перекрыт; 2 — едет обходом по следу
  float nearT = 0, parkT = 0, copSlowT = 0, backLeft = 0, prevD = 1e9f, copAx = 0, stuckT = 0, nearParkT = 0; Result r = {secs, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};
  int frames = (int)(secs * 60); if (stay) mode = 1; else ntrail = 0;
  for (int f = 0; f < frames; f++) {
    Car *c = &W.car; float d = hypotf(cop.x - c->x, cop.z - c->z), closing = (prevD - d) * 60.f; prevD = d;
    // --- беглец
    unsigned b = 0; float ax = 0;
    if (!stay && mode != 2 && d < F->alarm && closing > F->closing) {   // тревога: к узлу подальше от погони
      int best = -1; float bs = -1e9f;
      for (int k = 0; k < 12; k++) { int n = randNodeNear(c->x, c->z, 40.f, 120.f); float s = hypotf(node[n].x - cop.x, node[n].z - cop.z) - hypotf(node[n].x - c->x, node[n].z - c->z) * .3f; if (s > bs) { bs = s; best = n; } }
      fn = navPlan(c->x, c->y, c->z, node[best].x, node[best].y, node[best].z, fq, MAXWP); fseg = 0; mode = 2;
    }
    if (mode == 1) { if (fabsf(c->v) > .5f) b = c->v > 0 ? GP_L : GP_R; }   // стоять (L при нуле — задний ход, поэтому только гасить)
    else {
      navSteer(fq, fn, &fseg, c, F->par, &b, &ax);
      if (hypotf(fq[fn - 1].x - c->x, fq[fn - 1].z - c->z) < 6.f) mode = 1;
    }
    bwStep(&W, b, ax, 0.f);
    // --- погоня: тот же ввод игрока (gameCarInput), тот же car.c
    unsigned cb = 0; float cax = 0;
    float tx = c->x + sinf(c->h) * c->v * C->lead, tz = c->z + cosf(c->h) * c->v * C->lead;
    if (plant && hypotf(tx - plX, tz - plZ) < plR) { float dx = tx - plX, dz = tz - plZ, l = hypotf(dx, dz) + 1e-3f; tx = plX + dx / l * plR; tz = plZ + dz / l * plR; }
#ifndef CHASE_OLD_PURSUIT
    // Обход по следу (группа corners-roads, 01.10; решено терминалом). Разбор пяти вечных углов ночи 30.09 (CHASE_WHY=1):
    // беглец стоит на ровной открытой опоре (контактов 0, мест поимки вокруг 97–144 из 144), а погоня последние метры едет
    // «прямо на него» и упирается в стенку/уступ между ними (ящики диска b18, b42, b495, b1448 — коллизия из данных, не
    // ошибка экспорта). Правило бота: если до беглеца ближе дальности «прямо» и прямой путь перекрыт (bwReachable — то же
    // правило, что у поимки), погоня едет по следу беглеца от ближайшей видимой ей точки следа — куда он проехал, туда
    // проедет и она. Сборка -DCHASE_OLD_PURSUIT=1 — старое поведение (отрицательный контроль гейта tests/chase_corners).
    if (backLeft <= 0 && d < fmaxf(C->direct, TRAIL_R)) {   // ближе TRAIL_R и прямой путь перекрыт — обход по следу
      if (f % 10 == 0) blocked = !bwReachable(cop.x, cop.y, cop.z, c->x, c->y, c->z);
    } else blocked = 0;
    const P3 *tk = copTrail ? copTrail : trail; const float *tkv = copTrail ? copTrailV : trailV; int tkn = copTrail ? copTrailN : ntrail;
    if (blocked && tkn >= 2 && f >= noTrail) {
      if (cmode != 2 || f % 10 == 0) {   // цель — точка следа: вход с ближайшей видимой, дальше по следу, срез только вблизи и видимый кузовом
        if (cmode != 2) {   // вход в обход: ближайшая видимая точка следа (не больше 8 проверок), иначе просто ближайшая
          int used[8] = {0}, nu = 0; tkAt = -1;
          for (int tries = 0; tries < 8; tries++) {
            int k = -1; float kd = 1e9f;
            for (int i = 0; i < tkn; i++) { int skip = 0; for (int u = 0; u < nu; u++) skip |= used[u] == i; if (skip) continue;
              float di = hypotf(tk[i].x - cop.x, tk[i].z - cop.z); if (di < kd) { kd = di; k = i; } }
            if (k < 0) break; used[nu++] = k;
            if (wideSee(&cop, tk[k])) { tkAt = k; break; }
          }
          if (tkAt < 0) { noTrail = f + 120; goto trailOff; }   // ни одной видимой точки следа — обход не помогает (застрянет в упоре), 2 с по дорогам
        }
        while (tkAt < tkn - 1 && hypotf(tk[tkAt].x - cop.x, tk[tkAt].z - cop.z) < 5.f) tkAt++;   // точку прошли — к следующей
        for (int j = tkn - 1; j > tkAt; j--)   // срезать по следу можно только вблизи (8 м) и если видно кузовом
          if (hypotf(tk[j].x - cop.x, tk[j].z - cop.z) < 8.f && wideSee(&cop, tk[j])) { tkAt = j; break; }
        cn = 0; for (int i = tkAt; i < tkn && cn < 3; i++) cq[cn++] = tk[i];
        if (tkAt >= tkn - 1) cq[cn++] = (P3){c->x, c->y, c->z};
        if (cn < 2) cq[cn++] = (P3){c->x, c->y, c->z};
        cseg = 0; cmode = 2;
      }
      float p3[NPAR]; memcpy(p3, C->par, sizeof p3); p3[2] = p3[3] = fminf(C->par[3], fmaxf(tkv[tkAt], 3.f) + 1.5f);   // по следу не быстрее беглеца в этой точке: с разгона щель за трамплином (угол 124 220) перелетается
      navSteer(cq, cn, &cseg, &cop, p3, &cb, &cax);
      if (cop.v < 1.5f && hypotf(cq[cn - 1].x - cop.x, cq[cn - 1].z - cop.z) < 12.f) cb |= GP_R;   // подъезд к беглецу: не замирать
      goto copDone;
    }
    trailOff:
    if (cmode == 2) { cn = 0; cmode = 0; }   // вышли из обхода — путь построить заново
#endif
    if (backLeft > 0) { cb = GP_L; cax = -copAx; backLeft -= BW_DT; }
    else if (copTrail && d >= 12.f) {   // след беглеца, прорежен до MAXWP точек
      if (cn == 0) { int b0 = 0;
#ifndef CHASE_OLD_PURSUIT
        { float bd = 1e9f; for (int i = 0; i < copTrailN; i++) { float di = hypotf(copTrail[i].x - cop.x, copTrail[i].z - cop.z); if (di < bd) { bd = di; b0 = i; } } }   // после обхода — дальше от ближайшей точки, не с начала
#endif
        int st = (copTrailN - b0 + MAXWP - 1) / MAXWP; if (st < 1) st = 1; for (int i = b0; i < copTrailN && cn < MAXWP; i += st) cq[cn++] = copTrail[i]; cseg = 0; }
      navSteer(cq, cn, &cseg, &cop, C->par, &cb, &cax); }
    else if (d < 12.f) {   // последние метры: прямо в беглеца, скорость по расстоянию (не проскочить)
      float p2[NPAR]; memcpy(p2, C->par, sizeof p2); p2[2] = p2[3] = fminf(C->par[3], d * .8f + 2.f); p2[4] = 1.f;
      aimDirect(&cop, c->x, c->z, p2, &cb, &cax); cb |= (cop.v < 1.5f ? GP_R : 0); cb &= ~(unsigned)GP_SQUARE;
    } else if (d < C->direct) aimDirect(&cop, tx, tz, C->par, &cb, &cax);
    else { if (f % 60 == 0 || cn == 0) { cn = navPlan(cop.x, cop.y, cop.z, tx, c->y, tz, cq, MAXWP); cseg = 0; } navSteer(cq, cn, &cseg, &cop, C->par, &cb, &cax); }
#ifndef CHASE_OLD_PURSUIT
    copDone:
#endif
    if (plant && hypotf(cop.x - plX, cop.z - plZ) < plR + 6.f) {   // «вечный угол»: погоне туда нельзя — гасит скорость у края
      float inward = (sinf(cop.h) * (plX - cop.x) + cosf(cop.h) * (plZ - cop.z)) * cop.v;
      if (inward > 0) cb = cop.v > .3f ? GP_L : cop.v < -.3f ? GP_R : 0;
    }
    if (backLeft <= 0) copAx = cax;
    GamePad pad = {cb, 0, cax, 0}; CarInput in; gameCarInput(&W.G, &pad, &in);
    carUpdate(&cop, bwCol(), &in, BW_DT); carHitCar(&W.car, &cop, bwCol()); bwHitTraffic(&cop);   // Т1.2: погоня о трафик и стоящие
    // --- счёт
    if (fabsf(cop.v) < 1.f && backLeft <= 0) { copSlowT += BW_DT; if (copSlowT > 1.5f && (copSlowT - 1.5f) < BW_DT) backLeft = C->backT; } else if (fabsf(cop.v) >= 1.f) copSlowT = 0;
    if (fabsf(cop.v) < 1.f && d > 15.f) stuckT += BW_DT; else stuckT = 0;
    if (stuckT >= 15.f && !r.stuck) { r.stuck = 1; r.sx = cop.x; r.sy = cop.y; r.sz = cop.z; }
    if (fabsf(c->v) < 1.f) { parkT += BW_DT; if (d < 25.f) nearParkT += BW_DT; } else parkT = nearParkT = 0;
#ifdef CHASE_OLD_PURSUIT
    if (!stay && f % 30 == 0 && ntrail < 256) trail[ntrail++] = (P3){c->x, c->y, c->z};
#else   // след — только движение: точка, когда беглец отъехал на 2 м от прошлой (стоянка не забивает след одной точкой ×100)
    if (!stay && f % 6 == 0 && ntrail < 256 && (ntrail == 0 || hypotf(c->x - trail[ntrail - 1].x, c->z - trail[ntrail - 1].z) > 2.f)) { trailV[ntrail] = fabsf(c->v); trail[ntrail++] = (P3){c->x, c->y, c->z}; }
#endif
    if (catchNear(c, &cop, d)) nearT += BW_DT; else nearT = 0;
    if (trace && f % (trace > 1 ? 60 : 300) == 0) fprintf(stderr, "  t %.0f беглец %.1f %.1f v %.1f режим %d | погоня %.1f %.1f y %.1f v %.1f | d %.1f обход %d (%d/%d) след %d\n", f / 60.f, c->x, c->z, c->v, mode, cop.x, cop.z, cop.y, cop.v, d, cmode == 2, cseg, cn, copTrail ? copTrailN : ntrail);
    if (trace > 2 && f % 60 == 0) { CarBox q; carBox(&cop, &q); q.hl += .4f; q.hw += .2f; int n = colProbeCar(bwCol(), &q); fprintf(stderr, "     погоня курс %.2f цель (%.1f %.1f), касания:", cop.h, cn ? cq[cseg < cn - 1 ? cseg + 1 : cn - 1].x : 0, cn ? cq[cseg < cn - 1 ? cseg + 1 : cn - 1].z : 0);
      for (int k = 0; k < n && k < COL_MAX_CONTACTS; k++) fprintf(stderr, " %c%u(%.2f)", "tbcs"[q.type[k] & 3], (unsigned)q.index[k], q.depth[k]); fprintf(stderr, "\n"); }
    if (nearT >= 1.5f) { r.survive = (f + 1) / 60.f; r.caught = 1; break; }
  }
  if (!r.caught && parkT >= CORNER_PARK_S && nearParkT >= CORNER_NEAR_S) { r.corner = 1; r.kx = W.car.x; r.ky = W.car.y; r.kz = W.car.z; r.kh = W.car.h; }
  rs = keepRs;
  return r;
}
static Result playRound(const Fug *F, const Cop *C, const Starts *st, int trace) { return playRoundT(F, C, st, trace, ROUND_S, 0); }
static Starts makeStarts(const Fug *F) {
  Starts s; int a = randNodeNear(node[F->dest].x, node[F->dest].z, 60.f, 150.f), b = randNodeNear(node[a].x, node[a].z, 40.f, 80.f);
  int an = adjStart[a] < adjStart[a + 1] ? adj[adjStart[a]] : a;
  s.fx = node[a].x; s.fy = node[a].y; s.fz = node[a].z; s.fh = atan2f(node[an].x - node[a].x, node[an].z - node[a].z);
  s.cx = node[b].x; s.cy = node[b].y; s.cz = node[b].z; s.ch = atan2f(node[a].x - node[b].x, node[a].z - node[b].z);   // погоня смотрит на беглеца
  return s;
}

// подтверждение угла: беглец стоит в (x, z, h), погоня C заходит с 8 сторон (узлы дорог в 25–45 м), 30 с каждый; -> сколько поймали
static int confirmCorner(const Cop *C, float x, float y, float z, float h) {
  int caught = 0;
  for (int k = 0; k < 8; k++) {
    float a = k * .785398f; int n = nearestNode(x + sinf(a) * 35.f, y, z + cosf(a) * 35.f);
    if (hypotf(node[n].x - x, node[n].z - z) < 20.f) continue;
    Fug F; memset(&F, 0, sizeof F); for (int i = 0; i < NPAR; i++) F.par[i] = PAR0[i]; F.dest = nearestNode(x, y, z); F.alarm = 0; F.closing = 1e9f;
    Starts s = {x, y, z, h, node[n].x, node[n].y, node[n].z, atan2f(x - node[n].x, z - node[n].z)};
    Result r = playRoundT(&F, C, &s, 0, 30.f, 1);
    caught += r.caught;
  }
  if (!caught && ntrail > 2) {   // 9-й заход: погоня со старта беглеца по его следу — туда, где он проехал, она проедет тоже
    P3 tr[256]; float tv[256]; int n = ntrail; memcpy(tr, trail, sizeof(P3) * (size_t)n); memcpy(tv, trailV, sizeof(float) * (size_t)n);
    Fug F; memset(&F, 0, sizeof F); for (int i = 0; i < NPAR; i++) F.par[i] = PAR0[i]; F.dest = nearestNode(x, y, z); F.alarm = 0; F.closing = 1e9f;
    float hh = atan2f(tr[1].x - tr[0].x, tr[1].z - tr[0].z);
    Starts s = {x, y, z, h, tr[0].x, tr[0].y, tr[0].z, hh};
    copTrail = tr; copTrailV = tv; copTrailN = n; Result r = playRoundT(&F, C, &s, 0, ROUND_S, 1); copTrail = 0; copTrailV = 0; copTrailN = 0;
    caught += r.caught; ntrail = n;
  }
  return caught;
}

// ------------------------------------------------------------------ повтор раунда: файл
static void writeRound(const char *path, const Fug *F, const Cop *C, const Starts *s, const Result *r, const char *what) {
  FILE *f = fopen(path, "w"); if (!f) return;
  fprintf(f, "# chase: %s; повтор: build/bots/chase LEVEL HOMER ROADS --replay этот_файл\n", what);
  fprintf(f, "F"); for (int k = 0; k < NPAR; k++) fprintf(f, " %.9g", F->par[k]); fprintf(f, " %d %.9g %.9g\n", F->dest, F->alarm, F->closing);
  fprintf(f, "C"); for (int k = 0; k < NPAR; k++) fprintf(f, " %.9g", C->par[k]); fprintf(f, " %.9g %.9g %.9g\n", C->lead, C->direct, C->backT);
  fprintf(f, "S %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g\n", s->fx, s->fy, s->fz, s->fh, s->cx, s->cy, s->cz, s->ch);
  if (plant) fprintf(f, "P %.9g %.9g %.9g\n", plX, plZ, plR);
  fprintf(f, "R %.9g %d %d %d %.9g %.9g %.9g %.9g %.9g %.9g\n", r->survive, r->caught, r->corner, r->stuck, r->kx, r->ky, r->kz, r->sx, r->sy, r->sz);
  fclose(f);
}
static int readRound(const char *path, Fug *F, Cop *C, Starts *s, Result *r) {
  FILE *f = fopen(path, "r"); if (!f) return -1; char ln[1024]; int got = 0;
  while (fgets(ln, sizeof ln, f)) {
    char *p = ln + 1; int n;
    if (ln[0] == 'F') { for (int k = 0; k < NPAR; k++) { F->par[k] = strtof(p, &p); } F->dest = (int)strtol(p, &p, 10); F->alarm = strtof(p, &p); F->closing = strtof(p, &p); got |= 1; }
    else if (ln[0] == 'C') { for (int k = 0; k < NPAR; k++) { C->par[k] = strtof(p, &p); } C->lead = strtof(p, &p); C->direct = strtof(p, &p); C->backT = strtof(p, &p); got |= 2; }
    else if (ln[0] == 'S' && sscanf(p, "%f %f %f %f %f %f %f %f", &s->fx, &s->fy, &s->fz, &s->fh, &s->cx, &s->cy, &s->cz, &s->ch) == 8) got |= 4;
    else if (ln[0] == 'P' && sscanf(p, "%f %f %f", &plX, &plZ, &plR) == 3) plant = 1;
    else if (ln[0] == 'R' && sscanf(p, "%f %d %d %d %f %f %f %f %f %f%n", &r->survive, &r->caught, &r->corner, &r->stuck, &r->kx, &r->ky, &r->kz, &r->sx, &r->sy, &r->sz, &n) == 10) got |= 8;
  }
  fclose(f); return got == 15 ? 0 : -1;
}

// ------------------------------------------------------------------ кластеры
typedef struct { int kind, gx, gz, n, layer; float x, y, z; char file[96], obj[16]; } Clu;   // ключ Т1.1: вид + клетка 8 м + слой + объект
static Clu clu[2048]; static int nclu; static const char *kindName[2] = {"eternal_corner", "pursuer_stuck"};
static void addClu(int kind, float x, float y, float z, const char *out, const Fug *F, const Cop *C, const Starts *s, const Result *r) {
  int gx = (int)floorf(x / 8.f), gz = (int)floorf(z / 8.f), nl; char obj[16]; int layer = bwWhere(x, y, z, 2.5f, &nl, obj);
  for (int i = 0; i < nclu; i++) if (clu[i].kind == kind && clu[i].gx == gx && clu[i].gz == gz && clu[i].layer == layer && !strcmp(clu[i].obj, obj)) { clu[i].n++; return; }
  if (nclu >= 2048) return;
  Clu *c = &clu[nclu++]; *c = (Clu){kind, gx, gz, 1, layer, x, y, z, "", ""}; snprintf(c->obj, 16, "%s", obj);
  snprintf(c->file, sizeof c->file, "%s_%d_%d_L%d_%s.round", kindName[kind], gx * 8, gz * 8, layer, obj);
  if (out) { char p[600]; snprintf(p, sizeof p, "%s/%s", out, c->file); char what[128]; snprintf(what, sizeof what, "%s у %.0f %.0f", kindName[kind], x, z); writeRound(p, F, C, s, r, what); }
}

// --why (CHASE_WHY=1 при --replay): что держит беглеца в «вечном углу» — разбор для классификации (группа corners-roads, 01.10).
// Печатает контакты кузова беглеца (вид+номер примитива COL1, глубина, нормаль) и «места поимки»: точки в 2–4.5 м вокруг,
// где кузов погони стоит свободно, на том же этаже и без стены до беглеца (то же правило, что catchNear).
static void cornerWhy(const Car *f, const Car *c) {
  CarBox b; carBox(f, &b); int n = colProbeCar(bwCol(), &b);
  printf("почему: беглец %.2f %.2f %.2f курс %.2f v %.2f; контактов %d, худшая глубина %.2f\n", f->x, f->y, f->z, f->h, f->v, n, b.maxDepth);
  printf("  на земле %d, колёс %d, контактов со стенами %d; опоры под центром:", f->grounded, f->wheels, f->contacts);
  { float top = 1e4f, y, n3[3]; int m; for (int i = 0; i < 6 && colGroundMat(bwCol(), f->x, f->z, top, -1e4f, &y, n3, &m); i++) { printf(" %.2f(n.y %.2f%s)", y, n3[1], m ? " куст" : ""); top = y - .5f; } }
  printf("\n");
  for (int k = 0; k < n && k < COL_MAX_CONTACTS; k++) printf("  контакт %c%u глубина %.2f нормаль %.2f %.2f\n", "tbcs"[b.type[k] & 3], (unsigned)b.index[k], b.depth[k], b.nx[k], b.nz[k]);
  {   // профиль погоня -> беглец: высота опоры (ближайшая к линии) и первый примитив, который стоит поперёк (как в bwReachable)
    float dx = f->x - c->x, dz = f->z - c->z; int m = (int)(hypotf(dx, dz) / .5f), shown = 0; printf("  профиль от погони:");
    for (int i = 0; i <= m && m > 0; i++) {
      float t = i / (float)m, x = c->x + dx * t, z = c->z + dz * t, yl = c->y + (f->y - c->y) * t, y, n3[3];
      if (i % 4 == 0 && colGround(bwCol(), x, z, yl + 3.f, yl - 6.f, &y, n3)) printf(" %.1f", y);
      CarBox q; memset(&q, 0, sizeof q); q.x = x; q.z = z; q.fz = 1.f; q.hw = q.hl = .15f; q.y = yl; q.lo = .5f; q.hi = 1.5f;
      if (!shown && i > 0 && i < m && colProbeCar(bwCol(), &q) && q.maxDepth > .05f) { printf(" [стена %c%u у %.1f %.1f]", "tbcs"[q.type[0] & 3], (unsigned)q.index[0], x, z); shown = 1; }
    }
    printf("\n");
  }
  { CarBox cbx; carBox(c, &cbx); int cn2 = colProbeCar(bwCol(), &cbx); printf("  погоня: курс %.2f, контактов кузова %d, со стенами %d:", c->h, cn2, c->contacts);
    for (int k = 0; k < cn2 && k < COL_MAX_CONTACTS; k++) printf(" %c%u(%.2f; н %.2f %.2f)", "tbcs"[cbx.type[k] & 3], (unsigned)cbx.index[k], cbx.depth[k], cbx.nx[k], cbx.nz[k]); printf("\n"); }
  int spots = 0, free_ = 0, floor_ = 0;
  for (int ri = 0; ri < 6; ri++) for (int a = 0; a < 24; a++) {
    float r = 2.f + ri * .5f, an = a * 6.2831853f / 24.f, x = f->x + sinf(an) * r, z = f->z + cosf(an) * r;
    Car q; carInit(&q, NULL, bwCol(), x, f->y + .5f, z, atan2f(f->x - x, f->z - z)); CarBox qb; carBox(&q, &qb); colProbeCar(bwCol(), &qb);
    if (qb.maxDepth >= .3f) continue; free_++;
    if (fabsf(q.y - f->y) >= 2.f) continue; floor_++;
    if (!bwReachable(f->x, f->y, f->z, q.x, q.y, q.z)) continue; spots++;
    if (spots <= 3) printf("  место поимки %.1f %.1f %.1f (r %.1f)\n", q.x, q.y, q.z, r);
  }
  printf("  точек вокруг 144: кузов свободен %d, тот же этаж %d, без стены до беглеца %d; погоня в конце %.1f %.1f %.1f d %.1f, видит %d\n",
         free_, floor_, spots, c->x, c->y, c->z, hypotf(c->x - f->x, c->z - f->z), bwReachable(f->x, f->y, f->z, c->x, c->y, c->z));
}

typedef struct { float fit; int i; } Rank;
static int cmpRank(const void *a, const void *b) { float x = ((const Rank *)a)->fit, y = ((const Rank *)b)->fit; return x > y ? -1 : x < y; }

int main(int argc, char **argv) {
  if (argc < 4) { fprintf(stderr, "usage: chase LEVEL HOMER ROADS [--gens N --pop N --rounds N --seed S --out DIR --region X Z R --plant-corner X Z R] | --replay FILE\n"); return 2; }
  if (bwData(argv[1], argv[2], 0)) { fprintf(stderr, "chase: нет данных\n"); return 2; }
  navLoad(argv[3]);
  int gens = 20, pop = 16, rounds = 4, probe = 0; const char *out = 0, *replay = 0; float pf[6] = {0};
  for (int i = 4; i < argc; i++) {
    if (!strcmp(argv[i], "--gens") && i + 1 < argc) gens = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--pop") && i + 1 < argc) pop = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--rounds") && i + 1 < argc) rounds = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--seed") && i + 1 < argc) rs = (uint32_t)strtoul(argv[++i], 0, 10) | 1;
    else if (!strcmp(argv[i], "--out") && i + 1 < argc) out = argv[++i];
    else if (!strcmp(argv[i], "--replay") && i + 1 < argc) replay = argv[++i];
    else if (!strcmp(argv[i], "--region") && i + 3 < argc) { regX = (float)atof(argv[i + 1]); regZ = (float)atof(argv[i + 2]); regR = (float)atof(argv[i + 3]); i += 3; }
    else if (!strcmp(argv[i], "--catch-probe") && i + 6 < argc) { probe = 1; for (int k = 0; k < 6; k++) pf[k] = (float)atof(argv[i + 1 + k]); i += 6; }
    else if (!strcmp(argv[i], "--plant-corner") && i + 3 < argc) { plant = 1; plX = (float)atof(argv[i + 1]); plZ = (float)atof(argv[i + 2]); plR = (float)atof(argv[i + 3]); i += 3; }
  }
  bwNew(&W); bwSaveAlloc(&W, &S0); bwSave(&W, &S0);
  markFreeNodes();
  if (probe) {   // гейт Т1.1: оба стоят 3 с, поимка — то же правило, что в раунде
    bwLoad(&W, &S0); bwPlace(&W, pf[0], pf[1], pf[2], 0.f); carInit(&cop, NULL, bwCol(), pf[3], pf[4], pf[5], 0.f);
    float nearT = 0, d = 0; int caught = 0;
    for (int f = 0; f < 180 && !caught; f++) {
      bwStep(&W, 0, 0.f, 0.f); GamePad pad = {0, 0, 0, 0}; CarInput in; gameCarInput(&W.G, &pad, &in); carUpdate(&cop, bwCol(), &in, BW_DT); carHitCar(&W.car, &cop, bwCol());
      d = hypotf(cop.x - W.car.x, cop.z - W.car.z); if (catchNear(&W.car, &cop, d)) nearT += BW_DT; else nearT = 0; if (nearT >= 1.5f) caught = 1;
    }
    printf("проба поимки: беглец %.1f %.1f %.1f, погоня %.1f %.1f %.1f, по плоскости %.1f м, перепад %.1f м — %s\n", W.car.x, W.car.y, W.car.z, cop.x, cop.y, cop.z, d,
           fabsf(W.car.y - cop.y), caught ? "ПОЙМАН" : "не пойман");
    return 0;
  }
  if (replay) {
    Fug F; Cop C; Starts s; Result want, got;
    if (readRound(replay, &F, &C, &s, &want)) { fprintf(stderr, "chase: не читается %s\n", replay); return 2; }
    got = playRound(&F, &C, &s, getenv("CHASE_TRACE") ? atoi(getenv("CHASE_TRACE")) : 0);
    int same = got.caught == want.caught && fabsf(got.survive - want.survive) < 1e-4f && got.corner == want.corner && got.stuck == want.stuck &&
               fabsf(got.kx - want.kx) < 1e-3f && fabsf(got.kz - want.kz) < 1e-3f && fabsf(got.sx - want.sx) < 1e-3f && fabsf(got.sz - want.sz) < 1e-3f;
    printf("повтор: %s за %.2f с; угол %d (%.1f %.1f), погоня застряла %d (%.1f %.1f) — %s\n", got.caught ? "пойман" : "не пойман", got.survive,
           got.corner, got.kx, got.kz, got.stuck, got.sx, got.sz, same ? "ТОТ ЖЕ ИСХОД" : "РАЗОШЛОСЬ");
    if (got.corner && getenv("CHASE_WHY")) { cornerWhy(&W.car, &cop); printf("  след беглеца %d:", ntrail); for (int i = 0; i < ntrail; i++) printf(" (%.1f %.1f)", trail[i].x, trail[i].z); printf("\n"); }
    if (got.corner && getenv("CHASE_CONFIRM")) printf("подтверждение угла: поймали %d раз (8 заходов с дорог + заход по следу беглеца)\n", confirmCorner(&C, got.kx, got.ky, got.kz, got.kh));
    return same ? 0 : 1;
  }
  Fug *F = malloc(sizeof(Fug) * (size_t)pop), *F2 = malloc(sizeof(Fug) * (size_t)pop); Cop *C = malloc(sizeof(Cop) * (size_t)pop), *C2 = malloc(sizeof(Cop) * (size_t)pop);
  for (int i = 0; i < pop; i++) { F[i] = fugNew(); C[i] = copNew(); }
  float *ff = malloc(sizeof(float) * (size_t)pop), *cf = malloc(sizeof(float) * (size_t)pop); int *cn = malloc(sizeof(int) * (size_t)pop);
  long roundsPlayed = 0, weak = 0;
  for (int g = 0; g < gens; g++) {
    memset(ff, 0, sizeof(float) * (size_t)pop); memset(cf, 0, sizeof(float) * (size_t)pop); memset(cn, 0, sizeof(int) * (size_t)pop);
    float sum = 0, best = 0; int caught = 0, games = 0;
    for (int i = 0; i < pop; i++) for (int k = 0; k < rounds; k++) {
      int j = (i * 5 + k * 3 + g) % pop; Starts s = makeStarts(&F[i]);
      Result r = playRound(&F[i], &C[j], &s, 0); roundsPlayed++;
      ff[i] += r.survive; cf[j] += ROUND_S - r.survive; cn[j]++;
      sum += r.survive; games++; caught += r.caught; if (r.survive > best) best = r.survive;
      if (r.corner) { if (confirmCorner(&C[j], r.kx, r.ky, r.kz, r.kh) == 0) addClu(0, r.kx, r.ky, r.kz, out, &F[i], &C[j], &s, &r); else weak++; }
      if (r.stuck) addClu(1, r.sx, r.sy, r.sz, out, &F[i], &C[j], &s, &r);
    }
    printf("G\t%d\t%.2f\t%.2f\t%.3f\n", g, sum / games, best, caught / (float)games); fflush(stdout);
    // отбор: лучшие 4 каждой стороны остаются, остальные — потомки (скрещивание двух лучших + мутация)
    Rank rf[256], rc[256]; int P = pop < 256 ? pop : 256;
    for (int i = 0; i < P; i++) { rf[i] = (Rank){ff[i] / rounds, i}; rc[i] = (Rank){cn[i] ? cf[i] / cn[i] : 0, i}; }
    qsort(rf, (size_t)P, sizeof(Rank), cmpRank); qsort(rc, (size_t)P, sizeof(Rank), cmpRank);
    int E = P < 4 ? P : 4;
    for (int i = 0; i < P; i++) {
      if (i < E) { F2[i] = F[rf[i].i]; C2[i] = C[rc[i].i]; continue; }
      const Fug *a = &F[rf[xr() % E].i], *b = &F[rf[xr() % E].i]; Fug f = *a;
      for (int k = 0; k < NPAR; k++) if (xr() & 1) f.par[k] = b->par[k];
      mutPar(f.par); if (fr() < .3f) f.alarm = clampf(f.alarm + gauss() * 8.f, 4.f, 80.f); if (fr() < .3f) f.closing = clampf(f.closing + gauss(), 0.f, 8.f);
      if (fr() < .5f) { int n = randNodeNear(node[f.dest].x, node[f.dest].z, 0.f, 40.f); if (inRegion(n)) f.dest = n; }
      if (fr() < .15f) f.dest = fugNew().dest;
      F2[i] = f;
      const Cop *ca = &C[rc[xr() % E].i], *cb = &C[rc[xr() % E].i]; Cop c = *ca;
      for (int k = 0; k < NPAR; k++) if (xr() & 1) c.par[k] = cb->par[k];
      mutPar(c.par); if (fr() < .3f) c.lead = clampf(c.lead + gauss() * .3f, 0.f, 2.f); if (fr() < .3f) c.direct = clampf(c.direct + gauss() * 5.f, 5.f, 60.f);
      if (fr() < .3f) c.backT = clampf(c.backT + gauss() * .3f, .3f, 3.f);
      C2[i] = c;
    }
    Fug *tf = F; F = F2; F2 = tf; Cop *tc = C; C = C2; C2 = tc;
  }
  for (int i = 0; i < nclu; i++) printf("X\t%s\t%.1f\t%.1f\t%.1f\t%d\t%s\t%d\t%s\n", kindName[clu[i].kind], clu[i].x, clu[i].y, clu[i].z, clu[i].n, clu[i].file, clu[i].layer, clu[i].obj);
  printf("S\t%ld\t%.1f\t%ld\n", roundsPlayed, roundsPlayed * ROUND_S / 60.f, weak);   // раундов, минут игры, «углов» опровергнуто подтверждением
  return 0;
}
