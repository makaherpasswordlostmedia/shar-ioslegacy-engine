// Гейт правки Роба 135 («много разбивал, какой-то ненужный сэмпл, не в тему»): что звучит при ударах и разрушениях.
// Настоящие модули движка (sound.c + audio.c AUDIO_HOST, car.c, col.c, stateprops.c) и данные: пакет звука уровня 1
// (sfx.sab: ресурсы + таблица объектов OBJS) и level.shr (стейтпропы SPR1). Счёт звуков — перехват audioPlay в sound.c
// (-DaudioPlay=hookPlay: одинаково для старого и нового кода). Машина и примитивы — мини-мир COL1 вокруг НАСТОЯЩИХ объектов
// таблицы звука (дерево car_hit_tree, изгородь hit_shrub), как tests/foliage.
//   -DOLD    — старые правила (код базы dfb0441 и строки старого main.c / game.c): обязан упасть (красный)
//   -DNOLOG  — новый код без журнала sfxlog (135.7): обязан упасть на проверке журнала (отрицательный контроль)
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "car.h"
#include "sound.h"
#include "audio.h"
#include "props.h"
#include "stateprops.h"
#ifndef OLD
#include "carsnd.h"
#endif

static int fails;
static void check(const char *name, int ok) { printf("%s %s\n", ok ? "OK" : "FAIL", name); fails += !ok; }

// ---- перехват запуска звуков sound.c
static int nPlay; static char played[256][32];
int hookPlay(int id, float vol, float pan, float pitch) {
  const char *nm = audioSoundName(id);
  if (nPlay < 256) snprintf(played[nPlay++], 32, "%s", nm ? nm : "?");
  return audioPlay(id, vol, pan, pitch);
}
static int count(const char *nm) { int n = 0; for (int i = 0; i < nPlay; i++) n += !strcmp(played[i], nm); return n; }
static int crashes(void) { return count("small_car_crash") + count("medium_car_crash") + count("large_car_crash"); }
static void dump(const char *tag) { printf("  %s:", tag); for (int i = 0; i < nPlay; i++) printf(" %s", played[i]); printf("\n"); }

// ---- журнал 135.7
static int nLog; static char logLine[256][128];
static void logFn(const char *l) { if (nLog < 256) snprintf(logLine[nLog++], 128, "%s", l); }

// ---- объекты таблицы звука (SXT1 / OBJS, как sound.c)
typedef struct { float x, y, z, r; unsigned char kind, pad; short res; } XObj;
static const XObj *objs; static unsigned nobj;
static void loadObjs(void) {
  unsigned size; const unsigned char *e = audioBankExt(&size);
  if (!e || size < 8 || memcmp(e, "SXT1", 4)) return;
  unsigned ns = *(const unsigned *)(e + 4);
  for (unsigned i = 0; i < ns; i++) {
    const unsigned char *s = e + 8 + i * 16;
    if (!memcmp(s, "OBJS", 4) && *(const unsigned *)(s + 12) == 20) { objs = (const XObj *)(e + *(const unsigned *)(s + 4)); nobj = *(const unsigned *)(s + 8); }
  }
}
static const XObj *findObj(const char *res) {   // статичный (kind 2) объект со звуком res, у которого 12 м вокруг нет других
  for (unsigned i = 0; i < nobj; i++) {
    const XObj *o = &objs[i]; const char *nm = o->res >= 0 ? audioSoundName(o->res) : 0;
    if (o->kind != 2 || !nm || strcmp(nm, res)) continue;
    int alone = 1;
    for (unsigned k = 0; k < nobj && alone; k++) if (k != i && objs[k].res >= 0 && fabsf(objs[k].x - o->x) < 12 && fabsf(objs[k].z - o->z) < 12) alone = 0;
    if (alone) return o;
  }
  return 0;
}

// ---- мини-мир: земля 60x60 м на высоте gy вокруг (cx, cz) + один примитив (COL_BOX / COL_CYL / нет)
static unsigned char wbuf[1024] __attribute__((aligned(16))); static ColWorld w;
static int world(float cx, float gy, float cz, int type, const ColBox *box, const ColCyl *cyl) {
  ColHdr h; memset(&h, 0, sizeof h); memcpy(h.magic, "COL1", 4);
  h.ox = cx - 30; h.oz = cz - 30; h.cell = 60; h.W = h.H = 1; h.ntri = 2;
  int prim = type == COL_BOX || type == COL_CYL; h.nbox = type == COL_BOX; h.ncyl = type == COL_CYL; h.nref = 2 + prim;
  ColTri t[2] = {{{cx - 30, gy, cz - 30}, {cx + 30, gy, cz + 30}, {cx + 30, gy, cz - 30}, {0, 1, 0}},
                 {{cx - 30, gy, cz - 30}, {cx - 30, gy, cz + 30}, {cx + 30, gy, cz + 30}, {0, 1, 0}}};
  unsigned n = 0;
  memcpy(wbuf + n, &h, sizeof h); n += sizeof h; memcpy(wbuf + n, t, sizeof t); n += sizeof t;
  if (type == COL_BOX) { memcpy(wbuf + n, box, sizeof *box); n += sizeof *box; }
  if (type == COL_CYL) { memcpy(wbuf + n, cyl, sizeof *cyl); n += sizeof *cyl; }
  unsigned start[2] = {0, h.nref}, refs[3] = {0, 1, (unsigned)type << 29};
  memcpy(wbuf + n, start, sizeof start); n += sizeof start; memcpy(wbuf + n, refs, h.nref * 4); n += h.nref * 4;
  return colInit(&w, wbuf, n);
}

// ---- кадр звука машины: новый main.c (carSndFrame) или старая строка main.c
static float vy0; static int air0;
static void carSound(const Car *c) {
#ifdef OLD
  if (c->hitSpeed > 0.f) sndCarHit(c->hitSpeed, c->x, c->ry + .8f, c->z);          // main.c до правки 135
#else
  carSndFrame(c, &w);
#endif
  int air = !c->grounded && c->airT > .3f; sndCarAir(air);
  if (air0 && c->grounded) sndCarLand(-vy0);
  air0 = air; vy0 = c->vel[1];
  sndFrame(1.f / 60, c->x, c->y + 2.f, c->z, 1.f, 0.f, c->x, c->y, c->z);   // слушатель у машины
}
static void quiet(void) { for (int i = 0; i < 120; i++) sndFrame(1.f / 60, 0, 0, 0, 1, 0, 0, 0, 0); nPlay = 0; nLog = 0; air0 = 0; vy0 = 0; }

// машина с расстояния d по -x от точки (x, z), курс +x, скорость v, газ; 2 с по 1/60
static Car car, car2;
static void drive(float x, float y, float z, float d, float v) {
  carInit(&car, 0, &w, x - d, y + 1.f, z, 1.5707963f); carSetSpeed(&car, v);
  CarInput in = {1, 0, 0, 0};
  for (int i = 0; i < 120; i++) { carUpdate(&car, &w, &in, 1.f / 60); carSound(&car); }
}

int main(int argc, char **argv) {
  if (argc < 3) { fprintf(stderr, "usage: host PACKDIR/ level.shr\n"); return 2; }
  if (sndInit(argv[1]) < 0) { printf("FAIL sndInit %s\n", sndError()); return 2; }
  loadObjs();
  const XObj *tree = findObj("car_hit_tree"), *shrub = findObj("hit_shrub");
  printf("pack objs=%u tree=%s shrub=%s\n", nobj, tree ? "yes" : "no", shrub ? "yes" : "no");
  if (!tree || !shrub) { printf("FAIL no source objects\n"); return 2; }
#if !defined(OLD) && !defined(NOLOG)
  sndLogHook(logFn);
#endif

  // 1) контроль: въезд в ствол дерева (твёрдый цилиндр у объекта car_hit_tree) — crash + car_hit_tree (и до, и после)
  { ColCyl c; memset(&c, 0, sizeof c); c.c[0] = tree->x; c.c[1] = tree->y + 2; c.c[2] = tree->z; c.axis[1] = 1; c.r = .5f; c.halfLen = 2; c.flat = 1;
    world(tree->x, tree->y, tree->z, COL_CYL, 0, &c); quiet(); drive(tree->x, tree->y, tree->z, 7, 9); dump("tree");
    check("135.2 control: ствол дерева 9 м/с = crash + car_hit_tree", crashes() >= 1 && count("car_hit_tree") >= 1);
#ifndef OLD
    int lines = 0, same = nLog == nPlay;
    for (int i = 0; i < nLog && i < nPlay; i++) { char nm[32]; if (sscanf(logLine[i], "SFX %31s", nm) == 1 && !strcmp(nm, played[i])) lines++; else same = 0; }
    printf("  sfxlog lines=%d plays=%d first=\"%s\"\n", nLog, nPlay, nLog ? logLine[0] : "-");
    check("135.7 журнал: строка SFX <клип> <событие> x y z на каждый звук", same && lines == nPlay && nPlay > 0 &&
          (strstr(logLine[0], " crash ") || strstr(logLine[0], " obj ")));
#endif
    colFree(&w); }

  // 2) 135.2: стена дома (коробка, центр в 6 м от дерева) в 0.6 м перед деревом: удар о стену — только crash
  { ColBox b; memset(&b, 0, sizeof b); b.c[0] = tree->x - .85f; b.c[1] = tree->y + 1.5f; b.c[2] = tree->z + 6;
    b.ax[0] = 1; b.ay[1] = 1; b.az[2] = 1; b.h[0] = .25f; b.h[1] = 1.5f; b.h[2] = 10;
    world(tree->x, tree->y, tree->z, COL_BOX, &b, 0); quiet(); drive(tree->x, tree->y, tree->z, 7, 9); dump("wall");
    check("135.2 удар о стену рядом с деревом = crash без car_hit_tree", crashes() >= 1 && count("car_hit_tree") == 0);
    colFree(&w); }

  // 3) 135.5: въезд в изгородь (цилиндр FOLIAGE у объекта hit_shrub) 8 м/с — шорох, без металлического crash
  { ColCyl c; memset(&c, 0, sizeof c); c.c[0] = shrub->x; c.c[1] = shrub->y + .8f; c.c[2] = shrub->z; c.axis[2] = 1; c.r = .7f; c.halfLen = 3; c.pad[0] = 1;
    world(shrub->x, shrub->y, shrub->z, COL_CYL, 0, &c); quiet(); drive(shrub->x, shrub->y, shrub->z, 7, 8); dump("hedge");
    check("135.5 изгородь 8 м/с = hit_shrub, 0 crash", crashes() == 0 && count("hit_shrub") >= 1);
    // контроль: та же капсула твёрдая — crash есть
    c.pad[0] = 0; colFree(&w); world(shrub->x, shrub->y, shrub->z, COL_CYL, 0, &c); quiet(); drive(shrub->x, shrub->y, shrub->z, 7, 8); dump("hard");
    check("135.5 control: та же капсула твёрдая = crash", crashes() >= 1);
    colFree(&w); }

  // 4) 135.3: машина о машину у изгороди (без её примитива) — crash, без hit_shrub
  { world(shrub->x, shrub->y, shrub->z, -1, 0, 0); quiet();
    carInit(&car, 0, &w, shrub->x - 4, shrub->y + 1, shrub->z, 1.5707963f); carSetSpeed(&car, 9);
    carInit(&car2, 0, &w, shrub->x + 3, shrub->y + 1, shrub->z, 1.5707963f);
    CarInput in = {1, 0, 0, 0}, none = {0, 0, 0, 0}; int touched = 0;
    for (int i = 0; i < 120; i++) { carUpdate(&car, &w, &in, 1.f / 60); carUpdate(&car2, &w, &none, 1.f / 60); touched += carHitCar(&car, &car2, &w); carSound(&car); }
    dump("carcar");
    check("135.3 машина о машину у изгороди = crash, 0 hit_shrub", touched > 0 && crashes() >= 1 && count("hit_shrub") == 0);
    colFree(&w); }

  // 5) 135.4: посадка с 6 м на ровный асфальт (объектов рядом нет) — suspension_ronks, без crash
  { float x = tree->x + 200, z = tree->z + 200;
    world(x, tree->y, z, -1, 0, 0); quiet();
    carInit(&car, 0, &w, x, tree->y + 1, z, 0.3f); car.y += 6; car.ry = car.y;
    CarInput none = {0, 0, 0, 0};
    for (int i = 0; i < 180; i++) { carUpdate(&car, &w, &none, 1.f / 60); carSound(&car); }
    dump("landing");
    check("135.4 посадка с 6 м = suspension_ronks, 0 crash", crashes() == 0 && count("suspension_ronks") >= 1);
    colFree(&w); }

  // 6) 135.6: события трафика — сбит пешеход, разбита машина трафика (старый main.c звуков не звал)
  { quiet(); sndFrame(1.f / 60, tree->x, tree->y + 2, tree->z, 1, 0, tree->x, tree->y, tree->z);   // слушатель рядом
#ifndef OLD
    sndPedHit(tree->x, tree->y, tree->z); sndTrafficWreck(tree->x + 1, tree->y, tree->z);
#endif
    dump("traffic");
    check("135.6 пешеход = car_hit_pedestrian, машина трафика = generic_car_explode", count("car_hit_pedestrian") == 1 && count("generic_car_explode") == 1); }

  // 6б) 135.9 (Роб 01.10): «гул, как вращение колёс, в прыжке с трамплина — не должно быть»: машина в полёте — car_jump не звучит
  { quiet(); sndCarAir(1); dump("air"); check("135.9 полёт: петля car_jump не играет", count("car_jump") == 0); sndCarAir(0); }

  // 7) 135.1: стейтпропы уровня 1 (SPR1 level.shr): удар машиной по экземпляру каждого типа, 3 с кадров — звуков столько,
  //    сколько ударов; авто-переход (куст-шар встаёт через 1.3 с) звука не даёт
  { FILE *f = fopen(argv[2], "rb"); if (!f) { printf("FAIL %s\n", argv[2]); return 2; }
    fseek(f, 0, SEEK_END); long size = ftell(f); rewind(f);
    unsigned char *data = aligned_alloc(16, (size + 15) & ~15);
    if (!data || fread(data, 1, size, f) != (size_t)size) return 2;
    fclose(f);
    static Props props; static StateProps sp; static ColWorld lw;
    unsigned co = *(unsigned *)(data + 92), po = *(unsigned *)(data + 96), pv = *(unsigned *)(data + 88), ce = (unsigned)size;
    if (po > co && po < ce) ce = po; if (pv > co && pv < ce) ce = pv;
    if (colInit(&lw, data + co, ce - co) || propsInit(&props, data + po, *(unsigned *)(data + po + 40)) || spInit(&sp, props.spr, props.sprSize)) { printf("FAIL level\n"); return 2; }
    int hits = 0, sounds = 0, changes = 0, autoTypes = 0, autoQuiet = 0; unsigned seenType[256] = {0};
    for (unsigned i = 0; i < sp.ninst; i++) {
      unsigned ty = sp.inst[i].type; if (i >= 512 || ty >= 256 || seenType[ty]) continue;
      if (!sp.run[i].alive || sp.run[i].state != 0) continue;
      seenType[ty] = 1;
      unsigned char st[512]; for (unsigned k = 0; k < sp.ninst && k < 512; k++) st[k] = (unsigned char)sp.run[k].state;
#ifndef OLD
      { unsigned q; while (spSndPop(&sp, &q)) {} }
#endif
      if (!spEvent(&sp, i, SP_EV_VEHICLE_HIT) || sp.run[i].state == 0) continue;
      hits++;
      int s0 = 0, c0 = 0;
      for (int n = 0; n < 180; n++) {
        if (n) spUpdate(&sp, &lw, NULL, NULL, 1.f / 60);
        unsigned k = i;
        if (sp.run[k].state != st[k]) c0++;
#ifdef OLD
        if (sp.run[k].state != st[k]) s0++;                        // game.c до правки: звук на любую смену состояния
#else
        unsigned q; while (spSndPop(&sp, &q)) s0 += q == i;        // game.c: звук на удар (очередь)
#endif
        st[k] = (unsigned char)sp.run[k].state;
      }
      sounds += s0; changes += c0;
      if (c0 > 1) { autoTypes++; autoQuiet += s0 == 1; }
      spEnter(&sp, i, 0);
    }
    printf("  sprops types hit=%d sounds=%d state_changes=%d auto_types=%d auto_quiet=%d\n", hits, sounds, changes, autoTypes, autoQuiet);
    check("135.1 стейтпропы: звук = удар (не авто-переход/возврат)", hits > 0 && autoTypes > 0 && sounds == hits && autoQuiet == autoTypes); }

  printf("RESULT %s fails=%d\n", fails ? "FAIL" : "PASS", fails);
  return fails ? 1 : 0;
}
