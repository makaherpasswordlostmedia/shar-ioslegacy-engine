// Перепись стен (просьба Роба 28.09: «если оно прозрачное, почему оно не даёт проехать»). Рой машин на ботах
// cartest (дорога / дикий / таран) ездит по уровню; машины друг друга не видят, поэтому любая воспроизводится одна
// по (seed, номер, эпоха). Модули движка те же, что на PSP: viewer/car.c + col.c. Без AI и сети.
// Событие — строка TSV в stdout:
//   ev seed car epoch tick kind v x y z nx nz ptype pidx mat top vis rise prop
// kind: wall — удар о стену мира (car.wallV > VMIN, один раз в 1 с на пару машина+примитив);
//       edge16 / edge32 / push1 — подшаг отменён: край мира / земля выше, чем можно въехать / не вытолкнулось.
// Сверка с картинкой (рисуемые куски города, ближняя версия, обе стороны треугольников, альфа и стекло тоже):
//   vis  — 1: горизонтальный луч на высоте 0.4..1.4 м над полом из точки удара в сторону препятствия (3 луча вбок
//          через 0.5 м) упирается в нарисованный треугольник не дальше 1 м за точкой; 0 — на картинке там пусто.
//          Для edge16/32: 1 — под новым местом машины нарисованная земля есть (в пределах пол ±1.5 м)
//   rise — насколько нарисованная земля за точкой удара (0.5 и 1 м) выше пола машины, м (-9 — земли нет)
//   top  — верх примитива коллизии над полом, м;  prop — ближе 2.5 м есть предмет PRP1/SPR1 (1/0)
// Происхождение: машины видов 0 и 1 стартуют на дороге — «естественное»; 2 и 3 (любая опора, крыши, таран) — «стресс».
// Итог в stderr. Сборка и запуск: tools/cartest/walls.py (рой по ядрам, сводка, повторы).
//   cc -std=c99 -O2 tools/cartest/walls.c viewer/car.c viewer/col.c viewer/props.c viewer/stateprops.c viewer/coins.c -lm
//   walls --level L --roads R --seed S --cars N --secs T [--episode 30] [--replay CAR EPOCH] [--vmin 2]
#define main cartestLegacyMain
#include "cartest.c"
#undef main
#include "../../viewer/props.h"
#include "../../viewer/stateprops.h"

// ---------------------------------------------------------------- рисуемая геометрия (как tools/wind.c читает куски)
typedef struct { float bb[6]; int32_t tex; uint32_t flags, nv, ni, owner; float ox, oy, oz, sc; uint32_t off, nf, cell, pad[2]; } Rec;
typedef struct { float bb[6]; uint32_t first, n, owner, off, size, pad; } CellRec;
static Props renderedProps; static StateProps renderedSP;
static int staticOnly;
static void addPropRender(void);
static float *T; static unsigned NT;              // треугольники: 9 float
static float HIDE[3] = {0, 0, -1};   // --hide X Z R: не видеть рисуемые треугольники в круге (отрицательный контроль)
static unsigned *gStart, *gList; static int GW, GH; static float GOX, GOZ; static const float GC = 2.f;
static void loadRender(void) {
  uint32_t npc, tableOff, cellOff; memcpy(&npc, file + 8, 4); memcpy(&tableOff, file + 76, 4); memcpy(&cellOff, file + 84, 4);
  const Rec *recs = (const Rec *)(file + tableOff); const CellRec *cells = (const CellRec *)(file + cellOff);
  unsigned cap = 1 << 20; T = malloc(sizeof(float) * 9 * cap);
  for (unsigned i = 0; i < npc; i++) {
    const Rec *r = &recs[i]; if (r->owner != 0 || (r->flags & 4) || !(r->flags & 16)) continue;   // город, не небо, без индексов
    int vs = (r->flags & 32) ? 12 : 16; const uint8_t *b = file + cells[r->cell].off + r->off;
    for (unsigned k = 0; k + 2 < r->ni; k += 3) {
      if (HIDE[2] > 0) { const int16_t *q = (const int16_t *)(b + (size_t)k * vs + (vs == 12 ? 6 : 8));
        float x = r->ox + q[0] * (r->sc / 32768.f), z = r->oz + q[2] * (r->sc / 32768.f);
        if ((x - HIDE[0]) * (x - HIDE[0]) + (z - HIDE[1]) * (z - HIDE[1]) < HIDE[2] * HIDE[2]) continue; }
      if (NT == cap) { cap *= 2; T = realloc(T, sizeof(float) * 9 * cap); }
      for (int j = 0; j < 3; j++) {
        const int16_t *q = (const int16_t *)(b + (size_t)(k + j) * vs + (vs == 12 ? 6 : 8));
        T[9 * NT + 3 * j] = r->ox + q[0] * (r->sc / 32768.f); T[9 * NT + 3 * j + 1] = r->oy + q[1] * (r->sc / 32768.f);
        T[9 * NT + 3 * j + 2] = r->oz + q[2] * (r->sc / 32768.f);
      }
      NT++;
    }
  }
  if (!staticOnly) addPropRender();
  GOX = W.ox; GOZ = W.oz; GW = (int)(W.W * W.cell / GC) + 1; GH = (int)(W.H * W.cell / GC) + 1;
  gStart = calloc((size_t)GW * GH + 1, 4);
  for (int pass = 0; pass < 2; pass++) {
    for (unsigned t = 0; t < NT; t++) {
      const float *a = T + 9 * t;
      float x0 = fminf(a[0], fminf(a[3], a[6])), x1 = fmaxf(a[0], fmaxf(a[3], a[6]));
      float z0 = fminf(a[2], fminf(a[5], a[8])), z1 = fmaxf(a[2], fmaxf(a[5], a[8]));
      int cx0 = (int)floorf((x0 - GOX) / GC), cx1 = (int)floorf((x1 - GOX) / GC), cz0 = (int)floorf((z0 - GOZ) / GC), cz1 = (int)floorf((z1 - GOZ) / GC);
      if (cx0 < 0) cx0 = 0; if (cz0 < 0) cz0 = 0; if (cx1 >= GW) cx1 = GW - 1; if (cz1 >= GH) cz1 = GH - 1;
      for (int z = cz0; z <= cz1; z++) for (int x = cx0; x <= cx1; x++) {
        size_t c = (size_t)z * GW + x; if (pass == 0) gStart[c + 1]++; else gList[gStart[c]++] = t;
      }
    }
    if (pass == 0) { for (size_t c = 0; c < (size_t)GW * GH; c++) gStart[c + 1] += gStart[c]; gList = malloc(sizeof(unsigned) * (gStart[(size_t)GW * GH] + 1)); }
    else { for (size_t c = (size_t)GW * GH; c > 0; c--) gStart[c] = gStart[c - 1]; gStart[0] = 0; }
  }
}
// луч o + d*t, t in [0, tmax]: ближайшее пересечение с треугольником (обе стороны), иначе -1
static float rayTri(const float *o, const float *d, const float *a) {
  float e1[3] = {a[3] - a[0], a[4] - a[1], a[5] - a[2]}, e2[3] = {a[6] - a[0], a[7] - a[1], a[8] - a[2]};
  float p[3] = {d[1] * e2[2] - d[2] * e2[1], d[2] * e2[0] - d[0] * e2[2], d[0] * e2[1] - d[1] * e2[0]};
  float det = e1[0] * p[0] + e1[1] * p[1] + e1[2] * p[2]; if (fabsf(det) < 1e-9f) return -1;
  float inv = 1.f / det, s[3] = {o[0] - a[0], o[1] - a[1], o[2] - a[2]};
  float u = (s[0] * p[0] + s[1] * p[1] + s[2] * p[2]) * inv; if (u < 0 || u > 1) return -1;
  float q[3] = {s[1] * e1[2] - s[2] * e1[1], s[2] * e1[0] - s[0] * e1[2], s[0] * e1[1] - s[1] * e1[0]};
  float v = (d[0] * q[0] + d[1] * q[1] + d[2] * q[2]) * inv; if (v < 0 || u + v > 1) return -1;
  return (e2[0] * q[0] + e2[1] * q[1] + e2[2] * q[2]) * inv;
}
static float rayCast(const float *o, const float *d, float tmax) {
  float ex = o[0] + d[0] * tmax, ez = o[2] + d[2] * tmax, best = -1;
  int cx0 = (int)floorf((fminf(o[0], ex) - GOX) / GC), cx1 = (int)floorf((fmaxf(o[0], ex) - GOX) / GC);
  int cz0 = (int)floorf((fminf(o[2], ez) - GOZ) / GC), cz1 = (int)floorf((fmaxf(o[2], ez) - GOZ) / GC);
  if (cx0 < 0) cx0 = 0; if (cz0 < 0) cz0 = 0; if (cx1 >= GW) cx1 = GW - 1; if (cz1 >= GH) cz1 = GH - 1;
  for (int z = cz0; z <= cz1; z++) for (int x = cx0; x <= cx1; x++) {
    size_t c = (size_t)z * GW + x;
    for (unsigned k = gStart[c]; k < gStart[c + 1]; k++) { float t = rayTri(o, d, T + 9 * gList[k]); if (t >= 0 && t <= tmax && (best < 0 || t < best)) best = t; }
  }
  return best;
}
// нарисованная земля в (x, z) не выше yTop: высота или -1e9
static float renderGround(float x, float z, float yTop) {
  float o[3] = {x, yTop, z}, d[3] = {0, -1, 0}, t = rayCast(o, d, 60.f); return t < 0 ? -1e9f : yTop - t;
}

// ---------------------------------------------------------------- верх примитива коллизии
static float primTop(int type, unsigned i) {
  if (type == COL_TRI && i < W.ntri) { const ColTri *t = &W.tri[i]; return fmaxf(t->a[1], fmaxf(t->b[1], t->c[1])); }
  if (type == COL_BOX && i < W.nbox) { const ColBox *b = &W.box[i]; return b->c[1] + fabsf(b->ax[1]) * b->h[0] + fabsf(b->ay[1]) * b->h[1] + fabsf(b->az[1]) * b->h[2]; }
  if (type == COL_CYL && i < W.ncyl) { const ColCyl *c = &W.cyl[i]; return c->c[1] + fabsf(c->axis[1]) * c->halfLen + c->r; }
  if (type == COL_SEG && i < W.nseg) return W.seg[i].y1;
  return NAN;
}

// ---------------------------------------------------------------- предметы (только где стоят)
static float *propXZ; static unsigned nProp;
static void loadProps(void) {
  unsigned po = *(unsigned *)(file + 96); if (!po || po + 64 > fileSize) return;
  Props *pp = &renderedProps; StateProps *ss = &renderedSP; unsigned size = *(unsigned *)(file + po + 40);
  if (propsInit(pp, file + po, size) || spInit(ss, pp->spr, pp->sprSize)) return;
#define P (*pp)
#define S (*ss)
  propXZ = malloc(sizeof(float) * 3 * (P.ninst + S.ninst + 1));
  for (unsigned i = 0; i < P.ninst; i++) { propXZ[3 * nProp] = P.def[i].x; propXZ[3 * nProp + 1] = P.def[i].y; propXZ[3 * nProp + 2] = P.def[i].z; nProp++; }
  for (unsigned i = 0; i < S.ninst; i++) { propXZ[3 * nProp] = S.inst[i].x; propXZ[3 * nProp + 1] = S.inst[i].y; propXZ[3 * nProp + 2] = S.inst[i].z; nProp++; }
}
#undef P
#undef S
// The swarm's collision world is frame zero. Compare it with the same SPR1 pose,
// not only the static city (which falsely labels the crane/billboard invisible).
static void addPropRender(void) {
  StateProps *sp=&renderedSP; unsigned cap=NT;
  for(unsigned i=0;i<sp->ninst;i++) {
    const SpType *ty=&sp->type[sp->inst[i].type]; spPose(sp,i);
    for(unsigned k=0;k<ty->nPiece;k++) {
      if(!spPieceOn(sp,i,k)) continue;
      const SpPiece *p=&sp->piece[ty->firstPiece+k];
      if(NT+p->ni/3>cap) { cap=NT+p->ni/3+4096; T=realloc(T,9*sizeof(float)*cap); }
      float m[16];spPieceMatrix(sp,i,k,m);
      const unsigned short *ix=(const unsigned short *)((const char *)sp->idxBase+p->iOff);
      const unsigned char *vb=(const unsigned char *)sp->vertBase+p->vOff;
      for(unsigned t=0;t+2<p->ni;t+=3) {
        for(int j=0;j<3;j++) {
          const short *q=(const short *)(vb+16*ix[t+j]+8);
          for(int a=0;a<3;a++) T[9*NT+3*j+a]=m[12+a]+m[a]*q[0]+m[4+a]*q[1]+m[8+a]*q[2];
        }
        NT++;
      }
    }
  }
}
static int nearProp(float x, float y, float z) {
  for (unsigned i = 0; i < nProp; i++) {
    float dx = propXZ[3 * i] - x, dy = propXZ[3 * i + 1] - y, dz = propXZ[3 * i + 2] - z;
    if (dx * dx + dz * dz < 2.5f * 2.5f && fabsf(dy) < 4.f) return 1;
  }
  return 0;
}

// ---------------------------------------------------------------- рой
typedef struct { float x, y, z; int stacked; } Start;
static int areaOn; static float area[4];
static Start *starts; static int nstart;
static void makeStarts(void) {
  int cap = 1 << 16; starts = malloc(sizeof(Start) * cap);
  for (float z = W.oz + 3; z < W.oz + W.H * W.cell; z += 6)
    for (float x = W.ox + 3; x < W.ox + W.W * W.cell; x += 6) {
      float top = 10000, g; int first = nstart;
      for (int l = 0; l < 8; l++) {
        float n[3]; if (!colGround(&W, x, z, top, -1000, &g, n)) break;
        if (n[1] > .8f) { if (nstart == cap) { cap *= 2; starts = realloc(starts, sizeof(Start) * cap); } starts[nstart++] = (Start){x, g, z, l > 0}; if (l) starts[first].stacked = 1; }
        top = g - .12f;
      }
    }
}
typedef struct { Car c; Bot b; uint32_t random; int epoch, rev0; int lastT, lastType; unsigned lastIdx; int lastEdge; float vPrev; } Driver;
static Driver *fleet; static int fleetN = 128; static uint32_t seed = 1; static float VMIN = 2.f;
static long evN[5]; static double carSec, distAll;
static const char *models[] = {"famil_v", "sportsa", "pickupa", "schoolbu"};
static int spawn(int id, int epoch) {
  Driver *d = &fleet[id]; memset(d, 0, sizeof *d); d->epoch = epoch; d->lastT = -1000;
  rng = seed ^ (0x9e3779b9u * (unsigned)(id + 1)) ^ (0x85ebca6bu * (unsigned)(epoch + 1)); if (!rng) rng = 1;
  int kind = id % 4;   // 0 бот по дороге, 1 дикий с дороги, 2 дикий с любой опоры (крыши тоже), 3 таран с любой опоры
  for (int tries = 0; tries < 500; tries++) {
    float x, y, z, h;
    if (kind < 2 && nroad) {
      int r = (int)(rnd() % (unsigned)nroad); Road *R = &roads[r]; float u = .1f + .8f * frand();
      x = R->ax + (R->bx - R->ax) * u; y = R->ay + (R->by - R->ay) * u; z = R->az + (R->bz - R->az) * u;
      h = atan2f(R->bx - R->ax, R->bz - R->az) + (kind == 1 && (rnd() & 1) ? PI : 0);
      d->b.mode = kind == 0 ? 0 : 1; d->b.cur = r; d->b.nxt = pickNext(r);
    } else {
      Start *s = &starts[rnd() % (unsigned)nstart]; x = s->x; y = s->y; z = s->z; h = frand() * 2 * PI; d->b.mode = kind == 2 ? 1 : 2;
    }
    if (areaOn && (x < area[0] || x > area[1] || z < area[2] || z > area[3])) continue;
    CarParams p; carParamsFor(models[(id / 4) % 4], &p);
    carInit(&d->c, &p, &W, x, y, z, h); CarBox b; carBox(&d->c, &b); colProbeCar(&W, &b);
    if (b.maxDepth > .025f || !d->c.grounded || d->c.wheels < 3 || fabsf(d->c.y - y) > 1.4f) continue;
    d->b.lastX = d->c.x; d->b.lastZ = d->c.z;
    carSetSpeed(&d->c, kind == 0 ? 8.f + 5.f * frand() : 5.f + 21.f * frand());
    d->random = rng; d->rev0 = d->c.reverts; return 1;
  }
  return 0;
}
// сводка по кластерам: удар — по примитиву (тип, номер), отмена подшага — по клетке 4 м и слою 3 м. В кластере
// число событий, сколько «видно на картинке», сколько «на картинке ровно» (не видно и земля за точкой выше пола
// меньше чем на 0.3 м), у предмета, скорости и повтор самого сильного события
typedef struct { uint64_t key; int kind, pt; unsigned pi; long n, nvis, nflat, nprop, nNat; double vsum; float vmax, vmaxNat;
                 int car, epoch, tick, carN, epochN, tickN; float x, y, z, nx, nz, top, rise; } Cl;
#define NCL (1 << 16)
static Cl cl[NCL]; static int ncl, RAW;
static const char *KIND[4] = {"wall", "edge16", "edge32", "push1"};
static void emit(int id, int tick, int kind, float v, float x, float y, float z, float nx, float nz, int pt, unsigned pi, int mat,
                 float top, int vis, float rise) {
  Driver *d = &fleet[id]; int prop = nearProp(x, y, z), nat = id % 4 < 2;   // естественное: старт на дороге (виды 0, 1)
  if (RAW) printf("ev\t%u\t%d\t%d\t%d\t%s\t%.2f\t%.2f\t%.2f\t%.2f\t%.3f\t%.3f\t%d\t%u\t%d\t%.2f\t%d\t%.2f\t%d\n", seed, id, d->epoch, tick, KIND[kind], v,
                  x, y, z, nx, nz, pt, pi, mat, top, vis, rise, prop);
  uint64_t key = kind == 0 ? ((uint64_t)(pt + 1) << 32 | pi) :
                 ((uint64_t)(8 + kind) << 56 | (uint64_t)(uint16_t)(int)floorf(x / 4) << 32 | (uint64_t)(uint16_t)(int)floorf(z / 4) << 16 | (uint16_t)(int)floorf(y / 3));
  unsigned h = (unsigned)((key * 0x9E3779B97F4A7C15ULL) >> 48) & (NCL - 1);
  while (cl[h].n && cl[h].key != key) h = (h + 1) & (NCL - 1);
  Cl *c = &cl[h];
  if (!c->n) { if (ncl >= NCL * 3 / 4) return; ncl++; c->key = key; c->kind = kind; c->pt = pt; c->pi = pi; }
  c->n++; c->nvis += vis; c->nflat += !vis && rise < .3f; c->nprop += prop; c->vsum += v; c->nNat += nat;
  if (nat && v > c->vmaxNat) { c->vmaxNat = v; c->carN = id; c->epochN = d->epoch; c->tickN = tick; }
  if (v > c->vmax) { c->vmax = v; c->car = id; c->epoch = d->epoch; c->tick = tick; c->x = x; c->y = y; c->z = z; c->nx = nx; c->nz = nz; c->top = top; c->rise = rise; }
}
// удар о стену: есть ли на картинке препятствие за точкой удара
static void wallEvent(int id, int tick) {
  Car *c = &fleet[id].c; float nx = c->wallN[0], nz = c->wallN[1], *P = c->wallP, fl = P[1];
  static const float H[4] = {.4f, .7f, 1.f, 1.4f}; int vis = 0;
  for (int s = -1; s <= 1 && !vis; s++) for (int k = 0; k < 4 && !vis; k++) {
    float o[3] = {P[0] + nx * .3f + nz * .5f * s, fl + H[k], P[2] + nz * .3f - nx * .5f * s}, dd[3] = {-nx, 0, -nz};
    float t = rayCast(o, dd, 1.3f); if (t >= 0) vis = 1;
  }
  float rise = -9.f;
  for (int k = 1; k <= 2; k++) { float g = renderGround(P[0] - nx * .5f * k, P[2] - nz * .5f * k, fl + 3.f); if (g > -1e8f) rise = fmaxf(rise, g - fl); }
  emit(id, tick, 0, c->wallV, P[0], fl, P[2], nx, nz, c->wallType, c->wallIdx, c->wallMat, primTop(c->wallType, c->wallIdx) - fl, vis, rise);
  evN[0]++;
}
static void edgeEvent(int id, int tick, int why, float v) {
  Car *c = &fleet[id].c; float vx = c->vel[0], vz = c->vel[2], l = hypotf(vx, vz); if (l < 1e-3f) { vx = sinf(c->h); vz = cosf(c->h); l = 1; }
  vx /= l; vz /= l;
  float ax = c->x + vx * 1.f, az = c->z + vz * 1.f, g = renderGround(ax, az, c->y + 1.5f);
  int vis = g > c->y - 1.5f; float rise = g > -1e8f ? g - c->y : -9.f;
  emit(id, tick, why & 16 ? 1 : why & 32 ? 2 : 3, v, c->x, c->y, c->z, -vx, -vz, -1, 0, 0, NAN, vis, rise);
  evN[why & 16 ? 1 : why & 32 ? 2 : 3]++;
}
static void step(int id, int tick, int epTick) {
  Driver *d = &fleet[id]; Car *c = &d->c;
  rng = d->random; CarInput in; botStep(&d->b, c, &in, epTick / 60.f); d->random = rng;
  float v0 = hypotf(c->vel[0], c->vel[2]), x0 = c->x, z0 = c->z; int rev = c->reverts;
  carUpdate(c, &W, &in, 1.f / 60); distAll += hypotf(c->x - x0, c->z - z0);
  if (epTick < 60) { d->lastT = tick; d->lastType = c->wallType; d->lastIdx = c->wallIdx; d->lastEdge = tick; return; }   // первая секунда: старт на скорости, не езда
  if (c->wallV > VMIN && c->wallMat == COL_MAT_HARD) {
    int same = c->wallType == d->lastType && c->wallIdx == d->lastIdx && tick - d->lastT < 60;
    if (!same) wallEvent(id, tick);
    d->lastT = tick; d->lastType = c->wallType; d->lastIdx = c->wallIdx;
  }
  if (c->reverts > rev && (c->revWhy & (1 | 16 | 32)) && v0 > VMIN && tick - d->lastEdge >= 60) { edgeEvent(id, tick, c->revWhy, v0); d->lastEdge = tick; }
}

#ifndef WALLS_LIBRARY
#ifndef WALLS_NO_MAIN   // ledge.c подключает этот файл целиком (загрузчики, рисуемая геометрия)
int main(int argc, char **argv) {
  const char *level = 0, *road = 0; float secs = 60, episode = 30; int repCar = -1, repEpoch = 0;
  for (int i = 1; i < argc; i++) {
    if (!strcmp(argv[i], "--level") && i + 1 < argc) level = argv[++i];
    else if (!strcmp(argv[i], "--roads") && i + 1 < argc) road = argv[++i];
    else if (!strcmp(argv[i], "--cars") && i + 1 < argc) fleetN = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--seed") && i + 1 < argc) seed = (uint32_t)strtoul(argv[++i], 0, 10);
    else if (!strcmp(argv[i], "--secs") && i + 1 < argc) secs = atof(argv[++i]);
    else if (!strcmp(argv[i], "--episode") && i + 1 < argc) episode = atof(argv[++i]);
    else if (!strcmp(argv[i], "--vmin") && i + 1 < argc) VMIN = atof(argv[++i]);
    else if (!strcmp(argv[i], "--area") && i + 4 < argc) { areaOn=1; for(int k=0;k<4;k++) area[k]=atof(argv[++i]); }
    else if (!strcmp(argv[i], "--static-only")) staticOnly=1;
    else if (!strcmp(argv[i], "--raw")) RAW = 1;
    else if (!strcmp(argv[i], "--hide") && i + 3 < argc) { HIDE[0] = atof(argv[++i]); HIDE[1] = atof(argv[++i]); HIDE[2] = atof(argv[++i]); }
    else if (!strcmp(argv[i], "--replay") && i + 2 < argc) { repCar = atoi(argv[++i]); repEpoch = atoi(argv[++i]); }
    else { fprintf(stderr, "unknown argument %s\n", argv[i]); return 2; }
  }
  if (!level || !road || fleetN < 1) { fprintf(stderr, "usage: walls --level L --roads R [--seed S --cars N --secs T]\n"); return 2; }
  loadLevel(level); loadRoads(road); loadProps(); loadRender(); makeStarts();
  fprintf(stderr, "walls: рисуемых треугольников %u, стартов %d, предметов %u\n", NT, nstart, nProp);
  int epT = (int)(episode * 60), ticks = (int)(secs * 60);
  if (repCar >= 0) {   // повтор одной машины одной эпохи: те же события, что в рое (машины друг друга не видят)
    fleetN = repCar + 1; fleet = calloc(fleetN, sizeof(Driver));
    if (!spawn(repCar, repEpoch)) return 3;
    RAW = 1; for (int t = 0; t < epT; t++) step(repCar, repEpoch * epT + t + 1, t);
    return 0;
  }
  fleet = calloc(fleetN, sizeof(Driver));
  for (int i = 0; i < fleetN; i++) if (!spawn(i, 0)) { fprintf(stderr, "spawn failed %d\n", i); return 3; }
  double t0 = now();
  for (int tick = 1; tick <= ticks; tick++) {
    int et = (tick - 1) % epT;
    if (et == 0 && tick > 1) for (int i = 0; i < fleetN; i++) if (!spawn(i, fleet[i].epoch + 1)) return 3;
    for (int i = 0; i < fleetN; i++) step(i, tick, et);
  }
  carSec = (double)fleetN * ticks / 60.;
  for (int h = 0; h < NCL; h++) if (cl[h].n) { Cl *c = &cl[h];
    printf("cl\t%s\t%d\t%u\t%ld\t%ld\t%ld\t%ld\t%.2f\t%.2f\t%u\t%d\t%d\t%d\t%.2f\t%.2f\t%.2f\t%.3f\t%.3f\t%.2f\t%.2f\t%ld\t%d\t%d\t%d\n", KIND[c->kind], c->pt, c->pi,
           c->n, c->nvis, c->nflat, c->nprop, c->vsum, c->vmax, seed, c->car, c->epoch, c->tick, c->x, c->y, c->z, c->nx, c->nz, c->top, c->rise,
           c->nNat, c->nNat ? c->carN : -1, c->epochN, c->tickN); }
  printf("st\t%u\t%d\t%.0f\t%.1f\t%ld\t%ld\t%ld\t%ld\n", seed, fleetN, carSec, distAll / 1000., evN[0], evN[1], evN[2], evN[3]);
  fprintf(stderr, "walls: seed %u машино-секунд %.0f (проехали %.0f км) за %.1f с; wall %ld edge16 %ld edge32 %ld push1 %ld\n", seed, carSec, distAll / 1000., now() - t0, evN[0], evN[1], evN[2], evN[3]);
  return 0;
}

#endif /* WALLS_LIBRARY */

#endif
