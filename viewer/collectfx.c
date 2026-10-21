// Эффект цели миссии SetCollectibleEffect — описание в collectfx.h. Чистый C, без GU (рисует fx.c через fxSprite).
#include <string.h>
#include <math.h>
#include "collectfx.h"
#include "collectfx_data.h"
#include "fx.h"

#define CFX_MAX 6           // одновременно горящих (точки гонки идут через 1–2 с, квады гаснут за 0.37 с)
typedef struct { const CfxDef *d; float t, p[3]; } CfxRun;
static CfxRun run[CFX_MAX];
int cfxOld;
unsigned cfxSprites;
// №463 (Роб; запись PS2, knowledge/facts/ps2-obs-video-m1-rings-wrench.yaml, В57): на въезде в точку этапа wrench_collect даёт не вспышку звёзд
// 0,37 с, а бледно-голубой полупрозрачный вертикальный столб со спиралью: растёт из машины, через 0,2 с 3-4 высоты машины, потом выше
// ~8 м (в порте 12 м), виден ~0,9 с. Столб — стопка мягких спрайтов glowsolid.bmp со спиральным сдвигом, поверх прежних звёзд.
// CFX_COLUMN_OLD=1 — как было (без столба)
#ifndef CFX_COLUMN_OLD
#define CFX_COLUMN_OLD 0
#endif
#define CFX_COL_MAX 3
#define CFX_COL_LIFE 0.9f
#define CFX_COL_H 12.f
typedef struct { float t, p[3]; int on; } CfxCol;
static CfxCol col[CFX_COL_MAX];

static const CfxDef *find(const char *name) {
  for (int i = 0; i < CFX_NDEF; i++) if (!strcmp(cfxDefs[i].name, name)) return &cfxDefs[i];
  return 0;
}

int cfxPlay(const char *name, const float pos[3]) {
  if (cfxOld || !name || !*name || !pos) return 0;
  const CfxDef *d = find(name); if (!d) return 0;   // "none" и неизвестные — ничего
  int n = 0;
  if (!CFX_COLUMN_OLD && !strcmp(name, "wrench_collect")) {
    int s = 0; float oldest = -1.f;
    for (int i = 0; i < CFX_COL_MAX; i++) { if (!col[i].on) { s = i; break; } if (col[i].t > oldest) { oldest = col[i].t; s = i; } }
    col[s].on = 1; col[s].t = 0.f; col[s].p[0] = pos[0]; col[s].p[1] = pos[1]; col[s].p[2] = pos[2];
  }
  for (int k = 0; k < d->nps; k++) {   // частицы — один раз (fx.c ведёт их сам до конца таймлайна системы)
    int id = fxFind(d->ps[k].sys); if (id < 0) continue;
    float p[3] = {pos[0] + d->ps[k].off[0], pos[1] + d->ps[k].off[1], pos[2] + d->ps[k].off[2]};
    if (fxBurst(id, p, 0)) n++;
  }
  if (d->nbill) {
    int s = 0; float oldest = -1.f;
    for (int i = 0; i < CFX_MAX; i++) { if (!run[i].d) { s = i; break; } if (run[i].t > oldest) { oldest = run[i].t; s = i; } }
    run[s].d = d; run[s].t = 0.f; run[s].p[0] = pos[0]; run[s].p[1] = pos[1]; run[s].p[2] = pos[2];
    n += d->nbill;
  }
  return n;
}

static void columnFrame(float dt) {
  int tex = fxTexFind("glowsolid.bmp");
  for (int i = 0; i < CFX_COL_MAX; i++) {
    CfxCol *c = &col[i]; if (!c->on) continue;
    float t = c->t, h = fminf(CFX_COL_H, 25.f * t);
    float a = fminf(1.f, t / .1f) * (t > .65f ? fmaxf(0.f, (CFX_COL_LIFE - t) / (CFX_COL_LIFE - .65f)) : 1.f);
    if (tex >= 0 && h > .2f && a > .01f) {
      float lvl = .42f * a; unsigned v = (unsigned)(lvl * 255.f + .5f);
      unsigned col32 = 0xff000000u | (v << 16) | ((unsigned)(lvl * .85f * 255.f + .5f) << 8) | (unsigned)(lvl * .6f * 255.f + .5f);   // abgr: бледно-голубой
      for (float y = 0.f; y < h; y += .7f) {
        float ph = y * 1.8f - t * 9.f, sx = .35f * cosf(ph), sz = .35f * sinf(ph);
        if (fxGlowGlint && !GLOW_GLINT_OLD) { fxGlowGlint(c->p[0] + sx, c->p[1] + y, c->p[2] + sz, 1.05f, 0xFFFFD999u, a, y * .37f); cfxSprites++; continue; }   // №839: столб — бликами
        fxSprite(tex, c->p[0] + sx, c->p[1] + y, c->p[2] + sz, 1.5f, 1.5f, 0.f, col32, 1, 0);
        fxSprite(tex, c->p[0] - sx, c->p[1] + y + .35f, c->p[2] - sz, 1.5f, 1.5f, 0.f, col32, 1, 0);
        cfxSprites += 2;
      }
    }
    c->t += dt; if (c->t >= CFX_COL_LIFE) c->on = 0;
  }
}

void cfxFrame(float dt) {
  if (!CFX_COLUMN_OLD) columnFrame(dt);
  for (int i = 0; i < CFX_MAX; i++) {
    CfxRun *r = &run[i]; if (!r->d) continue;
    for (int k = 0; k < r->d->nbill; k++) {
      const CfxBill *b = &r->d->bill[k];
      float f = r->t * b->fps; int f0 = (int)f; if (f0 >= b->nfr - 1) continue;
      float u = f - f0; const float *A = b->tr[f0], *B = b->tr[f0 + 1]; float v[6];
      for (int c = 0; c < 6; c++) v[c] = A[c] + (B[c] - A[c]) * u;
      if (b->blend ? fmaxf(v[2], fmaxf(v[3], v[4])) <= .004f : v[5] <= .004f) continue;   // погасший квад не тратит заливку
      if (b->blend == 1 && fxGlowGlint && !GLOW_GLINT_OLD) {   // №839: звезда/вспышка сложением — векторным бликом
        unsigned c_ = 0; for (int c = 0; c < 3; c++) { float x = v[2 + c] * 255.f + .5f; c_ |= (x <= 0.f ? 0u : x >= 255.f ? 255u : (unsigned)x) << (8 * c); }
        fxGlowGlint(r->p[0] + b->off[0], r->p[1] + b->off[1], r->p[2] + b->off[2], fmaxf(v[0], v[1]) * .7f, c_, 1.f, (float)k * .53f); cfxSprites++; continue; }
      int tex = fxTexFind(b->tex); if (tex < 0) continue;
      unsigned c8[4]; for (int c = 0; c < 4; c++) { float x = v[2 + c] * 255.f + .5f; c8[c] = x <= 0.f ? 0u : x >= 255.f ? 255u : (unsigned)x; }
      fxSprite(tex, r->p[0] + b->off[0], r->p[1] + b->off[1], r->p[2] + b->off[2], v[0], v[1], 0.f,
               (c8[3] << 24) | (c8[2] << 16) | (c8[1] << 8) | c8[0], b->blend, 0);
      cfxSprites++;
    }
    r->t += dt;
    if (r->t >= r->d->dur) r->d = 0;
  }
}

void cfxReset(void) { memset(run, 0, sizeof run); memset(col, 0, sizeof col); }
int cfxActive(void) { int n = 0; for (int i = 0; i < CFX_MAX; i++) n += run[i].d != 0; for (int i = 0; i < CFX_COL_MAX; i++) n += col[i].on; return n; }
