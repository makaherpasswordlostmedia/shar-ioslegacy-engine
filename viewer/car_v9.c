// Машина с честной коллизией — см. car.h.
// Подшаг (p.sub, по умолчанию 1/120 с — при 30 м/с это 25 см, тоньше кузова в 9 раз):
//   1) руль/газ/тормоз как в main.c v8 (+ доля уклона), боковое скольжение гасится сцеплением;
//   2) сдвиг по xz, выталкивание кузова colPushCar (прямоугольник + слой над полом), со скорости снимается
//      составляющая в стену (скольжение вдоль), жёсткий удар — отскок и потеря скорости; не вытолкнулось или
//      центр кузова пересёк забор — подшаг отменяется целиком (машина остаётся там, где была чистой);
//   3) опора: 4 колеса + днище (центр) лучами colGround; плоскость по колёсам (3 колеса — «треножник»; меньше —
//      держит днище или диагональ, иначе переваливается и падает); в воздухе — гравитация 22, посадка на плоскость;
//      край мира (под началом машины нет ничего вообще) — как стена;
//   4) страховка: кольцо надёжных мест (раз в 0.25 с, 4 колеса на земле, без касаний); возврат, если нет земли
//      под машиной 1.5 с, если застряла в геометрии 0.5 с, если сидит на днище без колёс 2 с, если в воздухе 8 с,
//      если приземлилась ниже точки отрыва больше fallReset (через 1 с), если y < -150.
#include "car.h"
#include <math.h>
#include <string.h>
#ifdef COL_DEBUG
#include <stdio.h>
extern int colDebug;
#endif

#define SAFE_EVERY 0.25f
#define PEN_REVERT 0.02f     // осталось больше 2 см после выталкивания — подшаг отменяем
#define EMBED_PEN 0.3f

static float clampf(float v, float a, float b) { return v < a ? a : v > b ? b : v; }

void carDefaults(CarParams *p) {
  p->halfW = 1.10f; p->halfL = 2.675f; p->bodyOfs = -0.32f;
  p->wheelX = 0.91f; p->wheelF = 1.47f; p->wheelR = 1.82f;
  p->bandLo = 0.35f; p->bandHi = 1.6f; p->step = 0.35f;
  p->accel = 14.f; p->brake = 30.f; p->revAccel = 8.f; p->maxFwd = 30.f; p->maxRev = 9.f; p->drag = 1.2f;
  p->steerRate = 2.1f; p->steerResp = 8.f; p->steerFull = 6.f; p->steerFade = 25.f;
  p->gravity = 22.f; p->slopeK = 0.35f; p->grip = 6.f;
  p->bounce = 0.2f; p->hardHit = 4.f;
  p->snapDown = 0.06f; p->fallReset = 20.f; p->sub = 1.f / 120.f;
}

void carBox(const Car *c, CarBox *b) {
  float fx = sinf(c->h), fz = cosf(c->h);
  b->x = c->x + fx * c->p.bodyOfs; b->z = c->z + fz * c->p.bodyOfs;
  b->fx = fx; b->fz = fz; b->hw = c->p.halfW; b->hl = c->p.halfL;
  b->y = c->y + c->gx * (b->x - c->x) + c->gz * (b->z - c->z); b->gx = c->gx; b->gz = c->gz;
  b->lo = c->p.bandLo; b->hi = c->p.bandHi;
  b->fsupOn = 0; b->fsup = 0.f;   // правка 339 (col.h): старая машина v9 — без опорного верха внутренних заборов, как было
}

// опора под машиной. reachUp — насколько выше привычного может оказаться земля (уклон * пройденное),
// reachDown — насколько ниже (падение за подшаг). Возврат: сколько колёс нашли опору (+ днище в *belly);
// *yT — высота начала машины на опоре, *sf/*sr — уклон вперёд/вправо; *anyBelow — хоть что-то есть внизу вообще.
static int support(const Car *c, const ColWorld *w, float fx, float fz, float reachUp, float reachDown, float dt,
                   float *yT, float *sf, float *sr, int *belly, int *anyBelow, float *gcAny) {
  const CarParams *P = &c->p;
  float rx = -fz, rz = fx, g[4], yw[4]; int fnd[4], n = 0, any = 0;
  for (int k = 0; k < 4; k++) {
    float lon = k < 2 ? P->wheelF : -P->wheelR, lat = (k & 1) ? P->wheelX : -P->wheelX;
    float ox = fx * lon + rx * lat, oz = fz * lon + rz * lat, gg;
    yw[k] = c->y + c->gx * ox + c->gz * oz;
    fnd[k] = 0;
    if (colGround(w, c->x + ox, c->z + oz, yw[k] + P->step + reachUp, -1e6f, &gg, 0)) {
      any = 1;
      if (gg > yw[k] - 0.5f - reachDown) { g[k] = gg; fnd[k] = 1; n++; }
    }
  }
  float gc; int bl = 0;
  *gcAny = -3.0e38f;
  if (colGround(w, c->x, c->z, c->y + P->step + reachUp, -1e6f, &gc, 0)) { any = 1; bl = gc > c->y - 0.5f - reachDown; *gcAny = gc; }
  *anyBelow = any; *belly = 0;
  // устойчиво: 3-4 колеса, днище на опоре или два колеса по диагонали (линия опоры проходит под центром);
  // иначе (одно колесо, одна ось, один борт над пустотой) машина переваливается — падает
  if (!(n >= 3 || bl || (n == 2 && ((fnd[0] && fnd[3]) || (fnd[1] && fnd[2]))))) return 0;
  if (n == 3) {   // треножник: недостающее колесо — по плоскости трёх (FL + RR = FR + RL)
    if (!fnd[0]) g[0] = g[1] + g[2] - g[3];
    else if (!fnd[1]) g[1] = g[0] + g[3] - g[2];
    else if (!fnd[2]) g[2] = g[0] + g[3] - g[1];
    else g[3] = g[1] + g[2] - g[0];
  } else if (n < 3) {
    for (int k = 0; k < 4; k++) if (!fnd[k]) g[k] = yw[k];   // без опоры — как стояло (не проседает)
  }
  float wb = P->wheelF + P->wheelR;
  float hF = (g[0] + g[1]) * .5f, hR = (g[2] + g[3]) * .5f, hL = (g[0] + g[2]) * .5f, hRt = (g[1] + g[3]) * .5f;
  float s1 = clampf((hF - hR) / wb, -1.2f, 1.2f), s2 = clampf((hRt - hL) / (2.f * P->wheelX), -1.2f, 1.2f);
  float y = (hF * P->wheelR + hR * P->wheelF) / wb;
  if (!n) { s1 = c->gx * fx + c->gz * fz; s2 = c->gx * rx + c->gz * rz; y = gc; *belly = 1; }
  else if (bl && gc > y) { y = gc; *belly = 1; }   // днище лежит на краю — ниже не опускаемся
  *yT = y; *sf = s1; *sr = s2;
  return n ? n : 1;
}

static void pushSafe(Car *c) {
  c->safeHead = (c->safeHead + 1) % CAR_SAFE;
  c->safe[c->safeHead].x = c->x; c->safe[c->safeHead].y = c->y; c->safe[c->safeHead].z = c->z;
  c->safe[c->safeHead].h = c->h; c->safe[c->safeHead].t = c->t;
  if (c->nsafe < CAR_SAFE) c->nsafe++;
}

static void settle(Car *c, const ColWorld *w) {
  float fx = sinf(c->h), fz = cosf(c->h), rx = -fz, rz = fx;
  for (int it = 0; it < 4; it++) {
    CarBox b; carBox(c, &b); float mx, mz, nx, nz, g;
    colPushCar(w, &b, &mx, &mz, &nx, &nz);
    // вытолкнуло за край мира / через забор — не двигаем (лучше чуть в стене, чем в пустоте)
    if (colGround(w, c->x + mx, c->z + mz, c->y + 2.f, -1e6f, &g, 0) && !colCrossFence(w, c->x, c->z, c->x + mx, c->z + mz, 0, 0) &&
        !colCrossFence(w, b.x - mx, b.z - mz, b.x, b.z, 0, 0)) { c->x += mx; c->z += mz; }
    float yT, sf, sr, gca; int belly, any;
    int n = support(c, w, fx, fz, 0.5f, 0.5f, 0.f, &yT, &sf, &sr, &belly, &any, &gca);
    if (n) { c->y = yT; c->gx = fx * sf + rx * sr; c->gz = fz * sf + rz * sr; c->grounded = 1; c->wheels = belly && n == 1 ? 0 : n; }
  }
}

void carPlace(Car *c, const ColWorld *w, float x, float y, float z, float h) {
  c->x = x; c->z = z; c->h = h; c->v = c->vl = c->vy = 0; c->gx = c->gz = 0; c->steer = 0;
  float g;
  c->y = colGround(w, x, z, y + 2.f, -1e6f, &g, 0) ? g : y;
  c->grounded = 0; settle(c, w);
  c->pitch = atanf(c->gx * sinf(h) + c->gz * cosf(h)); c->roll = atanf(-c->gx * cosf(h) + c->gz * sinf(h));
  c->ry = c->y; c->rvy = 0; c->rpitch = c->pitch; c->rroll = c->roll;
  c->airT = c->noGroundT = c->embedT = c->bellyT = 0; c->fallPending = 0; c->fallPendT = 0; c->fallTop = c->y; c->fallT0 = c->t;
  c->acc = 0; c->contacts = 0; c->hitSpeed = 0; c->pen = 0;
}

void carInit(Car *c, const CarParams *p, const ColWorld *w, float x, float y, float z, float h) {
  memset(c, 0, sizeof *c);
  if (p) c->p = *p; else carDefaults(&c->p);
  carPlace(c, w, x, y, z, h);
  c->homeX = c->x; c->homeY = c->y; c->homeZ = c->z; c->homeH = c->h;
  c->safeT = -1e9f;
}

// вернуть на надёжное место не новее, чем before (сек. времени машины); более новые места забываются
static void recover(Car *c, const ColWorld *w, float before) {
  int pick = -1, age = 0;
  for (int i = 0; i < c->nsafe; i++) {
    int k = (c->safeHead - i + CAR_SAFE) % CAR_SAFE;
    if (c->safe[k].t <= before) { pick = k; age = i; break; }
  }
  if (pick < 0 && c->nsafe) { age = c->nsafe - 1; pick = (c->safeHead - age + CAR_SAFE) % CAR_SAFE; }
  float x = c->homeX, y = c->homeY, z = c->homeZ, h = c->homeH;
  if (pick >= 0) {
    x = c->safe[pick].x; y = c->safe[pick].y; z = c->safe[pick].z; h = c->safe[pick].h;
    c->nsafe -= age + 1; c->safeHead = (pick - 1 + CAR_SAFE) % CAR_SAFE;   // и само место — чтобы не вернуться туда же снова
  }
  float t = c->t; int rec = c->recoveries, rev = c->reverts;
  carPlace(c, w, x, y, z, h);
  c->t = t; c->recoveries = rec + 1; c->reverts = rev; c->safeT = t;
}

static void substep(Car *c, const ColWorld *w, const CarInput *in, float dt) {
  const CarParams *P = &c->p;
  c->t += dt;
  // 1) управление
  float st = clampf(in->steer, -1.f, 1.f), thr = clampf(in->throttle, 0.f, 1.f), brk = clampf(in->brake, 0.f, 1.f);
  c->steer += (st - c->steer) * fminf(1.f, dt * P->steerResp);
  float h0 = c->h, x0 = c->x, z0 = c->z, yS = c->y;
  if (c->grounded) {
    float sf = c->gx * sinf(c->h) + c->gz * cosf(c->h), sinP = sf / sqrtf(1.f + sf * sf);
    float slopeA = P->gravity * P->slopeK * sinP;
    if (thr > 0.f) c->v += (c->v < 0.f ? P->brake : P->accel) * thr * dt;
    else if (brk > 0.f) c->v -= (c->v > 0.f ? P->brake : P->revAccel) * brk * dt;
    else {
      c->v -= c->v * P->drag * dt;
      if (fabsf(c->v) < 0.5f && fabsf(slopeA) < 4.f) { c->v = 0.f; slopeA = 0.f; }   // стоит — не катится
    }
    c->v -= slopeA * dt;
    c->v = clampf(c->v, -P->maxRev, P->maxFwd);
    float av = fabsf(c->v);
    float turn = c->steer * P->steerRate * fminf(1.f, av / P->steerFull) / (1.f + av / P->steerFade);
    c->h -= turn * dt * (c->v >= 0.f ? 1.f : -1.f);
    c->vl -= c->vl * fminf(1.f, P->grip * dt);
  }
  float fx = sinf(c->h), fz = cosf(c->h), rx = -fz, rz = fx;
  float Vx = fx * c->v + rx * c->vl, Vz = fz * c->v + rz * c->vl;
  // 2) сдвиг и стены. На земле машина едет по плоскости пола: высота меняется вместе со сдвигом (и с толчком от
  // стены) — тогда слой кузова для colPushCar и для проверок после него один и тот же (иначе на склоне расходится)
  float pgx = c->grounded ? c->gx : 0.f, pgz = c->grounded ? c->gz : 0.f;
  c->x += Vx * dt; c->z += Vz * dt; c->y += pgx * Vx * dt + pgz * Vz * dt;
  CarBox b; carBox(c, &b);
  float bx0 = x0 + sinf(h0) * P->bodyOfs, bz0 = z0 + cosf(h0) * P->bodyOfs;
  float mx, mz, nx, nz;
  colPushCar(w, &b, &mx, &mz, &nx, &nz);
  // не вытолкнулось: осталось больше 2 см и больше, чем было в начале подшага (зажатая в щели машина может
  // выехать туда, где не теснее; вдавиться глубже — нет)
  float pen0 = c->pen;
  int revert = (b.maxDepth > fmaxf(PEN_REVERT, pen0)) | (b.behindFence ? 2 : 0);
  if (!revert && colCrossFence(w, bx0, bz0, b.x, b.z, &nx, &nz)) revert = 4;
  if (!revert && colCrossFence(w, x0, z0, b.x - fx * P->bodyOfs, b.z - fz * P->bodyOfs, &nx, &nz)) revert = 8;
  if (revert == 1 && c->h != h0) {
    // тесно из-за поворота кузова (в узкой щели руль довернул углы в стены) — пробуем тот же сдвиг без поворота
    c->h = h0; fx = sinf(h0); fz = cosf(h0); rx = -fz; rz = fx;
    carBox(c, &b); colPushCar(w, &b, &mx, &mz, &nx, &nz);
    revert = (b.maxDepth > fmaxf(PEN_REVERT, pen0)) | (b.behindFence ? 2 : 0);
    if (!revert && colCrossFence(w, bx0, bz0, b.x, b.z, &nx, &nz)) revert = 4;
    if (!revert && colCrossFence(w, x0, z0, b.x - fx * P->bodyOfs, b.z - fz * P->bodyOfs, &nx, &nz)) revert = 8;
  }
#ifdef COL_DEBUG
  if (colDebug) printf("  substep: move %.4f %.4f -> maxDepth %.4f pen0 %.4f behind %d revert %d (h %.4f -> %.4f)\n",
                       c->x - x0, c->z - z0, b.maxDepth, pen0, b.behindFence, revert, h0, c->h);
#endif
  if (revert) {
    // вытолкнуть не вышло (зажали с двух сторон / за забором) — подшаг отменяем, скорость гасим
    c->x = x0; c->z = z0; c->h = h0; c->y = yS; c->reverts++; c->revWhy = revert;
    fx = sinf(h0); fz = cosf(h0); rx = -fz; rz = fx;
    Vx *= -0.1f; Vz *= -0.1f;
    CarBox pb; carBox(c, &pb); colProbeCar(w, &pb);
    c->pen = pb.maxDepth;
    c->contacts = 0;
    for (int k = 0; k < pb.n && c->contacts < 4; k++) { c->cnx[c->contacts] = pb.nx[k]; c->cnz[c->contacts] = pb.nz[k]; c->ctype[c->contacts] = pb.type[k]; c->contacts++; }
  } else {
    c->x += mx; c->z += mz; c->y += pgx * mx + pgz * mz; c->pen = b.maxDepth;
    c->contacts = 0;
    int touched = 0;
    for (int k = 0; k < b.n; k++) {
      float cx = b.nx[k], cz = b.nz[k], vn = Vx * cx + Vz * cz;
      if (c->contacts < 4) { c->cnx[c->contacts] = cx; c->cnz[c->contacts] = cz; c->ctype[c->contacts] = b.type[k]; c->contacts++; }
      touched = 1;
      if (vn >= 0.f) continue;
      float imp = -vn;
      Vx -= vn * cx; Vz -= vn * cz;                            // скольжение вдоль стены
      if (imp > P->hardHit) {
        float keep = 1.f - fminf(0.5f, 0.015f * imp);         // жёсткий удар: теряем скорость и чуть отскакиваем
        Vx = Vx * keep + cx * imp * P->bounce; Vz = Vz * keep + cz * imp * P->bounce;
      }
      if (imp > c->hitSpeed) c->hitSpeed = imp;
    }
    if (touched) { float k = 1.f - fminf(1.f, 0.8f * dt); Vx *= k; Vz *= k; }   // трение о стену
  }
  // под началом машины (в новом положении) должна быть проходимая поверхность не выше, чем можно въехать (top).
  // Нет её, но на 0.3/1/2/3 м дальше по ходу земля есть не выше (top + 0.3) — это щель/дыра в сетке или
  // полоска под отвесной стенкой обрыва: едем. Иначе: чуть выше (до 6 м) есть поверхность — въезжаем под землю
  // сбоку (обрыв без стенки в сетке, низкий навес) — стена; нет ничего вообще — край мира, тоже стена.
  if (!revert && (c->x != x0 || c->z != z0)) {
    float g_, mdx = c->x - x0, mdz = c->z - z0, ml = sqrtf(mdx * mdx + mdz * mdz);
    float top = c->y + P->step + 1.8f * ml;
    int why = 0;
    if (!colGround(w, c->x, c->z, top, -1e6f, &g_, 0)) {
      static const float look[4] = {0.3f, 1.f, 2.f, 3.f};
      why = 16;
      for (int k = 0; k < 4 && why; k++)
        if (colGround(w, c->x + mdx / ml * look[k], c->z + mdz / ml * look[k], top + 0.3f, -1e6f, &g_, 0)) why = 0;
      if (why && colGround(w, c->x, c->z, c->y + 6.f, top, &g_, 0)) why = 32;   // выше 6 м — крыша/мост, не склон
    }
    if (why) {
      c->x = x0; c->z = z0; c->h = h0; c->y = yS; c->reverts++; c->revWhy = why;
      fx = sinf(h0); fz = cosf(h0); rx = -fz; rz = fx;
      Vx *= -0.1f; Vz *= -0.1f;
    }
  }
  c->v = Vx * fx + Vz * fz; c->vl = Vx * rx + Vz * rz;
  // 3) опора
  float dxm = c->x - x0, dzm = c->z - z0, moved = sqrtf(dxm * dxm + dzm * dzm);
  float reachUp = 1.8f * moved + (c->vy > 0.f ? c->vy * dt : 0.f);
  float reachDown = c->vy < 0.f ? -c->vy * dt * 1.5f + P->gravity * dt * dt : P->gravity * dt * dt;
  float yT = 0, sf = 0, sr = 0, gcAny; int belly, any;
  int ns = support(c, w, fx, fz, reachUp, reachDown, dt, &yT, &sf, &sr, &belly, &any, &gcAny);
  // на земле высота уже сдвинута вдоль пола (шаг 2) — дальше только прибавка от гравитации
  float vy = c->vy - P->gravity * dt, yFree = c->grounded ? c->y - P->gravity * dt * dt : c->y + vy * dt;
  int was = c->grounded;
  float y0 = c->y, gx0 = c->gx, gz0 = c->gz;
  if (ns && (yFree <= yT + 0.002f || (was && yFree - yT <= P->snapDown))) {
    c->y = yT; c->gx = fx * sf + rx * sr; c->gz = fz * sf + rz * sr;
    c->vy = Vx * c->gx + Vz * c->gz;                           // по земле: вертикальная скорость — вдоль склона
    c->grounded = 1; c->wheels = belly && ns == 1 ? 0 : ns;
  } else if (yFree <= gcAny) {
    // опоры колёсами нет (переваливается через край), но под началом машины земля — сквозь неё не падаем
    c->y = gcAny; c->vy = 0.f; c->grounded = 1; c->wheels = 0;
  } else {
    c->y = yFree; c->vy = vy; c->grounded = 0; c->wheels = 0;
    float k = 1.f - fminf(1.f, 3.f * dt);                      // в полёте кузов плавно выравнивается
    c->gx *= k; c->gz *= k;
  }
  // сдвиг по высоте (полёт, ступенька, наклон) не должен вгонять кузов в препятствие: падая, кузов ложится на верх
  // ящика / край стены (не выталкивается вбок на метры), взлетая — упирается в навес. Ищем ближайшую высоту, где не
  // глубже, чем было после сдвига по xz (d0). Итог — c->pen, с ним сравнивается следующий подшаг.
  {
    // мелкое (до 2 см, как у сдвига по xz) оставляем — следующий подшаг вытолкнет вбок как обычный контакт со стеной
    float d0 = c->pen, ok = fmaxf(d0, PEN_REVERT);
    CarBox vb; carBox(c, &vb); colProbeCar(w, &vb);
    float dN = vb.maxDepth;
    if (dN > ok && (c->gx != gx0 || c->gz != gz0)) {          // сначала — новая высота со старым наклоном
      float gxN = c->gx, gzN = c->gz;
      c->gx = gx0; c->gz = gz0; carBox(c, &vb); colProbeCar(w, &vb);
      if (vb.maxDepth <= ok) dN = vb.maxDepth; else { c->gx = gxN; c->gz = gzN; }
    }
    if (dN > ok) {
      float yN = c->y, gxN = gx0, gzN = gz0;                   // дальше — со старым наклоном
      float lo = y0, hi = yN;                                  // lo — как было, hi — задевает
      for (int it = 0; it < 6; it++) {
        float m = (lo + hi) * .5f; c->y = m; c->gx = gxN; c->gz = gzN; carBox(c, &vb); colProbeCar(w, &vb);
        if (vb.maxDepth <= ok) lo = m; else hi = m;
      }
      c->y = lo; c->gx = gxN; c->gz = gzN;
      if (yN < y0) { c->vy = 0.f; c->grounded = 1; }           // лёг кузовом на препятствие: сцепление есть
      else if (c->vy > 0.f) c->vy = 0.f;                       // удар крышей
      carBox(c, &vb); colProbeCar(w, &vb); dN = vb.maxDepth;
    }
#ifdef COL_DEBUG
    if (colDebug) printf("  vertical: y %.4f -> %.4f g (%.3f %.3f) -> (%.3f %.3f) d0 %.4f dN %.4f grounded %d wheels %d\n", y0, c->y, gx0, gz0, c->gx, c->gz, d0, dN, c->grounded, c->wheels);
#endif
    c->pen = dN;
  }
  c->pitch = atanf(c->gx * fx + c->gz * fz); c->roll = atanf(c->gx * rx + c->gz * rz);
  // 4) страховка
  if (!c->grounded) {
    if (was) { c->fallTop = c->y; c->fallT0 = c->t; }   // высота отрыва
    c->airT += dt;
  } else {
    if (!was && c->fallTop - c->y > P->fallReset && !c->fallPending) { c->fallPending = 1; c->fallPendT = 0; }
    c->airT = 0;
  }
  c->noGroundT = any ? 0.f : c->noGroundT + dt;
  c->bellyT = c->grounded && c->wheels == 0 ? c->bellyT + dt : 0.f;   // сел на днище без колёс — не выехать
  c->embedT = c->pen > EMBED_PEN ? c->embedT + dt : 0.f;
  if (c->fallPending) c->fallPendT += dt;
  if (c->y < -150.f || c->noGroundT > 1.5f || c->embedT > 0.5f || c->airT > 8.f || c->bellyT > 2.f) { recover(c, w, c->t - 1.f); return; }
  if (c->fallPending && c->fallPendT > 1.f) { recover(c, w, c->fallT0 - 0.5f); return; }
  if (c->grounded && c->wheels == 4 && !c->fallPending && c->pen < 0.01f && c->contacts == 0 && c->t - c->safeT >= SAFE_EVERY) {
    pushSafe(c); c->safeT = c->t;
  }
}

void carUpdate(Car *c, const ColWorld *w, const CarInput *in, float dt) {
  if (dt > 0.1f) dt = 0.1f;
  if (dt < 0.f) dt = 0.f;
  c->acc += dt; c->hitSpeed = 0;
  int n = 0;
  while (c->acc >= c->p.sub * 0.999f && n < 16) { substep(c, w, in, c->p.sub); c->acc -= c->p.sub; n++; }
  if (c->acc < 0.f) c->acc = 0.f;
  // сглаживание для отрисовки: высота — пружина с критическим затуханием (ступеньки и посадки), наклон — плавно
  float off = c->ry - c->y, om = 18.f;
  c->rvy += (-om * om * off - 2.f * om * c->rvy) * dt;
  off += c->rvy * dt;
  if (off > 0.35f) { off = 0.35f; if (c->rvy > 0) c->rvy = 0; }
  if (off < -0.35f) { off = -0.35f; if (c->rvy < 0) c->rvy = 0; }
  c->ry = c->y + off;
  float k = fminf(1.f, dt * 12.f);
  c->rpitch += (c->pitch - c->rpitch) * k; c->rroll += (c->roll - c->rroll) * k;
}

void carPieceMatrix(const Car *c, float lift, float ox, float oy, float oz, float sc, float m[16]) {
  // оси машины в мире: F — вперёд (по наклону), U — вверх, R = F x U — вправо; модель: X = R, Y = U, Z = -F
  float fx = sinf(c->h), fz = cosf(c->h), rx = -fz, rz = fx;
  float tp = tanf(c->rpitch), tr = tanf(c->rroll);
  float gx = fx * tp + rx * tr, gz = fz * tp + rz * tr;       // градиент пола из сглаженных наклонов
  float Ux = -gx, Uy = 1.f, Uz = -gz, l = 1.f / sqrtf(Ux * Ux + Uy * Uy + Uz * Uz); Ux *= l; Uy *= l; Uz *= l;
  float Fx = fx, Fy = tp, Fz = fz;
  float d = Fx * Ux + Fy * Uy + Fz * Uz; Fx -= d * Ux; Fy -= d * Uy; Fz -= d * Uz;
  l = 1.f / sqrtf(Fx * Fx + Fy * Fy + Fz * Fz); Fx *= l; Fy *= l; Fz *= l;
  float Rx = Fy * Uz - Fz * Uy, Ry = Fz * Ux - Fx * Uz, Rz = Fx * Uy - Fy * Ux;
  float Tx = c->x + Ux * lift, Ty = c->ry + Uy * lift, Tz = c->z + Uz * lift;
  m[0] = Rx * sc; m[1] = Ry * sc; m[2] = Rz * sc; m[3] = 0;
  m[4] = Ux * sc; m[5] = Uy * sc; m[6] = Uz * sc; m[7] = 0;
  m[8] = -Fx * sc; m[9] = -Fy * sc; m[10] = -Fz * sc; m[11] = 0;
  m[12] = Tx + Rx * ox + Ux * oy - Fx * oz; m[13] = Ty + Ry * ox + Uy * oy - Fy * oz; m[14] = Tz + Rz * ox + Uz * oy - Fz * oz; m[15] = 1;
}
