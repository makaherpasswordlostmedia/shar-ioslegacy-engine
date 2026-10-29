// Отсечение города на Media Engine (кандидат B, docs/case/ПРИМЕНЕНО_ИЛИ_НЕТ.md ч.2; слово Роба №653).
// Чистая арифметика без вызовов системы, без libc, без $gp: один и тот же текст считает ME (viewer/me/mework.h), служба-пустышка эмулятора
// (viewer/me/meprobe.c), запасной путь и хост-сверка (tests/citycull/host.c). Решение то же, что у главного потока (main_render.h cullCity,
// ветка PVS + иерархия клеток cullhier.h, затем цикл по клеткам для кусков дальше pvsRange): те же float-выражения в том же порядке.
// Что ME не делает: куски без горячей записи (CullRec.pad != 0) и куски вне клеток (cell == 0xFFFF) читают структуру Piece — ME кладёт в
// выход МЕТКУ (CC_MK_CALL / CC_MK_CHECK), главный потом вызывает cullPiece для неё на своём месте в порядке (порядок результата тот же).
// Состояние клеток: снимок state[ncell] (бит 0 — state == 2, бит 1 — state == 2 и owner == 0), сделанный главным при отдаче задания.
#ifndef CITYCULL_H
#define CITYCULL_H
#include "cullhier.h"
#define CC_MAXDRAW 2048                 // = MAXDRAW главного (main_render.h)
#define CC_MAXCELL 2048
#define CC_MK_CALL 0xFFFFu              // otk: главный зовёт cullPiece(otp)
#define CC_MK_CHECK 0xFFFEu             // otk: главный проверяет cl[pc[k].r.cell].state == 2 && boxD2(pc[k].r.bb) <= pr2 и зовёт cullPiece(otp)
#define CC_F_FAR 1u                     // opt & O_FAR
#define CC_F_FARLOOP 2u                 // drawDist > pvsRange: после списка PVS — цикл по клеткам
typedef struct { float bb[6]; unsigned short tk, tcl, cell; unsigned char rg, pad; } CcRec;   // = CullRec (main_state.h), проверяется _Static_assert в main_render.h
typedef struct { float bb[6]; unsigned first, n; } CcCell;                                     // статика уровня: ящик и диапазон кусков клетки
typedef struct CcJob {
  float eye[3], dd, mg, pr2, lod;       // глаз, дальность, запас ящиков cullMg, pr2 (1e30 или pvsRange²), LOD_DIST
  float pl[4][3];                       // боковые плоскости (setupPlanes)
  unsigned fcsr, flags, n, ncell, npc, regEye;
  unsigned inv[8][2];                   // ME сбрасывает свой кэш над этими участками (адрес, байт) до счёта: статика уровня, список PVS
  const unsigned short *list, *crc;     // список PVS глаза (n кусков), клетка куска
  const CcRec *cr;
  const CcCell *cells;
  const unsigned char *state;           // снимок состояния клеток
  // выход (пишет ME); начинается с новой строки кэша, чтобы кэш главного не делил строку с входом
  unsigned nOut __attribute__((aligned(64))), regCut, nMark, ovf, magic;
  unsigned char cls[CC_MAXCELL];        // класс клетки за этот расчёт (0xFF — не считан)
  unsigned short otk[CC_MAXDRAW], otp[CC_MAXDRAW], otcl[CC_MAXDRAW]; unsigned char otf[CC_MAXDRAW];
} __attribute__((aligned(64))) CcJob;
#define CC_MAGIC 0x31434359u            // "YCC1": задание посчитано до конца

// те же выражения, что boxD2/visBox главного (main_render.h) с запасом cullMg; порядок вычислений не менять (бит в бит)
static inline float ccBoxD2(const float *b, float mg, float ex, float ey, float ez) {
  float dx = b[0] - mg - ex > 0 ? b[0] - mg - ex : (ex - b[3] - mg > 0 ? ex - b[3] - mg : 0);
  float dy = b[1] - mg - ey > 0 ? b[1] - mg - ey : (ey - b[4] - mg > 0 ? ey - b[4] - mg : 0);
  float dz = b[2] - mg - ez > 0 ? b[2] - mg - ez : (ez - b[5] - mg > 0 ? ez - b[5] - mg : 0);
  return dx * dx + dy * dy + dz * dz;
}
static inline int ccVisBox(const float *b, float mg, const float pl[4][3], float ex, float ey, float ez) {
  for (int i = 0; i < 4; i++) {
    float px = (pl[i][0] > 0 ? b[3] + mg : b[0] - mg) + 0.f - ex;
    float py = (pl[i][1] > 0 ? b[4] + mg : b[1] - mg) + 0.f - ey;
    float pz = (pl[i][2] > 0 ? b[5] + mg : b[2] - mg) + 0.f - ez;
    if (px * pl[i][0] + py * pl[i][1] + pz * pl[i][2] < 0) return 0;
  }
  return 1;
}
// cellClassC главного: ящик клетки с запасом (если mg > 0) и chClassify; клетка не готова (state != 2) — 0
static inline int ccCellClass(const CcJob *J, unsigned ci) {
  if (!(J->state[ci] & 1u)) return 0;
  float bi[6]; const float *bb = J->cells[ci].bb;
  for (int i = 0; i < 6; i++) bi[i] = bb[i];
  if (J->mg > 0.f) { bi[0] -= J->mg; bi[1] -= J->mg; bi[2] -= J->mg; bi[3] += J->mg; bi[4] += J->mg; bi[5] += J->mg; }
  return chClassify(bi, J->pl, J->eye[0], J->eye[1], J->eye[2], J->dd);
}
// принять кусок с горячей записью (cullPieceIn / горячая ветка cullPiece): inside — плоскости пройдены клеткой целиком. 0 — переполнение
static inline int ccTake(CcJob *J, unsigned k, int inside, int farLoop) {
  const CcRec *h = &J->cr[k]; unsigned rg = h->rg;
  if (rg && rg <= 16 && !((J->regEye >> (rg - 1)) & 1u)) { J->regCut++; return 1; }
  float d2 = ccBoxD2(h->bb, J->mg, J->eye[0], J->eye[1], J->eye[2]);
  if (d2 > J->dd * J->dd || (!inside && !ccVisBox(h->bb, J->mg, J->pl, J->eye[0], J->eye[1], J->eye[2]))) return 1;
  (void)farLoop;
  int far_ = (J->flags & CC_F_FAR) ? d2 > J->lod * J->lod : 0;
  if (J->nOut >= CC_MAXDRAW) { J->ovf = 1; return 0; }
  unsigned o = J->nOut++; J->otk[o] = h->tk; J->otp[o] = (unsigned short)k; J->otf[o] = (unsigned char)far_; J->otcl[o] = h->tcl;
  return 1;
}
static inline int ccMark(CcJob *J, unsigned k, unsigned short kind) {
  if (J->nOut >= CC_MAXDRAW) { J->ovf = 1; return 0; }
  unsigned o = J->nOut++; J->otk[o] = kind; J->otp[o] = (unsigned short)k; J->otf[o] = 0; J->otcl[o] = 0; J->nMark++;
  return 1;
}
// Весь расчёт. Возврат 1 — посчитано (J->ovf == 0), 0 — переполнение: главный считает сам
static inline int ccRun(CcJob *J) {
  J->nOut = J->regCut = J->nMark = J->ovf = 0;
  if (J->ncell > CC_MAXCELL) { J->ovf = 1; return 0; }
  for (unsigned i = 0; i < J->ncell; i++) J->cls[i] = 0xFFu;
  const unsigned short *list = J->list, *crc = J->crc; const CcRec *cr = J->cr;
  const float pr2 = J->pr2;
  for (unsigned i = 0; i < J->n; i++) {                                   // 1) список PVS: cullCity, ветка cullHierReady
    unsigned k = list[i]; if (k >= J->npc) continue;
    unsigned ci = crc[k];
    if (ci != 0xFFFFu && ci < J->ncell) {
      int c = J->cls[ci]; if (c == 0xFF) { c = ccCellClass(J, ci); J->cls[ci] = (unsigned char)c; }
      if (!c) continue;
      const CcRec *h = &cr[k];
      if (!h->pad) { if (ccBoxD2(h->bb, J->mg, J->eye[0], J->eye[1], J->eye[2]) <= pr2) { if (!ccTake(J, k, c == 2, 0)) return 0; } }
      else if (ccBoxD2(h->bb, J->mg, J->eye[0], J->eye[1], J->eye[2]) <= pr2) { if (!ccMark(J, k, CC_MK_CALL)) return 0; }
    } else if (cr[k].cell == 0xFFFFu) { if (!ccMark(J, k, CC_MK_CHECK)) return 0; }
  }
  if (J->flags & CC_F_FARLOOP) {                                           // 2) за pvsRange PVS нет: клетки по пирамиде, куски дальше pr2
    for (unsigned i = 0; i < J->ncell; i++) {
      if (!(J->state[i] & 2u)) continue;                                   // c->owner || c->state != 2
      const CcCell *c = &J->cells[i];
      if (ccBoxD2(c->bb, J->mg, J->eye[0], J->eye[1], J->eye[2]) > J->dd * J->dd || !ccVisBox(c->bb, J->mg, J->pl, J->eye[0], J->eye[1], J->eye[2])) continue;
      for (unsigned k = c->first; k < c->first + c->n; k++) {
        if (k >= J->npc) break;
        const CcRec *h = &cr[k];
        if (!(ccBoxD2(h->bb, J->mg, J->eye[0], J->eye[1], J->eye[2]) > pr2)) continue;   // boxD2(pc[k].r.bb) > pr2 (cr[k].bb == pc[k].r.bb)
        if (!h->pad && h->cell != 0xFFFFu) { if (!ccTake(J, k, 0, 1)) return 0; }       // горячая ветка cullPiece
        else if (!ccMark(J, k, CC_MK_CALL)) return 0;                                    // иначе cullPiece по Piece — на главном
      }
    }
  }
  J->magic = CC_MAGIC;
  return 1;
}
#endif
