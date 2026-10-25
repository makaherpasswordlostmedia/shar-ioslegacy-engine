// Рой физических ботов с детекторами находок: только процессор Мака, без окон, звука и эмулятора.
// Берёт настоящие viewer/car.c, col.c, props.c, stateprops.c (текущие правила порта) и уровень level.shr;
// боты, старт, дороги и сценарии — те же, что в sandbox.c (подключён как есть, свой main у него выключен).
//   bots_swarm --level LEVEL.shr --lvl N [--roads roads-lN.bin] --out НАХОДКИ.tsv [--cars 128] [--seed 1]
//              [--seconds 600] [--until EPOCH] [--cap 6] [--inject through|stuck|launch|carunder]
// Находки — TSV autoexplore: уровень x y z тип вес seed кадр описание. Повтор: тот же --seed и --cars, --seconds до кадра/60.
// Типы: through (центр кузова прошёл сквозь поверхность за один кадр), stuck (12 с почти на месте под газом),
//   launch (подброс без зоны прыжка), carunder (кузов в кузове другой машины), carover (машина едет на крыше машины),
//   roof (села на крышу вне дороги), ramp (прыжок с трамплина или края без зоны, ≥ 1 с), recovery (игра вернула машину
//   на надёжное место), embed (глубина проникновения > 0,15 м 12 кадров подряд).
#define SANDBOX_NO_MAIN
#include <stdarg.h>
#include "sandbox.c"

#define LOOK 60                              // кадров «до события», по которым выбираем ли вес
typedef struct {
  float px, py, pz; int epoch, rec, rev, ok;
  float ax, az, sx, sz; int aTick;           // якорь «на месте», точка старта эпизода
  int stuckRep;
  int air, takeoffTick, takeoffZone, takeoffHit; float takeoffV, takeoffY, maxY, takeoffX, takeoffZ;
  int flightRep, groundTicks, roofRep;
  int underWith, underTicks, overTicks, overRep, lastHitTick;
  int pend, pTick, pFace, pSeg; char pPrim[200]; float pHit[3], pDir[2], pStep, pFrac, pV, pGround;   // проверка «проезда»: дошла ли машина дальше места пересечения
  int cool[16]; int pPhantom, pSegIx, pReturn, t0, esc0;
} Det;
static Det det[FLEET];
#define HIST 180                           // кадров истории центра кузова (3 с): откуда машина пришла к забору
static float hist[FLEET][HIST][2];
enum { K_THROUGH, K_STUCK, K_LAUNCH, K_UNDER, K_OVER, K_ROOF, K_RAMP, K_REC, K_EMBED, K_BACK, K_PHANTOM, K_DEATH, K_STUCKBOT, K_BACKRET, K_ESCAPE, K_N };
static const char *KN[K_N] = {"through", "stuck", "launch", "carunder", "carover", "roof", "ramp", "recovery", "embed", "backfence", "phantom", "death", "stuckbot", "backreturn", "escape"};
static unsigned long found[K_N], written[K_N];
#define CELLS 65536
static unsigned char cellN[K_N][CELLS];
static FILE *tsv, *poseF; static int lvlNo = 1, cap = 6, injectKind = -1, traceCar = -1, traceT0 = 0, traceT1 = 0, deathOn = 1, phantomOn = 1, drillOn = 1, backRetOn = 1, escOn = 1;
static const char *MODELS[4] = {"famil_v", "sportsa", "pickupa", "schoolbu"};

// что за примитив сидит в точке (маленькая коробка в слое стен у места пересечения): тип, индекс, для забора — нормаль и высоты
static void primAt(const Car *c, float x, float z, const float dir[2], char *out, size_t n, int *fromFace, int *isSeg, int *isPhantom, int *segIx) {
  *fromFace = 0; *isSeg = 0; *isPhantom = 0; *segIx = -1;
  CarBox b; memset(&b, 0, sizeof b);
  b.x = x; b.z = z; b.fx = 0; b.fz = 1; b.hw = .7f; b.hl = .7f; b.y = c->y; b.lo = c->p.bandLo; b.hi = c->p.bandHi;
  int k = colProbeCar(&W, &b);
  if (k <= 0) { snprintf(out, n, "prim=none"); return; }
  static const char *TN[4] = {"tri", "box", "cyl", "seg"};
  int j = 0; for (int q = 1; q < b.n; q++) if (b.depth[q] > b.depth[j]) j = q;
  unsigned t = b.type[j] < 4 ? b.type[j] : 0, ix = b.index[j];
  if (t == COL_SEG && ix < W.nseg) {
    const ColSeg *s = &W.seg[ix]; *isSeg = 1; *segIx = (int)ix;
    float dn = dir[0] * s->n[0] + dir[1] * s->n[1]; *fromFace = dn < -.05f;   // ехали против нормали забора: с лицевой стороны внутрь
    snprintf(out, n, "prim=seg#%u n=(%.2f,%.2f) y=%.6g..%.6g len=%.1f%s dotN=%.2f", ix, s->n[0], s->n[1], s->y0, s->y1, hypotf(s->b[0] - s->a[0], s->b[1] - s->a[1]), s->y0 <= COL_SEG_FOL_Y0 + 1.f ? " foliage" : "", dn);
  } else if (t == COL_BOX && ix < W.nbox) {
    const ColBox *q = &W.box[ix]; *isPhantom = q->pad == 2.f;   // прозрачная стена (правка 475): ящик без рисунка, машину не держит по решению Роба 10.10
    snprintf(out, n, "prim=box#%u depth=%.2f n=(%.2f,%.2f) c=(%.1f,%.1f,%.1f) h=(%.1f,%.1f,%.1f) up=(%.2f,%.2f,%.2f)", ix, b.depth[j], b.nx[j], b.nz[j], q->c[0], q->c[1], q->c[2], q->h[0], q->h[1], q->h[2], q->ay[0], q->ay[1], q->ay[2]);
  } else {
    if (t == COL_CYL && ix < W.ncyl) *isPhantom = W.cyl[ix].pad[0] == 2.f;
    snprintf(out, n, "prim=%s#%u depth=%.2f n=(%.2f,%.2f)", TN[t], ix, b.depth[j], b.nx[j], b.nz[j]);
  }
}
static void report(int id, int kind, float x, float y, float z, float weight, const char *fmt, ...) {
  found[kind]++;
  unsigned h = (unsigned)((int)floorf(x / 8.f) * 73856093) ^ (unsigned)((int)floorf(z / 8.f) * 19349663) ^ (unsigned)((int)floorf(y / 6.f) * 83492791);
  unsigned char *n = &cellN[kind][h & (CELLS - 1)];
  if (*n >= cap) return;                     // место уже описано cap раз; в сводке счётчик found считает все
  (*n)++; written[kind]++;
  char d[400]; va_list ap; va_start(ap, fmt); vsnprintf(d, sizeof d, fmt, ap); va_end(ap);
  // повтор — в начале описания (cluster.py режет описание на 160 знаках): тот же --seed и --cars, --seconds до кадра
  fprintf(tsv, "%d\t%.2f\t%.2f\t%.2f\t%s\t%.2f\t%u\t%d\tcar=%d %s rep=--seed %u --cars %d --seconds %d | %s\n", lvlNo, x, y, z, KN[kind], weight,
          campaignSeed, tick, id, MODELS[id % 4], campaignSeed, fleetN, tick / 60 + 2, d);
  fflush(tsv);
}

static int coolOk(Det *d, int kind, int span) {      // не чаще раза за span кадров у одной машины
  if (tick - d->cool[kind] < span && d->cool[kind]) return 0;
  d->cool[kind] = tick; return 1;
}

// прямоугольник кузова в xz: центр, ось вперёд, полуразмеры
typedef struct { float x, z, fx, fz, hw, hl; } Rect;
static Rect rectOf(const Car *c) {
  float fx = sinf(c->h), fz = cosf(c->h);
  return (Rect){c->x + fx * c->p.bodyOfs, c->z + fz * c->p.bodyOfs, fx, fz, c->p.halfW, c->p.halfL};
}
static float satPen(const Rect *a, const Rect *b) {     // глубина проникновения прямоугольников (минимум по 4 осям), < 0 — не пересекаются
  float ax[4][2] = {{a->fx, a->fz}, {-a->fz, a->fx}, {b->fx, b->fz}, {-b->fz, b->fx}}, best = 1e9f;
  float dx = b->x - a->x, dz = b->z - a->z;
  for (int i = 0; i < 4; i++) {
    float ux = ax[i][0], uz = ax[i][1];
    float ra = fabsf(a->fx * ux + a->fz * uz) * a->hl + fabsf(-a->fz * ux + a->fx * uz) * a->hw;
    float rb = fabsf(b->fx * ux + b->fz * uz) * b->hl + fabsf(-b->fz * ux + b->fx * uz) * b->hw;
    float o = ra + rb - fabsf(dx * ux + dz * uz);
    if (o < best) best = o;
  }
  return best;
}


// набор манёвров игрока из позы «застряла»: 7 копий машины. 0–5: 6 с, вперёд/назад × прямо/влево/вправо. 6: 10 с газ вперёд 1,2 с / назад 1,2 с по кругу, руль прямо
// (так в игре срабатывает №738 «зажата ровно» — нужны оба направления и ≥ 3 с в круге 1,5 м; в одном направлении он молчит).
// Вышла = ушла от точки на 8 м, игра вернула (recoveries) или сама вывела (№738 wedgeEsc, перч perchEsc, тупик escapes32). Возвращает число манёвров; в *viaGame — выходов только силами игры.
static int escapeDrill(const Car *c0, int *viaGame) {
  int esc = 0; *viaGame = 0;
  for (int man = 0; man < 7; man++) {
    Car c = *c0; float sx = c.x, sz = c.z; int rc0 = c.recoveries, g0 = c.wedgeEsc + c.perchEsc + c.escapes32;
    int n = man == 6 ? 600 : 360;
    for (int t = 0; t < n; t++) {
      CarInput in = {0};
      if (man == 6) { if ((t / 72) % 2 == 0) in.throttle = 1; else in.brake = 1; }
      else { if (man < 3) in.throttle = 1; else in.brake = 1; in.steer = man % 3 == 1 ? -1.f : man % 3 == 2 ? 1.f : 0.f; }
      carUpdate(&c, &W, &in, 1.f / 60);
      if (!sane(&c)) break;
      if (man == 6 && getenv("DRILLDBG") && t % 30 == 0) fprintf(stderr, "  t=%d d=%.2f wedgeT=%.2f tried=%d gr=%d wh=%d v=%.2f dh=%.2f esc=%d pitch=%.2f y=%.2f\n", t, hypotf(c.x - sx, c.z - sz), c.wedgeT, c.wedgeTried, c.grounded, c.wheels, c.v, c.h - c0->h, c.wedgeEsc, c.pitch, c.y);
      int game = c.wedgeEsc + c.perchEsc + c.escapes32 > g0;
      if (hypotf(c.x - sx, c.z - sz) >= 8.f || c.recoveries > rc0 || game) { esc++; if (game && !(hypotf(c.x - sx, c.z - sz) >= 8.f)) (*viaGame)++; break; }
    }
  }
  return esc;
}

static void perCar(int i) {
  Driver *dr = &fleet[i]; Car *c = &dr->c; Det *d = &det[i];
  // зоны DEATH уровня (water/пропасти): игра переносит игрока в точку возврата (game.c gameDeath); без этого рой падал в воду и копился на дне
  if (deathOn && W.ndeath && !(dr->flags & 2) && d->ok && d->epoch == dr->epoch) {
    int k = colDeathAtEx(&W, c->x, c->y + .5f, c->z, .5f, 0);
    if (k >= 0) {
      float h = c->h; colDeathHeading(&W, (uint32_t)k, &h); const float *A = W.death[k].apex;
      report(i, K_DEATH, c->x, c->y, c->z, 1.f, "zone=%s to=(%.1f,%.1f,%.1f) v=%.1f", W.death[k].name, A[0], A[1], A[2], c->v);
      carPlace(c, &W, A[0], A[1], A[2], h); carBox(c, &dr->previous);
      d->ok = 0;                        // как новый старт: якоря, полёт и проверки заново
    }
  }
  int fresh = !d->ok || d->epoch != dr->epoch;
  // высота луча «сквозь стену» — середина твёрдого слоя кузова для стен (bandLo..bandHi, как в colPushCar): что выше него, машина проезжает по правилам
  float cy = c->y + .5f * (c->p.bandLo + c->p.bandHi), cx = c->x, cz = c->z;
  // собственный выход игры (№738 wedge, перч, тупик 32): плавный сдвиг/перенос в точку рядом идёт сквозь забор по замыслу — это не проезд
  int escN = c->perchEsc + c->wedgeEsc + c->escapes32, gm = escOn && (c->glideT > 0.f || escN != d->esc0);
  if (gm && !fresh && escN != d->esc0 && coolOk(d, K_ESCAPE, 60)) report(i, K_ESCAPE, c->x, c->y, c->z, 1.f, "perch=%d wedge=%d dead32=%d glide=%.2f", c->perchEsc, c->wedgeEsc, c->escapes32, c->glideT);
  d->esc0 = escN; if (gm) d->pend = 0;
  int teleported = c->recoveries != d->rec || c->reverts != d->rev || gm;
  if (c->recoveries > d->rec && !fresh && coolOk(d, K_REC, 120))
    report(i, K_REC, c->x, c->y, c->z, (float)(c->recoveries - d->rec), "v=%.1f why=%d", c->v, c->revWhy);
  if (fresh) {
    memset(d, 0, sizeof *d);
    d->epoch = dr->epoch; d->ok = 1; d->ax = d->sx = cx; d->az = d->sz = cz; d->aTick = tick; d->underWith = -1;
    d->rec = c->recoveries; d->rev = c->reverts; d->px = cx; d->py = cy; d->pz = cz; d->takeoffZone = -1; d->t0 = tick;
    return;
  }
  if (injectKind == K_STUCK && i == 0 && tick >= 300 && tick < 1200) {   // контроль: машина прибита на месте
    static float fx, fy, fz; if (tick == 300) { fx = c->x; fy = c->y; fz = c->z; }
    c->x = fx; c->y = fy; c->z = fz; c->vel[0] = c->vel[1] = c->vel[2] = 0; c->v = 0;
  }
  if (injectKind == K_LAUNCH && i == 0 && tick == 600) { c->vel[1] = 15.f; c->grounded = 0; c->y += .5f; }   // контроль: подброс без зоны
  if (injectKind == K_THROUGH && i == 0 && (tick == 600 || tick == 601)) {   // контроль: машина прыгает через забор с лица на изнанку
    static int seg = -1; static float mx, mz, nx, nz;
    if (tick == 600) {
      for (uint32_t k = (uint32_t)fleetN * 7; k < W.nseg && seg < 0; k++) {
        const ColSeg *q = &W.seg[k]; float g, n3[3]; mx = .5f * (q->a[0] + q->b[0]); mz = .5f * (q->a[1] + q->b[1]); nx = q->n[0]; nz = q->n[1];
        if (q->y0 < -1.2e6f || q->y1 > 1e5f || hypotf(q->b[0] - q->a[0], q->b[1] - q->a[1]) < 6.f) continue;
        if (colGround(&W, mx + nx * 1.5f, mz + nz * 1.5f, q->y1 + 2.f, q->y1 - 40.f, &g, n3) && g + 2.f < q->y1) { seg = (int)k; c->x = mx + nx * 1.5f; c->z = mz + nz * 1.5f; c->y = g; }
      }
    } else if (seg >= 0) { c->x = mx - nx * 1.5f; c->z = mz - nz * 1.5f; }
    c->vel[0] = c->vel[1] = c->vel[2] = 0;
  }
  if (injectKind == K_UNDER && (i == 0 || i == 1) && tick >= 600 && tick < 720) {   // контроль: машины 0 и 1 держим кузов в кузове
    static float hx, hy, hz; Car *c0 = &fleet[0].c;
    if (i == 0) { if (tick == 600) { hx = c->x; hy = c->y; hz = c->z; } c->x = hx; c->y = hy; c->z = hz; }
    else { c->x = c0->x + .4f; c->y = c0->y; c->z = c0->z + .4f; c->h = c0->h; }
    c->vel[0] = c->vel[1] = c->vel[2] = 0;
  }
  hist[i][tick % HIST][0] = cx; hist[i][tick % HIST][1] = cz;
  int dead = (dr->flags & 2) != 0, age = (tick - 1) % episodeTicks;
  if (age < 90) {                           // посадка после спавна: ничего не считаем, только запоминаем путь
    d->px = cx; d->py = cy; d->pz = cz; d->rec = c->recoveries; d->rev = c->reverts; d->ax = cx; d->az = cz; d->aTick = tick;
    return;
  }
  // --- сквозь поверхность: путь центра кузова за кадр пересёк COL1 (земля/стены/ящики/заборы), кусты не считаются
  if (!teleported && !dead) {
    float a[3] = {d->px, d->py, d->pz}, b[3] = {cx, cy, cz};
    float dd = hypotf(hypotf(b[0] - a[0], b[1] - a[1]), b[2] - a[2]);
    if (dd > .02f && dd < 60.f) {
      float fr = colRayFrac(&W, a, b, 0);
      if (fr < .999f) {
        float hx = a[0] + (b[0] - a[0]) * fr, hy = a[1] + (b[1] - a[1]) * fr, hz = a[2] + (b[2] - a[2]) * fr, g, n3[3];
        // луч упёрся в землю под центром (центр кузова «просел» к полу) — это посадка кузова, не стена: пропускаем
        int onGround = colGround(&W, hx, hz, hy + .6f, hy - 3.f, &g, n3) && fabsf(hy - g) < .35f;
        if (!onGround && !d->pend && coolOk(d, K_THROUGH, 60)) {
          float ex = b[0] - a[0], ez = b[2] - a[2], el = hypotf(ex, ez);
          d->pend = 1; d->pTick = tick; d->pHit[0] = hx; d->pHit[1] = hy; d->pHit[2] = hz; d->pDir[0] = el > 1e-4f ? ex / el : 0; d->pDir[1] = el > 1e-4f ? ez / el : 0;
          d->pStep = dd; d->pFrac = fr; d->pV = c->v; d->pGround = colGround(&W, hx, hz, hy + .6f, hy - 6.f, &g, n3) ? hy - g : 99.f;
          primAt(c, hx, hz, d->pDir, d->pPrim, sizeof d->pPrim, &d->pFace, &d->pSeg, &d->pPhantom, &d->pSegIx);
          // возврат: машина пришла от изнанки этого звена (вошла с изнанки по замыслу PS2 — colBackKeep — и отскочила обратно): та же поездка, не проезд с лица.
          // Проверка по истории: за последние 3 с центр кузова был по ту сторону звена, куда он теперь вышел (и в пределах длины звена)
          d->pReturn = 0;
          if (d->pSeg && d->pFace && d->pSegIx >= 0) {
            const ColSeg *sg = &W.seg[d->pSegIx]; float sl = hypotf(sg->b[0] - sg->a[0], sg->b[1] - sg->a[1]) + 1e-6f;
            for (int k = 2; k < HIST && tick - k > d->t0; k++) {
              const float *q = hist[i][(tick - k) % HIST];
              float sd = (q[0] - sg->a[0]) * sg->n[0] + (q[1] - sg->a[1]) * sg->n[1];
              float tt = ((q[0] - sg->a[0]) * (sg->b[0] - sg->a[0]) + (q[1] - sg->a[1]) * (sg->b[1] - sg->a[1])) / sl;
              if (sd < -0.5f && tt > -1.f && tt < sl + 1.f) { d->pReturn = 1; break; }
            }
          }
        }
      }
    }
  }
  if (d->pend && tick - d->pTick >= 20) {      // 20 кадров спустя: машина по ту сторону места пересечения (ушла дальше) или физика вернула её
    d->pend = 0;
    float beyond = (cx - d->pHit[0]) * d->pDir[0] + (cz - d->pHit[2]) * d->pDir[1];
    if (!teleported && beyond > 1.f)
      report(i, d->pPhantom && phantomOn ? K_PHANTOM : d->pReturn && backRetOn ? K_BACKRET : d->pSeg && !d->pFace ? K_BACK : K_THROUGH, d->pHit[0], d->pHit[1], d->pHit[2], (beyond + fabsf(d->pV) * .1f) * ((d->pPhantom && phantomOn) || (d->pReturn && backRetOn) || (d->pSeg && !d->pFace) ? .1f : 1.f), "v=%.1f step=%.2f frac=%.3f beyond=%.1fm groundBelow=%.2f at=%d %s", d->pV, d->pStep, d->pFrac, beyond, d->pGround, d->pTick, d->pPrim);
    (void)0;
  }
  // --- застрял: 12 с под газом не отошёл от якоря дальше 2 м (бот сам разворачивается после 1,5 с — это уже после его попыток)
  if (hypotf(cx - d->ax, cz - d->az) > 2.f || dead) { d->ax = cx; d->az = cz; d->aTick = tick; d->stuckRep = 0; }
  else if (tick - d->aTick >= 12 * 60 && !d->stuckRep) {
    d->stuckRep = 1;
    if (poseF) fprintf(poseF, "%d\t%.3f\t%.3f\t%.3f\t%.4f\t%d\t%.3f\t%.3f\t%d\t%d\n", lvlNo, cx, c->y, cz, c->h, i % 4, c->pitch, c->roll, i, tick);   // --poses: поза застрявшей
    int viaGame = 0, drill = drillOn ? escapeDrill(c, &viaGame) : 0;   // игрок выбрался бы? (7 манёвров): да — застрял бот (stuckbot), нет — ловушка (stuck)
    report(i, drill ? K_STUCKBOT : K_STUCK, cx, c->y, cz, drill ? 1.f : 12.f, "drill=%d/7 viaGame=%d contacts=%d pitch=%.2f roll=%.2f dmg=%.2f grounded=%d wheels=%d mode=%d", drill, viaGame, c->contacts, c->pitch, c->roll, c->damage, c->grounded, c->wheels, dr->b.mode);
  }
  // --- полёты: подброс (без зоны прыжка) и трамплин
  int designed = dr->scenario >= 2 && tick % episodeTicks < 120;   // стартовые броски сценариев 3/4 заданы нами
  if (!c->grounded) {
    if (!d->air) {
      d->air = 1; d->takeoffTick = tick; d->takeoffZone = c->flightZone; d->takeoffY = c->y; d->maxY = c->y;
      d->takeoffV = hypotf(c->vel[0], c->vel[2]); d->takeoffX = cx; d->takeoffZ = cz; d->flightRep = 0;
      d->takeoffHit = (tick - d->lastHitTick) < 12;
    } else { d->air++; if (c->y > d->maxY) d->maxY = c->y; }
    float rise = d->maxY - d->takeoffY;
    if (!designed && c->flightZone < 0 && !d->flightRep && (c->vel[1] > 9.f || rise > 2.5f) && (d->takeoffV < 12.f || d->takeoffHit || c->vel[1] > 12.f)) {
      d->flightRep = 1;
      if (coolOk(d, K_LAUNCH, 120)) report(i, K_LAUNCH, d->takeoffX, d->takeoffY, d->takeoffZ, rise > c->vel[1] ? rise : c->vel[1],
                                           "vy=%.1f rise=%.1f takeoffV=%.1f hit=%d", c->vel[1], rise, d->takeoffV, d->takeoffHit);
    }
  } else {
    if (d->air >= 90 && d->takeoffZone < 0 && !d->flightRep && !(dr->scenario >= 2 && d->takeoffTick % episodeTicks < 240)) {
      float rise = d->maxY - d->takeoffY;
      if (coolOk(d, K_RAMP, 120)) report(i, K_RAMP, d->takeoffX, d->takeoffY, d->takeoffZ, d->air / 60.f,
                                         "air=%.1fs rise=%.1f dist=%.0f takeoffV=%.1f dy=%.1f", d->air / 60.f, rise, hypotf(cx - d->takeoffX, cz - d->takeoffZ), d->takeoffV, c->y - d->takeoffY);
    }
    d->air = 0;
  }
  // --- на крыше: стоим на опоре, под которой ниже 3 м ещё земля, и дороги рядом на этом уровне нет
  d->groundTicks = c->grounded && c->wheels >= 3 ? d->groundTicks + 1 : 0;
  if (d->groundTicks == 90 && !d->roofRep && !dead && hypotf(cx - d->sx, cz - d->sz) > 25.f) {   // не там, где машину поставил спавн
    // выше окружения: верхняя поверхность в кольце 10 м (8 точек) в медиане ниже машины больше чем на 3,5 м
    float ys[8], g, n3[3]; int k = 0;
    for (int a = 0; a < 8; a++) { float qx = cx + 10.f * sinf(a * PI / 4), qz = cz + 10.f * cosf(a * PI / 4); if (colGround(&W, qx, qz, 10000.f, -1000.f, &g, n3)) ys[k++] = g; }
    for (int a = 1; a < k; a++) for (int b = a; b > 0 && ys[b] < ys[b - 1]; b--) { float t = ys[b]; ys[b] = ys[b - 1]; ys[b - 1] = t; }
    float med = k >= 5 ? ys[k / 2] : c->y;
    if (c->y - med > 3.5f) {
      int r = nearestRoad(cx, cz, 100.f, 14.f);
      int onRoad = r >= 0 && fabsf(c->y - .5f * (roads[r].ay + roads[r].by)) < 3.f;   // мост и эстакада — дорога, не крыша
      if (!onRoad) { d->roofRep = 1; report(i, K_ROOF, cx, c->y, cz, c->y - med, "above=%.1f ringMedian=%.1f zoneFlight=%d v=%.1f fromSpawn=%.0f", c->y - med, med, d->takeoffZone >= 0, c->v, hypotf(cx - d->sx, cz - d->sz)); }
    }
  }
  // --- встроенный контроль проникновения (как sandbox.c): > 0,15 м 12 кадров подряд
  if (dr->penTicks == 12 && coolOk(d, K_EMBED, 300)) report(i, K_EMBED, cx, c->y, cz, dr->penTicks / 12.f, "v=%.1f contacts=%d", c->v, c->contacts);
  if (c->hitSpeed > 4.f) d->lastHitTick = tick;
  d->px = cx; d->py = cy; d->pz = cz; d->rec = c->recoveries; d->rev = c->reverts;
}

static int order[FLEET];
static int byXdet(const void *aa, const void *bb) { float x = fleet[*(const int *)aa].c.x - fleet[*(const int *)bb].c.x; return x < 0 ? -1 : x > 0 ? 1 : *(const int *)aa - *(const int *)bb; }
static void pairs(void) {
  float radius = 0;
  for (int i = 0; i < fleetN; i++) { order[i] = i; Car *c = &fleet[i].c; radius = fmaxf(radius, hypotf(c->p.halfL, c->p.halfW) + fabsf(c->p.bodyOfs)); }
  qsort(order, (size_t)fleetN, sizeof *order, byXdet);
  for (int i = 0; i < fleetN; i++) if (det[i].underWith >= 0 && det[i].underTicks < 0) det[i].underWith = -1;
  static unsigned char seen[FLEET];
  memset(seen, 0, (size_t)fleetN);
  for (int a = 0; a < fleetN; a++) for (int b = a + 1; b < fleetN; b++) {
    Car *p = &fleet[order[a]].c, *q = &fleet[order[b]].c;
    if (q->x - p->x > radius * 2) break;
    if (fabsf(q->z - p->z) > radius * 2 || det[order[a]].epoch != fleet[order[a]].epoch) continue;
    float lo1 = p->y + p->p.bodyLo, hi1 = p->y + p->p.bodyHi, lo2 = q->y + q->p.bodyLo, hi2 = q->y + q->p.bodyHi;
    float vo = fminf(hi1, hi2) - fmaxf(lo1, lo2);                 // общая высота
    if (vo <= 0) continue;
    Rect ra = rectOf(p), rb = rectOf(q);
    float pen = satPen(&ra, &rb);
    int ia = order[a], ib = order[b];
    if (pen > .6f && vo > .7f) {
      Det *d = &det[ia < ib ? ia : ib]; int other = ia < ib ? ib : ia;
      if (d->underWith != other) { d->underWith = other; d->underTicks = 0; }
      seen[ia < ib ? ia : ib] = 1;
      if (++d->underTicks == 12 && coolOk(d, K_UNDER, 240)) {
        Car *k = ia < ib ? p : q, *m = ia < ib ? q : p;
        report(ia < ib ? ia : ib, K_UNDER, k->x, k->y, k->z, pen + vo, "with=%d pen=%.2f common_h=%.2f dy=%.2f slope=%.2f/%.2f", other, pen, vo, m->y - k->y, k->pitch, m->pitch);
      }
    }
  }
  for (int i = 0; i < fleetN; i++) {
    Det *d = &det[i]; if (!seen[i]) { d->underWith = -1; d->underTicks = 0; }
    Car *c = &fleet[i].c;
    d->overTicks = c->supOn ? d->overTicks + 1 : 0;
    if (d->overTicks == 90 && !d->overRep && coolOk(d, K_OVER, 300)) {
      d->overRep = 1; report(i, K_OVER, c->x, c->y, c->z, d->overTicks / 60.f, "supY=%.2f dy=%.2f v=%.1f pitch=%.2f", c->supY, c->y - c->supY, c->v, c->pitch);
    }
    if (!c->supOn) d->overRep = 0;
  }
}

int main(int argc, char **argv) {
  const char *level = 0, *road = 0, *out = 0; int seconds = 600; double until = 0;
  for (int i = 1; i < argc; i++) {
    if (!strcmp(argv[i], "--level") && i + 1 < argc) level = argv[++i];
    else if (!strcmp(argv[i], "--roads") && i + 1 < argc) road = argv[++i];
    else if (!strcmp(argv[i], "--out") && i + 1 < argc) out = argv[++i];
    else if (!strcmp(argv[i], "--lvl") && i + 1 < argc) lvlNo = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--cars") && i + 1 < argc) fleetN = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--seed") && i + 1 < argc) campaignSeed = (uint32_t)strtoul(argv[++i], 0, 10);
    else if (!strcmp(argv[i], "--seconds") && i + 1 < argc) seconds = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--until") && i + 1 < argc) until = atof(argv[++i]);
    else if (!strcmp(argv[i], "--cap") && i + 1 < argc) cap = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--poses") && i + 1 < argc) { poseF = fopen(argv[++i], "a"); if (!poseF) { perror("poses"); return 2; } }
    else if (!strcmp(argv[i], "--nophantom")) phantomOn = 0;   // прежнее: проход прозрачной стены считается сквозным проездом
    else if (!strcmp(argv[i], "--noescape")) escOn = 0;   // прежнее: сдвиг собственного выхода игры считается проездом сквозь забор
    else if (!strcmp(argv[i], "--nobackret")) backRetOn = 0;   // прежнее: возврат через то же звено считается проездом с лица
    else if (!strcmp(argv[i], "--nodrill")) drillOn = 0;        // прежнее: застрявшая всегда ошибка, без проверки манёврами
    else if (!strcmp(argv[i], "--nodeath")) deathOn = 0;   // прежнее поведение роя (зоны DEATH не применяются)
    else if (!strcmp(argv[i], "--trace") && i + 3 < argc) { traceCar = atoi(argv[++i]); traceT0 = atoi(argv[++i]); traceT1 = atoi(argv[++i]); }
    else if (!strcmp(argv[i], "--inject") && i + 1 < argc) { const char *k = argv[++i]; for (int j = 0; j < K_N; j++) if (!strcmp(k, KN[j])) injectKind = j; if (injectKind < 0) { fprintf(stderr, "unknown inject %s\n", k); return 2; } }
    else { fprintf(stderr, "unknown argument: %s\n", argv[i]); return 2; }
  }
  if (!level || !out || fleetN < 2 || fleetN > FLEET || seconds < 1) { fprintf(stderr, "usage: bots_swarm --level L.shr --lvl N --out F.tsv [--roads R.bin] [--cars 2..%d] [--seed S] [--seconds T] [--until EPOCH]\n", FLEET); return 2; }
  tsv = fopen(out, "a"); if (!tsv) { perror(out); return 2; }
  if (!freopen("/dev/null", "w", stdout)) return 2;   // JSON-события sandbox.c не нужны: находки идут в TSV
  loadLevel(level); loadObjects(); if (road) loadRoads(road); makeStarts();
  for (int i = 0; i < fleetN; i++) spawn(i, 0);
  began = now(); int ticks = seconds * 60, stop = 0;
  while (tick < ticks && !stop) {
    if (!simulate(NULL)) { fprintf(stderr, "FATAL: нечисловое состояние на кадре %d (уровень %d)\n", tick, lvlNo); stop = 1; break; }
    for (int i = 0; i < fleetN; i++) perCar(i);
    pairs();
    if (traceCar >= 0 && tick >= traceT0 && tick <= traceT1) { const Car *c = &fleet[traceCar].c;   // --trace ID T0 T1: кадры одной машины в stderr
      fprintf(stderr, "T%d x=%.3f y=%.3f z=%.3f h=%.3f v=%.2f vel=(%.2f,%.2f,%.2f) gr=%d wh=%d contacts=%d hit=%.1f pen=%d fz=%d sup=%d mode=%d", tick, c->x, c->y, c->z, c->h, c->v, c->vel[0], c->vel[1], c->vel[2], c->grounded, c->wheels, c->contacts, c->hitSpeed, fleet[traceCar].penTicks, c->flightZone, c->supOn, fleet[traceCar].b.mode);
      fprintf(stderr, " | glide=%.3f to=(%.2f,%.2f) perch=%d wedge=%d dead32=%d rec=%d rights=%d wedgeT=%.2f perchT=%.2f stuck32=%d belly=%.2f flip=%.2f", c->glideT, c->gx1, c->gz1, c->perchEsc, c->wedgeEsc, c->escapes32, c->recoveries, c->rights, c->wedgeT, c->perchT, c->stuck32, c->bellyT, c->flipT);
      CarBox pb; carBox(c, &pb); colProbeCar(&W, &pb);   // что видит узкая фаза у машины в этом кадре
      fprintf(stderr, " | probe n=%d max=%.2f y=%.2f band=%.2f..%.2f fsup=%.2f/%d", pb.n, pb.maxDepth, pb.y, pb.y + pb.lo, pb.y + pb.hi, pb.fsup, pb.fsupOn);
      for (int q = 0; q < pb.n; q++) fprintf(stderr, " [%d#%u d=%.2f n=(%.2f,%.2f)]", pb.type[q], pb.index[q], pb.depth[q], pb.nx[q], pb.nz[q]);
      for (int q = 0; q < fleetN; q++) if (q != traceCar) { const Car *o = &fleet[q].c; if (hypotf(o->x - c->x, o->z - c->z) < 6.f && fabsf(o->y - c->y) < 12.f) fprintf(stderr, " <%d:%s y=%.1f v=%.1f gr=%d mode=%d rec=%d>", q, MODELS[q % 4], o->y, o->v, o->grounded, fleet[q].b.mode, o->recoveries); }
      fputc('\n', stderr); }
    if (until > 0 && (tick & 255) == 0) { struct timespec t; clock_gettime(CLOCK_REALTIME, &t); if (t.tv_sec >= until) stop = 1; }
  }
  fprintf(tsv, "# итог L%d seed=%u cars=%d кадров=%d ", lvlNo, campaignSeed, fleetN, tick);
  fprintf(stderr, "L%d seed=%u cars=%d ticks=%d wall=%.1fs cpu=%.1fs updates=%lu pairs=%lu fatal=%d |", lvlNo, campaignSeed, fleetN, tick, now() - began, cpuNow(), updates, hits, fatal);
  for (int k = 0; k < K_N; k++) { fprintf(stderr, " %s=%lu/%lu", KN[k], written[k], found[k]); fprintf(tsv, "%s=%lu/%lu ", KN[k], written[k], found[k]); }
  fprintf(stderr, "\n"); fputc('\n', tsv); fclose(tsv);
  propsFree(&objects); spFree(&stateObjects); free(glassVisited); colFree(&W);
  return fatal ? 1 : 0;
}
