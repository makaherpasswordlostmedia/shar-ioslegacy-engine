// Гейт правки Роба 328 (04.10: «машины NPC иногда появляются внезапно прямо передо мной на дороге — убрать; пусть тупят, но не
// настолько, чтобы мешать»). Замер на Маке по настоящим данным уровня (build/levels/l<N>/level.shr COL1 + traffic.shr TRF1):
// игрок едет по дорогам уровня (тот же водитель полос, что у трафика, быстрее в K раз; «призрак» — трафик об него не бьётся),
// камера за машиной (кадр порта: 62° по вертикали, 16:9; пружина курса с отставанием до 0,5 рад, как chaseCamUpdate),
// кадр за кадром тот же порядок, что main.c: машина игрока -> trafficUpdate с камерой ПРОШЛОГО кадра -> камера этого кадра.
// Рождение машины трафика (слот был выключен, стал включён) проверяется по камере, которая рисует кадр рождения:
// сфера кузова (carR) в пирамиде кадра и ближе дальности рисования машин (drawDist 90 м) — «родилась на глазах».
// Заслонение домами не учитывается (запас: гейт требует ноль даже для машин, рождённых за домом в кадре).
// Ситуации: езда (K = 1; 1,5; 2), сброс трафика (NEW GAME / телепорт goto: первые 2 с), перенос игрока сценарием БЕЗ сброса
// (телепорт миссии: камера ещё старая на кадре переноса, скан трафика в этот кадр — худший случай).
// Плотность: машин в пуле в среднем, машин ближе 60 м от игрока, машин в кадре ближе 90 м.
//   tests/traffic/spawnview.sh  (все 7 уровней, красный — прежнее правило trfSpawnOld = 1, зелёный — новое)
//   spawnview level.shr traffic.shr [old] [секунд на прогон]
#include "../../viewer/traffic.c"   // целиком: водитель полос (driveStep) и помощники полос — статические

static ColWorld world; static Traffic T;
static const float DT = 1.f / 60.f;
static const float TAN_V = 0.60086f;              // tan(31°): FOVY 62 (viewer/main.c)
static const float TAN_H = 0.60086f * 16.f / 9.f;  // ASPECT 16:9
static const float BACK = 8.3f, EYE_H = 2.8f, TGT_F = 3.f, TGT_H = 1.2f;   // камера за машиной L1 (famil_v, правка 198+)

static unsigned char *readAt(FILE *f, unsigned off, unsigned sz) {
  unsigned char *m = aligned_alloc(64, (sz + 63) & ~63u);
  fseek(f, off, SEEK_SET); if (fread(m, 1, sz, f) != sz) { free(m); return 0; }
  return m;
}
typedef struct { float yaw, yawV; int init; float eye[3], fwd[3]; } Cam;
static void camStep(Cam *c, const Car *k, float dt) {
  float ty = k->h;
  if (!c->init) { c->init = 1; c->yaw = ty; c->yawV = 0.f; }
  else { float e = wrapPi(c->yaw - ty), ev = c->yawV, w = 6.f, x = e, v = ev, kk = expf(-w * dt), cc = v + w * x;
    e = (x + cc * dt) * kk; ev = (v - w * cc * dt) * kk;
    if (e > .5f) { e = .5f; if (ev > 0) ev = 0; } if (e < -.5f) { e = -.5f; if (ev < 0) ev = 0; }
    c->yaw = wrapPi(ty + e); c->yawV = ev; }
  c->eye[0] = k->x - sinf(c->yaw) * BACK; c->eye[2] = k->z - cosf(c->yaw) * BACK; c->eye[1] = k->y + EYE_H;
  float L[3] = {k->x + sinf(c->yaw) * TGT_F, k->y + TGT_H, k->z + cosf(c->yaw) * TGT_F}, f[3], l;
  for (int i = 0; i < 3; i++) f[i] = L[i] - c->eye[i];
  l = sqrtf(f[0] * f[0] + f[1] * f[1] + f[2] * f[2]); for (int i = 0; i < 3; i++) c->fwd[i] = f[i] / l;
}
// сфера (p, R) в пирамиде кадра камеры c и ближе дальности рисования; *dist — от глаза, *ang — от оси кадра, °
static int inFrame(const Cam *c, const float p[3], float R, float drawDist, float *dist, float *ang) {
  float v[3] = {p[0] - c->eye[0], p[1] - c->eye[1], p[2] - c->eye[2]}, d = sqrtf(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]);
  const float *f = c->fwd; float hl = sqrtf(f[0] * f[0] + f[2] * f[2]);
  float r[3] = {f[2] / hl, 0.f, -f[0] / hl}, u[3] = {r[1] * f[2] - r[2] * f[1], r[2] * f[0] - r[0] * f[2], r[0] * f[1] - r[1] * f[0]};
  float z = v[0] * f[0] + v[1] * f[1] + v[2] * f[2], x = v[0] * r[0] + v[2] * r[2], y = v[0] * u[0] + v[1] * u[1] + v[2] * u[2];
  if (dist) *dist = d; if (ang) *ang = acosf(fmaxf(-1.f, fminf(1.f, z / fmaxf(d, 1e-3f)))) * 57.2958f;
  if (d - R > drawDist) return 0;
  if (z < -R) return 0;
  if (fabsf(x) - z * TAN_H > R * sqrtf(1.f + TAN_H * TAN_H)) return 0;
  if (fabsf(y) - z * TAN_V > R * sqrtf(1.f + TAN_V * TAN_V)) return 0;
  return 1;
}
typedef struct {
  double sec, poolSum, near60Sum, frameSum; long frames;
  int spawns, vis, vis30, vis60, freshSpawns, freshVis, tpSpawns, tpVis, tpN, resets, jumps;
  float visMin, freshMin, tpMin;
} St;
static void stInit(St *s) { memset(s, 0, sizeof *s); s->visMin = s->freshMin = s->tpMin = 1e9f; }
static void stAdd(St *a, const St *b) {
  a->sec += b->sec; a->poolSum += b->poolSum; a->near60Sum += b->near60Sum; a->frameSum += b->frameSum; a->frames += b->frames;
  a->spawns += b->spawns; a->vis += b->vis; a->vis30 += b->vis30; a->vis60 += b->vis60; a->freshSpawns += b->freshSpawns;
  a->freshVis += b->freshVis; a->tpSpawns += b->tpSpawns; a->tpVis += b->tpVis; a->tpN += b->tpN; a->resets += b->resets; a->jumps += b->jumps;
  a->visMin = fminf(a->visMin, b->visMin); a->freshMin = fminf(a->freshMin, b->freshMin); a->tpMin = fminf(a->tpMin, b->tpMin);
}
static unsigned pseed = 12345u;
static float prnd(void) { pseed = pseed * 1664525u + 1013904223u; return (float)(pseed >> 8) * (1.f / 16777216.f); }
// водитель игрока на случайной полосе уровня
static void placePlayer(TrCar *pd, const float *awayFrom) {
  for (int tries = 0; tries < 1000; tries++) {
    int r = (int)(prnd() * T.hd->nRoad) % (int)T.hd->nRoad; if (!roadOk(&T, r) || !T.road[r].lanes) continue;
    int l = (int)(prnd() * T.road[r].lanes) % T.road[r].lanes; float L = laneLen(&T, r, l); if (L < 30.f) continue;
    float s = prnd() * (L - 20.f), p[3], a[3]; lanePos(&T, r, l, s, p);
    if (awayFrom) { float dx = p[0] - awayFrom[0], dz = p[2] - awayFrom[2]; if (dx * dx + dz * dz < 200.f * 200.f) continue; }
    lanePos(&T, r, l, s + LOOK, a);
    int model = T.slot[0].model; memset(pd, 0, sizeof *pd); pd->model = model; pd->road = r; pd->lane = l; pd->s = s; pd->junc = -1;
    carInit(&pd->car, &T.params[model], &world, p[0], p[1], p[2], atan2f(a[0] - p[0], a[2] - p[2]));
    pd->mode = TRM_DRIVE; pd->v = 10.f; return;
  }
}
// один прогон: secs секунд езды со скоростью K; перенос игрока БЕЗ сброса каждые tpEvery с (0 — нет)
static void run(St *S, float K, float secs, unsigned seed, float tpEvery) {
  TrCar pd; Cam cam; memset(&cam, 0, sizeof cam);
  pseed = seed * 2654435761u + 1u; placePlayer(&pd, 0);
  trafficReset(&T, &world); T.seed = seed * 7919u + 17u; S->resets++;
  camStep(&cam, &pd.car, DT);
  Cam prev = cam; float stuck = 0.f, sinceReset = 0.f, sinceTp = 1e9f, tpT = tpEvery;
  float lastPos[TR_MAXCAR][2]; int lastVis[TR_MAXCAR]; memset(lastVis, 0, sizeof lastVis);
  int nf = (int)(secs / DT);
  for (int f = 0; f < nf; f++) {
    int tp = 0;
    if (tpEvery > 0.f && (tpT -= DT) <= 0.f) { tpT = tpEvery; tp = 1; }
    if (stuck > 3.f) { tp = 2; stuck = 0.f; }   // водитель игрока встал (тупик, стоящая машина) — перенос (в счёт переносов не идёт)
    if (tp) { float at[3] = {pd.car.x, pd.car.y, pd.car.z}; placePlayer(&pd, at); cam.init = 0; if (tp == 1) { T.scanT = 0.f; sinceTp = 0.f; S->tpN++; } }
    // водитель игрока: шаг dt*K (скорость в K раз выше трафика), своё зерно (случайность трафика не трогает)
    { unsigned sv = T.seed; T.seed = pseed; driveStep(&T, &world, &pd, 0, 0, DT * K); pseed = T.seed; T.seed = sv; }
    stuck = pd.v < .1f ? stuck + DT : 0.f;
    Car pl = pd.car; for (int i = 0; i < 3; i++) pl.vel[i] *= K; pl.v *= K; pl.y -= 100.f;   // призрак: трафик тормозит, но не бьётся
    float pp[3] = {pd.car.x, pd.car.y, pd.car.z};
    int was[TR_MAXCAR]; for (int i = 0; i < T.maxCars; i++) was[i] = T.car[i].mode;
    trafficUpdate(&T, &world, &pl, 1, pp, prev.eye, prev.fwd, DT);   // камера прошлого кадра (как main.c)
    TrEvent e; while (trafficPopEvent(&T, &e)) {}
    camStep(&cam, &pd.car, DT);   // камера этого кадра: она и рисует рождённую машину
    sinceReset += DT; sinceTp += DT;
    int near60 = 0, inF = 0;
    for (int i = 0; i < T.maxCars; i++) {
      const TrCar *c = &T.car[i]; if (c->mode == TRM_OFF) { lastVis[i] = 0; continue; }
      float p[3] = {c->car.x, c->car.y + 1.f, c->car.z}, d, a, dx = c->car.x - pp[0], dz = c->car.z - pp[2];
      int v = inFrame(&cam, p, carR(&c->car), T.drawDist, &d, &a);
      near60 += dx * dx + dz * dz < 60.f * 60.f; inF += v;
      if (was[i] == TRM_OFF) {   // родилась в этот кадр
        int fresh = sinceReset < 2.f, tpw = sinceTp < 1.f;
        if (fresh) { S->freshSpawns++; if (v) { S->freshVis++; S->freshMin = fminf(S->freshMin, d); } }
        else if (tpw) { S->tpSpawns++; if (v) { S->tpVis++; S->tpMin = fminf(S->tpMin, d); } }
        else { S->spawns++; if (v) { S->vis++; S->vis30 += d < 30.f; S->vis60 += d < 60.f; S->visMin = fminf(S->visMin, d);
            if (getenv("SV_VERBOSE")) printf("    VIS t=%.2f d=%.1f ang=%.0f car=%.1f,%.1f player=%.1f,%.1f dp=%.1f\n", f * DT, d, a, c->car.x, c->car.z, pp[0], pp[2], sqrtf(dx * dx + dz * dz)); } }
      } else if (lastVis[i] && v) {   // видимая машина прыгнула (возврат на полосу и т. п.) — для сведения
        float jx = c->car.x - lastPos[i][0], jz = c->car.z - lastPos[i][1]; if (jx * jx + jz * jz > 2.f * 2.f) S->jumps++;
      }
      lastPos[i][0] = c->car.x; lastPos[i][1] = c->car.z; lastVis[i] = v;
    }
    if (sinceReset >= 2.f && sinceTp >= 1.f) { S->poolSum += T.activeCars; S->near60Sum += near60; S->frameSum += inF; S->frames++; }
    prev = cam;
  }
  S->sec += secs;
}
int main(int argc, char **argv) {
  if (argc < 3) { printf("usage: spawnview level.shr traffic.shr [old] [secs]\n"); return 2; }
  FILE *f = fopen(argv[1], "rb"); if (!f) { printf("no %s\n", argv[1]); return 2; }
  unsigned char hdr[104]; if (fread(hdr, 1, 104, f) != 104 || memcmp(hdr, "SHR7", 4)) { printf("bad level\n"); return 2; }
  unsigned pvsOff = *(unsigned *)(hdr + 88), colOff = *(unsigned *)(hdr + 92), propOff = *(unsigned *)(hdr + 96);
  fseek(f, 0, SEEK_END); unsigned fsize = (unsigned)ftell(f);
  unsigned end = fsize; if (pvsOff > colOff && pvsOff < end) end = pvsOff; if (propOff > colOff && propOff < end) end = propOff;
  unsigned char *cm = readAt(f, colOff, end - colOff); fclose(f);
  if (!cm || colInit(&world, cm, end - colOff)) { printf("COL1 failed\n"); return 2; }
  FILE *g = fopen(argv[2], "rb"); if (!g) { printf("no %s\n", argv[2]); return 2; }
  fseek(g, 0, SEEK_END); unsigned tsize = (unsigned)ftell(g); unsigned char *buf = readAt(g, 0, tsize); fclose(g);
  if (trafficInitMem(&T, buf, tsize, 0)) { printf("TRF1 failed\n"); return 2; }
  trfSpawnOld = argc > 3 ? atoi(argv[3]) : 0;
  float secs = argc > 4 ? (float)atof(argv[4]) : 120.f;
  static const float Ks[3] = {1.f, 1.5f, 2.f};
  St all; stInit(&all);
  for (int k = 0; k < 3; k++) {
    St s; stInit(&s);
    for (int r = 0; r < 6; r++) { St one; stInit(&one); run(&one, Ks[k], secs, (unsigned)(k * 100 + r + 1), r % 2 ? 20.f : 0.f); stAdd(&s, &one); }
    double min = s.sec / 60.0;
    printf("  K=%.1f  %4.0f s: spawns %4d (%.1f/min)  in-frame <90m %3d (%.2f/min; <60m %d, <30m %d; nearest %.1f m)  reset: %d/%d in frame (nearest %.1f)  "
           "teleport x%d: %d/%d in frame (nearest %.1f)  pool %.2f  near60 %.2f  in-frame %.2f  jumps %d\n",
           Ks[k], s.sec, s.spawns, s.spawns / min, s.vis, s.vis / min, s.vis60, s.vis30, s.visMin < 1e8f ? s.visMin : -1.f,
           s.freshVis, s.freshSpawns, s.freshMin < 1e8f ? s.freshMin : -1.f, s.tpN, s.tpVis, s.tpSpawns, s.tpMin < 1e8f ? s.tpMin : -1.f,
           s.frames ? s.poolSum / s.frames : 0, s.frames ? s.near60Sum / s.frames : 0, s.frames ? s.frameSum / s.frames : 0, s.jumps);
    stAdd(&all, &s);
  }
  double min = all.sec / 60.0;
  printf("SPAWNVIEW %s: drive %.0f min, spawns %d, in-frame<90m %d (%.2f/min, <60m %d, <30m %d), reset in-frame %d/%d, teleport in-frame %d/%d, "
         "pool %.2f, near60 %.2f, in-frame %.2f\n", trfSpawnOld ? "OLD" : "NEW", min, all.spawns, all.vis, all.vis / min, all.vis60, all.vis30,
         all.freshVis, all.freshSpawns, all.tpVis, all.tpSpawns, all.frames ? all.poolSum / all.frames : 0, all.frames ? all.near60Sum / all.frames : 0,
         all.frames ? all.frameSum / all.frames : 0);
  printf("RESULT visible=%d reset=%d teleport=%d pool=%.3f near60=%.3f inframe=%.3f spawnsPerMin=%.2f\n", all.vis, all.freshVis, all.tpVis,
         all.frames ? all.poolSum / all.frames : 0, all.frames ? all.near60Sum / all.frames : 0, all.frames ? all.frameSum / all.frames : 0, all.spawns / min);
  return 0;
}
