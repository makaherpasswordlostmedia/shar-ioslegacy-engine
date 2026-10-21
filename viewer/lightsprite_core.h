// №599 «свет спрайтами»: ядро без GE (общий код игры и хост-проверок tests/lsprite/).
// Постоянный свет уровня — билборды стейтпропов SPR1 со сложением (ореолы фонарей и ламп, неон, лучи АЭС), которые у экземпляра в
// своём состоянии не двигаются и не мигают. Раньше их квады считались каждый кадр заново по позе экземпляра, рисовались по одному
// с привязкой текстуры на каждый квад и только в 60 м от глаза: на этой границе свечение появлялось щелчком. Теперь при загрузке
// уровня из тех же данных диска один раз снимается таблица: положение, оси, размер, цвет, текстура; рисуется одной пачкой на текстуру,
// дальше 60 м — с плавным появлением по дальности (LSP_FADE_M). Динамический свет (анимация BQG, мигание PVIS, тень-вычитание, огонь
// состояний) остаётся на прежнем пути. LIGHT_SPRITE_OLD=1 (в сценарии «flag lspold 1») — всё как до правки.
#ifndef LIGHTSPRITE_CORE_H
#define LIGHTSPRITE_CORE_H
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "stateprops.h"

#ifndef LIGHT_SPRITE_OLD
#define LIGHT_SPRITE_OLD 1   // магистраль 16.10 (слово дирижёра): по умолчанию выкл, пока свет таблицей не проверен на железе; 0 — включить при сборке, «flag lspnew 1» — в туре
#endif
#ifndef LSP_DIST_M
#define LSP_DIST_M 100.f    // дальше свечение не рисуется
#endif
#ifndef LSP_FADE_M
#define LSP_FADE_M 24.f     // от LSP_DIST_M − LSP_FADE_M проявляется плавно (прежний путь обрывал свечение на 60 м)
#endif
#ifndef LSP_PLANT_OLD
#define LSP_PLANT_OLD 0     // отрицательный контроль гейта: 1 — полуразмер квада в таблице занижен вдвое (картинка не равна прежней)
#endif

typedef struct {
  float p[3];            // центр квада (мир)
  float X[3], Y[3];      // NOAX: полуоси квада (мир); YAX/LYAX: Y — единичная ось (X вычисляется от глаза); AAX: не используются
  float hw, hh;          // полуширина и полувысота после анимации BQG
  uint32_t abgr;         // цвет GE (ARGB диска → ABGR)
  int32_t tex;
  uint32_t flags;        // SpBill.flags
  uint32_t inst;         // экземпляр SPR1
  uint16_t bill;         // номер билборда в типе
  uint8_t mode, state0;  // SpBill.mode; состояние экземпляра, в котором снят квад
  float snap[12];        // x, y, z, R[9] экземпляра на момент снимка: сдвинули (физика) — свет возвращается на прежний путь
} LspE;

typedef struct {
  LspE *e; unsigned n;
  unsigned *base;        // base[i]: номер в idx для (экземпляр i, билборд 0); 0xFFFFFFFF — у экземпляра таблицы нет
  uint16_t *idx;         // [base[i] + b] -> номер записи таблицы или 0xFFFF
  unsigned nidx;
  uint8_t *live;         // [i] — запись экземпляра в этом кадре «своя» (живой, то же состояние, на месте)
  const void *spInst; unsigned spN;   // для каких данных SPR1 построено
  int axesOld;           // spBillAxesOld на момент построения
} LspTab;

static void lspFree(LspTab *t) { free(t->e); free(t->base); free(t->idx); free(t->live); memset(t, 0, sizeof *t); }

static int lspTexCmp(const void *a, const void *b) {
  const LspE *x = (const LspE *)a, *y = (const LspE *)b;
  if (x->tex != y->tex) return x->tex < y->tex ? -1 : 1;
  return x->inst != y->inst ? (x->inst < y->inst ? -1 : 1) : (int)x->bill - (int)y->bill;
}

// Какие билборды экземпляра «постоянный свет» в его текущем состоянии: сложение (BLMD 2), не мигающий по PVIS, без покадровой анимации BQG
// (>1 строки), без автоперехода и такой, что его квад не двигается за весь клип позы состояния (у ламп клип часто крутится, но сустав
// билборда стоит: проверяем квад на нескольких кадрах клипа — проверка раз при построении таблицы, не в кадре)
static int lspQuadSame(StateProps *sp, unsigned i, unsigned b, const float *ref, float poseF) {
  SpRun *r = &sp->run[i]; float v[12]; uint32_t col, fl; int tx;
  r->poseF = poseF; r->poseValid = 0; spPose(sp, i);
  if (!spBillQuad(sp, i, b, r->x + 30.f, r->y + 3.f, r->z + 17.f, v, &col, &tx, &fl)) return 0;
  for (int k = 0; k < 12; k++) if (fabsf(v[k] - ref[k]) > 2e-3f) return 0;
  return 1;
}
static int lspStatic(StateProps *sp, unsigned i, unsigned b) {
  SpRun *r = &sp->run[i]; const SpType *T = &sp->type[sp->inst[i].type];
  if (!r->alive || b >= T->nBill || b >= 31 || T->kind != 0) return 0;
  const SpState *S = &sp->state[T->firstState + r->state];
  if (S->autoTo != 0xFF) return 0;
  const SpBill *B = &sp->bill[T->firstBill + b];
  if (((B->flags >> 8) & 0xFF) != 2) return 0;
  if (B->flags & SP_BILL_PVIS) return 0;
  if (sp->bqgIdx) { unsigned n = sp->bqgIdx[2 * (T->firstBill + b) + 1]; if (n > 1) return 0; }
  if (S->poseMode != 0) {   // клип позы играет: билборд обязан стоять на всех кадрах клипа
    unsigned nfr = T->frames & 0xFFFF; float keep = r->poseF; float ref[12]; uint32_t col, fl; int tx;
    spPose(sp, i);
    if (!spBillQuad(sp, i, b, r->x + 30.f, r->y + 3.f, r->z + 17.f, ref, &col, &tx, &fl)) return 0;
    int same = 1;
    if (nfr > 1) for (int k = 0; k < 6 && same; k++) same = lspQuadSame(sp, i, b, ref, (float)(nfr - 1) * (float)k / 5.f);
    r->poseF = keep; r->poseValid = 0; spPose(sp, i);   // как было
    if (!same) return 0;
  }
  return 1;
}

static void lspBuild(LspTab *t, StateProps *sp, int axesOld) {
  lspFree(t); t->spInst = sp->inst; t->spN = sp->ninst; t->axesOld = axesOld;
  if (axesOld || !sp->ninst) return;   // служебный прежний разворот осей (flag spaxesold): таблица не нужна
  unsigned cap = 0;
  for (unsigned i = 0; i < sp->ninst; i++) cap += sp->type[sp->inst[i].type].nBill;
  t->base = (unsigned *)malloc(sizeof(unsigned) * sp->ninst); t->live = (uint8_t *)calloc(sp->ninst, 1);
  t->idx = (uint16_t *)malloc(sizeof(uint16_t) * (cap + 1)); t->e = (LspE *)malloc(sizeof(LspE) * (cap + 1));
  if (!t->base || !t->live || !t->idx || !t->e) { lspFree(t); return; }
  unsigned ni = 0, ne = 0;
  for (unsigned i = 0; i < sp->ninst; i++) {
    const SpType *T = &sp->type[sp->inst[i].type]; t->base[i] = 0xFFFFFFFFu;
    if (!T->nBill) continue;
    unsigned first = ni; int any = 0;
    spPose(sp, i);
    for (unsigned b = 0; b < T->nBill; b++) {
      t->idx[ni + b] = 0xFFFF;
      if (!lspStatic(sp, i, b) || ne >= 0xFFFE) continue;
      const SpRun *r = &sp->run[i]; float v[12], c[3] = {r->x, r->y, r->z}; uint32_t col, fl; int tx;
      if (!spBillQuad(sp, i, b, c[0] + 30.f, c[1] + 3.f, c[2] + 17.f, v, &col, &tx, &fl) || !(col >> 24)) continue;
      LspE *e = &t->e[ne]; memset(e, 0, sizeof *e);
      const SpBill *B = &sp->bill[T->firstBill + b];
      for (int k = 0; k < 3; k++) {
        e->p[k] = (v[k] + v[3 + k] + v[6 + k] + v[9 + k]) * .25f;
        e->X[k] = (v[3 + k] - v[k]) * .5f; e->Y[k] = (v[6 + k] - v[k]) * .5f;
      }
      e->hw = sqrtf(e->X[0] * e->X[0] + e->X[1] * e->X[1] + e->X[2] * e->X[2]);
      e->hh = sqrtf(e->Y[0] * e->Y[0] + e->Y[1] * e->Y[1] + e->Y[2] * e->Y[2]);
      if (B->mode == 2 || B->mode == 3) { if (e->hh < 1e-6f) continue; for (int k = 0; k < 3; k++) e->Y[k] /= e->hh; }
      if (LSP_PLANT_OLD) { e->hw *= .5f; e->hh *= .5f; for (int k = 0; k < 3; k++) e->X[k] *= .5f; if (B->mode == 0) for (int k = 0; k < 3; k++) e->Y[k] *= .5f; }
      e->abgr = col; e->tex = tx; e->flags = fl; e->inst = i; e->bill = (uint16_t)b; e->mode = B->mode; e->state0 = r->state;
      memcpy(e->snap, &r->x, sizeof e->snap);
      t->idx[ni + b] = (uint16_t)ne; ne++; any = 1;
    }
    if (any) { t->base[i] = first; ni += T->nBill; } else ni = first;   // у экземпляра без записей места в idx не держим
  }
  t->nidx = ni; t->n = ne;
  // порядок записей — по текстуре (пачка на текстуру); idx перестраиваем по новым номерам
  if (ne > 1) {
    qsort(t->e, ne, sizeof(LspE), lspTexCmp);
    for (unsigned i = 0; i < sp->ninst; i++) if (t->base[i] != 0xFFFFFFFFu) for (unsigned b = 0; b < sp->type[sp->inst[i].type].nBill; b++) t->idx[t->base[i] + b] = 0xFFFF;
    for (unsigned k = 0; k < ne; k++) t->idx[t->base[t->e[k].inst] + t->e[k].bill] = (uint16_t)k;
  }
}

// Запись «своя» в этом кадре: экземпляр жив, в том же состоянии и на том же месте (снимок x, y, z, R). Иначе — прежний путь.
static void lspFrameLive(LspTab *t, const StateProps *sp) {
  if (!t->live) return;
  memset(t->live, 0, t->spN);
  for (unsigned k = 0; k < t->n; k++) {
    const LspE *e = &t->e[k]; const SpRun *r = &sp->run[e->inst];
    if (r->alive && r->state == e->state0 && !memcmp(&r->x, e->snap, sizeof e->snap)) t->live[e->inst] = 1;
  }
  // экземпляр «свой» только целиком: хоть одна запись не снимается (нет места) — прежний путь тоже её не потеряет, так как владеем по записи
}
static inline int lspOwns(const LspTab *t, unsigned inst, unsigned b) {
  return t->live && inst < t->spN && t->live[inst] && t->base[inst] != 0xFFFFFFFFu && t->idx[t->base[inst] + b] != 0xFFFF;
}
static inline int lspEntryOf(const LspTab *t, unsigned inst, unsigned b) {   // номер записи или −1 (для счётчиков)
  if (!t->base || inst >= t->spN || t->base[inst] == 0xFFFFFFFFu) return -1;
  unsigned v = t->idx[t->base[inst] + b]; return v == 0xFFFF ? -1 : (int)v;
}

// Квад записи для глаза (ex, ey, ez): то же, что spBillQuad (viewer/stateprops.c) на снятой позе, без позы и состояния
// 16.10 (план финала, Камера п.2): конусы света гаража АЭС (mode 2) как у PS2 — шире, ярче, до пола (факты ps2-test26-audit: у PS2 «конусы шире и ярче, доходят до пола, полупрозрачные жёлто-зелёные»).
// Множители ширины, длины (верх конуса у лампы остаётся на месте, растёт вниз) и яркости (альфа); 1/1/1 — как было. flag conewide 1 — подобранный набор LSP_CONE_*; conew/conel/conea — отдельно
#ifndef CONE_WIDE_OLD
#define CONE_WIDE_OLD 0   // 1 — конусы гаража как до 16.10 (файл coneold рядом с EBOOT делает то же)
#endif
#ifndef LSP_CONE_W
#define LSP_CONE_W 1.7f
#endif
#ifndef LSP_CONE_L
#define LSP_CONE_L 1.5f
#endif
#ifndef LSP_CONE_A
#define LSP_CONE_A 1.5f
#endif
static float lspConeW = 1.f, lspConeL = 1.f, lspConeA = 1.f;
static void lspQuad(const LspE *e, float ex, float ey, float ez, float v[12]) {
  float X[3], Y[3];
  if (e->mode == 0) { memcpy(X, e->X, sizeof X); memcpy(Y, e->Y, sizeof Y); }
  else if (e->mode == 2 || e->mode == 3) {
    for (int k = 0; k < 3; k++) Y[k] = e->Y[k];
    float D[3] = {ex - e->p[0], ey - e->p[1], ez - e->p[2]};
    X[0] = Y[1] * D[2] - Y[2] * D[1]; X[1] = Y[2] * D[0] - Y[0] * D[2]; X[2] = Y[0] * D[1] - Y[1] * D[0];
    float xl = sqrtf(X[0] * X[0] + X[1] * X[1] + X[2] * X[2]);
    if (xl < 1e-6f) {
      float D0[3] = {0.f, 0.f, 1.f}; if (fabsf(Y[2]) > .9f) { D0[0] = 1.f; D0[2] = 0.f; }
      X[0] = Y[1] * D0[2] - Y[2] * D0[1]; X[1] = Y[2] * D0[0] - Y[0] * D0[2]; X[2] = Y[0] * D0[1] - Y[1] * D0[0];
      xl = sqrtf(X[0] * X[0] + X[1] * X[1] + X[2] * X[2]);
    }
    float W_ = 1.f, L_ = 1.f, sh_[3] = {0.f, 0.f, 0.f};
    if (e->mode == 2 && (lspConeW != 1.f || lspConeL != 1.f)) {   // верх конуса (конец Y с большей высотой) остаётся у лампы, нижний уходит вниз
      W_ = lspConeW; L_ = lspConeL; float dn = Y[1] > 0.f ? -1.f : 1.f;   // направление «вниз» вдоль оси конуса
      for (int k = 0; k < 3; k++) sh_[k] = dn * Y[k] * e->hh * (L_ - 1.f);
    }
    for (int k = 0; k < 3; k++) { X[k] *= e->hw * W_ / xl; Y[k] *= e->hh * L_; }
    for (int k = 0; k < 3; k++) { v[k] = e->p[k] + sh_[k] - X[k] - Y[k]; v[3 + k] = e->p[k] + sh_[k] + X[k] - Y[k]; v[6 + k] = e->p[k] + sh_[k] - X[k] + Y[k]; v[9 + k] = e->p[k] + sh_[k] + X[k] + Y[k]; }
    return;
  } else {
    float dx = e->p[0] - ex, dy = e->p[1] - ey, dz = e->p[2] - ez, l = sqrtf(dx * dx + dz * dz);
    if (l < 1e-3f) l = 1e-3f;
    X[0] = dz / l; X[1] = 0; X[2] = -dx / l;
    float dl = sqrtf(dx * dx + dy * dy + dz * dz); if (dl < 1e-6f) dl = 1e-6f;
    Y[0] = -(dy / dl) * (dx / l); Y[1] = l / dl; Y[2] = -(dy / dl) * (dz / l);
    for (int k = 0; k < 3; k++) { X[k] *= e->hw; Y[k] *= e->hh; }
  }
  for (int k = 0; k < 3; k++) {
    v[k] = e->p[k] - X[k] - Y[k]; v[3 + k] = e->p[k] + X[k] - Y[k]; v[6 + k] = e->p[k] - X[k] + Y[k]; v[9 + k] = e->p[k] + X[k] + Y[k];
  }
}

// Прозрачность по дальности: 1 до LSP_DIST_M − LSP_FADE_M, к LSP_DIST_M — 0 (линейно по расстоянию от глаза)
static inline float lspFadeAt(float d2) {
  float end = LSP_DIST_M, beg = LSP_DIST_M - LSP_FADE_M;
  if (d2 <= beg * beg) return 1.f;
  if (d2 >= end * end) return 0.f;
  return (end - sqrtf(d2)) / LSP_FADE_M;
}
static inline uint32_t lspFadeCol(uint32_t abgr, float f) {
  if (f >= 1.f) return abgr;
  unsigned a = (unsigned)((float)(abgr >> 24) * f + .5f);
  return (abgr & 0x00FFFFFFu) | (a << 24);
}
#endif
