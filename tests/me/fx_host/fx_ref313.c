// Правка 313: ЭТАЛОН для сверки tests/me/run.py «Мак, частицы» — viewer/fx.c как он был до правки 313 (ac7880e), без изменений.
// Новый viewer/fx.c + viewer/fxdsp.h (счёт, который берёт Media Engine) обязан давать на стенде tests/me/fx_host/fx_host.c тот же вывод.
// В игру не собирается.
// Частицы: реализация (см. fx.h, формат — tools/fx_pack.py, данные — docs/fx_spec.md).
#include "fx.h"
#include <pspgu.h>
#include <pspkernel.h>
#include <pspiofilemgr.h>
#include <math.h>
#include <string.h>
#include <stdlib.h>
#include <malloc.h>
#include <unistd.h>
#include <stdio.h>

enum { P_RAT, P_SPD, P_SPDV, P_LIF, P_LIFV, P_SIZ, P_SIZV, P_SPI, P_SPIV, P_WGT, P_WGTV, P_GRA, P_DRA, P_ALP, P_ALPV,
       P_CLRR, P_CLRG, P_CLRB, P_CLRV, P_NUM, P_TX, P_TY, P_TZ, P_QW, P_QX, P_QY, P_QZ, NP };
#define NOL 16
#define MAXE 32          // эмиттеров в одной системе (взрыв — 24)
#define MAXSPR 96        // блёсток/спрайтов на кадр

typedef struct { char magic[4]; unsigned ver, nTex, nSys, nEmit, nKey, nBB, nAmb, nBrk,
                 offTex, offSys, offEmit, offKey, offBB, offAmb, offBrk; } FxHdr;
typedef struct { unsigned short w, h, bufw; unsigned char psm, swz; unsigned offPix, offClut; char name[16]; } FxTex;
typedef struct { char name[32]; unsigned short firstEmit, nEmit, nFrames; unsigned char oneShot, maxInst; float fps;
                 short instType, brkType; unsigned short firstBB, nBB; unsigned pad; } FxSys;
typedef struct { unsigned short tex; unsigned char cols, rows, nFr, texMode, blend, angleMode, gen, flags, pad[2];
                 float texRate, angle, aspect, genW, genH, spreadH, spreadV;
                 unsigned short key[NP][2]; unsigned ol[NOL];
                 float olSize[NOL], olSpeed[NOL], olSpin[NOL], olWeight[NOL]; } FxEmit;
typedef struct { unsigned short frame, pad; float v; } FxKey;
typedef struct { unsigned short tex; unsigned char blend, mode; float dist, rot[4]; unsigned short nFrames, pad;
                 unsigned offLut; } FxBB;
typedef struct { unsigned short sys, pad; float x, y, z; } FxAmb;
typedef struct { short type; unsigned short nSys, sys[4], firstBB, nBB; } FxBrk;
_Static_assert(sizeof(FxHdr) == 64 && sizeof(FxTex) == 32 && sizeof(FxSys) == 56 && sizeof(FxEmit) == 468 &&
               sizeof(FxKey) == 8 && sizeof(FxBB) == 32 && sizeof(FxAmb) == 16 && sizeof(FxBrk) == 16, "FXP1");

static unsigned char *blob;
static FxHdr *H; static FxTex *T; static FxSys *S; static FxEmit *E; static FxKey *K; static FxBB *BB;
static FxAmb *AM; static FxBrk *BR;

// частица
typedef struct { float x, y, z, vx, vy, vz, vg, ga, age, inv, size, ang, spin, lnd, ak; unsigned rgb;
                 unsigned short em, inst; unsigned char seed, pad[3]; } P;
static P ps[FX_MAX]; static int np;

// экземпляр системы
typedef struct { short sys; unsigned char used, spawning, once, pad; unsigned short gen; float t, bbT, rate, age;
                 float pos[3], m[9]; float acc[MAXE], ek[MAXE]; unsigned short live[MAXE]; int nlive; } Inst;
static Inst in_[FX_MAX_INST];
static unsigned short genCtr = 1;

typedef struct { float x, y, z, w, h, rot; unsigned c; unsigned short tex; unsigned char blend, flat; } Spr;
static Spr spr[MAXSPR]; static int nspr;

float fxVel = 30.f;
static int ready, sysCar = -1, sysSpark = -1, sysPaint = -1, sysDust = -1, texScratch = -1, texGlow = -1;
static float eye[3]; static int haveEye;
static int ambH[64];

static unsigned rs = 777u;
static inline float fr(void) { rs = rs * 1664525u + 1013904223u; return (rs >> 8) * (1.f / 16777216.f); }
static inline float fr2(void) { return fr() * 2.f - 1.f; }

// ---------- загрузка ----------
int fxLoad(const char *path) {
  SceUID fd = sceIoOpen(path, PSP_O_RDONLY, 0);
  if (fd < 0) return 0;
  int sz = sceIoLseek32(fd, 0, PSP_SEEK_END); sceIoLseek32(fd, 0, PSP_SEEK_SET);
  unsigned char *b = memalign(16, sz);
  if (!b) { sceIoClose(fd); return 0; }
  int rd = sceIoRead(fd, b, sz); sceIoClose(fd);
  if (rd != sz || memcmp(b, "FXP1", 4)) { free(b); return 0; }
  if (blob) free(blob);
  blob = b; H = (FxHdr *)b;
  T = (FxTex *)(b + H->offTex); S = (FxSys *)(b + H->offSys); E = (FxEmit *)(b + H->offEmit);
  K = (FxKey *)(b + H->offKey); BB = (FxBB *)(b + H->offBB); AM = (FxAmb *)(b + H->offAmb); BR = (FxBrk *)(b + H->offBrk);
  sceKernelDcacheWritebackRange(b, sz);
  ready = 1;
  sysCar = fxFindInst(14); if (sysCar < 0) sysCar = fxFind("car_damage3SysShape");
  sysSpark = fxFind("code_spark"); sysPaint = fxFind("code_paint"); sysDust = fxFind("code_dust");
  texScratch = fxTexFind("scratch2.bmp"); texGlow = fxTexFind("glow2.bmp");
  return 1;
}

void fxInit(int level) {
  np = 0; nspr = 0; memset(in_, 0, sizeof in_); memset(ambH, 0, sizeof ambH);
  if (ready) return;
  // частицы уровня: у уровня 1 — fx.shr рядом с EBOOT, у 2–7 — l<N>/fx.shr (tools/fx_pack.py --level N; viewer/main.c levelFile)
  char nm[32], p[304]; if (level > 1) snprintf(nm, sizeof nm, "l%d/fx.shr", level); else strcpy(nm, "fx.shr");
  if (getcwd(p, 256)) { size_t l = strlen(p); if (l && p[l - 1] != '/') strcat(p, "/"); strcat(p, nm); if (fxLoad(p)) return; }
  if (fxLoad(nm)) return;
  snprintf(p, sizeof p, "ms0:/PSP/GAME/SHARVIEW/%s", nm); fxLoad(p);
}
int fxReady(void) { return ready; }
// смена уровня (viewer/main.c levelUnload): пакет частиц уровня — обратно в кучу; fxInit(N) прочитает l<N>/fx.shr
void fxFree(void) {
  np = 0; nspr = 0; memset(in_, 0, sizeof in_); memset(ambH, 0, sizeof ambH);
  if (blob) free(blob);
  blob = 0; H = 0; ready = 0;
  sysCar = sysSpark = sysPaint = sysDust = texScratch = texGlow = -1;
}

int fxFind(const char *name) {
  if (!ready) return -1;
  for (unsigned i = 0; i < H->nSys; i++) if (!strncmp(S[i].name, name, 31)) return i;
  return -1;
}
int fxFindInst(int type) {
  if (!ready) return -1;
  for (unsigned i = 0; i < H->nSys; i++) if (S[i].instType == type) return i;
  return -1;
}
int fxTexFind(const char *name) {
  if (!ready) return -1;
  for (unsigned i = 0; i < H->nTex; i++) if (!strncmp(T[i].name, name, 15)) return i;
  return -1;
}

// ---------- кривые ----------
static float key(const FxEmit *e, int p, float t) {
  const FxKey *k = K + e->key[p][0]; int n = e->key[p][1];
  if (n <= 1 || t <= k[0].frame) return k[0].v;
  for (int i = 1; i < n; i++)
    if (t <= k[i].frame) { float f0 = k[i - 1].frame, f1 = k[i].frame; return k[i - 1].v + (k[i].v - k[i - 1].v) * (t - f0) / (f1 - f0); }
  return k[n - 1].v;
}
static inline float lut(const float *l, float u) {
  float f = u * (NOL - 1); int i = (int)f; if (i >= NOL - 1) return l[NOL - 1]; if (i < 0) return l[0];
  return l[i] + (l[i + 1] - l[i]) * (f - i);
}
static inline unsigned lutc(const unsigned *l, float u) {
  float f = u * (NOL - 1); int i = (int)f; if (i >= NOL - 1) return l[NOL - 1]; if (i < 0) return l[0];
  unsigned a = l[i], b = l[i + 1], o = 0; float t = f - i;
  for (int s = 0; s < 32; s += 8) { float ca = (a >> s) & 255, cb = (b >> s) & 255; o |= ((unsigned)(ca + (cb - ca) * t) & 255) << s; }
  return o;
}
static void qrot(const float q[4], const float v[3], float o[3]) {   // q = w,x,y,z
  float w = q[0], x = q[1], y = q[2], z = q[3];
  float cx = y * v[2] - z * v[1], cy = z * v[0] - x * v[2], cz = x * v[1] - y * v[0];
  float dx = y * cz - z * cy, dy = z * cx - x * cz, dz = x * cy - y * cx;
  o[0] = v[0] + 2.f * (w * cx + dx); o[1] = v[1] + 2.f * (w * cy + dy); o[2] = v[2] + 2.f * (w * cz + dz);
}
static void basis(const float dir[3], float m[9]) {   // столбцы x, y, z; y = dir
  float y[3] = {0, 1, 0};
  if (dir) { float l = sqrtf(dir[0] * dir[0] + dir[1] * dir[1] + dir[2] * dir[2]); if (l > 1e-5f) { y[0] = dir[0] / l; y[1] = dir[1] / l; y[2] = dir[2] / l; } }
  float r[3] = {0, 0, 1}; if (fabsf(y[2]) > .9f) { r[0] = 1; r[2] = 0; }
  float x[3] = {y[1] * r[2] - y[2] * r[1], y[2] * r[0] - y[0] * r[2], y[0] * r[1] - y[1] * r[0]};
  float l = sqrtf(x[0] * x[0] + x[1] * x[1] + x[2] * x[2]); x[0] /= l; x[1] /= l; x[2] /= l;
  float z[3] = {x[1] * y[2] - x[2] * y[1], x[2] * y[0] - x[0] * y[2], x[0] * y[1] - x[1] * y[0]};
  m[0] = x[0]; m[1] = x[1]; m[2] = x[2]; m[3] = y[0]; m[4] = y[1]; m[5] = y[2]; m[6] = z[0]; m[7] = z[1]; m[8] = z[2];
}
static inline void mv(const float m[9], const float v[3], float o[3]) {
  o[0] = m[0] * v[0] + m[3] * v[1] + m[6] * v[2]; o[1] = m[1] * v[0] + m[4] * v[1] + m[7] * v[2]; o[2] = m[2] * v[0] + m[5] * v[1] + m[8] * v[2];
}
static const float I9[9] = {1, 0, 0, 0, 1, 0, 0, 0, 1};

// ---------- рождение ----------
// vel: NULL = из эмиттера; addv: добавить к скорости (машина едет); ak: множитель альфы
static P *spawn(int ei, int inst, float t, float fps, const float pos[3], const float m[9], const float *vel,
                const float *addv, float ak) {
  if (np >= FX_MAX) return NULL;
  const FxEmit *e = &E[ei];
  P *p = &ps[np++];
  float q[4] = {key(e, P_QW, t), key(e, P_QX, t), key(e, P_QY, t), key(e, P_QZ, t)};
  float ql = sqrtf(q[0] * q[0] + q[1] * q[1] + q[2] * q[2] + q[3] * q[3]); if (ql < 1e-6f) { q[0] = 1; ql = 1; }
  q[0] /= ql; q[1] /= ql; q[2] /= ql; q[3] /= ql;
  static const float X[3] = {1, 0, 0}, Y[3] = {0, 1, 0}, Z[3] = {0, 0, 1};
  float ax[3], ay[3], az[3]; qrot(q, X, ax); qrot(q, Y, ay); qrot(q, Z, az);
  float lp[3] = {key(e, P_TX, t), key(e, P_TY, t), key(e, P_TZ, t)};
  if (e->gen == 1) {           // плоскость W×H поперёк оси вылета
    float a = fr2() * .5f * e->genW, b = fr2() * .5f * e->genH;
    for (int i = 0; i < 3; i++) lp[i] += ax[i] * a + az[i] * b;
  } else if (e->gen == 2) {    // сфера радиуса R
    float zz = fr2(), ph = fr() * 6.2831853f, rr = sqrtf(1.f - zz * zz);
    lp[0] += e->genW * rr * cosf(ph); lp[1] += e->genW * zz; lp[2] += e->genW * rr * sinf(ph);
  }
  float th = fr2() * e->spreadH, tv = fr2() * e->spreadV, ch = cosf(th), sh = sinf(th), cv = cosf(tv), sv = sinf(tv);
  float ld[3]; for (int i = 0; i < 3; i++) ld[i] = ay[i] * ch * cv + ax[i] * sh * cv + az[i] * sv;
  float wp[3], wd[3]; mv(m, lp, wp); mv(m, ld, wd);
  p->x = pos[0] + wp[0]; p->y = pos[1] + wp[1]; p->z = pos[2] + wp[2];
  if (vel) { p->vx = vel[0]; p->vy = vel[1]; p->vz = vel[2]; }
  else {
    float sp = (key(e, P_SPD, t) + key(e, P_SPDV, t) * fr2()) * fxVel;
    p->vx = wd[0] * sp; p->vy = wd[1] * sp; p->vz = wd[2] * sp;
  }
  if (addv) { p->vx += addv[0]; p->vy += addv[1]; p->vz += addv[2]; }
  p->vg = 0.f;
  float wgt = key(e, P_WGT, t) + key(e, P_WGTV, t) * fr2();
  p->ga = key(e, P_GRA, t) * wgt * fxVel * fxVel;
  float life = (key(e, P_LIF, t) + key(e, P_LIFV, t) * fr2()) / fps; if (life < .02f) life = .02f;
  p->age = 0.f; p->inv = 1.f / life;
  p->size = key(e, P_SIZ, t) + key(e, P_SIZV, t) * fr2(); if (p->size < .01f) p->size = .01f;
  p->spin = (key(e, P_SPI, t) + key(e, P_SPIV, t) * fr2()) * fps;
  p->ang = e->angleMode == 1 ? fr() * 6.2831853f : e->angle;
  float dra = key(e, P_DRA, t); p->lnd = (dra > 0.f && dra < .9999f) ? logf(dra) * 30.f : 0.f;
  float alp = key(e, P_ALP, t) + key(e, P_ALPV, t) * fr2(); if (alp < 0) alp = 0; if (alp > 255) alp = 255;
  p->ak = ak * alp * (1.f / 255.f);
  float br = 1.f + key(e, P_CLRV, t) * (1.f / 255.f) * fr2();
  int r = key(e, P_CLRR, t) * br, g = key(e, P_CLRG, t) * br, b = key(e, P_CLRB, t) * br;
  r = r < 0 ? 0 : r > 255 ? 255 : r; g = g < 0 ? 0 : g > 255 ? 255 : g; b = b < 0 ? 0 : b > 255 ? 255 : b;
  p->rgb = (b << 16) | (g << 8) | r;
  p->em = ei; p->inst = inst < 0 ? 0xffff : inst; p->seed = (unsigned char)(fr() * 255.f);
  if (inst >= 0) { in_[inst].live[ei - S[in_[inst].sys].firstEmit]++; in_[inst].nlive++; }
  return p;
}

// ---------- системы ----------
static int handleOf(int i) { return (in_[i].gen << 8) | (i + 1); }
static Inst *fromHandle(int h) {
  int i = (h & 255) - 1; if (i < 0 || i >= FX_MAX_INST) return NULL;
  Inst *s = &in_[i]; return (s->used && s->gen == (unsigned short)(h >> 8)) ? s : NULL;
}
static int start(int id, const float pos[3], const float dir[3], int once) {
  if (!ready || id < 0 || id >= (int)H->nSys) return 0;
  int slot = -1, cnt = 0, oldest = -1; float oa = -1.f;
  for (int i = 0; i < FX_MAX_INST; i++) {
    if (!in_[i].used) { if (slot < 0) slot = i; continue; }
    if (in_[i].sys == id && in_[i].once) { cnt++; if (in_[i].age > oa) { oa = in_[i].age; oldest = i; } }
  }
  if (once && cnt >= S[id].maxInst && oldest >= 0) in_[oldest].spawning = 0;   // потолок maxInstances: гасим старейшую
  if (slot < 0) return 0;
  Inst *s = &in_[slot]; memset(s, 0, sizeof *s);
  s->sys = id; s->used = 1; s->spawning = 1; s->once = once || S[id].oneShot; s->rate = 1.f;
  s->gen = genCtr++; if (!genCtr) genCtr = 1;
  for (int k = 0; k < MAXE; k++) s->ek[k] = 1.f;
  s->pos[0] = pos[0]; s->pos[1] = pos[1]; s->pos[2] = pos[2]; basis(dir, s->m);
  return handleOf(slot);
}
int fxStartSystem(int id, const float pos[3], const float dir[3]) { return start(id, pos, dir, 0); }
int fxStart(const char *name, const float pos[3], const float dir[3]) { return start(fxFind(name), pos, dir, 0); }
int fxBurst(int id, const float pos[3], const float dir[3]) { return start(id, pos, dir, 1); }
// правка Роба 80: окно EFX предмета «кадры 80..95» — система с кадра 80 (как контроллер оригинала), а не с нуля (развал ящика
// запаздывал на ~2.7 с: эмиттеры системы ящика работают только на её кадрах 80..95)
int fxBurstAt(int id, const float pos[3], const float dir[3], float frame) {
  int h = start(id, pos, dir, 1); if (!h || frame <= 0.f) return h;
  Inst *s = &in_[(h & 0xFF) - 1]; float nf = (float)S[id].nFrames; s->t = frame < nf ? frame : 0.f;
  return h;
}
int fxBurstBreakable(int type, const float pos[3], const float dir[3]) {
  if (!ready) return 0;
  for (unsigned i = 0; i < H->nBrk; i++) if (BR[i].type == type) {
    int h = 0;
    for (int k = 0; k < BR[i].nSys && k < 4; k++) { int x = start(BR[i].sys[k], pos, dir, 1); if (!h) h = x; }
    return h;
  }
  return 0;
}
void fxMove(int h, const float pos[3], const float dir[3]) {
  Inst *s = fromHandle(h); if (!s) return;
  s->pos[0] = pos[0]; s->pos[1] = pos[1]; s->pos[2] = pos[2]; if (dir) basis(dir, s->m);
}
void fxSetRate(int h, float k) { Inst *s = fromHandle(h); if (s) s->rate = k; }
void fxSetEmitRate(int h, int e, float k) { Inst *s = fromHandle(h); if (s && e >= 0 && e < MAXE) s->ek[e] = k; }
void fxStop(int h) { Inst *s = fromHandle(h); if (s) s->spawning = 0; }
int fxAlive(int h) { return fromHandle(h) != NULL; }

// ---------- старый API ----------
void fxSpawn(int kind, float x, float y, float z, float vx, float vy, float vz) {
  if (!ready) return;
  float pos[3] = {x, y, z}, add[3] = {vx, 0.f, vz}, vel[3] = {vx, vy, vz};
  switch (kind) {
    case FX_SMOKE: if (sysCar >= 0) spawn(S[sysCar].firstEmit, -1, 0, S[sysCar].fps, pos, I9, NULL, add, .6f); break;
    case FX_DARK:  if (sysCar >= 0) spawn(S[sysCar].firstEmit, -1, 0, S[sysCar].fps, pos, I9, NULL, add, 1.f); break;
    case FX_FIRE:
      if (sysCar >= 0 && S[sysCar].nEmit >= 3)
        for (int k = 0; k < 4; k++) spawn(S[sysCar].firstEmit + 1 + (k & 1), -1, 0, S[sysCar].fps, pos, I9, NULL, add, 1.f);
      break;
    case FX_SPARK: if (sysSpark >= 0) spawn(S[sysSpark].firstEmit, -1, 0, 30.f, pos, I9, vel, NULL, 1.f); break;
    case FX_PAINT: if (sysPaint >= 0) spawn(S[sysPaint].firstEmit, -1, 0, 30.f, pos, I9, vel, NULL, 1.f); break;
    case FX_DUST:  if (sysDust >= 0) spawn(S[sysDust].firstEmit, -1, 0, 30.f, pos, I9, vel, NULL, 1.f); break;
  }
}

int fxHomerDust(int kind, float x, float y, float z, float power) {
  if (!ready || sysDust < 0) return 0;
  if (kind == FXD_STEP) { fxSpawn(FX_DUST, x, y + .08f, z, (fr() - .5f) * .4f, .2f + fr() * .15f, (fr() - .5f) * .4f); return 1; }   // клуб на шаг: почти на месте
  int n = kind == FXD_BOUNCE ? 5 : (power > FXD_LAND_MIN ? (power > 14.f ? 4 : 3) : 0);
  float sp = kind == FXD_BOUNCE ? 1.2f : .5f + .04f * fminf(power, 20.f);   // разлёт вбок, м/с
  for (int k = 0; k < n; k++) {
    float a = (k + fr() * .6f) * (6.2831853f / (float)n);
    fxSpawn(FX_DUST, x + cosf(a) * .25f, y + .08f, z + sinf(a) * .25f, cosf(a) * sp, .25f + fr() * .2f, sinf(a) * sp);
  }
  return n;
}

// ---------- обновление ----------
static void ambient(void) {
  if (!haveEye || !H->nAmb) return;
  for (unsigned i = 0; i < H->nAmb && i < 64; i++) {
    float dx = AM[i].x - eye[0], dy = AM[i].y - eye[1], dz = AM[i].z - eye[2], d2 = dx * dx + dy * dy + dz * dz;
    if (!ambH[i] && d2 < 60.f * 60.f) { float p[3] = {AM[i].x, AM[i].y, AM[i].z}; ambH[i] = start(AM[i].sys, p, NULL, 0); }
    else if (ambH[i] && (d2 > 70.f * 70.f || !fxAlive(ambH[i]))) { fxStop(ambH[i]); ambH[i] = 0; }
  }
}

void fxUpdate(float dt) {
  if (!ready) return;
  if (dt > .1f) dt = .1f;
  ambient();
  // системы: рождение по таймлайну
  for (int i = 0; i < FX_MAX_INST; i++) {
    Inst *s = &in_[i]; if (!s->used) continue;
    const FxSys *y = &S[s->sys];
    float df = dt * y->fps;
    s->age += dt; s->bbT += df;
    if (s->spawning) {
      for (int k = 0; k < y->nEmit && k < MAXE; k++) {
        const FxEmit *e = &E[y->firstEmit + k];
        float rat = key(e, P_RAT, s->t) * s->rate * s->ek[k];
        if (rat <= 0.f) continue;
        s->acc[k] += rat * df;
        int n = (int)s->acc[k]; s->acc[k] -= n;
        int num = (int)key(e, P_NUM, s->t);
        while (n-- > 0 && s->live[k] < num && np < FX_MAX) spawn(y->firstEmit + k, i, s->t, y->fps, s->pos, s->m, NULL, NULL, 1.f);
      }
      s->t += df;
      if (s->t >= y->nFrames) { if (s->once) s->spawning = 0; else s->t = fmodf(s->t, (float)y->nFrames); }
    }
    int bbDone = 1;
    for (int b = 0; b < y->nBB; b++) if (s->bbT < BB[y->firstBB + b].nFrames) bbDone = 0;
    if (!s->spawning && s->nlive <= 0 && bbDone) s->used = 0;
  }
  // частицы
  for (int i = 0; i < np; ) {
    P *p = &ps[i];
    p->age += dt;
    float u = p->age * p->inv;
    if (u >= 1.f) {
      if (p->inst != 0xffff) { Inst *s = &in_[p->inst]; s->live[p->em - S[s->sys].firstEmit]--; s->nlive--; }
      ps[i] = ps[--np]; continue;
    }
    const FxEmit *e = &E[p->em];
    p->vg += p->ga * lut(e->olWeight, u) * dt;
    if (p->lnd != 0.f) { float k = expf(p->lnd * dt); p->vx *= k; p->vy *= k; p->vz *= k; }
    float sp = lut(e->olSpeed, u);
    p->x += p->vx * sp * dt; p->y += (p->vy * sp + p->vg) * dt; p->z += p->vz * sp * dt;
    p->ang += p->spin * lut(e->olSpin, u) * dt;
    i++;
  }
}

int fxCount(void) { return np; }

// ---------- спрайты ----------
void fxSprite(int tex, float x, float y, float z, float w, float h, float rot, unsigned abgr, int blend, int flat) {
  if (!ready || tex < 0 || tex >= (int)H->nTex || nspr >= MAXSPR) return;
  Spr *s = &spr[nspr++]; s->x = x; s->y = y; s->z = z; s->w = w; s->h = h; s->rot = rot; s->c = abgr;
  s->tex = tex; s->blend = blend; s->flat = flat;
}
void fxSparkleC(float x, float y, float z, float size, float phase, unsigned abgr) {
  float pu = .75f + .25f * sinf(phase * 6.2831853f);
  unsigned c = abgr, o = 0;
  for (int k = 0; k < 24; k += 8) o |= ((unsigned)(((c >> k) & 255) * pu) & 255) << k;
  o |= 0xff000000u;
  if (texGlow >= 0) fxSprite(texGlow, x, y, z, size * .6f, size * .6f, 0.f, (o >> 2) & 0xff3f3f3f, 1, 0);
  if (texScratch >= 0) fxSprite(texScratch, x, y, z, size * 1.3f * pu, size * 1.3f * pu, phase * 1.5707963f, o, 1, 0);
}
void fxSparkle(float x, float y, float z, float size, float phase) { fxSparkleC(x, y, z, size, phase, 0xffc8f0ff); }

// ---------- рисование ----------
typedef struct { float u, v; unsigned c; float x, y, z; } FV;
static unsigned short qidx[(FX_MAX + MAXSPR + 3 * FX_MAX_INST) * 6] __attribute__((aligned(16)));
static int qidxN;
static unsigned short order[FX_MAX + MAXSPR + 3 * FX_MAX_INST];
static unsigned short keyOf[FX_MAX + MAXSPR + 3 * FX_MAX_INST];

static inline unsigned mulc(unsigned a, unsigned b) {   // покомпонентно /255
  unsigned o = 0;
  for (int s = 0; s < 32; s += 8) o |= ((((a >> s) & 255) * ((b >> s) & 255) + 127) / 255) << s;
  return o;
}
static void bindTex(int t) {
  const FxTex *x = &T[t];
  sceGuClutMode(GU_PSM_8888, 0, 0xff, 0);
  sceGuClutLoad(x->psm == 4 ? 2 : 32, blob + x->offClut);
  sceGuTexMode(x->psm == 4 ? GU_PSM_T4 : GU_PSM_T8, 0, 0, x->swz);
  sceGuTexImage(0, x->w, x->h, x->bufw, blob + x->offPix);
  sceGuTexFlush();
}
int fxTexBind(int t) { if (!ready || t < 0 || t >= (int)H->nTex) return 0; bindTex(t); return 1; }

#define FX_FOCAL 226.f            // пикселей на единицу tan: 136 / tan(62°/2) (FOVY main.c)
#define FX_NEAR_BUDGET 120000.f   // пикселей на ближние частицы за кадр (~1 экран)
float fxFill; int fxSkipped;
#define FX_TOTAL_BUDGET 260000.f  // пикселей на все частицы за кадр (~2 экрана): больше — плавно ужимаем (не меньше 0.75)
static float fillK = 1.f;
static int (*geRoomFn)(unsigned);
void fxSetGeRoom(int (*room)(unsigned bytes)) { geRoomFn = room; }
void fxDraw(float ex, float ey, float ez, float fx, float fy, float fz) {
  eye[0] = ex; eye[1] = ey; eye[2] = ez; haveEye = 1;
  float nearFill = 0.f; fxFill = 0.f; fxSkipped = 0;
  if (!ready) { nspr = 0; return; }
  // элементы: частицы, биллборды систем, спрайты
  int nb = 0; unsigned short bbI[3 * FX_MAX_INST], bbS[3 * FX_MAX_INST];
  for (int i = 0; i < FX_MAX_INST; i++) {
    Inst *s = &in_[i]; if (!s->used) continue;
    const FxSys *y = &S[s->sys];
    for (int b = 0; b < y->nBB && nb < 3 * FX_MAX_INST; b++) if (s->bbT < BB[y->firstBB + b].nFrames) { bbI[nb] = y->firstBB + b; bbS[nb++] = i; }
  }
  int n = np + nb + nspr; if (!n) return;
  // сортировка подсчётом по (смешивание, текстура): 0 alpha, 1 add, 2 subtract
  int nt = H->nTex, nk = 3 * nt;
  static unsigned short cnt[3 * 256 + 1];
  if (nk > 3 * 256) nk = 3 * 256;
  memset(cnt, 0, sizeof(unsigned short) * (nk + 1));
  for (int i = 0; i < n; i++) {
    int k;
    if (i < np) { const FxEmit *e = &E[ps[i].em]; k = e->blend * nt + e->tex; }
    else if (i < np + nb) { const FxBB *b = &BB[bbI[i - np]]; k = b->blend * nt + b->tex; }
    else { Spr *s = &spr[i - np - nb]; k = s->blend * nt + s->tex; }
    if (k >= nk) k = nk - 1;
    keyOf[i] = k; cnt[k + 1]++;
  }
  for (int k = 0; k < nk; k++) cnt[k + 1] += cnt[k];
  { static unsigned short pos_[3 * 256 + 1]; memcpy(pos_, cnt, sizeof(unsigned short) * (nk + 1));
    for (int i = 0; i < n; i++) order[pos_[keyOf[i]]++] = i; }
  if (qidxN < n) {
    int m = FX_MAX + MAXSPR + 3 * FX_MAX_INST;
    for (int q = 0; q < m; q++) { unsigned short *d = qidx + q * 6, b = q * 4; d[0] = b; d[1] = b + 1; d[2] = b + 2; d[3] = b; d[4] = b + 2; d[5] = b + 3; }
    qidxN = m; sceKernelDcacheWritebackRange(qidx, sizeof qidx);
  }
  // оси камеры
  float rx = -fz, rz = fx, rl = sqrtf(rx * rx + rz * rz); if (rl < 1e-4f) { rx = 1; rz = 0; rl = 1; }
  rx /= rl; rz /= rl;
  float R[3] = {rx, 0, rz}, U[3] = {-rz * fy, rz * fx - rx * fz, rx * fy};

  sceGuDisable(GU_FOG); sceGuDisable(GU_ALPHA_TEST);
  sceGuEnable(GU_TEXTURE_2D); sceGuEnable(GU_BLEND);
  sceGuTexFunc(GU_TFX_MODULATE, GU_TCC_RGBA);
  sceGuTexFilter(GU_LINEAR, GU_LINEAR); sceGuTexWrap(GU_CLAMP, GU_CLAMP);
  sceGuTexScale(1.f, 1.f); sceGuTexOffset(0.f, 0.f);
  sceGuDepthMask(GU_TRUE);   // глубину не пишем, но проверяем
  ScePspFMatrix4 Id; memset(&Id, 0, sizeof Id); Id.x.x = Id.y.y = Id.z.z = Id.w.w = 1.f;
  sceGuSetMatrix(GU_MODEL, &Id);

  for (int k = 0; k < nk; k++) {
    int a = cnt[k], b = cnt[k + 1]; if (a == b) continue;
    int blend = k / nt, tex = k % nt;
    if (blend == 1) sceGuBlendFunc(GU_ADD, GU_FIX, GU_FIX, 0xffffffff, 0xffffffff);
    else if (blend == 2) sceGuBlendFunc(GU_REVERSE_SUBTRACT, GU_FIX, GU_FIX, 0xffffffff, 0xffffffff);
    else sceGuBlendFunc(GU_ADD, GU_SRC_ALPHA, GU_ONE_MINUS_SRC_ALPHA, 0, 0);
    if (geRoomFn && !geRoomFn((unsigned)(b - a) * 4 * sizeof(FV) + 64)) { fxSkipped += b - a; continue; }   // правка 103: список GE полон
    bindTex(tex);
    FV *v = (FV *)sceGuGetMemory((b - a) * 4 * sizeof(FV)), *w = v; int nq = 0;
    for (int j = a; j < b; j++) {
      int i = order[j];
      float px, py, pz, hw, hh, ang, u0 = 0, u1 = 1, v0 = 0, v1 = 1; unsigned c; int flat = 0; const float *qr = NULL;
      if (i < np) {
        P *p = &ps[i]; const FxEmit *e = &E[p->em]; float u = p->age * p->inv;
        px = p->x; py = p->y; pz = p->z;
        hw = .5f * p->size * lut(e->olSize, u); hh = hw * e->aspect;
        unsigned ol = lutc(e->ol, u), rgb = p->rgb | 0xff000000u;
        c = mulc(ol, rgb);
        unsigned al = (unsigned)(((c >> 24) & 255) * p->ak); if (al > 255) al = 255;
        if (e->blend == 1 && !(e->flags & 1) && (e->flags & 2) && p->ak > 0.f) {   // add без COOL: гаснет по ALOL
          float f = al * (1.f / 255.f); c = mulc(c, ((unsigned)(f * 255) * 0x010101u) | 0xff000000u);
        }
        c = (c & 0xffffff) | (al << 24);
        if (e->angleMode == 2) {   // вдоль экранной скорости
          float sp = lut(e->olSpeed, u), vx = p->vx * sp, vy = p->vy * sp + p->vg, vz = p->vz * sp;
          ang = atan2f(vx * U[0] + vy * U[1] + vz * U[2], vx * R[0] + vz * R[2]);
        } else ang = p->ang;
        int nf = e->nFr;
        if (nf > 1 && e->texMode) {
          int f = e->texMode == 1 ? (int)((p->seed + (int)(p->age * e->texRate) * 97) % nf) : ((int)(p->age * e->texRate)) % nf;
          int cx = f % e->cols, cy = f / e->cols;
          u0 = (float)cx / e->cols; u1 = (float)(cx + 1) / e->cols; v0 = (float)cy / e->rows; v1 = (float)(cy + 1) / e->rows;
        } else if (e->cols > 1 || e->rows > 1) { u1 = 1.f / e->cols; v1 = 1.f / e->rows; }
      } else if (i < np + nb) {
        const FxBB *bq = &BB[bbI[i - np]]; Inst *s = &in_[bbS[i - np]];
        int f = (int)s->bbT; if (f >= bq->nFrames) f = bq->nFrames - 1; if (f < 0) f = 0;
        const float *L = (const float *)(blob + bq->offLut) + f * 3;
        hw = L[0] * .5f; hh = L[1] * .5f; c = ((const unsigned *)L)[2]; ang = 0;
        px = s->pos[0]; py = s->pos[1]; pz = s->pos[2];
        if (bq->mode == 0) { flat = 2; qr = bq->rot; py += .04f; }
        else { float dx = ex - px, dy = ey - py, dz = ez - pz, l = sqrtf(dx * dx + dy * dy + dz * dz);
               if (l > 1e-3f) { float k2 = fminf(bq->dist, l * .5f) / l; px += dx * k2; py += dy * k2; pz += dz * k2; } }
        if (bq->blend == 1) c |= 0xff000000u;
      } else {
        Spr *s = &spr[i - np - nb];
        px = s->x; py = s->y; pz = s->z; hw = s->w * .5f; hh = s->h * .5f; ang = s->rot; c = s->c; flat = s->flat;
      }
      // расстояние до глаза: не рисовать за камерой, ужать у объектива, гасить ближе 4 м.
      // Заливка GE — главный риск: дым, оставленный машиной, летит прямо в камеру (7 м сзади), и каждый клуб
      // у объектива закрывал до трети экрана. Потолок размера растёт с расстоянием (у камеры ~15% высоты кадра,
      // с 8 м — прежние 0.42·d, взрыв у машины не меняется), ближние (< 6 м) делят общий бюджет заливки.
      float d = (px - ex) * fx + (py - ey) * fy + (pz - ez) * fz;
      if (!flat) {
        if (d < 1.f) continue;
        hw *= fillK; hh *= fillK;
        float mx = d * fminf(.42f, .1f + .04f * d); if (hw > mx) { hh *= mx / hw; hw = mx; } if (hh > mx) { hw *= mx / hh; hh = mx; }
        float px2 = 4.f * hw * hh * (FX_FOCAL * FX_FOCAL) / (d * d);   // пикселей на экране
        if (d < 6.f) { if (nearFill + px2 > FX_NEAR_BUDGET) { fxSkipped++; continue; } nearFill += px2; }
        fxFill += px2;
        if (d < 4.f) {
          float f = (d - 1.f) * (1.f / 3.f);
          if (k / nt == 0) c = (c & 0xffffff) | ((unsigned)(((c >> 24) & 255) * f) << 24);
          else c = mulc(c, ((unsigned)(f * 255) * 0x010101u) | 0xff000000u);
        }
      }
      float e1[3], e2[3];
      if (flat == 2) {   // биллборд, лежащий по кватерниону ROT
        static const float X[3] = {1, 0, 0}, Y[3] = {0, 1, 0}; float a1[3], a2[3]; qrot(qr, X, a1); qrot(qr, Y, a2);
        for (int t = 0; t < 3; t++) { e1[t] = a1[t] * hw; e2[t] = a2[t] * hh; }
      } else if (flat) {
        float cs = cosf(ang), sn = sinf(ang);
        e1[0] = cs * hw; e1[1] = 0; e1[2] = sn * hw; e2[0] = -sn * hh; e2[1] = 0; e2[2] = cs * hh;
      } else {
        float cs = cosf(ang), sn = sinf(ang);
        for (int t = 0; t < 3; t++) { e1[t] = (cs * R[t] + sn * U[t]) * hw; e2[t] = (-sn * R[t] + cs * U[t]) * hh; }
      }
      FV q0 = {u0, v0, c, px - e1[0] + e2[0], py - e1[1] + e2[1], pz - e1[2] + e2[2]};
      FV q1 = {u1, v0, c, px + e1[0] + e2[0], py + e1[1] + e2[1], pz + e1[2] + e2[2]};
      FV q2 = {u1, v1, c, px + e1[0] - e2[0], py + e1[1] - e2[1], pz + e1[2] - e2[2]};
      FV q3 = {u0, v1, c, px - e1[0] - e2[0], py - e1[1] - e2[1], pz - e1[2] - e2[2]};
      w[0] = q0; w[1] = q1; w[2] = q2; w[3] = q3; w += 4; nq++;
    }
    if (nq) sceGuDrawArray(GU_TRIANGLES, GU_INDEX_16BIT | GU_TEXTURE_32BITF | GU_COLOR_8888 | GU_VERTEX_32BITF | GU_TRANSFORM_3D,
                           nq * 6, qidx, v);
  }
  nspr = 0;
  { float raw = fxFill / (fillK * fillK), want = raw > FX_TOTAL_BUDGET ? sqrtf(FX_TOTAL_BUDGET / raw) : 1.f;
    if (want < .75f) want = .75f;
    fillK += (want - fillK) * (want < fillK ? .3f : .05f); }
  sceGuBlendFunc(GU_ADD, GU_SRC_ALPHA, GU_ONE_MINUS_SRC_ALPHA, 0, 0);
  sceGuDisable(GU_BLEND);
  sceGuDepthMask(GU_FALSE);
  sceGuTexWrap(GU_REPEAT, GU_REPEAT);
  sceGuTexScale(128.f, 128.f);
  sceGuEnable(GU_FOG);
}
