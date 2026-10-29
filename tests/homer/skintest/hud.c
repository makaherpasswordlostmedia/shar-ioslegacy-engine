// SNAPSHOT of viewer/hud.c (26.09) for the standalone Homer test; the engine copy is the one to edit.
// HUD text overlay drawn by the GE (see hud.h for API and the exact GU state it changes).
#pragma GCC optimize("O2")   // keep the per-frame loop optimized even in an -O0 build
#include <stdint.h>
#include <string.h>
#include <pspkernel.h>
#include <psputils.h>
#include <pspgu.h>
#include "hud.h"

extern unsigned char msx[];   // libpspdebug 8x8 font: 256 glyphs x 8 rows, bit 7 = leftmost pixel

#ifndef HUD_STRIP_ABGR
#define HUD_STRIP_ABGR 0x90000000u   // translucent black behind each block of used rows
#endif
#ifndef HUD_SHADOW
#define HUD_SHADOW 1                 // 1 px black shadow baked into the font (CLUT entry 2)
#endif
#ifndef HUD_UNCACHED_VERTS
#define HUD_UNCACHED_VERTS 0         // 1 = write vertices straight to the (uncached) list
#endif

#define FONT_W 128                   // 16 x 16 glyph cells of 8x8
#define FONT_H 128
#define HUD_VT (GU_TEXTURE_16BIT | GU_COLOR_8888 | GU_VERTEX_16BIT | GU_TRANSFORM_2D)

// vertex = 16 bytes = 4 words: [u | v<<16] [abgr] [x | y<<16] [z=0 | pad=0]
static unsigned char __attribute__((aligned(16))) fontTex[FONT_W * FONT_H / 2];   // T4, swizzled
static unsigned int __attribute__((aligned(64))) fontClut[16];
static unsigned char blank[256];                  // glyph has no pixels -> not drawn
static unsigned char text[HUD_ROWS][HUD_COLS];
static unsigned char rowLen[HUD_ROWS];            // cells up to and including the last visible glyph
static unsigned short rowVis[HUD_ROWS];           // visible glyphs in the row
static unsigned int rowColor[HUD_ROWS];

// swizzled T4: blocks of 16 bytes (32 texels) x 8 rows, stored block after block, row-major
static void putTexel(unsigned x, unsigned y, unsigned idx) {
  unsigned bx = x >> 1;
  unsigned off = ((y >> 3) * (FONT_W / 32) + (bx >> 4)) * 128 + (y & 7) * 16 + (bx & 15);
  if (x & 1) fontTex[off] = (unsigned char)((fontTex[off] & 0x0f) | (idx << 4));   // odd texel: high nibble
  else fontTex[off] = (unsigned char)((fontTex[off] & 0xf0) | idx);
}

void hudInit(void) {
  memset(fontTex, 0, sizeof fontTex);
  for (unsigned c = 0; c < 256; c++) {
    const unsigned char *g = msx + c * 8;
    unsigned ox = (c & 15) * 8, oy = (c >> 4) * 8, any = 0;
    for (unsigned y = 0; y < 8; y++)
      for (unsigned x = 0; x < 8; x++) {
        if (g[y] & (0x80u >> x)) { putTexel(ox + x, oy + y, 1); any = 1; }
        else if (x && y && (g[y - 1] & (0x80u >> (x - 1)))) putTexel(ox + x, oy + y, 2);
      }
    blank[c] = !any;
  }
  memset(fontClut, 0, sizeof fontClut);
  fontClut[1] = 0xffffffffu;
  fontClut[2] = HUD_SHADOW ? 0xff000000u : 0u;
  sceKernelDcacheWritebackRange(fontTex, sizeof fontTex);
  sceKernelDcacheWritebackRange(fontClut, sizeof fontClut);
  hudClear();
}

void hudClear(void) {
  memset(rowLen, 0, sizeof rowLen);
  memset(rowVis, 0, sizeof rowVis);
}

void hudLine(int row, unsigned abgr, const char *s) {
  if ((unsigned)row >= HUD_ROWS) return;
  unsigned char *d = text[row];
  unsigned n = 0, last = 0, vis = 0;
  if (s)
    for (; n < HUD_COLS; n++) {
      unsigned char c = (unsigned char)s[n];
      if (!c || c == '\n' || c == '\r') break;
      d[n] = c;
      if (!blank[c]) { vis++; last = n + 1; }
    }
  rowLen[row] = (unsigned char)last;
  rowVis[row] = (unsigned short)vis;
  rowColor[row] = abgr;
}

void hudDraw(void) {
  // strips: one per block of used rows (a single empty row between used rows is bridged),
  // as wide as the longest row of the block
  unsigned total = 0, nrun = 0;
  unsigned char rs[HUD_ROWS], re[HUD_ROWS], rw[HUD_ROWS];
  int last = -9;
  for (int r = 0; r < HUD_ROWS; r++) {
    if (!rowVis[r]) continue;
    total += rowVis[r];
    if (r - last > 2) { rs[nrun] = (unsigned char)r; rw[nrun] = 0; nrun++; }
    re[nrun - 1] = (unsigned char)r;
    if (rowLen[r] > rw[nrun - 1]) rw[nrun - 1] = rowLen[r];
    last = r;
  }
  if (!total) return;

  unsigned bytes = (total + nrun) * 32;   // strips + glyphs, 2 vertices x 16 B each
#if HUD_UNCACHED_VERTS
  unsigned *w = (unsigned *)sceGuGetMemory((int)bytes);
#else
  // list memory is handed out through its uncached alias; write through the cached alias
  // instead, on whole 64-byte cache lines that lie inside this allocation only, then write
  // them back and drop them (so no stale line can ever cover display-list commands)
  uintptr_t m = (uintptr_t)sceGuGetMemory((int)bytes + 128) & ~(uintptr_t)0x40000000;
  unsigned *w = (unsigned *)((m + 63) & ~(uintptr_t)63);
#endif
  unsigned *v = w;

  for (unsigned k = 0; k < nrun; k++, w += 8) {
    unsigned sx = rw[k] * 8u; if (sx > 480) sx = 480;
    w[0] = 0; w[1] = HUD_STRIP_ABGR; w[2] = (unsigned)rs[k] << 19;                  w[3] = 0;
    w[4] = 0; w[5] = HUD_STRIP_ABGR; w[6] = sx | (unsigned)(re[k] + 1) << 19;        w[7] = 0;
  }
  for (int r = rs[0]; r <= re[nrun - 1]; r++) {
    if (!rowVis[r]) continue;
    const unsigned char *t = text[r];
    unsigned col = rowColor[r], xy = (unsigned)(r * 8) << 16, n = rowLen[r];
    for (unsigned i = 0; i < n; i++, xy += 8) {
      unsigned ch = t[i];
      if (blank[ch]) continue;
      unsigned uv = ((ch & 15) << 3) | ((ch >> 4) << 19);    // u = 8*(ch%16), v = 8*(ch/16)
      w[0] = uv;           w[1] = col; w[2] = xy;           w[3] = 0;
      w[4] = uv + 0x80008; w[5] = col; w[6] = xy + 0x80008; w[7] = 0;   // +8,+8
      w += 8;
    }
  }
#if !HUD_UNCACHED_VERTS
  sceKernelDcacheWritebackInvalidateRange(v, (bytes + 63) & ~63u);
#endif

  sceGuDisable(GU_DEPTH_TEST);
  sceGuDepthMask(GU_TRUE);
  sceGuDisable(GU_FOG);
  sceGuDisable(GU_ALPHA_TEST);
  sceGuEnable(GU_BLEND);
  sceGuBlendFunc(GU_ADD, GU_SRC_ALPHA, GU_ONE_MINUS_SRC_ALPHA, 0, 0);
  sceGuDisable(GU_TEXTURE_2D);
  sceGuDrawArray(GU_SPRITES, HUD_VT, (int)nrun * 2, 0, v);

  sceGuEnable(GU_TEXTURE_2D);
  sceGuClutMode(GU_PSM_8888, 0, 0x0f, 0);
  sceGuClutLoad(2, fontClut);                     // 16 entries = 2 blocks of 8
  sceGuTexMode(GU_PSM_T4, 0, 0, 1);
  sceGuTexImage(0, FONT_W, FONT_H, FONT_W, fontTex);
  sceGuTexFunc(GU_TFX_MODULATE, GU_TCC_RGBA);
  sceGuTexFilter(GU_NEAREST, GU_NEAREST);
  sceGuDrawArray(GU_SPRITES, HUD_VT, (int)total * 2, 0, v + nrun * 8);
}
