// HUD: 8x8 text overlay drawn by the GE inside the frame's display list.
//
// Replaces per-frame pspDebugScreenPrintf (CPU writes into VRAM after sceGuSync).
// Text is a 60x34 grid of 8x8 cells covering the 480x272 screen; row r is at y = 8*r.
//
// Usage (once):  sceGuInit ... sceGuDisplay(GU_TRUE); hudInit();
// Per frame:     hudClear(); hudLine(0, 0xffffffff, buf); ...
//                sceGuStart(...); <scene> ; hudDraw(); <re-establish GU state> ; sceGuFinish();
// Text persists between frames until changed, so rows that never change can be set once.
// Not thread-safe: call every hud* function from the thread that builds the display list
// (hudDraw sizes its vertex block from the row counters, then walks the text again).
//
// Link: needs libpspdebug (uses its built-in 'msx' 8x8 font), libpspgu, libpspkernel.
//
// Font texture: 128x128 GU_PSM_T4, swizzled, 8 KB (fits the GE texture cache), 16-entry
// 8888 CLUT: 0 = transparent, 1 = white (glyph), 2 = black (1 px drop shadow, bottom-right).
// Glyph colour = vertex colour (GU_TFX_MODULATE with a white texel).
//
// ---------------------------------------------------------------------------------------
// GU STATE LEFT CHANGED BY hudDraw()  (only if at least one visible glyph exists; with no
// text it emits nothing and changes nothing):
//   GU_TEXTURE_2D      ENABLED
//   texture mode       sceGuTexMode(GU_PSM_T4, 0, 0, 1)  (swizzled, no mipmaps)
//   texture level 0    sceGuTexImage(0, 128, 128, 128, <hud font>)   (levels 1..7 untouched)
//   CLUT               sceGuClutMode(GU_PSM_8888, 0, 0x0f, 0) + sceGuClutLoad(2, <hud clut>)
//                      -> before the next CLUT8 draw the caller MUST re-send BOTH its CLUT
//                         mode (index mask 0xff, else T8 indices are masked to 4 bits) and
//                         its CLUT. main.c: resetState() (bound = -2) makes bindTexLean
//                         reload the CLUT, but bindTexLean does NOT send sceGuClutMode; that
//                         is only re-sent at frame start, so hudDraw must stay the last draw
//                         of the frame, or sceGuClutMode(GU_PSM_8888, 0, 0xff, 0) must be
//                         re-sent after it (bindTexLegacy sends both).
//   texture filter     sceGuTexFilter(GU_NEAREST, GU_NEAREST)
//   texture function   sceGuTexFunc(GU_TFX_MODULATE, GU_TCC_RGBA)   (same values as main.c)
//   GU_BLEND           ENABLED
//   blend function     sceGuBlendFunc(GU_ADD, GU_SRC_ALPHA, GU_ONE_MINUS_SRC_ALPHA, 0, 0)
//                      (same values as main.c)
//   GU_ALPHA_TEST      DISABLED   (sceGuAlphaFunc is NOT touched)
//   GU_DEPTH_TEST      DISABLED   (sceGuDepthFunc is NOT touched)
//   depth write        sceGuDepthMask(GU_TRUE)  = writes OFF
//   GU_FOG             DISABLED   (sceGuFog params NOT touched)
//   vertex type        TRANSFORM_2D sprite format (every sceGuDrawArray/sceGumDrawArray with a
//                      non-zero vtype re-sends it, so nothing to do)
// NOT touched: tex wrap, tex scale/offset (ignored in 2D/through mode), tex level mode,
//   shade model, alpha func, depth func/range, cull, clip planes, scissor, viewport/offset,
//   matrices (GUM), material/ambient colour, clear colour/depth, stencil, logic op, dither.
// ---------------------------------------------------------------------------------------
//
// Cost: text is kept in a static grid; hudDraw writes 2 sprite vertices (32 B) per visible
// glyph into sceGuGetMemory space (spaces cost nothing), then issues 2 GU_SPRITES draws:
// the translucent dark strips (one sprite per block of used rows, as wide as its longest row;
// a single empty row between used rows is bridged), then all glyphs in one draw.
// No heap allocation. Vertices are written through the cached alias of the list memory
// (64-byte aligned, then sceKernelDcacheWritebackInvalidateRange) instead of 8 uncached
// stores per glyph; build with -DHUD_UNCACHED_VERTS=1 to use plain uncached writes.
#ifndef HUD_H
#define HUD_H

#define HUD_ROWS 34
#define HUD_COLS 60

#ifdef __cplusplus
extern "C" {
#endif

// Build the font texture + CLUT in RAM (dcache written back) and clear all text.
// Call once, after sceGuInit/sceGuDisplay, before any other hud* call. Emits no GU commands.
void hudInit(void);

// Clear all rows.
void hudClear(void);

// Set the text of one row (0..HUD_ROWS-1; other rows are ignored). Copies up to HUD_COLS
// chars, stopping at NUL, '\n' or '\r'. All 256 msx glyphs are drawable (bytes are glyph
// indices; ASCII 32..126 is standard). abgr = 0xAABBGGRR vertex colour for the whole row
// (alpha < 0xff gives translucent text). text == NULL or "" clears the row.
void hudLine(int row, unsigned abgr, const char *text);

// Append the HUD to the CURRENTLY OPEN GU list (sceGuStart already called).
// Changes GU state as listed above; the caller re-establishes what it needs afterwards.
void hudDraw(void);

// Оверлей тест-апки для видео с телефона (TEST16E): три строки крупно в левом верхнем углу на тёмной подложке (шрифт HUD, масштаб scaleN кратно 8 px),
// плюс белый квадрат-метка 40x40 в правом верхнем углу при flash != 0. Дорисовывается в открытый список GE; состояние GE меняет — после вызова resetState().
void hudOverlay(const char *l0, int scale0, const char *l1, const char *l2, int scale12, int flash);

// TEST18: тонкий оверлей видео-теста — одна строка 8 px по нижнему краю (центр в x = centerX, ширина по тексту, не шире maxW), полупрозрачная подложка;
// метка сцены — белый квадрат 12×12 px в нижнем левом углу (flash != 0). Верх экрана и радар справа внизу не заслоняются.
void hudOverlayLine(const char *line, int centerX, int maxW, int flash);

#ifdef __cplusplus
}
#endif

#endif
