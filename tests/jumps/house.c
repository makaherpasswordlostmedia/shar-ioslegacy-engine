unsigned homerSolidFrame;
// Правки Роба 247 («слишком сильный перепрыг у дома») и 353 («нос в конце полёта макает вниз — как у PS2»), 09.10: перепрыг дома J10
// с трамплина jumpzone17 против записей PS2 80 / 90 / 100 км/ч накатом (эталон tests/jumps/house_ps2.tsv, tests/jumps/house_ref.py).
// Порт ставится в ту же точку разгона, что и запись (место, курс, скорость), едет тем же правилом (газ, пока скорость ниже цели бота;
// накат 100 — отпустить газ в позиции кадра 146 рецепта наблюдателя и больше не нажимать; руль на линию до кромки, дальше прямо), отсчёты по
// 25 Гц, как у записи. Сравнение:
//   кромка  — скорость на кромке, ±7 % (не меньше 0,7 м/с);
//   исход   — перелетела дом (посадка за коньком, along > 14,5, ниже верха стены y < 7) или встала у ската (дальше 14 м не ушла);
//   посадка — где села за домом, ±15 % (не меньше 2 м);  встала — где стоит через 3 с после кромки, ±2 м;
//   нос     — наименьший тангаж от кромки до посадки (нос вниз в конце полёта), ±10°; тангаж перед посадкой и стоя у ската, ±15°;
//   за коньком — горизонтальная скорость на along 20 (сколько потеряла на крыше), ±15 % (не меньше 0,7 м/с).
//   tests/jumps/house.sh [level.shr] [--trace DIR]   — код выхода = число провалов
//   tests/jumps/house.sh --gate [level.shr]          — strict: все величины, без исключений
//   tests/jumps/house.sh --known-gate [level.shr]    — отдельная частичная проверка, исключения — tests/jumps/house_known.tsv
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "props.h"
#include "stateprops.h"

static Props props; static StateProps sp; static ColWorld W; static Car car; static PropState *st0;
static int onKick(void *u, unsigned i, float dx, float dz) {
  (void)u; (void)dx; (void)dz;
  int b = spBreakOf(&sp, props.def[i].type); if (b < 0) return 0;
  float pos[3] = {props.def[i].x, props.def[i].y, props.def[i].z};
  return spBreak(&sp, (unsigned)b, pos, props.def[i].q);
}
static float wrapf(float a) { while (a > 3.14159265f) a -= 6.2831853f; while (a < -3.14159265f) a += 6.2831853f; return a; }
static const float LX = 121.37f, LZ = 213.02f;   // кромка jumpzone17 (оси движка), вдоль +z

typedef struct { float vlip, land, minPitch, landPitch, stopA, stopPitch, v20; int over; } Res;
static Res runPort(float x0, float y0, float z0, float h0, float v0, float vt, float coastA, FILE *trace) {
  Res r = {-1, NAN, NAN, NAN, NAN, NAN, NAN, 0};
  memcpy(props.st, st0, sizeof(PropState) * props.ninst); props.havePreviousCar = 0; spFree(&sp); spInit(&sp, props.spr, props.sprSize);
  carInit(&car, NULL, &W, x0, y0 + 1.f, z0, h0);
  for (int k = 0; k < 10; k++) { CarInput in = {0}; carUpdate(&car, &W, &in, 1 / 60.f); }
  carSetSpeed(&car, v0);
  enum { NMAX = 10 * 60 };
  static float T[NMAX], A[NMAX], Y[NMAX], VY[NMAX], PT[NMAX];
  const float dt = 1 / 60.f; int n = 0, kLip = -1, coasting = 0;
  if (trace) fprintf(trace, "time\tx\ty\talong\tspeed\tvy\tpitch\tgrounded\twheels\tthrottle\n");
  for (int fr = 0; fr < NMAX; fr++) {
    float along = car.z - LZ;
    CarInput in = {0}; float v = hypotf(car.vel[0], car.vel[2]);
    if (along >= coastA) coasting = 1;
    in.throttle = v < vt && !coasting ? 1.f : 0.f;
    if (along < 0.f) {   // руль на точку линии в 15 м впереди (как бот оригинала)
      float tz = LZ + fminf(along, 0.f) + 15.f;
      in.steer = fmaxf(-1.f, fminf(1.f, -2.f * wrapf(atan2f(LX - car.x, tz - car.z) - car.h)));
    }
    carUpdate(&car, &W, &in, dt); propsUpdate(&props, &W, &car, dt); spUpdate(&sp, &W, &car, NULL, dt);
    if ((int)((fr + 1) * 25 / 60) == (int)(fr * 25 / 60)) continue;   // отсчёты по 0,04 с, как у записи
    T[n] = (fr + 1) * dt; A[n] = car.z - LZ; Y[n] = car.y; VY[n] = car.vel[1]; PT[n] = car.pitch * 57.2958f;
    if (kLip < 0 && A[n] >= 0.f) { kLip = n; r.vlip = hypotf(car.vel[0], car.vel[2]); }
    if (r.v20 != r.v20 && A[n] >= 20.f) r.v20 = hypotf(car.vel[0], car.vel[2]);   // скорость за коньком
    if (trace) fprintf(trace, "%.2f\t%.3f\t%.3f\t%.2f\t%.3f\t%.3f\t%.2f\t%d\t%d\t%.0f\n", T[n], car.x, car.y, A[n], hypotf(car.vel[0], car.vel[2]), car.vel[1],
                       PT[n], car.grounded, car.wheels, in.throttle);
    n++;
  }
  if (kLip < 0) return r;
  int land = -1;
  for (int k = kLip + 1; k < n; k++)
    if (A[k] > 14.5f && Y[k] < 7.f && VY[k] - VY[k - 1] > 2.f && VY[k - 1] < -1.f) { land = k; break; }
  if (land >= 0) {
    r.over = 1; r.land = A[land]; r.landPitch = PT[land - 1]; r.minPitch = 1e9f;
    for (int k = kLip; k < land; k++) if (PT[k] < r.minPitch) r.minPitch = PT[k];
  } else {
    int k3 = kLip; float amax = -1e9f;
    for (int k = kLip; k < n && T[k] - T[kLip] < 3.f - 1e-4f; k++) { k3 = k + 1; if (A[k] > amax) amax = A[k]; }
    if (k3 >= n) k3 = n - 1;
    r.over = amax >= 14.f ? 2 : 0;   // 2: ушла за конёк, но посадки за домом нет (на крыше / упала иначе)
    r.stopA = A[k3]; r.stopPitch = PT[k3];
  }
  return r;
}

static int within(float port, float orig, float rel, float floor) { return fabsf(port - orig) <= fmaxf(rel * fabsf(orig), floor); }
// Открытые расхождения (tests/jumps/house_known.tsv: id, буквы величин, причина): n — нос мин., p — тангаж перед посадкой, v — скорость
// за коньком. Такая величина
// печатается с пометкой «отк» и причиной и в счёт провалов не идёт; остальные величины строки проверяются как обычно.
static const char *knownPath = "tests/jumps/house_known.tsv";
static int useKnown = 1;
static int known(const char *id, char what, char *why) {
  if (!useKnown) return 0;
  FILE *f = fopen(knownPath, "r"); char l[512]; int hit = 0;
  while (f && fgets(l, sizeof l, f)) { char kid[32], km[16]; int nn = 0;
    if (l[0] != '#' && sscanf(l, "%31s %15s %n", kid, km, &nn) == 2 && !strcmp(kid, id) && strchr(km, what)) {
      hit = 1; snprintf(why, 256, "%s", l + nn); why[strcspn(why, "\n")] = 0; } }
  if (f) fclose(f);
  return hit;
}

int main(int argc, char **argv) {
  const char *lvl = "build/level.shr", *ref = "tests/jumps/house_ps2.tsv", *traceDir = NULL; int pos = 0;
  for (int i = 1; i < argc; i++) {
    if (!strcmp(argv[i], "--ref") && i + 1 < argc) ref = argv[++i];
    else if (!strcmp(argv[i], "--strict")) useKnown = 0;
    else if (!strcmp(argv[i], "--trace") && i + 1 < argc) traceDir = argv[++i];
    else if (pos++ == 0) lvl = argv[i];
  }
  FILE *f = fopen(lvl, "rb"); if (!f) { printf("нет %s\n", lvl); return 99; }
  fseek(f, 0, SEEK_END); long size = ftell(f); rewind(f);
  unsigned char *data = aligned_alloc(16, (size + 15) & ~15L); if (fread(data, 1, size, f) != (size_t)size) return 99; fclose(f);
  unsigned co = *(unsigned *)(data + 92), po = *(unsigned *)(data + 96), pv = *(unsigned *)(data + 88), ce = (unsigned)size;
  if (po > co && po < ce) ce = po; if (pv > co && pv < ce) ce = pv;
  if (colInit(&W, data + co, ce - co) || propsInit(&props, data + po, *(unsigned *)(data + po + 40)) || spInit(&sp, props.spr, props.sprSize)) {
    printf("уровень не читается\n"); return 99; }
  props.onKick = onKick;
  st0 = malloc(sizeof(PropState) * props.ninst); memcpy(st0, props.st, sizeof(PropState) * props.ninst);
  FILE *rf = fopen(ref, "r"); if (!rf) { printf("нет %s\n", ref); return 99; }
  printf("house: %s, эталон %s\n", lvl, ref);
  printf("%-6s | %-17s | %-13s | %-15s | %-15s | %-15s | %-15s | %-15s | %-15s\n", "заезд", "кромка ор/порт км/ч", "исход ор/порт", "посадка ор/порт м",
         "нос мин. ор/порт", "перед посадкой", "за коньком м/с", "встала ор/порт м", "тангаж стоя");
  char line[1024], why[256] = ""; int n = 0, fails = 0, nOpen = 0; unsigned refMask = 0;
  while (fgets(line, sizeof line, rf)) {
    why[0] = 0;
    if (line[0] == '#' || line[0] == '\n') continue;
    char id[32], out[16], run[96]; float x0, y0, z0, h0, v0, vt, coastA, oV, oLand, oMin, oLP, oStop, oSP, oV20;
    if (sscanf(line, "%31s %f %f %f %f %f %f %f %f %15s %f %f %f %f %f %95s %f", id, &x0, &y0, &z0, &h0, &v0, &vt, &coastA, &oV, out, &oLand, &oMin,
               &oLP, &oStop, &oSP, run, &oV20) != 17) continue;
    unsigned refBit = !strcmp(id, "h80") ? 1 : !strcmp(id, "h90") ? 2 : !strcmp(id, "h100c") ? 4 : 0;
    if (!refBit || (refMask & refBit) || (strcmp(out, "over") && strcmp(out, "stuck"))) {
      printf("house: FAIL invalid or duplicate reference %s\n", id); fclose(rf); return 99;
    }
    refMask |= refBit;
    FILE *tr = NULL;
    if (traceDir) { char p[512]; snprintf(p, sizeof p, "%s/%s.tsv", traceDir, id); tr = fopen(p, "w"); }
    Res r = runPort(x0, y0, z0, h0, v0, vt, coastA, tr);
    if (tr) fclose(tr);
    int oOver = !strcmp(out, "over");
    int okV = r.vlip > 0.f && within(r.vlip, oV, .07f, .7f), okO = r.over == oOver, ok = okV && okO;
    char c1[64] = "-", c2[64] = "-", c3[64] = "-", c4[64] = "-", c5[64] = "-", c6[64] = "-";
    if (oOver && r.over == 1) {
      int a = within(r.land, oLand, .15f, 2.f), b = fabsf(r.minPitch - oMin) <= 10.f, c = fabsf(r.landPitch - oLP) <= 15.f;
      int d = r.v20 == r.v20 && within(r.v20, oV20, .15f, .7f);
      int kb = known(id, 'n', why), kc = known(id, 'p', why), kd = known(id, 'v', why);   // открытое расхождение: печатается, в счёт не идёт
      ok = ok && a && (b || kb) && (c || kc) && (d || kd); nOpen += (!b && kb) + (!c && kc) + (!d && kd);
      snprintf(c6, sizeof c6, "%5.1f %5.1f %s", oV20, r.v20, d ? "ok" : kd ? "отк" : "НЕТ");
      snprintf(c1, sizeof c1, "%5.1f %5.1f %s", oLand, r.land, a ? "ok" : "НЕТ");
      snprintf(c2, sizeof c2, "%5.1f %5.1f %s", oMin, r.minPitch, b ? "ok" : kb ? "отк" : "НЕТ");
      snprintf(c3, sizeof c3, "%5.1f %5.1f %s", oLP, r.landPitch, c ? "ok" : kc ? "отк" : "НЕТ");
    } else if (!oOver && r.over == 0) {
      int a = fabsf(r.stopA - oStop) <= 2.f, b = fabsf(r.stopPitch - oSP) <= 15.f; ok = ok && a && b;
      snprintf(c4, sizeof c4, "%5.1f %5.1f %s", oStop, r.stopA, a ? "ok" : "НЕТ");
      snprintf(c5, sizeof c5, "%5.1f %5.1f %s", oSP, r.stopPitch, b ? "ok" : "НЕТ");
    } else if (r.over == 1) {
      snprintf(c1, sizeof c1, "  -   %5.1f", r.land); snprintf(c2, sizeof c2, "  -   %5.1f", r.minPitch);
    } else { snprintf(c4, sizeof c4, "  -   %5.1f", r.stopA); snprintf(c5, sizeof c5, "  -   %5.1f", r.stopPitch); }
    static const char *O[3] = {"встала", "перелет", "за коньком"};
    fails += !ok; n++;
    printf("%-6s | %5.1f %5.1f %-3s | %-6s %-6s | %-15s | %-15s | %-15s | %-15s | %-15s | %-15s %s\n", id, oV * 3.6f, r.vlip * 3.6f, okV ? "ok" : "НЕТ",
           oOver ? O[1] : O[0], O[r.over], c1, c2, c3, c6, c4, c5, ok ? "" : "<- FAIL");
    if (why[0] && (strstr(c2, "отк") || strstr(c3, "отк") || strstr(c6, "отк"))) printf("       открыто (%s): %s\n", knownPath, why);
  }
  fclose(rf);
  if (n != 3 || refMask != 7) { printf("house: FAIL incomplete reference (%d/3 заездов)\n", n); return 99; }
  printf("house: %s (%d заездов, %d вне допуска; открытых величин %d — %s; strict=%d)\n",
         fails ? "FAIL" : nOpen ? "PARTIAL" : "PASS", n, fails, nOpen, knownPath, !useKnown);
  return fails;
}
