/* ge_list.c - libpspgu / libpspgum replacement: writes real GE command words into the
 * caller's list buffer, executes finished direct lists through ge_gles2.c. */
#include "psp_compat.h"
#undef sceGuSetMatrix    /* geguard.h (-include) renames these to geSetMatrixSafe/geBoneMatrixSafe; here are the real ones */
#undef sceGuBoneMatrix
void ge_exec(const uint32_t *list);
void ge_frame_end(void);
void ge_invalidate_range(const void *p, unsigned n);

typedef struct { uint32_t *start, *cur; int mode; } Ctx;
static Ctx stk[8]; static int sp = -1;
static uint32_t *cur, *start; static int mode;
static int status[32]; static int scissorOn = 1;
static int scx, scy, scw = 480, sch = 272;
static unsigned clearCol, clearDepth; static int drawFmt;

static inline void E(int c, unsigned a) { if (cur) *cur++ = ((unsigned)c << 24) | (a & 0xffffff); }
static inline void EF(int c, float f) { union { float f; unsigned u; } x; x.f = f; E(c, x.u >> 8); }
static void EP(int slot, const void *p) { unsigned u = (unsigned)(uintptr_t)p; E(GE_PTRLO, (slot << 16) | (u & 0xffff)); E(GE_PTRHI, (slot << 16) | (u >> 16)); }

void sceGuInit(void) { sp = -1; cur = start = 0; memset(status, 0, sizeof status); scissorOn = 1; }
void sceGuTerm(void) {}
void sceGuStart(int cid, void *list) {
  if (cur && sp < 7) { sp++; stk[sp].start = start; stk[sp].cur = cur; stk[sp].mode = mode; }
  start = cur = (uint32_t *)list; mode = cid;
}
int sceGuFinish(void) {
  if (mode == GU_CALL) E(0x0b, 0); else { E(0x0f, 0); E(0x0c, 0); }
  int wasDirect = mode == GU_DIRECT; uint32_t *s = start;
  if (sp >= 0) { start = stk[sp].start; cur = stk[sp].cur; mode = stk[sp].mode; sp--; } else { cur = 0; }
  if (wasDirect && !cur) ge_exec(s);
  else if (wasDirect) ge_exec(s);   /* direct list nested in another: run now */
  return 0;
}
int sceGuFinishId(unsigned id) { (void)id; return sceGuFinish(); }
int sceGuSync(int m, int w) { (void)m; (void)w; return 0; }
void *sceGuSwapBuffers(void) { ge_frame_end(); ios_present(); return 0; }
void sceGuDisplay(int s) { (void)s; }
int sceGuCheckList(void) { return cur ? (int)((cur - start) * 4) : 0; }
void *sceGuGetMemory(int size) {
  size = (size + 3) & ~3; unsigned w = (unsigned)size / 4;
  E(0xf2, w); void *r = cur; cur += w; return r;
}
void sceGuCallList(const void *l) { EP(GE_SLOT_CALL, l); E(0x0a, 0); }
void sceGuSendCommandi(int c, int a) { E(c, (unsigned)a); }
void sceGuSendCommandf(int c, float a) { EF(c, a); }
void sceGuDrawBuffer(int psm, void *fbp, int fbw) { (void)fbp; (void)fbw; drawFmt = psm; }
void sceGuDispBuffer(int w, int h, void *dp, int dw) { (void)w; (void)h; (void)dp; (void)dw; }
void sceGuDepthBuffer(void *z, int w) { (void)z; (void)w; }
void sceGuOffset(unsigned x, unsigned y) { E(0x4c, x << 4); E(0x4d, y << 4); }
void sceGuViewport(int cx, int cy, int w, int h) {
  EF(0x42, w / 2.f); EF(0x43, -h / 2.f); EF(0x45, (float)cx); EF(0x46, (float)cy);
}
static int dn = 65535, df = 0;
void sceGuDepthRange(int n, int f) { dn = n; df = f; EF(0x44, (n - f) / 2.f); EF(0x47, (n + f) / 2.f); E(0xd6, f); E(0xd7, n); }
void sceGuScissor(int x, int y, int w, int h) { scx = x; scy = y; scw = w; sch = h; if (scissorOn) { E(0xd4, (y << 10) | x); E(0xd5, ((y + h - 1) << 10) | (x + w - 1)); } }
static const unsigned enOp[] = { 0x22, 0x23, 0, 0x24, 0x21, 0x1d, 0x20, 0x1f, 0x1c, 0x1e, 0x17, 0x18, 0x19, 0x1a, 0x1b, 0x25, 0, 0x26, 0x27, 0, 0, 0 };
void sceGuEnable(int s) { if (s < 0 || s > 21) return; status[s] = 1;
  if (s == GU_SCISSOR_TEST) { scissorOn = 1; E(0xd4, (scy << 10) | scx); E(0xd5, ((scy + sch - 1) << 10) | (scx + scw - 1)); } else if (enOp[s]) E(enOp[s], 1); }
void sceGuDisable(int s) { if (s < 0 || s > 21) return; status[s] = 0;
  if (s == GU_SCISSOR_TEST) { scissorOn = 0; E(0xd4, 0); E(0xd5, (271 << 10) | 479); } else if (enOp[s]) E(enOp[s], 0); }
int sceGuGetStatus(int s) { return (s >= 0 && s < 22) ? status[s] : 0; }
int sceGuSetStatus(int s, int st) { if (st) sceGuEnable(s); else sceGuDisable(s); return 0; }
void sceGuSetAllStatus(int s) { (void)s; } int sceGuGetAllStatus(void) { return 0; }
void sceGuDepthFunc(int f) { E(0xde, (unsigned)f); }
void sceGuDepthMask(int m) { E(0xe7, m ? 1 : 0); }
void sceGuDepthOffset(unsigned o) { (void)o; }
void sceGuAlphaFunc(int f, int v, int m) { E(0xdb, (unsigned)f | ((unsigned)v << 8) | ((unsigned)m << 16)); }
static unsigned fixS, fixD;
void sceGuBlendFunc(int op, int src, int dst, unsigned sf, unsigned df_) { E(0xdf, (unsigned)src | ((unsigned)dst << 4) | ((unsigned)op << 8)); E(0xe0, sf & 0xffffff); E(0xe1, df_ & 0xffffff); fixS = sf; fixD = df_; }
void sceGuFrontFace(int o) { E(0x9b, o == GU_CCW ? 0 : 1); }
void sceGuShadeModel(int m) { E(0x50, (unsigned)m); }
void sceGuFog(float n, float f, unsigned c) { float d = f - n; EF(0xcd, f); EF(0xce, d != 0.f ? 1.f / d : 0.f); E(0xcf, c & 0xffffff); }
void sceGuClearColor(unsigned c) { clearCol = c; E(0xf4, c & 0xffffff); E(0xf5, c >> 24); }
void sceGuClearDepth(unsigned d) { clearDepth = d; E(0xf6, d); }
void sceGuClear(int f) { E(0xf3, (unsigned)f); }
void sceGuColor(unsigned c) { E(0x55, c & 0xffffff); E(0x58, c >> 24); E(0x54, c & 0xffffff); E(0x56, c & 0xffffff); }
void sceGuAmbient(unsigned c) { E(0x55, c & 0xffffff); E(0x58, c >> 24); }
void sceGuAmbientColor(unsigned c) { sceGuAmbient(c); }
void sceGuColorMaterial(int c) { E(0x53, (unsigned)c << 1); }
void sceGuMaterial(int m, int c) { if (m & 1) { E(0x55, c & 0xffffff); E(0x58, (unsigned)c >> 24); } }
void sceGuModelColor(unsigned e, unsigned a, unsigned d, unsigned s) { (void)e; (void)d; (void)s; sceGuAmbient(a); }
void sceGuLight(int l, int t, int c, const ScePspFVector3 *p) { (void)l; (void)t; (void)c; (void)p; }
void sceGuLightColor(int l, int c, unsigned col) { (void)l; (void)c; (void)col; }
void sceGuLightAtt(int l, float a, float b, float c) { (void)l; (void)a; (void)b; (void)c; }
void sceGuLightSpot(int l, const ScePspFVector3 *d, float e, float c) { (void)l; (void)d; (void)e; (void)c; }
void sceGuSpecular(float p) { (void)p; }
void sceGuSetDither(const ScePspIMatrix4 *m) { (void)m; }
void sceGuSetMatrix(int type, const ScePspFMatrix4 *m) {
  const float *f = (const float *)m; int base = type == GU_PROJECTION ? 0x3e : type == GU_VIEW ? 0x3c : type == GU_MODEL ? 0x3a : 0x40;
  E(base, 0);
  if (type == GU_PROJECTION) { for (int i = 0; i < 16; i++) EF(base + 1, f[i]); }
  else { for (int r = 0; r < 4; r++) for (int c = 0; c < 3; c++) EF(base + 1, f[r * 4 + c]); }
}
void sceGuBoneMatrix(unsigned index, const ScePspFMatrix4 *m) {
  const float *f = (const float *)m; E(0x2a, index * 12);
  for (int r = 0; r < 4; r++) for (int c = 0; c < 3; c++) EF(0x2b, f[r * 4 + c]);
}
void sceGuTexMode(int t, int mm, int a2, int sw) { (void)a2; E(0xc2, ((unsigned)mm << 16) | (unsigned)sw); E(0xc3, (unsigned)t); }
void sceGuTexImage(int l, int w, int h, int tbw, const void *p) {
  int lw = 0, lh = 0; while ((1 << lw) < w) lw++; while ((1 << lh) < h) lh++;
  geTexAddr(l, p, tbw); E(0xb8 + l, (unsigned)(lh << 8) | (unsigned)lw);
}
void geTexAddr(int l, const void *p, int tbw) { EP(GE_SLOT_TEX0 + l, p); E(0xa8 + l, (unsigned)tbw); }
void geClutAddr(const void *p) { EP(GE_SLOT_CLUT, p); }
void sceGuTexFunc(int f, int c) { E(0xc9, (unsigned)f | ((unsigned)c << 8)); }
void sceGuTexEnvColor(unsigned c) { E(0xca, c & 0xffffff); }
void sceGuTexFilter(int mn, int mg) { E(0xc6, (unsigned)mn | ((unsigned)mg << 8)); }
void sceGuTexWrap(int u, int v) { E(0xc7, (unsigned)u | ((unsigned)v << 8)); }
void sceGuTexScale(float u, float v) { EF(0x48, u); EF(0x49, v); }
void sceGuTexOffset(float u, float v) { EF(0x4a, u); EF(0x4b, v); }
void sceGuTexLevelMode(unsigned m, float b) { (void)m; (void)b; }
void sceGuTexSlope(float s) { (void)s; }
void sceGuTexMapMode(int m, unsigned a, unsigned b) { (void)m; (void)a; (void)b; }
void sceGuTexProjMapMode(int m) { (void)m; }
void sceGuTexFlush(void) { E(0xcb, 0); } void sceGuTexSync(void) {}
void sceGuClutMode(unsigned cpsm, unsigned sh, unsigned mask, unsigned a3) { E(0xc5, cpsm | (sh << 2) | (mask << 8) | (a3 << 16)); }
void sceGuClutLoad(unsigned n, const void *p) { EP(GE_SLOT_CLUT, p); E(0xc4, n); }
void sceGuDrawArray(int prim, int vt, int cnt, const void *idx, const void *v) {
  if (vt) E(0x12, (unsigned)vt);
  if (idx) EP(GE_SLOT_IADDR, idx);
  EP(GE_SLOT_VADDR, v); E(0x04, ((unsigned)prim << 16) | (unsigned)cnt);
}
void sceGuDrawBezier(int a, int b, int c, int d, const void *e, const void *f) { (void)a; (void)b; (void)c; (void)d; (void)e; (void)f; }
void sceGuCopyImage(int psm, int sx, int sy, int w, int h, int sw, void *s, int dx, int dy, int dw, void *d) { (void)psm; (void)sx; (void)sy; (void)w; (void)h; (void)sw; (void)s; (void)dx; (void)dy; (void)dw; (void)d; }
void sceGuStencilFunc(int f, int r, int m) { (void)f; (void)r; (void)m; } void sceGuStencilOp(int a, int b, int c) { (void)a; (void)b; (void)c; }
void sceGuPixelMask(unsigned m) { (void)m; } void sceGuLogicalOp(int o) { (void)o; } void sceGuMorphWeight(int i, float w) { (void)i; (void)w; }
void sceGuSetCallback(int s, void (*cb)(int)) { (void)s; (void)cb; } void sceGuBreak(int m) { (void)m; } void sceGuContinue(void) {}
void sceGuSignal(int b, int s) { (void)b; (void)s; }
int sceGeListUpdateStallAddr(int q, void *s) { (void)q; (void)s; return 0; }

/* ---------------- GUM: row-vector matrices, OpenGL-style call order ---------------- */
typedef struct { float m[4][4]; } M4;
static M4 gst[4][16]; static int gtop[4]; static int gmode = GU_MODEL; static int gdirty[4] = {1, 1, 1, 1}; static int ginit;
static void mid(M4 *a) { memset(a, 0, sizeof *a); for (int i = 0; i < 4; i++) a->m[i][i] = 1; }
static void mmul(M4 *r, const M4 *a, const M4 *b) { M4 t; for (int i = 0; i < 4; i++) for (int j = 0; j < 4; j++) { float s = 0; for (int k = 0; k < 4; k++) s += a->m[i][k] * b->m[k][j]; t.m[i][j] = s; } *r = t; }
static void gi(void) { if (ginit) return; ginit = 1; for (int t = 0; t < 4; t++) mid(&gst[t][0]); }
static M4 *G(void) { gi(); return &gst[gmode][gtop[gmode]]; }
void gumLoadIdentity(ScePspFMatrix4 *m) { mid((M4 *)m); }
void sceGumMatrixMode(int m) { gmode = m; } void sceGumLoadIdentity(void) { mid(G()); gdirty[gmode] = 1; }
void sceGumLoadMatrix(const ScePspFMatrix4 *m) { *G() = *(const M4 *)m; gdirty[gmode] = 1; }
void sceGumStoreMatrix(ScePspFMatrix4 *m) { *(M4 *)m = *G(); }
/* OpenGL order: current = current * T  (T acts first on the model) == row algebra T * current */
static void gapply(const M4 *t) { mmul(G(), t, G()); gdirty[gmode] = 1; }
void sceGumMultMatrix(const ScePspFMatrix4 *m) { gapply((const M4 *)m); }
void sceGumPushMatrix(void) { gi(); if (gtop[gmode] < 15) { gst[gmode][gtop[gmode] + 1] = gst[gmode][gtop[gmode]]; gtop[gmode]++; } }
void sceGumPopMatrix(void) { gi(); if (gtop[gmode] > 0) gtop[gmode]--; gdirty[gmode] = 1; }
void sceGumTranslate(const ScePspFVector3 *v) { M4 t; mid(&t); t.m[3][0] = v->x; t.m[3][1] = v->y; t.m[3][2] = v->z; gapply(&t); }
void sceGumScale(const ScePspFVector3 *v) { M4 t; mid(&t); t.m[0][0] = v->x; t.m[1][1] = v->y; t.m[2][2] = v->z; gapply(&t); }
void sceGumRotateX(float a) { M4 t; mid(&t); float c = cosf(a), s = sinf(a); t.m[1][1] = c; t.m[1][2] = s; t.m[2][1] = -s; t.m[2][2] = c; gapply(&t); }
void sceGumRotateY(float a) { M4 t; mid(&t); float c = cosf(a), s = sinf(a); t.m[0][0] = c; t.m[0][2] = -s; t.m[2][0] = s; t.m[2][2] = c; gapply(&t); }
void sceGumRotateZ(float a) { M4 t; mid(&t); float c = cosf(a), s = sinf(a); t.m[0][0] = c; t.m[0][1] = s; t.m[1][0] = -s; t.m[1][1] = c; gapply(&t); }
void sceGumPerspective(float fovy, float asp, float n, float f) {
  float h = 1.f / tanf(fovy * (GU_PI / 180.f) * 0.5f); M4 t; memset(&t, 0, sizeof t);
  t.m[0][0] = h / asp; t.m[1][1] = h; t.m[2][2] = (f + n) / (n - f); t.m[2][3] = -1.f; t.m[3][2] = 2.f * f * n / (n - f);
  mmul(G(), &t, G()); gdirty[gmode] = 1;
}
void sceGumOrtho(float l, float r, float b, float tp, float n, float f) {
  M4 t; mid(&t); t.m[0][0] = 2 / (r - l); t.m[1][1] = 2 / (tp - b); t.m[2][2] = -2 / (f - n);
  t.m[3][0] = -(r + l) / (r - l); t.m[3][1] = -(tp + b) / (tp - b); t.m[3][2] = -(f + n) / (f - n); mmul(G(), &t, G()); gdirty[gmode] = 1;
}
void sceGumLookAt(const ScePspFVector3 *e, const ScePspFVector3 *c, const ScePspFVector3 *u) {
  float fx = c->x - e->x, fy = c->y - e->y, fz = c->z - e->z, l = sqrtf(fx * fx + fy * fy + fz * fz); if (l == 0) l = 1; fx /= l; fy /= l; fz /= l;
  float sx = fy * u->z - fz * u->y, sy = fz * u->x - fx * u->z, sz = fx * u->y - fy * u->x; l = sqrtf(sx * sx + sy * sy + sz * sz); if (l == 0) l = 1; sx /= l; sy /= l; sz /= l;
  float ux = sy * fz - sz * fy, uy = sz * fx - sx * fz, uz = sx * fy - sy * fx; M4 t; mid(&t);
  t.m[0][0] = sx; t.m[1][0] = sy; t.m[2][0] = sz; t.m[0][1] = ux; t.m[1][1] = uy; t.m[2][1] = uz; t.m[0][2] = -fx; t.m[1][2] = -fy; t.m[2][2] = -fz;
  t.m[3][0] = -(sx * e->x + sy * e->y + sz * e->z); t.m[3][1] = -(ux * e->x + uy * e->y + uz * e->z); t.m[3][2] = fx * e->x + fy * e->y + fz * e->z;
  mmul(G(), &t, G()); gdirty[gmode] = 1;
}
void sceGumFullInverse(void) {} void sceGumFastInverse(void) {}
void sceGumUpdateMatrix(void) {
  gi(); for (int t = 0; t < 3; t++) if (gdirty[t]) { sceGuSetMatrix(t, (const ScePspFMatrix4 *)&gst[t][gtop[t]]); gdirty[t] = 0; }
  if (gdirty[3]) { sceGuSetMatrix(GU_TEXTURE, (const ScePspFMatrix4 *)&gst[3][gtop[3]]); gdirty[3] = 0; }
}
void sceGumDrawArray(int p, int vt, int c, const void *i, const void *v) { sceGumUpdateMatrix(); sceGuDrawArray(p, vt, c, i, v); }
