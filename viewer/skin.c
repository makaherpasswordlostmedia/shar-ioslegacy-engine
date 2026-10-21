// skin.c: .chr loader, animation sampling/blending, bone palette, GE hardware-skinned drawing. See skin.h.
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "skin.h"
#include "levlight.h"

#ifdef SKIN_HOST
#include <stdio.h>
#else
#include <malloc.h>
#include <pspkernel.h>
#include <pspgu.h>
#endif

_Static_assert(sizeof(SkinHeader) == 128 && sizeof(SkinJoint) == 128 && sizeof(SkinBatch) == 48 && sizeof(SkinTex) == 48 &&
               sizeof(SkinClip) == 80 && sizeof(SkinTrackRec) == 16 && sizeof(SkinBlinkKey) == 8, "CHR1 layout");

// ---------------------------------------------------------------- loading
static int inside(const SkinHeader *h, unsigned off, unsigned len) { return off <= h->size && len <= h->size - off; }

int skinBatchValid(const SkinModel *m, const SkinBatch *b) {
  const SkinHeader *h=m->h; unsigned stored=b->nverts;
  if(!b->stride || b->nb<1 || b->nb>8 || b->tex>=h->nTex || b->offVerts>h->size)return 0;
  if(b->flags&4) {
#ifdef CHAR_INDEXED_OLD
    return 0;
#else
    if(h->version!=2 || (b->vtype & (3u<<11))!=(2u<<11) || (b->pad[0]&1) || b->pad[0]>h->size || b->nverts>(h->size-b->pad[0])/2)return 0;
    stored=b->pad[1];if(!stored || stored>65535)return 0;
    const unsigned short *idx=(const unsigned short *)(m->base+b->pad[0]);
    for(unsigned i=0;i<b->nverts;i++)if(idx[i]>=stored)return 0;
#endif
  }
  if(stored>(h->size-b->offVerts)/b->stride)return 0;
  for(unsigned j=0;j<b->nb;j++)if(b->bones[j]>=h->nJoints)return 0;
  return 1;
}

static SkinModel *skinFromBuf(unsigned char *d, unsigned size);
// №775: причина последнего отказа skinLoad (игрок уровня на PSP «только машина»): 1 не открылся, 2 нет памяти, 3 прочитано меньше (skinLoadGot — сколько),
// 4 разбор (заголовок, границы, батчи). 0 — прочитан
int skinLoadErr; unsigned skinLoadGot;
SkinModel *skinLoad(const char *path) {
  unsigned char *d = 0; unsigned size = 0; skinLoadErr = 0; skinLoadGot = 0;
#ifdef SKIN_HOST
  FILE *f = fopen(path, "rb"); if (!f) { skinLoadErr = 1; return 0; }
  fseek(f, 0, SEEK_END); size = (unsigned)ftell(f); fseek(f, 0, SEEK_SET);
  d = aligned_alloc(64, (size + 63) & ~63u);
  if (!d || fread(d, 1, size, f) != size) { skinLoadErr = d ? 3 : 2; fclose(f); free(d); return 0; }
  fclose(f);
#else
  SceUID fd = sceIoOpen(path, PSP_O_RDONLY, 0); if (fd < 0) { skinLoadErr = 1; return 0; }
  size = (unsigned)sceIoLseek32(fd, 0, PSP_SEEK_END); sceIoLseek32(fd, 0, PSP_SEEK_SET);
  d = memalign(64, size);
  if (!d) { skinLoadErr = 2; sceIoClose(fd); return 0; }
  int got = sceIoRead(fd, d, size);
  if (got != (int)size) { skinLoadErr = 3; skinLoadGot = (unsigned)got; sceIoClose(fd); free(d); return 0; }
  sceIoClose(fd);
#endif
  SkinModel *m = skinFromBuf(d, size); if (!m) skinLoadErr = 4;
  return m;
}
// разбор и проверка прочитанного файла .chr (d — память под модель, при отказе освобождается)
static SkinModel *skinFromBuf(unsigned char *d, unsigned size) {
  const SkinHeader *h = (const SkinHeader *)d;
  if (size < sizeof(SkinHeader) || memcmp(h->magic, "CHR1", 4) || (h->version != 1 && h->version != 2) || h->size != size || h->nJoints > SKIN_MAXJ ||
      !inside(h, h->offJoints, h->nJoints * 128) || !inside(h, h->offBatches, h->nBatches * 48) || !inside(h, h->offTex, h->nTex * 48) ||
      !inside(h, h->offClips, h->nClips * 80) || !inside(h, h->offBlink, h->nBlink * 8)) { free(d); return 0; }
#ifdef CHAR_INDEXED_OLD
  if(h->version!=1){free(d);return 0;}
#endif
  SkinModel *m = malloc(sizeof *m); if (!m) { free(d); return 0; }
  m->base = d; m->h = h;
  m->j = (const SkinJoint *)(d + h->offJoints); m->b = (const SkinBatch *)(d + h->offBatches);
  m->tex = (const SkinTex *)(d + h->offTex); m->c = (const SkinClip *)(d + h->offClips);
  m->blink = (const SkinBlinkKey *)(d + h->offBlink);
  for (unsigned i = 0; i < h->nBatches; i++) {       // everything the GE will read must be inside the file
    const SkinBatch *b = &m->b[i];
    if (!skinBatchValid(m,b)) { free(d); free(m); return 0; }
  }
  for (unsigned i = 0; i < h->nClips; i++) if (!inside(h, m->c[i].offTracks, h->nJoints * 16)) { free(d); free(m); return 0; }
#ifndef SKIN_HOST
  sceKernelDcacheWritebackRange(d, size);            // the GE reads vertices, CLUTs and texels from RAM
#endif
  return m;
}

// Предзагрузка модели без остановки кадра (разбор ночи 11.10 / тур 12: чтение .chr ~21–28 мс на модель — кадр 40–70 мс при каждой подгрузке персонажа этапа).
// PSP: чтение уходит в sceIoReadAsync, кадры идут; skinPreReady — прочитано, skinPreFinish — разбор из памяти (≈ мс); если ещё не прочитано, Finish ждёт остаток.
// Хост (SKIN_HOST, боты): читает сразу при Start — поведение и порядок прежние. Результат тот же, что у skinLoad.
struct SkinPre { int fd; unsigned char *d; unsigned size; int done, err; long long res; };   // done/res: итог sceIoPollAsync, когда он вернул «готово» (поллинг забирает результат: sceIoWaitAsync после него даёт ошибку)
SkinPre *skinPreStart(const char *path) {
  SkinPre *p = calloc(1, sizeof *p); if (!p) return 0; p->fd = -1;
#ifdef SKIN_HOST
  FILE *f = fopen(path, "rb"); if (!f) { free(p); return 0; }
  fseek(f, 0, SEEK_END); p->size = (unsigned)ftell(f); fseek(f, 0, SEEK_SET);
  p->d = aligned_alloc(64, (p->size + 63) & ~63u);
  if (!p->d || fread(p->d, 1, p->size, f) != p->size) { fclose(f); free(p->d); free(p); return 0; }
  fclose(f);
#else
  p->fd = sceIoOpen(path, PSP_O_RDONLY, 0); if (p->fd < 0) { free(p); return 0; }
  p->size = (unsigned)sceIoLseek32(p->fd, 0, PSP_SEEK_END); sceIoLseek32(p->fd, 0, PSP_SEEK_SET);
  p->d = memalign(64, p->size);
  if (!p->d || sceIoReadAsync(p->fd, p->d, p->size) < 0) { sceIoClose(p->fd); free(p->d); free(p); return 0; }
#endif
  return p;
}
// Ревизия 11.10 (1.2): sceIoPollAsync возвращает 0 — готово, 1 — идёт, отрицательное — ОШИБКА; ошибку считали «ещё идёт» вечно: слот очереди, буфер и дескриптор не освобождались, после четырёх таких
// сбоев модели персонажей этапа не грузились. Теперь ошибка = «закончено» (skinPreFinish вернёт 0, вызывающий читает синхронно). SKINPRE_ERR_OLD=1 — прежнее
// 15.10 (TEST18, разбор «недогрузки» D_L1_city): фоновое чтение моделей персонажей не срабатывало ни разу — 94 из 94 «MSNNPC async-fail, sync read» (каждый раз синхронное чтение 28–33 мс в кадре):
// skinPreReady опрашивал sceIoPollAsync (забирает результат), а skinPreFinish затем звал sceIoWaitAsync, который после этого возвращает ошибку. Теперь итог опроса запоминается и Wait не зовётся.
// SKINPRE_POLL_RES_OLD=1 — прежнее
#ifndef SKINPRE_POLL_RES_OLD
#define SKINPRE_POLL_RES_OLD 0
#endif
int skinPreDone(int pollRet) { return SKINPRE_ERR_OLD ? pollRet == 0 : pollRet <= 0; }
int skinPreReady(SkinPre *p) {
#ifdef SKIN_HOST
  (void)p; return 1;
#else
  if (!p) return 0;
  if (!SKINPRE_POLL_RES_OLD && p->done) return 1;
  SceInt64 res = -1; int r = sceIoPollAsync(p->fd, &res), d = skinPreDone(r);
  if (!SKINPRE_POLL_RES_OLD && d) { p->done = 1; p->err = r < 0; p->res = res; }
  return d;
#endif
}
SkinModel *skinPreFinish(SkinPre *p) {
  if (!p) return 0;
#ifndef SKIN_HOST
  SceInt64 res = -1; int r = 0;
  if (!SKINPRE_POLL_RES_OLD && p->done && !p->err) res = p->res;   // опрос уже вернул «готово» и забрал результат — Wait дал бы ошибку и модель шла бы синхронным чтением (TEST18: 94 из 94 «async-fail»)
  else r = sceIoWaitAsync(p->fd, &res);
  sceIoClose(p->fd);
  if (r < 0 || res != (SceInt64)p->size) { free(p->d); free(p); return 0; }
#endif
  unsigned char *d = p->d; unsigned size = p->size; free(p);
  return skinFromBuf(d, size);
}
void skinPreCancel(SkinPre *p) {
  if (!p) return;
#ifndef SKIN_HOST
  SceInt64 res; sceIoWaitAsync(p->fd, &res); sceIoClose(p->fd);
#endif
  free(p->d); free(p);
}

static struct { const SkinModel *m; int clip; float lift; } footCache[96]; static int nFootCache;   // №510: skinFootLift
void skinFree(SkinModel *m) {
  if (m) { for (int i = 0; i < nFootCache; ) if (footCache[i].m == m) footCache[i] = footCache[--nFootCache]; else i++;   // адрес модели может достаться другой
    free((void *)m->base); free(m); } }

int skinFindClip(const SkinModel *m, const char *name) {
  size_t n = strlen(name);
  for (unsigned i = 0; i < m->h->nClips; i++) if (!strcmp(m->c[i].name, name)) return (int)i;
  for (unsigned i = 0; i < m->h->nClips; i++) {
    size_t l = strlen(m->c[i].name);
    if (l > n && m->c[i].name[l - n - 1] == '_' && !strcmp(m->c[i].name + l - n, name)) return (int)i;
  }
  return -1;
}
int skinFindJoint(const SkinModel *m, const char *name) {
  for (unsigned i = 0; i < m->h->nJoints; i++) if (!strcmp(m->j[i].name, name)) return (int)i;
  return -1;
}

// ---------------------------------------------------------------- sampling
// key pair for frame f: fr[k] <= f < fr[k+1]; caller handles f outside [fr[0], fr[n-1]]
static int findKey(const unsigned short *fr, int n, float f) {
  int lo = 0, hi = n - 1;
  while (hi - lo > 1) { int mid = (lo + hi) >> 1; if ((float)fr[mid] <= f) lo = mid; else hi = mid; }
  return lo;
}

// shortest path; nlerp while the two rotations are close (dot > 0.95, < 36 deg), slerp beyond (a few Homer tracks
// have keys up to 120 deg apart). Result normalised.
static void qmix(float *o, const float *a, const float *b, float u) {
  float d = a[0] * b[0] + a[1] * b[1] + a[2] * b[2] + a[3] * b[3], sb = 1.f, ka, kb;
  if (d < 0) { d = -d; sb = -1.f; }
  if (d > .95f) { ka = 1.f - u; kb = u; }
  else { float th = acosf(d > 1.f ? 1.f : d), s = 1.f / sinf(th); ka = sinf((1.f - u) * th) * s; kb = sinf(u * th) * s; }
  kb *= sb;
  float x = ka * a[0] + kb * b[0], y = ka * a[1] + kb * b[1], z = ka * a[2] + kb * b[2], w = ka * a[3] + kb * b[3];
  float r = 1.f / sqrtf(x * x + y * y + z * z + w * w);
  o[0] = x * r; o[1] = y * r; o[2] = z * r; o[3] = w * r;
}

#define Q16 (1.f / 32767.f)
static void rotAt(const unsigned char *base, const SkinTrackRec *tr, float f, float *q) {
  int n = tr->nRot; const unsigned short *fr = (const unsigned short *)(base + tr->offRot);
  const short *v = (const short *)(base + tr->offRot + ((2 * n + 3) & ~3));
  int k; float u;
  if (n == 1 || f <= fr[0]) { k = 0; u = 0; }
  else if (f >= fr[n - 1]) { k = n - 1; u = 0; }
  else { k = findKey(fr, n, f); u = (f - fr[k]) / (float)(fr[k + 1] - fr[k]); }
  const short *a = v + 4 * k;
  if (u == 0.f) {
    float x = a[0] * Q16, y = a[1] * Q16, z = a[2] * Q16, w = a[3] * Q16, r = 1.f / sqrtf(x * x + y * y + z * z + w * w);
    q[0] = x * r; q[1] = y * r; q[2] = z * r; q[3] = w * r; return;
  }
  float qa[4] = {a[0] * Q16, a[1] * Q16, a[2] * Q16, a[3] * Q16}, qb[4] = {a[4] * Q16, a[5] * Q16, a[6] * Q16, a[7] * Q16};
  qmix(q, qa, qb, u);
}
static void transAt(const unsigned char *base, const SkinTrackRec *tr, float f, float *t) {
  int n = tr->nTrans; const unsigned short *fr = (const unsigned short *)(base + tr->offTrans);
  const float *v = (const float *)(base + tr->offTrans + ((2 * n + 3) & ~3));
  int k; float u;
  if (n == 1 || f <= fr[0]) { k = 0; u = 0; }
  else if (f >= fr[n - 1]) { k = n - 1; u = 0; }
  else { k = findKey(fr, n, f); u = (f - fr[k]) / (float)(fr[k + 1] - fr[k]); }
  const float *a = v + 3 * k;
  if (u == 0.f) { t[0] = a[0]; t[1] = a[1]; t[2] = a[2]; return; }
  t[0] = a[0] + (a[3] - a[0]) * u; t[1] = a[1] + (a[4] - a[1]) * u; t[2] = a[2] + (a[5] - a[2]) * u;
}

static float clipFrame(const SkinClip *c, float t) {
  float f = t * c->fps, last = c->frames - 1.f;
  return f < 0.f ? 0.f : f > last ? last : f;
}

void skinSample(const SkinModel *m, int clip, float t, SkinXf *out) {
  int nj = (int)m->h->nJoints, root = (int)m->h->rootJoint;
  if (clip < 0 || clip >= (int)m->h->nClips) {       // no clip: bind pose
    for (int j = 0; j < nj; j++) { memcpy(out[j].q, m->j[j].q, 16); memcpy(out[j].t, m->j[j].t, 12); }
    return;
  }
  const SkinClip *c = &m->c[clip]; float f = clipFrame(c, t);
  const SkinTrackRec *tr = (const SkinTrackRec *)(m->base + c->offTracks);
  for (int j = 0; j < nj; j++, tr++) {
    if (tr->nRot) rotAt(m->base, tr, f, out[j].q); else memcpy(out[j].q, m->j[j].q, 16);
    if (tr->nTrans && j != root) transAt(m->base, tr, f, out[j].t); else memcpy(out[j].t, m->j[j].t, 12);
  }
}

void skinRootMotion(const SkinModel *m, int clip, float t, float out[3]) {
  int root = (int)m->h->rootJoint;
  memcpy(out, m->j[root].t, 12);
  if (clip < 0 || clip >= (int)m->h->nClips) return;
  const SkinClip *c = &m->c[clip];
  const SkinTrackRec *tr = (const SkinTrackRec *)(m->base + c->offTracks) + root;
  if (tr->nTrans) transAt(m->base, tr, clipFrame(c, t), out);
}

void skinBlend(SkinXf *a, const SkinXf *b, float w, int n) {
  if (w <= 0.f) return;
  if (w >= 1.f) { memcpy(a, b, sizeof(SkinXf) * n); return; }
  for (int j = 0; j < n; j++) {
    qmix(a[j].q, a[j].q, b[j].q, w);
    for (int k = 0; k < 3; k++) a[j].t[k] += (b[j].t[k] - a[j].t[k]) * w;
  }
}

// ---------------------------------------------------------------- palette
// affine 3x4 matrices in ScePspFMatrix4 layout: x, y, z = basis columns, w = translation (w components unused)
static void mul34(ScePspFMatrix4 *o, const ScePspFMatrix4 *a, const float *b /* 4 columns x 3 */) {
  const float *A = (const float *)a; float *O = (float *)o;
  for (int c = 0; c < 4; c++) {
    const float *bc = b + 3 * c;
    O[4 * c + 0] = A[0] * bc[0] + A[4] * bc[1] + A[8] * bc[2];
    O[4 * c + 1] = A[1] * bc[0] + A[5] * bc[1] + A[9] * bc[2];
    O[4 * c + 2] = A[2] * bc[0] + A[6] * bc[1] + A[10] * bc[2];
    O[4 * c + 3] = 0.f;
  }
  O[12] += A[12]; O[13] += A[13]; O[14] += A[14]; O[15] = 1.f;
}

void skinPalette(const SkinModel *m, const SkinXf *xf, ScePspFMatrix4 *pal, ScePspFMatrix4 *world) {
  ScePspFMatrix4 wtmp[SKIN_MAXJ];
  ScePspFMatrix4 *W = world ? world : wtmp;
  int nj = (int)m->h->nJoints;
  for (int j = 0; j < nj; j++) {
    const SkinJoint *jt = &m->j[j]; const float *q = xf[j].q;
    float x = q[0], y = q[1], z = q[2], w = q[3];
    float L[12] = {                                   // local = T * R * S as 4 columns x 3 rows
      (1 - 2 * (y * y + z * z)) * jt->s[0], (2 * (x * y + z * w)) * jt->s[0], (2 * (x * z - y * w)) * jt->s[0],
      (2 * (x * y - z * w)) * jt->s[1], (1 - 2 * (x * x + z * z)) * jt->s[1], (2 * (y * z + x * w)) * jt->s[1],
      (2 * (x * z + y * w)) * jt->s[2], (2 * (y * z - x * w)) * jt->s[2], (1 - 2 * (x * x + y * y)) * jt->s[2],
      xf[j].t[0], xf[j].t[1], xf[j].t[2]};
    if (jt->parent < 0) {
      float *o = (float *)&W[j];
      for (int c = 0; c < 4; c++) { o[4 * c] = L[3 * c]; o[4 * c + 1] = L[3 * c + 1]; o[4 * c + 2] = L[3 * c + 2]; o[4 * c + 3] = 0; }
      o[15] = 1.f;
    } else mul34(&W[j], &W[jt->parent], L);
    mul34(&pal[j], &W[j], jt->inv);
  }
}

// ---------------------------------------------------------------- player
void skinInit(SkinPlayer *p, const SkinModel *m) {
  memset(p, 0, sizeof *p);
  p->m = m; p->clip = p->prev = -1; p->speed = 1.f; p->eyeTex = -1; p->seed = 12345u;
  p->blinkWait = 2.f; p->blinkT = -1.f; p->jaw = skinFindJoint(m, "Jaw"); p->jawOpen = 0.f;
  skinSample(m, -1, 0, p->xf); skinPalette(m, p->xf, p->pal, p->world);
}

void skinPlay(SkinPlayer *p, int clip, int loop, float fade) {
  if (clip == p->clip) { p->loop = loop; return; }
  if (p->clip >= 0 && fade > 0.f) {
    // if a fade is still running the outgoing pose is approximated by the current clip only
    p->prev = p->clip; p->prevT = p->t; p->prevLoop = p->loop; p->fade = 0.f; p->fadeLen = fade;
  } else p->prev = -1;
  p->clip = clip; p->t = 0.f; p->loop = loop;
}

static float advance(const SkinModel *m, int clip, float t, int loop) {
  if (clip < 0) return 0.f;
  float len = m->c[clip].length;
  if (len <= 0.f) return 0.f;
  if (loop) { t = fmodf(t, len); if (t < 0) t += len; }
  else if (t > len) t = len;
  return t;
}

void skinTick(SkinPlayer *p, float dt) {
  const SkinModel *m = p->m; float d = dt * p->speed;
  p->t = advance(m, p->clip, p->t + d, p->loop);
  if (p->prev >= 0) {
    p->fade += dt;
    if (p->fade >= p->fadeLen) p->prev = -1;
    else p->prevT = advance(m, p->prev, p->prevT + d, p->prevLoop);
  }
  // eye blink (original texture animation, 9 frames @ 30 fps), every 2..6 s
  p->eyeTex = -1;
  if (m->h->nBlink && m->h->blinkFps > 0.f) {
    if (p->blinkT < 0.f) {
      p->blinkWait -= dt;
      if (p->blinkWait <= 0.f) p->blinkT = 0.f;
    }
    if (p->blinkT >= 0.f) {
      float f = p->blinkT * m->h->blinkFps; const SkinBlinkKey *k = m->blink; int n = (int)m->h->nBlink;
      if (f > k[n - 1].frame + 1.f) {
        p->blinkT = -1.f; p->seed = p->seed * 1103515245u + 12345u;
        p->blinkWait = 2.f + (float)((p->seed >> 16) & 1023) * (4.f / 1023.f);
      } else {
        int i = 0; while (i + 1 < n && k[i + 1].frame <= f) i++;
        p->eyeTex = k[i].tex; p->blinkT += dt;
      }
    }
  }
}

void skinPose(SkinPlayer *p) {
  const SkinModel *m = p->m; int nj = (int)m->h->nJoints;
  skinSample(m, p->clip, p->t, p->xf);
  if (p->prev >= 0 && p->fadeLen > 0.f) {
    skinSample(m, p->prev, p->prevT, p->tmp);
    float u = p->fade / p->fadeLen; u = u * u * (3.f - 2.f * u);        // smoothstep
    skinBlend(p->tmp, p->xf, u, nj);
    memcpy(p->xf, p->tmp, sizeof(SkinXf) * nj);
  }
  if (p->jawOpen != 0.f) skinJawOpen(p->xf, p->jaw, p->jawOpen);
  skinPalette(m, p->xf, p->pal, p->world);
}
void skinJawOpen(SkinXf *xf, int j, float rad) {
  if (j < 0 || j >= SKIN_MAXJ || rad == 0.f) return;
  float s = sinf(rad * .5f), c = cosf(rad * .5f), *q = xf[j].q, x = q[0], y = q[1], z = q[2], w = q[3];   // q * (0, 0, s, c)
  q[0] = x * c + y * s; q[1] = y * c - x * s; q[2] = z * c + w * s; q[3] = w * c - z * s;
}

void skinUpdate(SkinPlayer *p, float dt) { skinTick(p, dt); skinPose(p); }

float skinClipSpeed(const SkinModel *m, int clip) {
  if (clip < 0 || clip >= (int)m->h->nClips || m->c[clip].length <= 0.f) return 0.f;
  float a[3], b[3]; skinRootMotion(m, clip, 0.f, a); skinRootMotion(m, clip, m->c[clip].length, b);
  float dx = b[0] - a[0], dz = b[2] - a[2];
  return sqrtf(dx * dx + dz * dz) / m->c[clip].length;
}

// №510 (Роб: «Милхаус ходит выше уровня»): клипы общего набора npd_loco_* сняты под один скелет, а у персонажей разные пропорции — стопы в клипе
// выше (Милхаус +0,18…0,22 м, Ральф +0,3…0,34, Нельсон +0,14…0,18) или ниже (Скиннер, Гил −0,11) своих стоп в позе привязки; клипы
// собственного набора (Барт, Лиза, Гомер) совпадают. Правило порта: самый низкий сустав стопы/носка/щиколотки клипа (min по кадрам) возвращается
// на высоту этого сустава в позе привязки — смещение по высоте при расстановке (skinPlace(..., y + lift)). Считается один раз на пару (модель,
// клип) и кешируется; меньше 3 см — 0. -DSKIN_FOOTLIFT_OLD=1 — без поправки
#ifndef SKIN_FOOTLIFT_OLD
#define SKIN_FOOTLIFT_OLD 0
#endif
static int footJoint(const char *n) {
  for (const char *p = n; *p; p++) { char c = (char)(*p | 0x20);
    if (c == 'f' && (p[1] | 0x20) == 'o' && (p[2] | 0x20) == 'o' && (p[3] | 0x20) == 't') return 1;
    if (c == 't' && (p[1] | 0x20) == 'o' && (p[2] | 0x20) == 'e') return 1;
    if (c == 'a' && (p[1] | 0x20) == 'n' && (p[2] | 0x20) == 'k' && (p[3] | 0x20) == 'l' && (p[4] | 0x20) == 'e') return 1; }
  return 0;
}
// №762 (Роб 17.10, TEST32 на PSP: «продавец ходит в воздухе, стопы на уровне колен Гомера»): у части моделей подошвы в позе привязки не на нуле — низ модели
// (bbox[1]; сустав стопы у всех на 5–10 см выше него): gil +0,30, skinner +0,36, прохожие male2/moleman/ralph/kearney/eddie +0,11…0,14, patty/selma −0,40.
// Поправка стоп считала только разницу клипа и позы привязки — персонаж висел или тонул на эту высоту. Теперь подошва позы привязки вычитается всегда
// (у Гомера и большинства 0). SKIN_SOLE_OLD=1 / «flag soleold 1» — как было
#ifndef SKIN_SOLE_OLD
#define SKIN_SOLE_OLD 0
#endif
static int skinSoleOld = SKIN_SOLE_OLD;
static float skinSole(const SkinModel *m) { if (skinSoleOld || !m || !m->h) return 0.f; float s = m->h->bbox[1]; return (fabsf(s) >= .03f && fabsf(s) < .8f) ? s : 0.f; }
void skinSetSoleOld(int on) { skinSoleOld = on; nFootCache = 0; }
float skinFootLift(const SkinModel *m, int clip) {
  if (SKIN_FOOTLIFT_OLD || !m) return 0.f;
  if (clip < 0 || clip >= (int)m->h->nClips || m->c[clip].length <= 0.f) return -skinSole(m);
  for (int i = 0; i < nFootCache; i++) if (footCache[i].m == m && footCache[i].clip == clip) return footCache[i].lift;
  float rest = 1e9f, low = 1e9f;
  for (unsigned j = 0; j < m->h->nJoints; j++) { if (!footJoint(m->j[j].name)) continue;
    const float *v = m->j[j].inv; float y = -(v[3] * v[9] + v[4] * v[10] + v[5] * v[11]);   // начало сустава в позе привязки: −Rᵀ·p, строка y (столбец 1 матрицы GE)
    if (y < rest) rest = y; }
  if (rest < 1e8f) {
    SkinXf xf[SKIN_MAXJ]; ScePspFMatrix4 pal[SKIN_MAXJ] __attribute__((aligned(16))), wd[SKIN_MAXJ] __attribute__((aligned(16)));
    for (int f = 0; f < 12; f++) { skinSample(m, clip, m->c[clip].length * (float)f / 12.f, xf); skinPalette(m, xf, pal, wd);
      for (unsigned j = 0; j < m->h->nJoints; j++) if (footJoint(m->j[j].name) && wd[j].w.y < low) low = wd[j].w.y; } }
  float lift = (rest < 1e8f && low < 1e8f) ? rest - low : 0.f;
  if (fabsf(lift) < .03f || fabsf(lift) > 1.f) lift = 0.f;
  lift -= skinSole(m);   // №762: подошва позы привязки — на землю
  if (nFootCache < 96) { footCache[nFootCache].m = m; footCache[nFootCache].clip = clip; footCache[nFootCache].lift = lift; nFootCache++; }
  return lift;
}

void skinPlace(ScePspFMatrix4 *w, float x, float y, float z, float heading) {
  float c = cosf(heading), s = sinf(heading);
  memset(w, 0, sizeof *w);
  w->x.x = c; w->x.z = -s; w->y.y = 1.f; w->z.x = s; w->z.z = c;       // +Z (model forward) -> (sin h, 0, cos h)
  w->w.x = x; w->w.y = y; w->w.z = z; w->w.w = 1.f;
}

void skinPlaceTilt(ScePspFMatrix4 *w, float x, float y, float z, float heading, float pitch, float pivotY) {
  float c = cosf(heading), s = sinf(heading), cp = cosf(pitch), sp = sinf(pitch);
  memset(w, 0, sizeof *w);                                    // Ry(heading) * [точка поворота] Rx(pitch)
  w->x.x = c;       w->x.z = -s;
  w->y.x = sp * s;  w->y.y = cp;  w->y.z = sp * c;            // +Y модели (голова) -> к курсу
  w->z.x = cp * s;  w->z.y = -sp; w->z.z = cp * c;            // +Z модели (лицо) -> вниз
  w->w.x = x - pivotY * sp * s; w->w.y = y + pivotY * (1.f - cp); w->w.z = z - pivotY * sp * c; w->w.w = 1.f;
}

int skinToon;
int skinToonEyes = !TOON_EYES_OLD;
unsigned skinToonDraws, skinToonVerts, skinToonBytesNow, skinToonHullCalls;
void skinSetToon(int on) { skinToon = SHAR_TOON_AVAILABLE ? !!on : 0; }

// ---------------------------------------------------------------- drawing
#ifndef SKIN_HOST
static ScePspFVector3 sunDir = {SKIN_SUN_DIR_X, SKIN_SUN_DIR_Y, SKIN_SUN_DIR_Z};
void skinSunDirXZ(float *x, float *z);
static unsigned sunCol = SKIN_SUN_ABGR, ambCol = SKIN_AMB_ABGR;   // свет уровня 1; уровень N — skinLight из LGT1 (main.c)

// 16.10 (№78, Роб: «Гомер сливается с дорогой»): контраст света персонажей чуть выше, форма света не меняется — солнце ярче, фон темнее (проценты; 100/100 — как было).
// Свет Гомера на улице: солнце 0x90 + фон 0x70 дают почти плоскую заливку (сумма 256). flag homerlit 1 = SKIN_LIT_SUN_PCT / SKIN_LIT_AMB_PCT; skinsun / skinamb — отдельно. Цена нулевая (те же команды GE)
int skinSunPct = 100, skinAmbPct = 100;
static unsigned skinScaleCol(unsigned c, int pct) {
  if (pct == 100) return c;
  unsigned r = (c & 255) * pct / 100, g = ((c >> 8) & 255) * pct / 100, b = ((c >> 16) & 255) * pct / 100;
  return (c & 0xff000000u) | ((b > 255 ? 255 : b) << 16) | ((g > 255 ? 255 : g) << 8) | (r > 255 ? 255 : r);
}
void skinLight(float dx, float dy, float dz, unsigned sunAbgr, unsigned ambientAbgr) {
  float l = sqrtf(dx * dx + dy * dy + dz * dz); if (l <= 0.f) l = 1.f;
  sunDir.x = dx / l; sunDir.y = dy / l; sunDir.z = dz / l; sunCol = sunAbgr; ambCol = ambientAbgr;
}
void skinSunDirXZ(float *x, float *z) { *x = sunDir.x; *z = sunDir.z; }   // живое направление НА солнце (то, что задал уровень)
void skinLightLevel(const float ambS[3], const float dirS[3], unsigned *sunAbgr, unsigned *ambAbgr) {
  sunDir.x = SKIN_SUN_DIR_X; sunDir.y = SKIN_SUN_DIR_Y; sunDir.z = SKIN_SUN_DIR_Z;   // как до 29.09 (без нормировки)
  sunCol = dirS ? levLightScale(SKIN_SUN_ABGR, dirS) : SKIN_SUN_ABGR;
  ambCol = ambS ? levLightScale(SKIN_AMB_ABGR, ambS) : SKIN_AMB_ABGR;
  if (sunAbgr) *sunAbgr = sunCol;
  if (ambAbgr) *ambAbgr = ambCol;
}
static int nLit; static ScePspFVector3 litDir[4]; static unsigned litCol[4], litAmb;   // skinLights (комната); nLit = 0 — солнце
void skinLights(int n, const float dir[][3], const unsigned *abgr, unsigned ambientAbgr) {
  nLit = n < 0 ? 0 : n > 4 ? 4 : n; litAmb = ambientAbgr;
  for (int i = 0; i < nLit; i++) {
    float l = sqrtf(dir[i][0] * dir[i][0] + dir[i][1] * dir[i][1] + dir[i][2] * dir[i][2]); if (l <= 0.f) l = 1.f;
    litDir[i].x = dir[i][0] / l; litDir[i].y = dir[i][1] / l; litDir[i].z = dir[i][2] / l; litCol[i] = abgr[i];
  }
}

unsigned gateSkinDraws, gateSkinBad;   // гейт «КАДР ИГРОКА»: пачек скелетных моделей (прохожие, NPC, Гомер) ушло в GE / из них с битой текстурой (индекс вне таблицы, нулевой размер)
static void bindTex(const SkinModel *m, int t) {
  const SkinTex *x = &m->tex[t];
  sceGuClutLoad(32, m->base + x->offClut);                         // 256 x 8888
  sceGuTexMode(GU_PSM_T8, 0, 0, x->swizzled ? 1 : 0);
  sceGuTexImage(0, x->w, x->h, x->w, m->base + x->offPix);          // also flushes the texture cache
}

// Правка Роба 428 «мультяшный режим» (РАСШИРЕНИЕ ПОРТА, не оригинал; выкл. по умолчанию): контур-оболочка персонажа и ровная
// заливка без света. Оболочка = копия вершин пачки, сдвинутых по своей нормали на SKIN_TOON_W, рисуется вторым проходом той же
// пачки (те же кости) чёрным, без текстуры и света, ПЕРЕД пачкой и без записи глубины: пачка ложится поверх, остаётся ободок
// за силуэтом и по краям частей (рука на фоне тела). Отсечение граней не нужно — обход полос в данных не проверен.
// Копии — в кэше по модели (строятся при первом рисовании, предел SKIN_TOON_BYTES); skinToonFlush — при смене уровня.
#ifndef SKIN_HOST
#define SKIN_TOON_W .025f          // правило порта (вкус): 2,5 см ≈ 1 пиксель PSP на 5,7 м (272 строки, FOVY 62°)
// №754 (Роб 17.10: «и на остальных персонажах тоже контур, просто внешний, на беглую руку»): оболочка 2,5 см с камеры дальше 6 м тоньше пикселя — у прохожих
// контура не видно. Теперь три готовые толщины по расстоянию до камеры (план КОНТУР_МУЛЬТИКА_ПЛАН, этап 2, запасной путь): 2,5 / 6 / 14 см до 7 / 16 / 35 м —
// на экране ~1–2,5 px; дальше 35 м без контура; глаза обводятся только вблизи. Кэш строит толщину при первой нужде. SKIN_TOON_LEVELS_OLD=1 — одна толщина, как TEST32
#ifndef SKIN_TOON_LEVELS_OLD
#define SKIN_TOON_LEVELS_OLD 0
#endif
// №779 (Роб 18.10: «вдалеке у них самая толстая линия — неправильно, усреднить, как в сериале 90-х; толщину — ползунком в настройках»; следом: «линия по толщине
// плюс-минус единая, а вдали чтобы толщина и контрастность немножечко описывали перспективу, глубину; мелким дальним персонажам — не толще»): толщина на экране
// от ползунка (skinToonLineParams: width 0..10, 5 — по умолчанию ≈ 1,7 px), пять готовых оболочек по дальности (до 4,5 / 8 / 14 / 24 / 40 м, дальше без контура).
// Вытяжка ступени считается по её БЛИЖНЕЙ границе: на любой дали линия не толще цели, а цель с расстоянием чуть тоньше (×1 до 4 м, ×0,78 к 14 м, ×0,56 к 24 м, не меньше ×0,45) —
// у мелких дальних никогда не толще ближних. Контраст — toonAirMix: тушь с расстоянием светлеет к цвету дали (воздушная перспектива). Смена ползунка — кэш заново.
// SKIN_TOON_W779_OLD=1 — толщины №754 (2,5 / 6 / 14 см до 7 / 16 / 35 м), без ползунка и без светления
#ifndef SKIN_TOON_W779_OLD
#define SKIN_TOON_W779_OLD 0
#endif
#define SKIN_TOON_K 5
static const float toonWk754[3] = {SKIN_TOON_W, .06f, .14f}, toonDk754[3] = {7.f, 16.f, 35.f};
static const float toonDk779[SKIN_TOON_K] = {4.5f, 8.f, 14.f, 24.f, 40.f}, toonDlo779[SKIN_TOON_K] = {3.f, 4.5f, 8.f, 14.f, 24.f};   // ступень 0 — по 3 м (камера у героя)
int skinToonLineW = 5, skinToonEyeMode = 1;
// №823 (Роб 18.10: «слишком большой диапазон толщины: у нас не сильно толстая линия, а вдали видна и не сразу уходит в тонкую»): спад цели с
// расстоянием мягче — к 74 м, не тоньше ×0,72 (было к 49 м, ×0,45). TOON_RANGE823_OLD=1 — как TEST35
static float toonPxAt(float d) { float g = 1.f - (d - 4.f) / (TOON_RANGE823_OLD ? 45.f : 70.f), gmin = TOON_RANGE823_OLD ? .45f : .72f; g = g > 1.f ? 1.f : g < gmin ? gmin : g; return (.32f * (float)skinToonLineW + .1f) * g; }   // цель, px на экране
static float toonWk(int lv) {   // вытяжка оболочки ступени lv, м: пиксели цели на ближней границе ступени × её расстояние / 226,3 (272 строки, FOVY 62°)
  if (SKIN_TOON_W779_OLD) return toonWk754[lv < 3 ? lv : 2];
  return toonPxAt(toonDlo779[lv]) * toonDlo779[lv] / 226.3f;
}
// №779: воздушная перспектива контура — доля цвета дали в туши: 0 до 5 м, к 40 м — 0,7. Цвет дали — skinToonAir (main_camera.h skyFogColor), пока нет — сиренево-серый
static unsigned toonAirABGR = 0xffc8b0b0u;
void skinToonAir(unsigned abgr) { toonAirABGR = 0xff000000u | (abgr & 0xffffffu); }
// №796 (Роб: «темнее и контрастнее; у машин обводка очень светлая»): светление к цвету дали с 8 м и не больше 0,45 к 40 м (было с 5 м до 0,7). TOON_AIR796_OLD=1 — как TEST34
static unsigned toonAirMix(unsigned ink, float d) {
  float d0 = TOON_AIR796_OLD ? 5.f : TOON_INK821_OLD ? 8.f : 12.f, kmax = TOON_AIR796_OLD ? .7f : TOON_INK821_OLD ? .45f : .25f;   // №821: темнее и вдали
  if (SKIN_TOON_W779_OLD || d <= d0) return ink;
  float k = (d - d0) / (40.f - d0); k = (k > 1.f ? 1.f : k) * kmax;
  unsigned o = 0xff000000u;
  for (int c = 0; c < 24; c += 8) { float a = (float)((ink >> c) & 255u), b = (float)((toonAirABGR >> c) & 255u); o |= (unsigned)(a + (b - a) * k + .5f) << c; }
  return o;
}
unsigned skinToonAirMix(unsigned ink, float d) { return toonAirMix(ink, d); }
unsigned skinToonAirColor(void) { return toonAirABGR; }   // №779: цвет дали — туман линий мира
// №779 (дирижёр 18.10, слово Роба: «машинам NPC — трафик, стоящие, машины миссий — тоже контур, как у машины игрока и героев»): вытяжка контура машины на расстоянии d, м —
// та же цель на экране, что у героев (toonPxAt), но без ступеней: машина раздувается матрицей (main_render.h carToonHull), кэша нет. 0 — без контура (ползунок 0 или дальше 40 м)
float skinToonWorldW(float d) {
  if (SKIN_TOON_W779_OLD) return .025f;
  if (skinToonLineW <= 0 || d > toonDk779[SKIN_TOON_K - 1]) return 0.f;
  float dmin_ = TOON_RANGE823_OLD ? 3.f : 2.f, dd = d < dmin_ ? dmin_ : d; return toonPxAt(dd) * dd / 226.3f;   // №823: вблизи (до 2 м) не толще цели
}   // №779: то же для линий мира (main_levels.h toonLinesDraw)
void skinToonLineParams(int width, int eyes) {   // настройки (main_save.h cfgApply): толщина контура и глаза
  width = width < 0 ? 0 : width > 10 ? 10 : width; eyes = eyes < 0 ? 0 : eyes > 2 ? 2 : eyes;
  if (width != skinToonLineW && !SKIN_TOON_W779_OLD) { skinToonLineW = width; skinToonFlush(); }
  skinToonEyeMode = eyes; skinToonEyes = eyes != 0;
}
static float toonEye[3]; static int toonEyeOk;
void skinToonEye(float x, float y, float z) { toonEye[0] = x; toonEye[1] = y; toonEye[2] = z; toonEyeOk = 1; }
static int toonLevel(const ScePspFMatrix4 *w, float *dist) {   // ступень оболочки по расстоянию от глаза до модели, -1 — без контура; dist — расстояние, м (0 — неизвестно)
  *dist = 0.f;
  if (SKIN_TOON_LEVELS_OLD || !toonEyeOk || !w) return 0;
  float dx = w->w.x - toonEye[0], dy = w->w.y - toonEye[1], dz = w->w.z - toonEye[2], d2 = dx * dx + dy * dy + dz * dz;
  *dist = sqrtf(d2);
  int nk = SKIN_TOON_W779_OLD ? 3 : SKIN_TOON_K; const float *dk = SKIN_TOON_W779_OLD ? toonDk754 : toonDk779;
  for (int k = 0; k < nk; k++) if (d2 < dk[k] * dk[k]) return k;
  return -1;
}
#define SKIN_TOON_BYTES (SKIN_TOON_LEVELS_OLD ? 1u << 20 : SKIN_TOON_W779_OLD ? 2u << 20 : (5u << 20) / 2) // правило порта: кэш оболочек не больше 1 МБ кучи (№754: 2 МБ на три толщины; №779: 2,5 МБ на пять)
#define SKIN_TOON_N 24
#ifndef SKIN_TOON_V2_OLD
#define SKIN_TOON_V2_OLD 0   // №428: 1 — оболочка как 09.10: копия nverts вершин и рисование без индексов (на CHR1 v2 читает за буфером и рисует не те вершины)
#endif
static inline unsigned toonStored(const SkinBatch *b) { return SKIN_TOON_V2_OLD ? b->nverts : skinBatchStoredVerts(b); }
static struct { const unsigned char *base; unsigned size, verts; unsigned char *hull[SKIN_TOON_K]; unsigned bytes[SKIN_TOON_K]; unsigned char tried; } toonC[SKIN_TOON_N];
static int vfmtOffsets(unsigned vt, unsigned stride, int *nOff, int *pOff) {   // смещения нормали (8 бит) и позиции (float) в вершине GE
  static const int wsz[4] = {0, 1, 2, 4}, tsz[4] = {0, 1, 2, 4}, csz[8] = {0, 0, 0, 0, 2, 2, 2, 4}, nsz[4] = {0, 1, 2, 4}, psz[4] = {0, 1, 2, 4};
  int wf = (vt >> 9) & 3, nw = wf ? (int)((vt >> 14) & 7) + 1 : 0, tf = vt & 3, cf = (vt >> 2) & 7, nf = (vt >> 5) & 3, pf = (vt >> 7) & 3;
  if (nf != 1 || pf != 3 || (vt & (7u << 18))) return 0;   // нужны нормаль 8 бит и позиция float, без морфа
  int o = 0, al = 1;
  if (wf) { o += nw * wsz[wf]; if (wsz[wf] > al) al = wsz[wf]; }
  if (tf) { o = (o + tsz[tf] - 1) & ~(tsz[tf] - 1); o += 2 * tsz[tf]; if (tsz[tf] > al) al = tsz[tf]; }
  if (cf) { o = (o + csz[cf] - 1) & ~(csz[cf] - 1); o += csz[cf]; if (csz[cf] > al) al = csz[cf]; }
  *nOff = o; o += 3 * nsz[nf];
  o = (o + 3) & ~3; *pOff = o; o += 3 * psz[pf]; if (4 > al) al = 4;
  o = (o + al - 1) & ~(al - 1);
  return (unsigned)o == stride;
}
void skinToonFlush(void) { for (int i = 0; i < SKIN_TOON_N; i++) { for (int k = 0; k < SKIN_TOON_K; k++) free(toonC[i].hull[k]); memset(&toonC[i], 0, sizeof toonC[i]); } skinToonBytesNow = 0; }
static unsigned char *toonHull(const SkinModel *m, int lv) {
  skinToonHullCalls++;
  int fr = -1;
  for (int i = 0; i < SKIN_TOON_N; i++) {
    if (toonC[i].base == m->base && toonC[i].size == m->h->size && toonC[i].verts == m->h->totalVerts) {
      if (toonC[i].hull[lv] || (toonC[i].tried >> lv & 1)) return toonC[i].hull[lv];
      fr = i; break; }
    if (!toonC[i].base && fr < 0) fr = i;
  }
  if (fr < 0) return 0;
  unsigned bytes = 0, bytes2 = 0; for (unsigned i = 0; i < m->h->nBatches; i++) { unsigned sz_ = (toonStored(&m->b[i]) * m->b[i].stride + 15) & ~15u; bytes += sz_;
    if (!EYE_SIL827_OLD && (m->b[i].flags & 3) == 1) bytes2 += sz_; }   // №827: копия глаз толщиной тела — для внешнего силуэта
  toonC[fr].base = m->base; toonC[fr].size = m->h->size; toonC[fr].verts = m->h->totalVerts; toonC[fr].tried |= (unsigned char)(1u << lv);   // и при отказе: не пробовать каждый кадр
  if (!bytes || skinToonBytesNow + bytes + bytes2 > SKIN_TOON_BYTES) return 0;
  unsigned char *h = memalign(16, bytes + bytes2); if (!h) return 0;
  unsigned o = 0;
  for (int pass = 0; pass < (bytes2 ? 2 : 1); pass++)   // проход 1 (№827) — копии глаз толщиной тела за основными оболочками
  for (unsigned i = 0; i < m->h->nBatches; i++) {
    const SkinBatch *b = &m->b[i]; int no, po; unsigned sv = toonStored(b), n = sv * b->stride;   // CHR1 v2: в файле хранится pad[1] вершин, не nverts
    if (pass && (b->flags & 3) != 1) continue;
    memcpy(h + o, m->base + b->offVerts, n);
    if (vfmtOffsets(b->vtype, b->stride, &no, &po))
      for (unsigned v = 0; v < sv; v++) {
        unsigned char *q = h + o + v * b->stride; const signed char *nn = (const signed char *)(q + no); float p[3];
        float nx = nn[0] / 127.f, ny = nn[1] / 127.f, nz = nn[2] / 127.f, l = sqrtf(nx * nx + ny * ny + nz * nz);
        if (l < 1e-3f) continue;
        memcpy(p, q + po, 12); float w_ = (b->flags & 1) && !pass ? SKIN_TOON_EYE_W : toonWk(lv); p[0] += nx / l * w_; p[1] += ny / l * w_; p[2] += nz / l * w_; memcpy(q + po, p, 12);
      }
    o += (n + 15) & ~15u;
  }
  sceKernelDcacheWritebackRange(h, bytes + bytes2);
  toonC[fr].hull[lv] = h; toonC[fr].bytes[lv] = bytes + bytes2; skinToonBytesNow += bytes + bytes2;
  return h;
}
#else
void skinToonFlush(void) {}
#endif
#ifndef SKIN_HOST
// рампа ступени тени: 32 x 8 texel 8888 (строки одинаковы, V не используется); U < 0,575 (N·L < 0,15) — тень (ABGR: чуть холоднее и темнее), выше — свет (белый)
static unsigned toonRamp[32 * 8] __attribute__((aligned(16))); static int toonRampOk;
static void toonRampInit(void) {
  if (toonRampOk) return;
  for (int y = 0; y < 8; y++) for (int x = 0; x < 32; x++) toonRamp[y * 32 + x] = x < 18 ? 0xffc8b8b8u : 0xffffffffu;
  sceKernelDcacheWritebackRange(toonRamp, sizeof toonRamp); toonRampOk = 1;
}
#endif
#ifndef SKIN_HOST
// №779: диапазон глубины (near, 0) двумя командами GE (масштаб и центр Z) вместо sceGuDepthRange (4 слова: ещё мин/макс Z — их сжатый диапазон не трогает).
// Те же числа, что считает libgu sceGuDepthRange(near, 0) при нулевом sceGuDepthOffset (у персонажей он 0); контекст libgu не меняется — возврат (65535) совпадает с ним
static void skinZRange(int nearZ) { float z = (float)((unsigned)nearZ >> 1); sceGuSendCommandf(68, z - (float)nearZ); sceGuSendCommandf(71, z); }
#endif
void skinDrawPal(const SkinModel *m, const ScePspFMatrix4 *pal, const ScePspFMatrix4 *world, int eyeTex) {
  sceGuSetMatrix(GU_MODEL, world);
  sceGuDisable(GU_BLEND); sceGuDisable(GU_ALPHA_TEST); sceGuDepthMask(GU_FALSE);
  sceGuEnable(GU_TEXTURE_2D);
  sceGuTexFunc(GU_TFX_MODULATE, GU_TCC_RGBA); sceGuTexFilter(GU_LINEAR, GU_LINEAR);
  sceGuTexScale(128.f, 128.f); sceGuTexOffset(0.f, 0.f);
  sceGuClutMode(GU_PSM_8888, 0, 0xff, 0);
  sceGuEnable(GU_LIGHTING);
  if (nLit) {   // LightGroup комнаты: источники 0..nLit-1
    for (int i = 0; i < nLit; i++) {
      sceGuEnable(GU_LIGHT0 + i); sceGuLight(i, GU_DIRECTIONAL, GU_DIFFUSE, &litDir[i]);
      sceGuLightColor(i, GU_DIFFUSE, litCol[i]); sceGuLightColor(i, GU_AMBIENT, 0);
    }
    sceGuAmbient(litAmb);
  } else {
    sceGuEnable(GU_LIGHT0);
    sceGuLight(0, GU_DIRECTIONAL, GU_DIFFUSE, &sunDir);
    sceGuLightColor(0, GU_DIFFUSE, skinScaleCol(sunCol, skinSunPct)); sceGuLightColor(0, GU_AMBIENT, 0);
    sceGuAmbient(skinScaleCol(ambCol, skinAmbPct));
  }
  sceGuModelColor(0, 0xffffffff, 0xffffffff, 0); sceGuAmbientColor(0xffffffff);
  int bound = -1, atest = 0; int slotBone[16]; memset(slotBone, 0, sizeof slotBone);   // слот пуст: в GE чужая матрица
#ifndef SKIN_HOST
  float tdist_ = 0.f; int tlv_ = skinToonEnabled() ? toonLevel(world, &tdist_) : -1;   // №754: толщина контура по расстоянию
  unsigned char *hull = tlv_ >= 0 ? toonHull(m, tlv_) : 0; unsigned hullOff = 0;
  // №779/№781 (Роб 18.10, Апу и Лиза: «свитер из отдельных блоков и каждому контур», «шипы и лицо разлинованы — ломано»): контур только по внешнему силуэту.
  // Оболочка тела рисуется со сдвигом глубины назад на SKIN_TOON_SIL_M (диапазон глубины GE сжат: (65535 − δ, 0), δ = 65535 · сдвиг / расстояние — тот же сдвиг
  // в метрах на любой дали): где за кромкой в нескольких сантиметрах своё же тело (соседний блок свитера, шип, лицо), оболочка проигрывает тест глубины и не видна;
  // остаётся кромка на фоне и линия там, где часть выступает вперёд больше сдвига (рука перед кофтой). Кадр 5650 без трафарета — только глубина.
  // SKIN_TOON_SIL_OLD=1 — прежнее (оболочка каждой пачки без сдвига: линии между частями)
#ifndef SKIN_TOON_SIL_OLD
#define SKIN_TOON_SIL_OLD 0
#endif
#ifndef SKIN_TOON_SIL_M
#define SKIN_TOON_SIL_M .12f
#endif
  int silD_ = (!SKIN_TOON_SIL_OLD && tdist_ > .3f) ? (int)fminf(20000.f, SKIN_TOON_SIL_M * 65535.f / tdist_) : 0;
  if (skinToonEnabled()) sceGuDisable(GU_LIGHTING);   // правка 428: ровная заливка — цвет текстуры без света
  // №797: оболочки ВСЕХ пачек тела сначала — без сдвига и без записи глубины, с тестом против уже нарисованного; потом все пачки тела. Тело закрывает оболочку
  // везде внутри своего силуэта (шипы, свитер, лицо — без линий), снаружи остаётся край против всего, что уже в кадре: мир и своя машина (она рисуется раньше героя,
  // main_loop.h). Глаза — прежним мягким кольцом у своей пачки, поверх уже нарисованного лица. SKIN_TOON_PRE_OLD=1 — как TEST34 (skin.h)
  int pre_ = hull && !SKIN_TOON_PRE_OLD && (SKIN_TOON_W779_OLD || skinToonLineW > 0);
  // №822 (Роб 18.10: «контур не замыкается под ногами, на светлом выглядит незавершённым»): низ оболочки под подошвой уходит под пол и
  // проигрывал тест глубины. Оболочки предпрохода — с выигрышем SKIN_TOON_FOOT_M по глубине против мира (диапазон глубины GE растянут
  // к глазу: (65535 + δ, 0), δ = 65535 · сдвиг / расстояние — тот же сдвиг в метрах на любой дали, как SKIN_TOON_SIL_M назад): линия под
  // ступнями видна над полом; тело (рисуется следом) закрывает оболочку внутри силуэта, как прежде. SKIN_TOON_FOOT_OLD=1 — как TEST35
#ifndef SKIN_TOON_FOOT_OLD
#define SKIN_TOON_FOOT_OLD 0
#endif
#ifndef SKIN_TOON_FOOT_M
#define SKIN_TOON_FOOT_M .08f
#endif
  int footD_ = (pre_ && !SKIN_TOON_FOOT_OLD && tdist_ > .3f) ? (int)fminf(8000.f, SKIN_TOON_FOOT_M * 65535.f / tdist_) : 0;
  if (pre_) {
    if (footD_) skinZRange(65535 + footD_);
    unsigned hc_ = TOON_HULL_BLEND_OLD || SKIN_TOON_V675_OLD ? 0xff000000u : toonAirMix(TOON_HULL_ABGR, tdist_);
    sceGuDisable(GU_TEXTURE_2D); sceGuAmbientColor(hc_); sceGuModelColor(0, hc_, hc_, 0); sceGuDepthMask(GU_TRUE);
    if (TOON_HULL_BLEND_OLD && !SKIN_TOON_V675_OLD) { sceGuEnable(GU_BLEND); sceGuBlendFunc(GU_ADD, GU_FIX, GU_FIX, 0, TOON_HULL_DST); }
    unsigned ho_ = 0, he_ = 0; if (!EYE_SIL827_OLD) for (unsigned i = 0; i < m->h->nBatches; i++) he_ += (toonStored(&m->b[i]) * m->b[i].stride + 15) & ~15u;   // №827: начало копий глаз
    for (unsigned i = 0; i < m->h->nBatches; i++) {
      const SkinBatch *b = &m->b[i];
      int eyeSil_ = !EYE_SIL827_OLD && (b->flags & 3) == 1 && (EYE_SIL838_OLD || tlv_ <= 1);   // №827: глаз — во внешний силуэт (копия толщиной тела); вырезы по альфе — нет; №838: только ближе 8 м
      if (!(b->flags & 3) || eyeSil_) {   // тело: не глаза (1) и не вырезы по альфе (2); №827 — и глаза
        for (int k = 0; k < b->nb; k++) {
#ifndef SKIN_BONECACHE_OLD
          if (k < 16 && slotBone[k] == b->bones[k] + 1) continue;
          if (k < 16) slotBone[k] = b->bones[k] + 1;
#endif
          sceGuBoneMatrix(k, &pal[b->bones[k]]); }
        const void *hi_ = 0;
#ifndef CHAR_INDEXED_OLD
        if (!SKIN_TOON_V2_OLD && (b->flags & 4)) hi_ = m->base + b->pad[0];   // CHR1 v2: оболочка теми же индексами, что и пачка
#endif
        sceGuDrawArray(b->prim, b->vtype, b->nverts, hi_, hull + (eyeSil_ ? he_ : ho_)); skinToonDraws++; skinToonVerts += b->nverts;
        if (eyeSil_) he_ += (toonStored(b) * b->stride + 15) & ~15u;
      }
      ho_ += (toonStored(b) * b->stride + 15) & ~15u;
    }
    if (TOON_HULL_BLEND_OLD && !SKIN_TOON_V675_OLD) sceGuDisable(GU_BLEND);
    if (footD_) skinZRange(65535);   // №822: диапазон глубины обратно
    sceGuDepthMask(GU_FALSE); sceGuEnable(GU_TEXTURE_2D); sceGuAmbientColor(0xffffffff); sceGuModelColor(0, 0xffffffff, 0xffffffff, 0);
  }
#endif
  for (unsigned i = 0; i < m->h->nBatches; i++) {
    const SkinBatch *b = &m->b[i];
    int t = (eyeTex >= 0 && (b->flags & 1)) ? eyeTex : b->tex;
    if (t != bound) { bindTex(m, t); bound = t; }
    if ((b->flags & 2) != atest) {                 // cut-out textures (necklaces etc.; none on Homer)
      atest = b->flags & 2;
      if (atest) { sceGuAlphaFunc(GU_GREATER, 0x40, 0xff); sceGuEnable(GU_ALPHA_TEST); } else sceGuDisable(GU_ALPHA_TEST);
    }
    // «быстрый расчёт» (npc L2 2,2 тыс. слов на ~6 персонажей; слово списка ≈ 1 мкс): матрица кости — 13 слов; пачки одного персонажа часто делят
    // кости, и GE хранит слот до перезаписи — не пишем ту же матрицу в тот же слот повторно в пределах вызова. -DSKIN_BONECACHE_OLD=1 — прежнее
    for (int k = 0; k < b->nb; k++) {
#ifndef SKIN_BONECACHE_OLD
      if (k < 16 && slotBone[k] == b->bones[k] + 1) continue;
      if (k < 16) slotBone[k] = b->bones[k] + 1;
#endif
      sceGuBoneMatrix(k, &pal[b->bones[k]]); }
#ifndef SKIN_HOST
    const void *hullIdx = 0;
#ifndef CHAR_INDEXED_OLD
    if (!SKIN_TOON_V2_OLD && (b->flags & 4)) hullIdx = m->base + b->pad[0];   // CHR1 v2: оболочка рисуется теми же индексами, что и пачка
#endif
    int eye_ = (b->flags & 1) != 0, bodyLine_ = SKIN_TOON_W779_OLD || skinToonLineW > 0;   // №779: ползунок 0 — тело без контура (глаза — своей строкой)
    if (hull && !(b->flags & 2) && (eye_ || bodyLine_) && (SKIN_TOON_V675_OLD || skinToonEyes || !eye_) && !(tlv_ > 0 && eye_) && !(pre_ && !eye_)) {   // №797: тело — уже в первом проходе   // №754: глаза — только вблизи   // №679: глаза (flags 1) — тонкий контур (skinToonEyes), без него — как №675. правка 428: оболочка-контур ДО пачки, без записи глубины: пачка ляжет поверх, снаружи силуэта
      // №675: контур ровным цветом TOON_HULL_ABGR (0x4d4d4d = 30 % яркости, «70 % чёрного»), без смешивания: прежнее (фон × 30 %) на траве и небе читалось чистым чёрным. TOON_HULL_BLEND_OLD=1 — как c535cd20
      unsigned hc_ = TOON_HULL_BLEND_OLD || SKIN_TOON_V675_OLD ? 0xff000000u : toonAirMix(TOON_HULL_ABGR, tdist_);   // №779: вдали тушь светлеет к цвету дали
      // №781 (Роб: «обводку глазам жёсткую не надо — мягкий общий контур, не такой контрастный»): глаза мягким кольцом — тушь на TOON_EYE_SOFT_PCT % поверх лица
      // (eyes 1, по умолчанию), полной тушью — eyes 2, без кольца — eyes 0. TOON_EYE_SOFT_OLD=1 — глаза как тело (полная тушь)
      int soft_ = eye_ && !TOON_EYE_SOFT_OLD && skinToonEyeMode == 1, sil_ = !eye_ && silD_ > 0;
      sceGuDisable(GU_TEXTURE_2D); sceGuAmbientColor(hc_); sceGuModelColor(0, hc_, hc_, 0); sceGuDepthMask(GU_TRUE);
      if (TOON_HULL_BLEND_OLD && !SKIN_TOON_V675_OLD) { sceGuEnable(GU_BLEND); sceGuBlendFunc(GU_ADD, GU_FIX, GU_FIX, 0, TOON_HULL_DST); }
      else if (soft_) { unsigned a_ = TOON_EYE_SOFT_PCT * 255u / 100u; sceGuEnable(GU_BLEND); sceGuBlendFunc(GU_ADD, GU_FIX, GU_FIX, a_ * 0x010101u, (255u - a_) * 0x010101u); }
      if (sil_) skinZRange(65535 - silD_);   // №779: оболочка на SKIN_TOON_SIL_M дальше — видна только кромка силуэта
      sceGuDrawArray(b->prim, b->vtype, b->nverts, hullIdx, hull + hullOff);   // останется ободок (вырезы по альфе — без контура)
      if (sil_) skinZRange(65535);
      if ((TOON_HULL_BLEND_OLD && !SKIN_TOON_V675_OLD) || soft_) sceGuDisable(GU_BLEND);
      sceGuDepthMask(GU_FALSE); sceGuEnable(GU_TEXTURE_2D); sceGuAmbientColor(0xffffffff); sceGuModelColor(0, 0xffffffff, 0xffffffff, 0);
      bound = -1; skinToonDraws++; skinToonVerts += b->nverts;
    }
    if (hull) hullOff += (toonStored(b) * b->stride + 15) & ~15u;
    if (t != bound) { bindTex(m, t); bound = t; }
#endif
    const void *indices=0;
#ifndef CHAR_INDEXED_OLD
    if(b->flags&4) indices=m->base+b->pad[0];
#endif
    gateSkinDraws++; if (t < 0 || t >= (int)m->h->nTex || m->tex[t].w <= 0 || m->tex[t].h <= 0) gateSkinBad++;
    sceGuDrawArray(b->prim, b->vtype, b->nverts, indices, m->base + b->offVerts);
  }
#ifndef SKIN_HOST
  if (skinToonShadeOn()) {   // №675: ступень тени вторым проходом (shade mapping), глаза и вырезы по альфе — без неё
    if (atest) { sceGuDisable(GU_ALPHA_TEST); atest = 0; }
    toonRampInit();
    const ScePspFVector3 *ld = nLit ? &litDir[0] : &sunDir;
    sceGuLight(2, GU_DIRECTIONAL, GU_DIFFUSE, ld); sceGuLight(3, GU_DIRECTIONAL, GU_DIFFUSE, ld);   // слоты 2, 3 не включены: только вектор для shade mapping
    sceGuTexMapMode(GU_ENVIRONMENT_MAP, 2, 3);
    sceGuTexMode(GU_PSM_8888, 0, 0, 0); sceGuTexImage(0, 32, 8, 32, toonRamp);
    sceGuTexFilter(GU_NEAREST, GU_NEAREST); sceGuTexWrap(GU_CLAMP, GU_CLAMP); sceGuTexFunc(GU_TFX_REPLACE, GU_TCC_RGB);
    sceGuDepthFunc(GU_EQUAL); sceGuDepthMask(GU_TRUE); sceGuEnable(GU_BLEND); sceGuBlendFunc(GU_ADD, GU_DST_COLOR, GU_FIX, 0, 0);
    for (unsigned i = 0; i < m->h->nBatches; i++) {
      const SkinBatch *b = &m->b[i]; if (b->flags & 3) continue;
      for (int k = 0; k < b->nb; k++) {
        if (k < 16 && slotBone[k] == b->bones[k] + 1) continue;
        if (k < 16) slotBone[k] = b->bones[k] + 1;
        sceGuBoneMatrix(k, &pal[b->bones[k]]); }
      const void *ix = 0;
#ifndef CHAR_INDEXED_OLD
      if (b->flags & 4) ix = m->base + b->pad[0];
#endif
      sceGuDrawArray(b->prim, b->vtype, b->nverts, ix, m->base + b->offVerts);
    }
    sceGuTexMapMode(GU_TEXTURE_COORDS, 0, 0); sceGuTexFilter(GU_LINEAR, GU_LINEAR); sceGuTexWrap(GU_REPEAT, GU_REPEAT);
    sceGuTexFunc(GU_TFX_MODULATE, GU_TCC_RGBA); sceGuDepthFunc(GU_GEQUAL); sceGuDepthMask(GU_FALSE); sceGuDisable(GU_BLEND);
  }
#endif
  if (atest) sceGuDisable(GU_ALPHA_TEST);
  for (int i = 0; i < (nLit ? nLit : 1); i++) sceGuDisable(GU_LIGHT0 + i);
  sceGuDisable(GU_LIGHTING);
}

// Правка Роба 103 (повтор 01.10): персонажи через skinDraw (фоновые и миссий — msn_view.c, пешеходы — traffic.c, гардероб) —
// только пока в списке GE есть место под всю модель (skinGeRoom ставит main.c: тот же предел GE_HARD бюджета, что у кусков города).
// Раньше их не проверял никто: город останавливался на 90 %, а персонажи, пропы гонок и значки миссий писали дальше — за конец
// массива list, и GE настоящей PSP исполнял мусор (встаёт вся приставка; эмулятор молчит). Гомер (homerDraw -> skinDrawPal) — всегда
int (*skinGeRoom)(unsigned bytes);
unsigned skinGeSkips;
// правка 428 (аудит железа TEST27 п.1): проход контура на пачку шлёт НЕ 16 слов, а 24: отключить текстуру 1, AmbientColor 2 (два слова: цвет и альфа),
// ModelColor 4, DepthMask 1, рисование оболочки до 6 (VTYPE, BASE+IADDR, BASE+VADDR, PRIM), DepthMask 1, включить текстуру 1, AmbientColor 2, ModelColor 4 = 22,
// +2: после контура основное рисование пачки с индексами тоже 6 слов, не 4 (bound = -1: привязка текстуры 9 слов уже в 16). Хост-счётчик tests/toon/ge_words.py.
// -DSKIN_GE_TOON_OLD=1 — прежняя оценка (+16): красный контроль, на плотной сцене занижает
#ifndef SKIN_GE_TOON_OLD
#define SKIN_GE_TOON_OLD 0
#endif
#define SKIN_GE_TOON_WORDS ((SKIN_GE_TOON_OLD ? 16u : 24u) + (SKIN_TOON_V675_OLD ? 0u : 3u) + (SKIN_TOON_SIL_OLD ? 0u : 4u))   // №675: +3 слова на включение/функцию смешения/выключение вокруг прохода контура; №779: +4 — масштаб и центр Z оболочки и возврат (по 2 слова)
unsigned skinGeBytes(const SkinModel *m) {   // оценка сверху, слов: состояние и 4 источника света комнаты <= 96, на пачку — CLUT и
  unsigned w = 96;                           // текстура 9, альфа-тест 3, кости 13 x nb (BOFS + 12), рисование 4
  for (unsigned i = 0; i < m->h->nBatches; i++) w += 16u + 13u * m->b[i].nb + (skinToonEnabled() ? SKIN_GE_TOON_WORDS + (SKIN_TOON_PRE_OLD ? 0u : 13u * m->b[i].nb) : 0u);   // №797: кости второй раз в первом проходе   // правка 428: проход контура
  if (skinToonShadeOn()) { w += SKIN_TOON_SHADE_BASE; for (unsigned i = 0; i < m->h->nBatches; i++) w += SKIN_TOON_SHADE_WORDS; }   // №675: проход ступени тени
  return w * 4u;
}
void skinDraw(const SkinPlayer *p, const ScePspFMatrix4 *world) {
  if (skinGeRoom && !skinGeRoom(skinGeBytes(p->m))) { skinGeSkips++; return; }
  skinDrawPal(p->m, p->pal, world, p->eyeTex);
}
#endif
