// Загрузочный экран «как настоящее железо» (пункт Л, Роб 28.09: «всё мелкое, пиксельные размеры шрифтов, без позы»):
// системный пиксельный шрифт PSPSDK 8×8 (правка 125: 60 колонок × 34 строки на 480×272), знак GONE Makers 1:1 в правом верхнем
// углу (viewer/bootanim.h), строки проверки железа и загрузки файлов слева, тонкая шкала внизу. Чистый C без PSP: общий для viewer/bootscreen.h и превью на Маке (tools/bootscreen_preview.c).
#ifndef BOOTUI_H
#define BOOTUI_H
#include <stdio.h>
#include "bootanim.h"

#define BUI_W 480
#define BUI_H 272
#ifndef BUI_CW
#define BUI_CW 8          // правка Роба 125 (01.10): клетка шрифта PSPSDK msx 8×8, сетка 60×34 на 480×272 (было 6, SF Mono)
#endif
#define BUI_CH 12         // правка Роба 148/149 (01.10): шрифт PSPLink 8×8, строка 12 px — воздух, как текстовый режим старых загрузочных экранов
#define BUI_X0 8          // левое поле
#define BUI_Y0 8          // верхнее поле
#define BUI_BG 0xFF000000u
#define BUI_DIM 0xFF505050u   // линии, рамки (правка 101: системная гамма — только серые)
#define BUI_KEY 0xFF9A9A9Au   // ключи
#define BUI_VAL 0xFFE0E0E0u   // значения
#define BUI_HI 0xFFFFFFFFu    // заголовок
#define BUI_ACC 0xFFFFFFFFu   // «OK» белым (правка 101: без оранжевого акцента, как системный экран)
#define BUI_ERR 0xFF5050E0u
// знак в правом верхнем углу, как знак на экране старого BIOS; место знака 232×80 (116×40 ×2, bootanim.h) стоит на
// сетке колонок текста (правка 125: x = BUI_X0 + 29·8 = 240, ровно 29×10 клеток) и прижато к правому полю (8 = левому)
#ifndef BUI_LOGO_LEFT   // правка Роба 203 (03.10): «GONE Makers справа, под ним все остальные логотипы, слева — текст системы»
#define BUI_LOGO_X (BUI_X0 + (BUI_W - 2 * BUI_X0 - BOOTANIM_PW * BOOTANIM_SCALE) / BUI_CW * BUI_CW)
#else                   // правка 169 (01.10): знак слева вверху, заголовок справа (отрицательный контроль tests/bootlogo)
#define BUI_LOGO_X BUI_X0
#endif
#define BUI_TEXT_R (BUI_LOGO_X - BUI_CW)   // правый край колонки текста слева (зазор до знака и логотипов — клетка)
#define BUI_LOGO_Y BUI_Y0

typedef void (*BuiPut)(void *u, int x, int y, unsigned abgr);
// правка Роба 125 (01.10): шрифт — встроенный шрифт PSPSDK `msx`, как у pspDebugScreen в gebench на PSPLink: клетка 8×8,
// 1 бит без сглаживания (пиксель либо цвет текста, либо фон), строка = байт, старший бит — левый пиксель. На PSP массив
// берётся прямо из libpspdebug.a (он уже слинкован для pspDebugScreenInit — ноль лишних байт), на Маке — копия
// viewer/bootmsx.h (tools/bootfont.py --msx, сверка --check). Лицензия PSPSDK BSD 3-clause: копирайт в шапке bootmsx.h.
// Прежний SF Mono 6×12 со сглаживанием — viewer/archive/bootfont.h (не подключается).
#ifdef __psp__
extern unsigned char msx[];
#define BUI_FONT msx
#else
#include "bootmsx.h"
#define BUI_FONT bootMsx
#endif
// Правка Роба 203 (03.10: «межбуквенный очень большой везде»): тот же шрифт msx 8×8 1 бит, но шаг знака — по его чернилам:
// от левого до правого закрашенного столбца + BUI_GAP px просвета; пробел BUI_SP px. Было: клетка 8 px на любой знак (у msx
// чернила знака 5 px — 3 px пустоты). BUI_MONO=1 — прежняя клетка 8 (отрицательный контроль tests/bootlogo)
#ifndef BUI_GAP
#define BUI_GAP 1
#endif
#define BUI_SP 3
static unsigned char buiSpan[256][2]; static int buiSpanOk;   // [0] левый столбец чернил, [1] ширина (0 — пустой знак)
static void buiSpans(void) {
  for (int ch = 0; ch < 256; ch++) {
    const unsigned char *g = BUI_FONT + 8 * ch; unsigned m = 0;
    for (int r = 0; r < 8; r++) m |= g[r];
    int l = 0, rr = 7; while (l < 8 && !(m >> (7 - l) & 1)) l++; while (rr >= 0 && !(m >> (7 - rr) & 1)) rr--;
    buiSpan[ch][0] = (unsigned char)(l < 8 ? l : 0); buiSpan[ch][1] = (unsigned char)(l < 8 ? rr - l + 1 : 0);
  }
  buiSpanOk = 1;
}
static int buiAdv(unsigned char ch) {
#if defined(BUI_MONO) && BUI_MONO
  (void)ch; return BUI_CW;
#else
  if (!buiSpanOk) buiSpans();
  return buiSpan[ch][1] ? buiSpan[ch][1] + BUI_GAP : BUI_SP;
#endif
}
static int buiTextW(const char *s) { int w = 0; for (; *s; s++) w += buiAdv((unsigned char)*s); return w > 0 ? w - BUI_GAP : 0; }
// строка текста с пикселя (x, y): каждый пиксель шага — фон или цвет текста; вернуть x за последним знаком
static int buiTextX(BuiPut put, void *u, int x, int y, unsigned abgr, const char *s) {
  if (!buiSpanOk) buiSpans();
  for (; *s; s++) {
    unsigned char ch = (unsigned char)*s; const unsigned char *g = BUI_FONT + 8 * ch;
#if defined(BUI_MONO) && BUI_MONO
    int l = 0;
#else
    int l = buiSpan[ch][1] ? buiSpan[ch][0] : 0;
#endif
    int a = buiAdv(ch);
    for (int r = 0; r < 8; r++) for (int c = 0; c < a; c++) { int bc = l + c; put(u, x + c, y + r, bc < 8 && (g[r] >> (7 - bc)) & 1 ? abgr : BUI_BG); }
    x += a;
  }
  return x;
}
static void buiClear(BuiPut put, void *u, int x0, int x1, int y) {   // полоса строки (8 px) — фоном: строка перерисовывается короче
  for (int r = 0; r < 8; r++) for (int x = x0; x < x1; x++) put(u, x, y + r, BUI_BG);
}
static void buiText(BuiPut put, void *u, int col, int row, unsigned abgr, const char *s) {   // столбец/строка сетки BUI_CW×BUI_CH
  buiTextX(put, u, BUI_X0 + col * BUI_CW, BUI_Y0 + row * BUI_CH, abgr, s);
}
static void buiRule(BuiPut put, void *u, int row, int cols) {   // тонкая линия по середине строки
  int y = BUI_Y0 + row * BUI_CH + BUI_CH / 2; for (int x = BUI_X0; x < BUI_X0 + cols * BUI_CW - 1; x++) put(u, x, y, BUI_DIM);
}
// шкала загрузки: 1 px, заполненная часть светлее
__attribute__((unused)) static void buiBar(BuiPut put, void *u, int done, int total) {   // в путь игрока не выводится (Роб 28.09)
  int x0 = BUI_X0, x1 = BUI_W - BUI_X0, y = BUI_H - BUI_Y0 - BUI_CH - 6, fill = x0 + (x1 - x0) * done / (total > 0 ? total : 1);
  for (int x = x0; x < x1; x++) put(u, x, y, x < fill ? BUI_VAL : BUI_DIM);
}
// колонки строк проверки: ключ, значение, размер, статус
#define BUI_HEAD_RULE ((BUI_LOGO_X - 2 * BUI_X0) / BUI_CW)
#define BUI_C_KEY 0
#define BUI_C_VAL 8
#define BUI_C_SIZE 26
#define BUI_C_STAT 36
#define BUI_ROW_FOOT ((BUI_H - 2 * BUI_Y0) / BUI_CH - 1)
#define BUI_ROW_HEAD 0   // правка 101: заголовок снова наверху слева (знак ×2 справа не мешает)
static void buiHeader(BuiPut put, void *u) {
  buiText(put, u, 0, BUI_ROW_HEAD, BUI_HI, "GONE MAKERS CO. SYSTEM BOOT");
  // строка «SHAR-PSP BUILD V0.1  OWN DISC DATA» убрана (Роб 28.09: служебный текст на экране не нужен)
  buiRule(put, u, BUI_ROW_HEAD + 1, BUI_HEAD_RULE);   // линия под заголовком — до знака
}
__attribute__((unused)) static void buiFooter(BuiPut put, void *u) {   // в путь игрока не выводится (Роб 28.09), превью на Маке
  buiText(put, u, 0, BUI_ROW_FOOT, BUI_DIM, "SHAR-PSP // UNOFFICIAL // OWN DISC DATA");
  buiText(put, u, (BUI_W - 2 * BUI_X0) / BUI_CW - 10, BUI_ROW_FOOT, BUI_KEY, "START SKIP");
}
static void buiCheck(BuiPut put, void *u, int row, const char *key, const char *val, const char *size, const char *stat, unsigned sc) {
  buiText(put, u, BUI_C_KEY, row, BUI_KEY, key); if (val) buiText(put, u, BUI_C_VAL, row, BUI_VAL, val);
  if (size) buiText(put, u, BUI_C_SIZE, row, BUI_VAL, size); if (stat) buiText(put, u, BUI_C_STAT, row, sc, stat);
}
#endif
