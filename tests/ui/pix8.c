// Гейт правки 126 (пузырь сообщений: пиксельный шрифт 8×8 и текст левее) — хост, Мак (CPU), без эмулятора.
// Логика — viewer/ui_layout.h (её же собирает ui.c), шрифт — viewer/bootmsx.h (msx из pspsdk), раскладка — из build/ui.shr.
// Плохие варианты (tests/ui/pix8.sh): -DUI_OBJ_OLD (текст без значка на месте из пакета), -DUI_WRAP_OLD (прежний перенос: '\n'
// рисуется «?»), -DPLANT_ALPHA (в атласе промежуточная альфа, как у ужатых шрифтов пакета), -DPLANT_MSX (глифы со сдвигом таблицы)
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "ui.h"
#include "ui_layout.h"
#include "bootmsx.h"

typedef struct {
  unsigned char type, screen, tag, field, fmt, halign, valign, flags;
  short x, y, w, h;
  unsigned color, color2;
  signed char sdx, sdy; unsigned char font, menu;
  unsigned short first, count;
  float px, py, ang; unsigned prefix; float clip; unsigned res[3];
} Item;   // = UiItem viewer/ui.c (64 Б)
enum { T_IMG = 2, T_TEXT = 3 };
static int fails, oks;
#define CHECK(c, ...) do { if (c) { oks++; printf("OK   "); } else { fails++; printf("FAIL "); } printf(__VA_ARGS__); printf("\n"); } while (0)

static int pixW(const void *ctx, const char *s, int n) {   // ширина как у ui.c: шаг знака pix8Adv (жирный — по букве), «?» вместо нет
  (void)ctx; int w = 0; for (int i = 0; i < n; i++) { int k = pix8Cell((unsigned char)s[i]); w += pix8Adv(bootMsx, k < 0 ? '?' - 32 : k); } return w; }
static unsigned char tex[PIX8_TEXBYTES];

int main(int argc, char **argv) {
  // ---- шрифт
  const unsigned char *src = bootMsx;
#ifdef PLANT_MSX
  static unsigned char shifted[2048]; memcpy(shifted, bootMsx + 8, 2040); src = shifted;
#endif
  pix8Build(src, tex);
#ifdef PLANT_ALPHA
  for (int i = 0; i < PIX8_TEXBYTES; i++) if (tex[i] & 0x0f) { tex[i] = (unsigned char)((tex[i] & 0xf0) | 0x07); break; }
#endif
  int bad = 0;
  for (int y = 0; y < PIX8_TH; y++) for (int x = 0; x < PIX8_TW; x++) { int a = pix8Texel(tex, x, y); if (a != 0 && a != 15) bad++; }
  CHECK(bad == 0, "F1 атлас 1 бит: альфа только 0/15 (иных текселей %d)", bad);
  int mism = 0;
  for (int c = 32; c <= 126; c++) {
    int k = pix8Cell((unsigned char)c); if (c == '@') continue;   // '@' — знак кнопки △ (библия)
    for (int y = 0; y < 8; y++) for (int x = 0; x < 8; x++)
      if ((pix8Texel(tex, (k & 15) * 8 + x, (k >> 4) * 8 + y) != 0) != ((pix8Row(bootMsx, k, y) >> (7 - x)) & 1)) mism++;
  }
  // источник: где нет ручной правки — msx pspsdk, утолщённый вправо без закрытия просветов (стебли и рисунок из msx)
  int srcBad = 0;
  for (int c = 33; c <= 126; c++) { int fixed = 0; for (unsigned i = 0; i < sizeof pix8Fix / sizeof pix8Fix[0]; i++) fixed |= pix8Fix[i].c == c;
    if (fixed || c == '@') continue;
    for (int y = 0; y < 8; y++) { unsigned r = bootMsx[c * 8 + y], want = (r | ((r >> 1) & ~(r << 1))) & 0xffu;
      if (pix8Row(bootMsx, pix8Cell((unsigned char)c), y) != want || (want & r) != r) srcBad++; } }
  CHECK(mism == 0 && srcBad == 0, "F2 атлас = строки шрифта (несовпавших пикселей %d); без ручной правки — msx, утолщённый без слипания (строк иначе %d)", mism, srcBad);
  const unsigned char btn[] = {0xa3, 0xae, 0xbf, 0xb5, 0xa7, 0xa9, '@'}; int nob = 0;
  for (unsigned i = 0; i < sizeof btn; i++) { int k = pix8Cell(btn[i]), px = 0;
    for (int y = 0; k >= 0 && y < 8; y++) for (int x = 0; x < 8; x++) px += pix8Texel(tex, (k & 15) * 8 + x, (k >> 4) * 8 + y) != 0;
    if (k < 95 || !px) nob++; }
  CHECK(nob == 0, "F3 знаки кнопок £®¿µ§©@ -> X ○ □ △ (без знака %d)", nob);
  CHECK(PIX8_LH == 10 && PIX8_NCELL <= (PIX8_TW / 8) * (PIX8_TH / 8), "F4 строка 10, %d ячеек в атласе %d×%d", PIX8_NCELL, PIX8_TW, PIX8_TH);
  // F5 уточнение Роба 01.10: «худой, межбуквенный громадный» — жирный: ни одного штриха шириной 1 px у букв и цифр; шаг = ширина + 1
  int thin = 0, wide = 0;
  for (int c = 33; c <= 126; c++) { if (c == '@') continue; int k = pix8Cell((unsigned char)c), l, w; pix8Ink(bootMsx, k, &l, &w);
    int caps = ((c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9')) && c != 'M' && c != 'W';   // штрих 2 px у заглавных и цифр; M, W — пик 1 px в середине (рисунок 7 px)
    for (int y = 0; y < 8; y++) { int run = 0; for (int x = 0; x <= 8; x++) { int on = x < 8 && pix8Texel(tex, (k & 15) * 8 + x, (k >> 4) * 8 + y);
        if (on) run++; else { if (run == 1 && caps) thin++; run = 0; } } }
    if (pix8Adv(bootMsx, k) != w + 1) wide++; }
  CHECK(thin == 0 && wide == 0, "F5 жирный компактный: штрихов 1 px у заглавных и цифр %d, шаг не «ширина + 1» у %d знаков", thin, wide);
  // F6 нет слипания: у заглавных и цифр в каждой строке между штрихами просвет (никакая строка не сплошная шире 6 px, кроме M/W/& рисунка)
  int blob = 0; const char *blobs = "MW&";
  for (int c = 'A'; c <= 'Z'; c++) if (!strchr(blobs, c)) { int k = pix8Cell((unsigned char)c);
    for (int y = 0; y < 8; y++) if ((pix8Row(bootMsx, k, y) & 0xfeu) == 0xfeu) blob++; }
  CHECK(blob == 0, "F6 заглавные без слипшейся строки шириной 7 (строк %d)", blob);

  // ---- раскладка пузыря из пакета
  const char *pak = argc > 1 ? argv[1] : "build/ui.shr";
  FILE *fp = fopen(pak, "rb"); if (!fp) { printf("FAIL нет %s\n", pak); return 1; }
  fseek(fp, 0, SEEK_END); long sz = ftell(fp); fseek(fp, 0, SEEK_SET);
  unsigned char *b = malloc((size_t)sz); if (fread(b, 1, (size_t)sz, fp) != (size_t)sz) return 1; fclose(fp);
  unsigned ni, oi; memcpy(&ni, b + 16, 4); memcpy(&oi, b + 20, 4);
  Item *it = (Item *)(b + oi), *tx = 0, *bub = 0;
  for (unsigned i = 0; i < ni; i++) if (it[i].screen == UI_SCREEN_HUD && it[i].type == T_TEXT && it[i].field == UI_F_OBJECTIVE) { tx = &it[i]; break; }
  if (!tx) { printf("FAIL текст задания HUD не найден\n"); return 1; }
  float field = 0.f; int bubble = 0;
  for (unsigned i = 0; i < ni; i++) {   // как objTextStart: пузырь, в котором начинается текст; поле — край + отступ от верха
    Item *q = &it[i];
    if (q->screen != UI_SCREEN_HUD || q->type != T_IMG || q->tag != tx->tag || q->w * 2 < tx->w) continue;
    if (tx->x < q->x || tx->y < q->y || tx->x >= q->x + q->w || tx->y >= q->y + q->h) continue;
    float lo = q->x + (tx->y - q->y); if (!bubble || lo > field) { field = lo; bub = q; } bubble = 1;
  }
  if (!bub) { printf("FAIL пузырь задания не найден\n"); return 1; }
  int inset = tx->y - bub->y;
  printf("пакет: пузырь [%d,%d,%d,%d] текст [%d,%d,%d,%d] отступ %d\n", bub->x, bub->y, bub->w, bub->h, tx->x, tx->y, tx->w, tx->h, inset);
  float x0 = uiObjStart(UI_OBJ_NOICON, 0.f, bubble, field);
  int start = x0 >= 0.f && x0 < tx->x ? (int)x0 : tx->x;   // как ui.c: сдвиг только влево
  // Правки 211/228 после 126: точно +6 px от исходного поля; константу берём независимо от UI_OBJ_PAD.
  CHECK(start == bub->x + inset + 6, "L1 без значка: левый край текста %d = край пузыря %d + поле %d + 6 px (211/228; было %d)", start, bub->x, inset, tx->x);
  float xa = uiObjStart(UI_OBJ_AVATAR, 30.f, bubble, field), xb = uiObjStart(UI_OBJ_AVATAR, 120.f, bubble, field);
  CHECK(xa == field && xb == 120.f, "L2 аватар: за его краем, не левее поля (30 -> %.0f, 120 -> %.0f)", xa, xb);
  // ширина и строки — как fitW: до правого поля пузыря, строк — до нижнего поля
  int w = bub->x + bub->w - inset - start, tw = tx->w + (tx->x - start); if (tw < w) w = tw;
  int maxLines = (bub->y + bub->h - inset - tx->y) / PIX8_LH;
  const char *msgs[] = {
    "VEHICLE DESTROYED!\nFIND A WRENCH,\nOR GO TO A PHONEBOOTH,\nTO REPAIR YOUR VEHICLE.",   // main.c uiMessage
    "GO TO THE KWIK-E-MART", "GET TO THE POWER PLANT BEFORE SMITHERS\\AND DESTROY THE EVIDENCE",
    "FOLLOW THE TRUCK TO FIND OUT WHERE IT IS TAKING THE STOLEN GOODS, BUT DON'T GET TOO CLOSE",
  };
  for (unsigned m = 0; m < sizeof msgs / sizeof *msgs; m++) {
    int st0[8], len[8], nl = uiWrap(msgs[m], w, 1, pixW, 0, st0, len, 8), over = 0, brk = 0;
    for (int l = 0; l < nl; l++) {
      if (pixW(0, msgs[m] + st0[l], len[l]) > w) over++;   // ширина строки — как рисует ui.c (жирный: по буквам)
      for (int i = 0; i < len[l]; i++) if (uiIsBreak(msgs[m][st0[l] + i])) brk++;
    }
    int hard = 0; for (const char *p = msgs[m]; *p; p++) hard += uiIsBreak(*p);
    CHECK(!over && !brk && nl <= maxLines && nl >= hard + 1, "L3 «%.24s…»: %d строк из %d, шире %d px: %d, знаков переноса в строках: %d",
          msgs[m], nl, maxLines, w, over, brk);
    if (m == 0) for (int l = 0; l < nl; l++) printf("       |%.*s|\n", len[l], msgs[m] + st0[l]);
  }
  printf("RESULT %d/%d\n", oks, oks + fails);
  return fails ? 1 : 0;
}
