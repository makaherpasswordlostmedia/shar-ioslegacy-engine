// Правка 313 (Роб 04.10: «делегируй Media Engine прозрачные элементы, свечение, музыку»): частицы и свечение — шаг жизни частиц
// и сборка биллбордов одной функцией над одной структурой задания, как смешивание звука (viewer/mixdsp.h). Тот же код считает везде:
// на Маке (tests/me/fx_test.c — сверка с прежним fx.c бит в бит), в эмуляторе и на PSP главным процессором (viewer/fx.c fxDraw),
// а с флаг-файлом mefx — на Media Engine (модуль viewer/me/sharme.prx собирает этот же заголовок).
// Правила конвейера ME: функции без вызовов системы и своих библиотек (циклы вместо memcpy/memset), без глобальных переменных;
// вход и выход — одна структура FxJob (выровнена на 64), указатели внутри — только FxJob.E/BB/blob (пакет частиц уровня, только
// чтение) и FxJob.vout (вершины для GE). Плавающая точка — та же, что у главного (без FMA у Allegrex, -fno-math-errno: sqrt.s);
// из libm — только чистые функции (cosf, sinf, atan2f, fminf, __ieee754_expf): у ME в модуле тот же машинный код libm.a.
// Код перенесён из viewer/fx.c (до правки 313) без изменения счёта и порядка действий; отличие одно — вершины пишутся в свой буфер
// (FxJob.vout), а не в список GE (sceGuGetMemory): ME списка GE не видит; группа без места в списке GE теперь пропускается после
// сборки (раньше — до, и её частицы не входили в бюджет заливки; бывает только при переполнении списка, правка 103).
#ifndef FXDSP_H
#define FXDSP_H
#include <math.h>
#include "fx.h"

// №937 «поп» звезды-sparkle: размер частицы плавной кривой от возраста — 0 → 1,15 за FXD_POP_T1 с, → 1 к FXD_POP_T2 с, дальше 1 (гаснет по ALOL/COOL эмиттера, как было).
// Только у эмиттеров с картинкой scratch2_blue / _red (флаг пункта эмиттера 0x40 ставит fx.c при загрузке). Чистая функция, без вызовов (ME). FX_SPARKLE937_OLD=1 — без попа
#ifndef FX_SPARKLE937_OLD
#define FX_SPARKLE937_OLD 0
#endif
#ifndef FXD_POP_T1
#define FXD_POP_T1 .07f
#endif
#ifndef FXD_POP_T2
#define FXD_POP_T2 .14f
#endif
#ifndef FXD_POP_OVER
#define FXD_POP_OVER 1.15f
#endif
static inline float fxdPop(float a) {
  if (a <= 0.f) return 0.f;
  if (a < FXD_POP_T1) { float u = a * (1.f / FXD_POP_T1), v = 1.f - u; return FXD_POP_OVER * (1.f - v * v); }
  if (a < FXD_POP_T2) { float u = (a - FXD_POP_T1) * (1.f / (FXD_POP_T2 - FXD_POP_T1)); return FXD_POP_OVER + (1.f - FXD_POP_OVER) * (u * u * (3.f - 2.f * u)); }
  return 1.f;
}

enum { P_RAT, P_SPD, P_SPDV, P_LIF, P_LIFV, P_SIZ, P_SIZV, P_SPI, P_SPIV, P_WGT, P_WGTV, P_GRA, P_DRA, P_ALP, P_ALPV,
       P_CLRR, P_CLRG, P_CLRB, P_CLRV, P_NUM, P_TX, P_TY, P_TZ, P_QW, P_QX, P_QY, P_QZ, NP };
#define NOL 16
#define MAXE 32          // эмиттеров в одной системе (взрыв — 24)
#define MAXSPR 96        // блёсток/спрайтов на кадр

typedef struct { unsigned short tex; unsigned char cols, rows, nFr, texMode, blend, angleMode, gen, flags, pad[2];
                 float texRate, angle, aspect, genW, genH, spreadH, spreadV;
                 unsigned short key[NP][2]; unsigned ol[NOL];
                 float olSize[NOL], olSpeed[NOL], olSpin[NOL], olWeight[NOL]; } FxEmit;
typedef struct { unsigned short frame, pad; float v; } FxKey;
typedef struct { unsigned short tex; unsigned char blend, mode; float dist, rot[4]; unsigned short nFrames, pad;
                 unsigned offLut; } FxBB;

// частица (прежде P в fx.c)
typedef struct { float x, y, z, vx, vy, vz, vg, ga, age, inv, size, ang, spin, lnd, ak; unsigned rgb;
                 unsigned short em, inst; unsigned char seed, pad[3]; } FxPart;
typedef struct { float x, y, z, w, h, rot; unsigned c; unsigned short tex; unsigned char blend, flat; } FxSpr;   // прежде Spr
typedef struct { float u, v; unsigned c; float x, y, z; } FxV;                                                    // прежде FV
typedef struct { unsigned short bb, pad; float x, y, z, t, up[3]; } FxJobBB; // №391: нормаль поверхности для кольца и пятна
typedef struct { unsigned short inst, em; } FxDead;                      // частица умерла: экземпляр и эмиттер (счётчики live — на главном)

#define FX_NEL (FX_MAX + MAXSPR + 3 * FX_MAX_INST)   // элементов кадра: частицы, биллборды систем, спрайты
#define FX_NK (3 * 256)                             // групп (смешивание × текстура)
#define FX_FOCAL 226.f            // пикселей на единицу tan: 136 / tan(62°/2) (FOVY main.c)
// Кадр «плавность» (10.10, M313_boom p95 14.5 мс, crate 12.2 мс): не считать и не отдавать GE биллборды, которых на экране нет —
// невидимых (альфа 0 при обычном смешивании, цвет 0 при добавлении/вычитании) и целиком вне конуса (запас: вертикальный угол до ~92°,
// кадр 16:9). Картинка та же; они же больше не раздувают заливку fxFill и ужатие fillK. -DFX_CULL_OLD=1 — прежнее
#ifndef FX_CULL_OLD
#define FX_CULL_OLD 0
#endif
#define FX_CULL_Y 1.05f
#define FX_CULL_X 1.9f
#define FX_NEAR_BUDGET 120000.f   // пикселей на ближние частицы за кадр (~1 экран)
#define FX_TOTAL_BUDGET 260000.f  // пикселей на все частицы за кадр (~2 экрана): больше — плавно ужимаем (не меньше 0.75)
#define FXD_SIM 1u                // FxJob.stage: шаг жизни частиц (прежний конец fxUpdate)
#define FXD_BUILD 2u              // сборка биллбордов (прежнее тело fxDraw без команд GE)
#define FXD_GROUND_OLD 4u         // №391: прежняя ориентация кольца по ROT

#ifndef FXD_EXPF                  // libm: expf = __ieee754_expf (обёртка добавляет только errno при переполнении; у нас |x| < 42)
float __ieee754_expf(float);
#define FXD_EXPF __ieee754_expf
#endif

typedef struct FxJob {
  // вход (главный -> задание)
  const FxEmit *E; const FxBB *BB; const unsigned char *blob;   // таблицы пакета частиц (только чтение)
  FxV *vout;                                                     // вершины: 4 на элемент, по группам подряд
  unsigned stage, fcsr;          // что считать; FCR31 главного потока (ME ставит такой же: округление и FS — бит в бит)
  int np, nb, nspr, nt;          // частиц, биллбордов систем, спрайтов; текстур пакета
  float dt, ex, ey, ez, fx, fy, fz;   // шаг (уже ограничен 0.1 с); глаз и единичный взгляд камеры
  float fillK;                   // вход и выход: ужатие частиц по общей заливке (прежнее static fillK)
  unsigned inv[4][2];            // ME: участки пакета (адрес, байт) — строки кэша ME над ними недействительны до счёта
  // выход
  int ndead, nk, nq, fxSkipped, empty;   // умерших; групп; вершин-четвёрок всего; ближних мимо бюджета; кадр без элементов
  float fxFill;                  // заливка частиц кадра, пикселей экрана
  unsigned pad0[6];
  unsigned short qs[FX_NK + 1], qn[FX_NK + 1];   // группа k: первая четвёрка и сколько их
  unsigned short order[FX_NEL], keyOf[FX_NEL], cnt[FX_NK + 1], pos[FX_NK + 1];   // рабочие (сортировка подсчётом)
  FxDead dead[FX_MAX];
  FxJobBB bb[3 * FX_MAX_INST];
  FxSpr spr[MAXSPR];
  FxPart ps[FX_MAX];             // состояние частиц (живёт здесь: главный рожает частицы между кадрами, счёт — тут)
} __attribute__((aligned(64))) FxJob;

// ---------- кривые и цвет (как в fx.c до правки 313) ----------
static inline __attribute__((always_inline)) float fxdLut(const float *l, float u) {
  float f = u * (NOL - 1); int i = (int)f; if (i >= NOL - 1) return l[NOL - 1]; if (i < 0) return l[0];
  return l[i] + (l[i + 1] - l[i]) * (f - i);
}
static inline __attribute__((always_inline)) unsigned fxdLutc(const unsigned *l, float u) {
  float f = u * (NOL - 1); int i = (int)f; if (i >= NOL - 1) return l[NOL - 1]; if (i < 0) return l[0];
  unsigned a = l[i], b = l[i + 1], o = 0; float t = f - i;
  for (int s = 0; s < 32; s += 8) { float ca = (a >> s) & 255, cb = (b >> s) & 255; o |= ((unsigned)(ca + (cb - ca) * t) & 255) << s; }
  return o;
}
static inline __attribute__((always_inline)) void fxdQrot(const float q[4], const float v[3], float o[3]) {   // q = w,x,y,z
  float w = q[0], x = q[1], y = q[2], z = q[3];
  float cx = y * v[2] - z * v[1], cy = z * v[0] - x * v[2], cz = x * v[1] - y * v[0];
  float dx = y * cz - z * cy, dy = z * cx - x * cz, dz = x * cy - y * cx;
  o[0] = v[0] + 2.f * (w * cx + dx); o[1] = v[1] + 2.f * (w * cy + dy); o[2] = v[2] + 2.f * (w * cz + dz);
}
static inline __attribute__((always_inline)) unsigned fxdMulc(unsigned a, unsigned b) {   // покомпонентно /255
  unsigned o = 0;
  for (int s = 0; s < 32; s += 8) o |= ((((a >> s) & 255) * ((b >> s) & 255) + 127) / 255) << s;
  return o;
}
static inline __attribute__((always_inline)) void fxdCopyPart(FxPart *d, const FxPart *s) {   // без memcpy (код ME — без вызовов)
  unsigned *dw = (unsigned *)d; const unsigned *sw = (const unsigned *)s;
  for (unsigned k = 0; k < sizeof(FxPart) / 4; k++) dw[k] = sw[k];
}

// Функции счёта — в своём файле viewer/fxdsp.c (FXDSP_IMPL), с одними ключами у игры и у модуля (-G0, без memset/memcpy и ловушки
// деления): машинный код одинаков, что проверяет tests/me/run.py (дизассемблер игры и sharme.elf)
void fxdSim(FxJob *j);
void fxdBuild(FxJob *j);
void fxdRun(FxJob *j);
#ifdef FXDSP_IMPL

// ---------- шаг жизни частиц (прежний цикл «частицы» в fxUpdate) ----------
// Умершая частица уходит перестановкой последней на её место (как раньше); счётчики live экземпляра — на главном по списку dead
void __attribute__((noinline, noclone)) fxdSim(FxJob *j) {
  const FxEmit *E = j->E; const float dt = j->dt;
  j->ndead = 0;
  for (int i = 0; i < j->np; ) {
    FxPart *p = &j->ps[i];
    p->age += dt;
    float u = p->age * p->inv;
    if (u >= 1.f) {
      if (p->inst != 0xffff) { FxDead *d = &j->dead[j->ndead++]; d->inst = p->inst; d->em = p->em; }
      --j->np; if (i != j->np) fxdCopyPart(p, &j->ps[j->np]);
      continue;
    }
    const FxEmit *e = &E[p->em];
    p->vg += p->ga * fxdLut(e->olWeight, u) * dt;
    if (p->lnd != 0.f) { float k = FXD_EXPF(p->lnd * dt); p->vx *= k; p->vy *= k; p->vz *= k; }
    float sp = fxdLut(e->olSpeed, u);
    p->x += p->vx * sp * dt; p->y += (p->vy * sp + p->vg) * dt; p->z += p->vz * sp * dt;
    p->ang += p->spin * fxdLut(e->olSpin, u) * dt;
    i++;
  }
}

// ---------- сборка биллбордов (прежнее тело fxDraw без команд GE) ----------
// Элементы: частицы, биллборды систем, спрайты (блёстки, свечение) — сортировка подсчётом по (смешивание, текстура), внутри группы —
// в прежнем порядке; на элемент — отсечение за камерой, потолок размера, бюджет ближней заливки, гашение у объектива, четыре вершины
void __attribute__((noinline, noclone)) fxdBuild(FxJob *j) {
  const FxEmit *E = j->E; const FxBB *BB = j->BB;
  const float ex = j->ex, ey = j->ey, ez = j->ez, fx = j->fx, fy = j->fy, fz = j->fz;
  float nearFill = 0.f, fxFill = 0.f, fillK = j->fillK; int fxSkipped = 0;
  const int np = j->np, nb = j->nb, nspr = j->nspr;
  int n = np + nb + nspr;
  j->nq = 0; j->empty = !n;
  if (!n) { j->fxFill = 0.f; j->fxSkipped = 0; j->nk = 0; return; }   // как раньше: пустой кадр — fillK не меняется
  int nt = j->nt, nk = 3 * nt;
  unsigned short *cnt = j->cnt, *keyOf = j->keyOf, *order = j->order;
  if (nk > FX_NK) nk = FX_NK;
  for (int k = 0; k <= nk; k++) cnt[k] = 0;
  for (int i = 0; i < n; i++) {
    int k;
    if (i < np) { const FxEmit *e = &E[j->ps[i].em]; k = e->blend * nt + e->tex; }
    else if (i < np + nb) { const FxBB *b = &BB[j->bb[i - np].bb]; k = b->blend * nt + b->tex; }
    else { const FxSpr *s = &j->spr[i - np - nb]; k = s->blend * nt + s->tex; }
    if (k >= nk) k = nk - 1;
    keyOf[i] = k; cnt[k + 1]++;
  }
  for (int k = 0; k < nk; k++) cnt[k + 1] += cnt[k];
  { unsigned short *pos_ = j->pos; for (int k = 0; k <= nk; k++) pos_[k] = cnt[k];
    for (int i = 0; i < n; i++) order[pos_[keyOf[i]]++] = i; }
  // оси камеры
  float rx = -fz, rz = fx, rl = sqrtf(rx * rx + rz * rz); if (rl < 1e-4f) { rx = 1; rz = 0; rl = 1; }
  rx /= rl; rz /= rl;
  float R[3] = {rx, 0, rz}, U[3] = {-rz * fy, rz * fx - rx * fz, rx * fy};
  const float invF = 1.f / sqrtf(fx * fx + fy * fy + fz * fz + 1e-12f);
  FxV *w = j->vout; int nq = 0;
  for (int k = 0; k < nk; k++) {
    int a = cnt[k], b = cnt[k + 1];
    j->qs[k] = (unsigned short)nq; j->qn[k] = 0;
    if (a == b) continue;
    int nq0 = nq;
    for (int jj = a; jj < b; jj++) {
      int i = order[jj];
      float px, py, pz, hw, hh, ang, u0 = 0, u1 = 1, v0 = 0, v1 = 1; unsigned c; int flat = 0; const float *qr = 0;
      if (i < np) {
        const FxPart *p = &j->ps[i]; const FxEmit *e = &E[p->em]; float u = p->age * p->inv;
        px = p->x; py = p->y; pz = p->z;
        hw = .5f * p->size * fxdLut(e->olSize, u); hh = hw * e->aspect;
        if (!FX_SPARKLE937_OLD && (e->flags & 0x40)) { float pk = fxdPop(p->age); hw *= pk; hh *= pk; }   // №937: поп звезды-sparkle
        unsigned ol = fxdLutc(e->ol, u), rgb = p->rgb | 0xff000000u;
        c = fxdMulc(ol, rgb);
        unsigned al = (unsigned)(((c >> 24) & 255) * p->ak); if (al > 255) al = 255;
        if (e->blend == 1 && !(e->flags & 1) && (e->flags & 2) && p->ak > 0.f) {   // add без COOL: гаснет по ALOL
          float f = al * (1.f / 255.f); c = fxdMulc(c, ((unsigned)(f * 255) * 0x010101u) | 0xff000000u);
        }
        c = (c & 0xffffff) | (al << 24);
        if (e->angleMode == 2) {   // вдоль экранной скорости
          float sp = fxdLut(e->olSpeed, u), vx = p->vx * sp, vy = p->vy * sp + p->vg, vz = p->vz * sp;
          ang = atan2f(vx * U[0] + vy * U[1] + vz * U[2], vx * R[0] + vz * R[2]);
        } else ang = p->ang;
        int nf = e->nFr;
        if (nf > 1 && e->texMode) {
          int f = e->texMode == 1 ? (int)((p->seed + (int)(p->age * e->texRate) * 97) % nf) : ((int)(p->age * e->texRate)) % nf;
          int cx = f % e->cols, cy = f / e->cols;
          u0 = (float)cx / e->cols; u1 = (float)(cx + 1) / e->cols; v0 = (float)cy / e->rows; v1 = (float)(cy + 1) / e->rows;
        } else if (e->cols > 1 || e->rows > 1) { u1 = 1.f / e->cols; v1 = 1.f / e->rows; }
      } else if (i < np + nb) {
        const FxJobBB *s = &j->bb[i - np]; const FxBB *bq = &BB[s->bb];
        int f = (int)s->t; if (f >= bq->nFrames) f = bq->nFrames - 1; if (f < 0) f = 0;
        const float *L = (const float *)(j->blob + bq->offLut) + f * 3;
        hw = L[0] * .5f; hh = L[1] * .5f; c = ((const unsigned *)L)[2]; ang = 0;
        px = s->x; py = s->y; pz = s->z;
        if (bq->mode == 0 || bq->mode == 2) { flat = bq->mode == 2 && !(j->stage & FXD_GROUND_OLD) ? 3 : 2; qr = bq->rot; py += .04f; }
        else { float dx = ex - px, dy = ey - py, dz = ez - pz, l = sqrtf(dx * dx + dy * dy + dz * dz);
               if (l > 1e-3f) { float k2 = fminf(bq->dist, l * .5f) / l; px += dx * k2; py += dy * k2; pz += dz * k2; } }
        if (bq->blend == 1) c |= 0xff000000u;
      } else {
        const FxSpr *s = &j->spr[i - np - nb];
        px = s->x; py = s->y; pz = s->z; hw = s->w * .5f; hh = s->h * .5f; ang = s->rot; c = s->c; flat = s->flat;
      }
      // расстояние до глаза: не рисовать за камерой, ужать у объектива, гасить ближе 4 м (правило и числа — как раньше в fxDraw)
      float d = (px - ex) * fx + (py - ey) * fy + (pz - ez) * fz;
      if (!flat) {
        if (d < 1.f) continue;
        if (!FX_CULL_OLD) {
          int bl = k / nt;
          if (bl == 0 ? !(c >> 24) : !(c & 0xffffffu)) continue;
          float dx = px - ex, dy = py - ey, dz = pz - ez, r = 1.5f * (hw > hh ? hw : hh) * fillK;
          float lx = dx * R[0] + dz * R[2], ly = (dx * U[0] + dy * U[1] + dz * U[2]) * invF, dn = d * invF;   // вперёд не обязательно единичный
          if (fabsf(lx) > dn * FX_CULL_X + r || fabsf(ly) > dn * FX_CULL_Y + r) continue;
        }
        hw *= fillK; hh *= fillK;
        float mx = d * fminf(.42f, .1f + .04f * d); if (hw > mx) { hh *= mx / hw; hw = mx; } if (hh > mx) { hw *= mx / hh; hh = mx; }
        float px2 = 4.f * hw * hh * (FX_FOCAL * FX_FOCAL) / (d * d);   // пикселей на экране
        if (d < 6.f) { if (nearFill + px2 > FX_NEAR_BUDGET) { fxSkipped++; continue; } nearFill += px2; }
        fxFill += px2;
        if (d < 4.f) {
          float f = (d - 1.f) * (1.f / 3.f);
          if (k / nt == 0) c = (c & 0xffffff) | ((unsigned)(((c >> 24) & 255) * f) << 24);
          else c = fxdMulc(c, ((unsigned)(f * 255) * 0x010101u) | 0xff000000u);
        }
      }
      float e1[3], e2[3];
      if (flat == 3) {   // №391, правило Роба: NOAX взрыва лежит на реальной поверхности; ROT сохраняет поворот в ней
        const FxJobBB *s = &j->bb[i - np];
        float n[3] = {s->up[0], s->up[1], s->up[2]}, nl = sqrtf(n[0]*n[0]+n[1]*n[1]+n[2]*n[2]);
        if (nl < 1e-5f) { n[0]=n[2]=0.f; n[1]=1.f; } else for (int t=0;t<3;t++) n[t]/=nl;
        static const float X[3]={1,0,0}, Z[3]={0,0,1}; float a[3]; fxdQrot(qr,X,a);
        float dot = a[0]*n[0]+a[1]*n[1]+a[2]*n[2];
        for (int t=0;t<3;t++) a[t]-=dot*n[t];
        float al=sqrtf(a[0]*a[0]+a[1]*a[1]+a[2]*a[2]);
        if (al<1e-5f) { fxdQrot(qr,Z,a); dot=a[0]*n[0]+a[1]*n[1]+a[2]*n[2]; for(int t=0;t<3;t++)a[t]-=dot*n[t]; al=sqrtf(a[0]*a[0]+a[1]*a[1]+a[2]*a[2]); }
        if (al<1e-5f) continue;
        for(int t=0;t<3;t++)a[t]/=al;
        float b[3]={n[1]*a[2]-n[2]*a[1],n[2]*a[0]-n[0]*a[2],n[0]*a[1]-n[1]*a[0]};
        for(int t=0;t<3;t++){e1[t]=a[t]*hw;e2[t]=b[t]*hh;}
      } else if (flat == 2) {   // биллборд, лежащий по кватерниону ROT
        static const float X[3] = {1, 0, 0}, Y[3] = {0, 1, 0}; float a1[3], a2[3]; fxdQrot(qr, X, a1); fxdQrot(qr, Y, a2);
        for (int t = 0; t < 3; t++) { e1[t] = a1[t] * hw; e2[t] = a2[t] * hh; }
      } else if (flat) {
        float cs = cosf(ang), sn = sinf(ang);
        e1[0] = cs * hw; e1[1] = 0; e1[2] = sn * hw; e2[0] = -sn * hh; e2[1] = 0; e2[2] = cs * hh;
      } else {
        float cs = cosf(ang), sn = sinf(ang);
        for (int t = 0; t < 3; t++) { e1[t] = (cs * R[t] + sn * U[t]) * hw; e2[t] = (-sn * R[t] + cs * U[t]) * hh; }
      }
      w[0].u = u0; w[0].v = v0; w[0].c = c; w[0].x = px - e1[0] + e2[0]; w[0].y = py - e1[1] + e2[1]; w[0].z = pz - e1[2] + e2[2];
      w[1].u = u1; w[1].v = v0; w[1].c = c; w[1].x = px + e1[0] + e2[0]; w[1].y = py + e1[1] + e2[1]; w[1].z = pz + e1[2] + e2[2];
      w[2].u = u1; w[2].v = v1; w[2].c = c; w[2].x = px + e1[0] - e2[0]; w[2].y = py + e1[1] - e2[1]; w[2].z = pz + e1[2] - e2[2];
      w[3].u = u0; w[3].v = v1; w[3].c = c; w[3].x = px - e1[0] - e2[0]; w[3].y = py - e1[1] - e2[1]; w[3].z = pz - e1[2] - e2[2];
      w += 4; nq++;
    }
    j->qn[k] = (unsigned short)(nq - nq0);
  }
  j->qs[nk] = (unsigned short)nq; j->qn[nk] = 0;
  j->nq = nq; j->nk = nk; j->fxFill = fxFill; j->fxSkipped = fxSkipped;
  { float raw = fxFill / (fillK * fillK), want = raw > FX_TOTAL_BUDGET ? sqrtf(FX_TOTAL_BUDGET / raw) : 1.f;
    if (want < .75f) want = .75f;
    fillK += (want - fillK) * (want < fillK ? .3f : .05f); }
  j->fillK = fillK;
}

// Задание целиком (главный процессор или ME): шаг жизни, затем сборка — по FxJob.stage
void fxdRun(FxJob *j) {
  if (j->stage & FXD_SIM) fxdSim(j);
  if (j->stage & FXD_BUILD) fxdBuild(j);
}
#endif   // FXDSP_IMPL

#endif
