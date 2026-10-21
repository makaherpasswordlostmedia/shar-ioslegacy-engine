// Гейт машин миссий с ИИ на Маке (viewer/msncar.c на настоящих данных уровня: COL1 level.shr, дороги traffic.shr, миссии
// levelNN.msn, модели msncars-l<N>.shr). Каждый этап миссий уровня, где машина получает ИИ (AddStageVehicle / ActivateVehicle
// не "NULL") и путь AddStageWaypoint, — отдельный прогон: машина одна на уровне (игрока нет — догонялка молчит), едет по
// точкам своего этапа. Погоня ("chase") — к стоящей машине игрока в 120 м по дорогам.
//   aicar_host LEVEL.shr TRAFFIC.shr LEVELNN.msn [MSNCARS.shr] [--plant-offroad] [--plant-speed K] [-v] [--case N]
// Проверки (все на настоящих данных должны пройти):
//   * точки пути этапов на дорогах: каждая AddStageWaypoint не дальше 12 м от оси полосы (дороги Road/RoadSegment диска)
//   * едет по дорогам: доля кадров дальше 6 м от оси ближней полосы <= 10% (у цели «вне дорог» — не считается)
//   * скорость по .con: доля кадров быстрее TopSpeed .con x множитель догонялки x 1.15 <= 0.5% (толчки трафика и спуски — редки)
//   * доезжает: >= 90% прогонов прошли все точки пути за отведённое время (длина пути по полосам / (0.3 TopSpeed) + 45 с), с живым
//     городом (трафик и стоящие машины traffic.shr вокруг машины миссии; --no-traffic — без них)
//   * погоня: догоняет стоящую машину игрока (ближе 8 м) за 40 с
// Отрицательные контроли (tests/aicar/host.sh): --plant-offroad (последняя точка каждого пути — в 60 м от дорог) и сборки
// -DMC_BREAK_SPEED=1 (скорость не по .con), -DMC_BREAK_ROADS=1 (дороги не используются) — каждая обязана уронить свою проверку.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "msncar.h"
#include "mission/msn.h"

static ColWorld world; static Traffic T; static MsnFile F; static int verbose, plantOff, onlyCase = -1, withTraffic = 1;
static int fails; static char failed[1024];
static const float DT = 1.f / 30.f;
static McGeo geo[64]; static int ngeo;

static void check(const char *what, float got, float lo, float hi, const char *expect) {
  int ok = got >= lo && got <= hi;
  if (!ok) { fails++; if (strlen(failed) + strlen(what) + 4 < sizeof failed) { strcat(failed, what); strcat(failed, "; "); } }
  printf("  %-4s %-56s %9.3f   (%s)\n", ok ? "ok" : "FAIL", what, got, expect);
}
static unsigned char *readFile(const char *p, unsigned *n) {
  FILE *f = fopen(p, "rb"); if (!f) return 0;
  fseek(f, 0, SEEK_END); long s = ftell(f); fseek(f, 0, SEEK_SET);
  unsigned char *b = aligned_alloc(64, ((size_t)s + 63) & ~(size_t)63);
  if (!b || fread(b, 1, (size_t)s, f) != (size_t)s) { fclose(f); free(b); return 0; }
  fclose(f); *n = (unsigned)s; return b;
}
static int loadGeo(const char *path) {   // пакет MCR1: заголовок 32 Б, каталог по 176 Б (имя 16, TrModel 128, 8 x u32)
  unsigned n; unsigned char *b = readFile(path, &n); if (!b) return -1;
  if (n < 32 || memcmp(b, "MCR1", 4)) { free(b); return -2; }
  unsigned dir = *(unsigned *)(b + 16); ngeo = dir < n ? mcGeoFromPack(b, b + dir, n - dir, geo, 64) : 0;
  free(b); mcSetGeo(geo, ngeo); return 0;
}

typedef struct { char name[16], ai[12], con[48]; float pos[3], h; int hasH; } Veh;
static Veh veh[32]; static int nveh;
static Veh *vfind(const char *n) { for (int i = 0; i < nveh; i++) if (msn_streq(veh[i].name, n)) return &veh[i]; return 0; }
static Veh *vput(const char *n) { Veh *v = vfind(n); if (!v && nveh < 32) { v = &veh[nveh++]; memset(v, 0, sizeof *v); strncpy(v->name, n, 15); } return v; }
static void setLoc(Veh *v, const MsnLoc *l) { if (!l) return; memcpy(v->pos, l->pos, 12); v->hasH = (l->flags & 1) != 0; v->h = v->hasH ? mcCarHeading(l->heading) : 0.f; }

// точка в 120 м по дорогам от p (для погони): вершина полосы ближе всего к 120 м
static int roadPoint(const float p[3], float dist, float out[3]) {
  float best = 1e30f;
  for (unsigned r = 0; r < T.hd->nRoad; r++) {
    if (T.road[r].flags & 3) continue;
    const TrPt *P = T.pt + T.road[r].firstPt;
    for (int k = 0; k < T.road[r].nPt; k++) {
      float d = hypotf(P[k].x - p[0], P[k].z - p[2]), e = fabsf(d - dist);
      if (e < best) { best = e; out[0] = P[k].x; out[1] = P[k].y; out[2] = P[k].z; }
    }
  }
  return best < 30.f;
}

static int hdTot, hdOk;
static int ncase, nfin, nchase, nchaseOk, wpTot, wpOff; static float offFrames, frames, worstSpeed, worstOffShare, fastFrames, allFrames; static char worstName[64];
static void runCase(const char *label, const Veh *v, const float wp[][3], int nwp, int laps, const float *rc, int hasRc, const float *tc, int hasTc, int skLo, int skHi, int hasSk) {
  int idx = ncase++;
  if (onlyCase >= 0 && idx != onlyCase) return;
  MsnCars m; mcInit(&m);
  McCar *c = mcSpawn(&m, &world, &T, v->name, v->pos, v->h, v->hasH, v->ai, v->con, "");
  if (!c) return;
  if (hasRc) mcCatchup(&m, v->name, 0, rc, 4); if (hasTc) mcCatchup(&m, v->name, 1, tc, 2); if (hasSk) mcParams(&m, v->name, skLo, skHi);
  Car player; memset(&player, 0, sizeof player); int chase = c->mode == MC_CHASE;
  McEnv e; memset(&e, 0, sizeof e); e.w = &world; e.tr = &T;
  float pp[3] = {1e6f, 0, 1e6f};
  if (chase) {
    if (!roadPoint(v->pos, 120.f, pp)) return;
    carInit(&player, 0, &world, pp[0], pp[1] + .5f, pp[2], 0.f); e.player = &player; e.driving = 1;
    memcpy(e.ppos, pp, 12);
  } else {
    for (int i = 0; i < nwp; i++) mcWaypoint(&m, i, wp[i], laps);
    memcpy(e.ppos, pp, 12);
  }
  // длина пути по дорогам (маршрут по полосам от точки к точке, как у ИИ), а не по прямой
  static float rt[1024][3]; float len = 0.f, prev[3], ph = v->hasH ? v->h : 0.f; memcpy(prev, v->pos, 12);
  for (int l = 0; l < laps; l++) for (int i = 0; i < nwp; i++) {
    int off, k = mcPlan(&T, prev[0], prev[1], prev[2], ph, wp[i], 1, rt, 1024, &off); float q[3]; memcpy(q, prev, 12);
    for (int j = 0; j < k; j++) { len += hypotf(rt[j][0] - q[0], rt[j][2] - q[2]); memcpy(q, rt[j], 12); }
    if (k >= 2) ph = atan2f(rt[k - 1][0] - rt[k - 2][0], rt[k - 1][2] - rt[k - 2][2]);
    memcpy(prev, wp[i], 12); }
  float top = c->baseTop, maxMult = hasRc ? fmaxf(fmaxf(rc[1], rc[2]), rc[3]) : 1.f;
  if (c->mode == MC_EVADE) maxMult *= 1.15f;
  float budget = chase ? 40.f : len / fmaxf(3.f, .3f * top) + 45.f, t = 0.f, vmax = 0.f, off = 0.f, fr = 0.f, closest = 1e9f, fast = 0.f;
  int done = 0;
  if (withTraffic) trafficReset(&T, &world);   // живой город: стоящие машины на местах, трафик вокруг машины миссии
  for (; t < budget && !done; t += DT) {
    mcUpdate(&m, &e, DT, 0, 0);
    if (withTraffic) { mcTrafficSees(&m, &T); Car *k = &c->car; float pp[3] = {k->x, k->y, k->z}, ey[3] = {k->x - sinf(k->h) * 7.f, k->y + 3.f, k->z - cosf(k->h) * 7.f}, fw[3] = {sinf(k->h), 0.f, cosf(k->h)};
      trafficUpdate(&T, &world, chase ? &player : 0, chase, chase ? pp : pp, ey, fw, DT); TrEvent te; while (trafficPopEvent(&T, &te)) {} T.nextra = 0; }
    Car *k = &c->car; float sp = sqrtf(k->vel[0] * k->vel[0] + k->vel[2] * k->vel[2]);
    if (sp > vmax) vmax = sp;
    fast += sp > 1.15f * top * maxMult;   // быстрее TopSpeed .con x догонялка (толчок трафика, спуск — редкие кадры)
    int nearOffGoal = 0;   // у точки «вне дорог» — не считается (её проверяет отдельная проверка точек)
    for (int i = 0; i < nwp; i++) if (mcLaneDist(&T, wp[i][0], wp[i][2]) > 12.f && hypotf(wp[i][0] - k->x, wp[i][2] - k->z) < 40.f) nearOffGoal = 1;
    if (!nearOffGoal) { fr++; if (mcLaneDist(&T, k->x, k->z) > 6.f) off++; }
    if (chase) { float d = hypotf(k->x - player.x, k->z - player.z); if (d < closest) closest = d; if (d < 8.f) done = 1; }
    else if (c->finished) done = 1;
    if (verbose && ((int)(t / DT)) % (verbose > 1 ? 6 : 90) == 0)
      printf("    t=%5.1f %s h %.2f pos %.1f %.1f %.1f v %.1f vt %.1f wp %d/%d route %d seg %d off %.1f lane %.1f stuck %d resets %u dmg %.2f prog %.1f avoid %d gap %.1f sw %.1f k%d\n", t, c->name, k->h, k->x, k->y, k->z,
             k->v, c->vt, c->wp, m.nwp * m.laps, c->nroute, c->seg, c->offLane, mcLaneDist(&T, k->x, k->z), c->stuckN, c->resets, k->damage, c->progT, c->navoid, c->dbgGap, c->dbgSwerve, c->dbgKind);
  }
  float share = fr > 0.f ? off / fr : 0.f, ratio = vmax / fmaxf(1.f, top * maxMult);
  fastFrames += fast; allFrames += t / DT;
  offFrames += off; frames += fr;
  if (ratio > worstSpeed) worstSpeed = ratio;
  if (share > worstOffShare) { worstOffShare = share; snprintf(worstName, sizeof worstName, "%s %s", label, v->name); }
  if (chase) { nchase++; nchaseOk += done; } else nfin += done;
  printf("  %-3d %-18s %-9s %-8s wp %2d x%d  %s %6.1f s (бюджет %5.1f)  путь %5.0f м  вне полос %4.1f%%  v/TopSpeed %.2f  возвратов %u%s\n", idx, label, v->name,
         v->ai, nwp, laps, done ? (chase ? "догнал " : "доехал ") : (chase ? "НЕ ДОГНАЛ" : "НЕ ДОЕХАЛ"), t, budget, len, share * 100.f, ratio, c->resets,
         chase ? "" : (c->offroad ? "  (цель вне дорог)" : ""));
  if (chase && !done && verbose) printf("       ближе всего %.1f м\n", closest);
}

int main(int argc, char **argv) {
  if (argc < 4) { fprintf(stderr, "usage: aicar_host LEVEL.shr TRAFFIC.shr LEVELNN.msn [MSNCARS.shr] [--plant-offroad] [-v] [--case N]\n"); return 2; }
  const char *geoPath = 0;
  for (int i = 4; i < argc; i++) {
    if (!strcmp(argv[i], "--plant-offroad")) plantOff = 1;
    else if (!strcmp(argv[i], "-v")) verbose = 1; else if (!strcmp(argv[i], "-vv")) verbose = 2;
    else if (!strcmp(argv[i], "--case") && i + 1 < argc) onlyCase = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--no-traffic")) withTraffic = 0;
    else geoPath = argv[i];
  }
  unsigned n; unsigned char *lvl = readFile(argv[1], &n);
  if (!lvl || n < 104 || memcmp(lvl, "SHR7", 4)) { fprintf(stderr, "нет level.shr\n"); return 2; }
  unsigned pv = *(unsigned *)(lvl + 88), co = *(unsigned *)(lvl + 92), po = *(unsigned *)(lvl + 96), ce = n;
  if (po > co && po < ce) ce = po; if (pv > co && pv < ce) ce = pv;
  if (colInit(&world, lvl + co, ce - co)) { fprintf(stderr, "COL1 не читается\n"); return 2; }
  if (trafficLoad(&T, argv[2])) { fprintf(stderr, "traffic.shr не читается\n"); return 2; }
  unsigned mn; unsigned char *mp = readFile(argv[3], &mn); char err[160];
  if (!mp || msn_open(&F, mp, mn, err, sizeof err)) { fprintf(stderr, "миссии: %s\n", mp ? err : "нет файла"); return 2; }
  if (geoPath && loadGeo(geoPath)) fprintf(stderr, "модели %s не читаются — кузова famil_v / трафика\n", geoPath);
  printf("машины миссий с ИИ, уровень %u: %u миссий, моделей в пакете %d%s\n", F.hdr->level, F.nmissions, ngeo, plantOff ? " [ПОДБРОС: точка пути вне дорог]" : "");
  for (unsigned mi = 0; mi < F.nmissions; mi++) {
    const MsnMission *M = &F.missions[mi]; nveh = 0;
    for (int ph = 0; ph < 2; ph++) {
      unsigned pidx = ph ? M->main : M->intro; if (pidx == MSN_NONE16) continue;
      const MsnPhase *P = &F.phases[pidx];
      for (unsigned s = 0; s < P->stage_count; s++) {
        const MsnStage *S = &F.stages[P->first_stage + s];
        float wp[MC_WP][3]; int nwp = 0, laps = 1; char act[MC_MAX][16]; int nact = 0;
        const MsnLoc *hs[8], *pstart = 0, *pfirst = 0; int nhs = 0;   // курс старта: машины этапа и игрок (PlacePlayerCar)
        float rc[8][4], tc[8][2]; int hasRc[8] = {0}, hasTc[8] = {0}, sk[8][2], hasSk[8] = {0};
        for (unsigned i = 0; i < S->cmd_count; i++) {
          const MsnCmd *c = &F.cmds[S->cmd_first + i];
          const char *a0 = msn_arg_s(&F, c, 0);
          switch (c->op) {
            case MSN_OP_ADDSTAGEVEHICLE: { Veh *v = vput(a0); if (!v) break; setLoc(v, msn_arg_loc(&F, c, 1)); if (nhs < 8) hs[nhs++] = msn_arg_loc(&F, c, 1);
              snprintf(v->ai, sizeof v->ai, "%s", msn_arg_s(&F, c, 2)); snprintf(v->con, sizeof v->con, "%s", msn_arg_s(&F, c, 3));
              if (mcMode(v->ai) != MC_PARKED && nact < MC_MAX) snprintf(act[nact++], 16, "%s", a0); break; }
            case MSN_OP_ACTIVATEVEHICLE: { Veh *v = vfind(a0); if (!v) break; setLoc(v, msn_arg_loc(&F, c, 1));
              snprintf(v->ai, sizeof v->ai, "%s", msn_arg_s(&F, c, 2)); if (mcMode(v->ai) != MC_PARKED && nact < MC_MAX) snprintf(act[nact++], 16, "%s", a0); break; }
            case MSN_OP_ADDSTAGEWAYPOINT: { const MsnLoc *l = msn_arg_loc(&F, c, 0); if (l && nwp < MC_WP) { memcpy(wp[nwp], l->pos, 12); nwp++; } break; }
            case MSN_OP_PLACEPLAYERCAR: pstart = msn_arg_loc(&F, c, 1); break;
            case MSN_OP_ADDCOLLECTIBLE: if (!pfirst) pfirst = msn_arg_loc(&F, c, 0); break;
            case MSN_OP_SETRACELAPS: laps = msn_arg_i(&F, c, 0) > 0 ? msn_arg_i(&F, c, 0) : 1; break;
            case MSN_OP_SETSTAGEAIRACECATCHUPPARAMS: for (int k = 0; k < nact; k++) if (msn_streq(act[k], a0)) { for (int j = 0; j < 4; j++) rc[k][j] = msn_arg_f(&F, c, j + 1); hasRc[k] = 1; } break;
            case MSN_OP_SETSTAGEAITARGETCATCHUPPARAMS: for (int k = 0; k < nact; k++) if (msn_streq(act[k], a0)) { tc[k][0] = msn_arg_f(&F, c, 1); tc[k][1] = msn_arg_f(&F, c, 2); hasTc[k] = 1; } break;
            case MSN_OP_SETVEHICLEAIPARAMS: for (int k = 0; k < nact; k++) if (msn_streq(act[k], a0)) { sk[k][0] = msn_arg_i(&F, c, 1); sk[k][1] = msn_arg_i(&F, c, 2); hasSk[k] = 1; } break;
            default: break;
          }
        }
        // курс старта (mcCarHeading): машина этапа смотрит на первую точку своего пути, игрок — на первую точку гонки (±90°)
        for (int k = 0; k <= nhs; k++) {
          const MsnLoc *a = k < nhs ? hs[k] : pstart; const float *b = k < nhs ? (nwp ? wp[0] : 0) : (pfirst ? pfirst->pos : 0);
          if (!a || !b || !(a->flags & 1) || hypotf(b[0] - a->pos[0], b[2] - a->pos[2]) < 20.f) continue;
          float want = atan2f(b[0] - a->pos[0], b[2] - a->pos[2]), e = fabsf(remainderf(mcCarHeading(a->heading) - want, 6.2831853f));
          // ОСТАТОК 09.10 п. 12: на L7 решётки sr2/sr3 стоят курсом данных вдоль улицы (+z, по полосе), а первая точка — в 400 м
          // наискосок за кварталом: по прямой «мимо», по дорогам — по ходу. Мера: курс смотрит на первую точку по прямой ИЛИ на путь
          // по дорогам (точка маршрута mcPlan в 15 м пути). HD_DIRECT_OLD=1 — прежняя мера (только по прямой)
          float er = 9.f;
#ifndef HD_DIRECT_OLD
          { static float rt[512][3]; int roff, n = mcPlan(&T, a->pos[0], a->pos[1], a->pos[2], mcCarHeading(a->heading), b, 1, rt, 512, &roff);
            float acc = 0.f, q[3]; memcpy(q, a->pos, 12);
            for (int j = 0; j < n; j++) { acc += hypotf(rt[j][0] - q[0], rt[j][2] - q[2]); memcpy(q, rt[j], 12);
              if (acc >= 15.f) { er = fabsf(remainderf(mcCarHeading(a->heading) - atan2f(rt[j][0] - a->pos[0], rt[j][2] - a->pos[2]), 6.2831853f)); break; } } }
#endif
          hdTot++; if (e < 1.5708f || er < 1.5708f) hdOk++;
          else if (verbose) printf("  старт смотрит мимо пути: %s %s (по прямой %.0f°, по дорогам %.0f°)\n", msn_str(&F, M->id), msn_str(&F, a->name), e * 57.3f, er * 57.3f);
        }
        if (plantOff && nwp) {   // подброс: последняя точка — в 60 м от дорог (сдвиг поперёк, пока не уйдёт от полос)
          for (float d = 60.f; d < 400.f; d += 10.f) {
            float x = wp[nwp - 1][0] + d, z = wp[nwp - 1][2] + d * .5f;
            if (mcLaneDist(&T, x, z) > 60.f) { wp[nwp - 1][0] = x; wp[nwp - 1][2] = z; break; }
          }
        }
        for (int i = 0; i < nwp; i++) { wpTot++; if (mcLaneDist(&T, wp[i][0], wp[i][2]) > 12.f) { wpOff++; if (verbose) printf("  точка пути вне дорог: %s этап %u #%d (%.0f, %.0f) — %.1f м\n", msn_str(&F, M->id), s, i, wp[i][0], wp[i][2], mcLaneDist(&T, wp[i][0], wp[i][2])); } }
        for (int k = 0; k < nact; k++) {
          Veh *v = vfind(act[k]); if (!v) continue;
          if (mcMode(v->ai) != MC_CHASE && !nwp) continue;
          char label[32]; snprintf(label, sizeof label, "%s/%s.%u", msn_str(&F, M->id), ph ? "main" : "sd", s);
          runCase(label, v, (const float (*)[3])wp, nwp, laps, rc[k], hasRc[k], tc[k], hasTc[k], sk[k][0], sk[k][1], hasSk[k]);
        }
      }
    }
  }
  printf("итог: прогонов по точкам %d, доехали %d; погонь %d, догнали %d; точек пути %d, вне дорог %d\n", ncase - nchase, nfin, nchase, nchaseOk, wpTot, wpOff);
  if (onlyCase >= 0) return 0;
  check("точки пути этапов вне дорог (> 12 м от полосы), доля", wpTot ? (float)wpOff / wpTot : 0.f, 0.f, 0.f, "0: путь ИИ задан по дорогам");
  check("старт смотрит на первую точку пути или путь по дорогам (±90°), доля", hdTot ? (float)hdOk / hdTot : 0.f, .9f, 1.f, ">= 90%: курс машины CarStart + π");
  check("кадры дальше 6 м от оси полос, доля (все прогоны)", frames > 0.f ? offFrames / frames : 1.f, 0.f, .10f, "<= 10%: едет по дорогам");
  check("кадры быстрее TopSpeed .con x догонялка x 1.15, доля", allFrames > 0.f ? fastFrames / allFrames : 1.f, 0.f, .005f, "<= 0.5%: скорость по .con");
  printf("  (наибольшая скорость / TopSpeed x догонялка за все прогоны: %.2f — толчок трафика, спуск)\n", worstSpeed);
  check("доехали до конца пути, доля прогонов", ncase - nchase ? (float)nfin / (ncase - nchase) : 0.f, .9f, 1.f, ">= 90% за длину/(0.3 TopSpeed)+45 с");
  if (nchase) check("погони: догнал за 40 с, доля", (float)nchaseOk / nchase, .9f, 1.f, ">= 90%");
  printf("худший по полосам: %s (%.1f%%)\n", worstName, worstOffShare * 100.f);
  printf("RESULT: %s%s\n", fails ? "FAIL: " : "PASS", failed);
  return fails ? 1 : 0;
}
