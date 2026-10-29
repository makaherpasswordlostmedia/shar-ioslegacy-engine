/* ge_gles2.c - PSP GE command interpreter on OpenGL ES 2.0 (iOS 7+, armv7).
 * Covers what the SHAR engine uses: transform/through prims, textures (T4/T8 CLUT, 5650/4444/5551/8888,
 * swizzle, mipmaps), blend, alpha test, depth, fog, scissor, clear. Lighting/stencil/morph are not emulated. */
#ifdef __APPLE__
#include <OpenGLES/ES2/gl.h>
#include <OpenGLES/ES2/glext.h>
#else
#include <GLES2/gl2.h>
#endif
#include "psp_compat.h"

#define GW 480
#define GH 272
typedef struct { float x, y, z, u, v; uint8_t c[4]; } Vtx;

static struct {
  uint32_t vtype; uintptr_t slot[24]; uint32_t prim;
  float world[16], view[16], proj[16], tgen[16]; int mn[4]; float bone[8][12]; int bn;
  float vs[3], vp[3], off[2]; float tsu, tsv, tou, tov;
  int en[40]; int blendOp, blendS, blendD; unsigned fixS, fixD;
  int aFunc, aRef; int zFunc, zMask; int cullFront; unsigned fogCol; float fogEnd, fogSlope;
  int tfx, tcc; unsigned envCol; int wrapU, wrapV, minF, magF;
  int texFmt, texSwz, texMips; int tw[8], th[8], tbw[8];
  unsigned clutFmt, clutBlocks; unsigned ambCol; int ambA; unsigned clearCol; int clearA; unsigned clearDepth;
  int sx1, sy1, sx2, sy2;
} S;

enum { EN_ALPHA = 0, EN_DEPTH, EN_BLEND = 4, EN_CULL = 5, EN_FOG = 7, EN_TEX = 9 };
static int vx, vy, vw, vh, fresh = 1, glready;
static GLuint prog, vbo_dummy; static GLint uMVP, uTex, uUseTex, uFunc, uTcc, uAF, uARef, uFog, uFogC, uFogE, uFogS, uZ, uThru, uVP, uOff, uEnv, uTS, uTO;
static GLint aPos, aUV, aCol;

static const char *VS =
 "attribute vec3 aPos; attribute vec2 aUV; attribute vec4 aCol;\n"
 "uniform mat4 uMVP; uniform float uThru; uniform vec2 uZ; uniform vec4 uVP; uniform vec2 uOff; uniform vec4 uTS; uniform vec4 uTO;\n"
 "varying vec2 vUV; varying vec4 vCol; varying float vW;\n"
 "void main(){ vCol=aCol; vUV=aUV*uTS.xy+uTO.xy;\n"
 " if(uThru>0.5){ float z=aPos.z/65535.0; gl_Position=vec4(aPos.x/240.0-1.0,1.0-aPos.y/136.0,z*2.0-1.0,1.0); vW=1.0; }\n"
 " else { vec4 c=uMVP*vec4(aPos,1.0); float zn=c.z/c.w; float zs=zn*uZ.x+uZ.y; vec2 s=vec2(c.x/c.w*uVP.x+uVP.z-uOff.x, c.y/c.w*uVP.y+uVP.w-uOff.y);\n"
 "  gl_Position=vec4((s.x/240.0-1.0)*c.w,(1.0-s.y/136.0)*c.w,(zs/32767.5-1.0)*c.w,c.w); vW=c.w; } }\n";
static const char *FS =
 "precision mediump float; varying vec2 vUV; varying vec4 vCol; varying float vW;\n"
 "uniform sampler2D uTex; uniform float uUseTex; uniform float uFunc; uniform float uTcc; uniform float uAF; uniform float uARef;\n"
 "uniform float uFog; uniform vec3 uFogC; uniform vec2 uFogE; uniform vec3 uEnv;\n"
 "void main(){ vec4 c=vCol;\n"
 " if(uUseTex>0.5){ vec4 t=texture2D(uTex,vUV); if(uTcc<0.5) t.a=1.0;\n"
 "  if(uFunc<0.5) c=c*t; else if(uFunc<1.5){ c.rgb=mix(c.rgb,t.rgb,t.a); } else if(uFunc<2.5){ c.rgb=mix(c.rgb,uEnv,t.rgb); c.a*=t.a; }\n"
 "  else if(uFunc<3.5) c=t; else { c.rgb+=t.rgb; c.a*=t.a; } }\n"
 " if(uAF>0.5){ float r=uARef; int f=int(uAF+0.5); bool ok=true;\n"
 "  if(f==1) ok=false; else if(f==3) ok=abs(c.a-r)<0.002; else if(f==4) ok=abs(c.a-r)>=0.002; else if(f==5) ok=c.a<r; else if(f==6) ok=c.a<=r; else if(f==7) ok=c.a>r; else if(f==8) ok=c.a>=r;\n"
 "  if(!ok) discard; }\n"
 " if(uFog>0.5){ float f=clamp((uFogE.x-vW)*uFogE.y,0.0,1.0); c.rgb=mix(uFogC,c.rgb,f); }\n"
 " gl_FragColor=c; }\n";

static GLuint sh(GLenum t, const char *s) { GLuint o = glCreateShader(t); glShaderSource(o, 1, &s, 0); glCompileShader(o);
  GLint ok = 0; glGetShaderiv(o, GL_COMPILE_STATUS, &ok); if (!ok) { char b[512]; glGetShaderInfoLog(o, 512, 0, b); ios_log("shader: %s", b); } return o; }
static void gl_init(void) {
  prog = glCreateProgram(); glAttachShader(prog, sh(GL_VERTEX_SHADER, VS)); glAttachShader(prog, sh(GL_FRAGMENT_SHADER, FS));
  glBindAttribLocation(prog, 0, "aPos"); glBindAttribLocation(prog, 1, "aUV"); glBindAttribLocation(prog, 2, "aCol"); glLinkProgram(prog); glUseProgram(prog);
#define U(n) glGetUniformLocation(prog, n)
  uMVP = U("uMVP"); uTex = U("uTex"); uUseTex = U("uUseTex"); uFunc = U("uFunc"); uTcc = U("uTcc"); uAF = U("uAF"); uARef = U("uARef"); uFog = U("uFog"); uFogC = U("uFogC");
  uFogE = U("uFogE"); uZ = U("uZ"); uThru = U("uThru"); uVP = U("uVP"); uOff = U("uOff"); uEnv = U("uEnv"); uTS = U("uTS"); uTO = U("uTO");
  glUniform1i(uTex, 0); glEnableVertexAttribArray(0); glEnableVertexAttribArray(1); glEnableVertexAttribArray(2); glready = 1;
  S.vs[0] = 240; S.vs[1] = -136; S.vs[2] = 32767.5f; S.vp[0] = 2048; S.vp[1] = 2048; S.vp[2] = 32767.5f; S.off[0] = 2048 - 240; S.off[1] = 2048 - 136; S.tsu = S.tsv = 1;
}
static void setup_view(void) {
  int w, h; ios_screen_size(&w, &h); float a = (float)GW / GH; vw = w; vh = (int)(w / a); if (vh > h) { vh = h; vw = (int)(h * a); } vx = (w - vw) / 2; vy = (h - vh) / 2;
  glDisable(GL_SCISSOR_TEST); glViewport(0, 0, w, h); glClearColor(0, 0, 0, 1); glDepthMask(GL_TRUE); glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT); glViewport(vx, vy, vw, vh);
}

/* ---------------- textures ---------------- */
typedef struct { uintptr_t p, clut; int fmt, w, h, swz, lv; unsigned chash; size_t bytes; GLuint id; int live; } TC;
static TC tc[384]; static int tcn;
void ge_invalidate_range(const void *p, unsigned n) {
  uintptr_t a = (uintptr_t)p, b = a + n;
  for (int i = 0; i < tcn; i++) if (tc[i].live && tc[i].p < b && tc[i].p + tc[i].bytes > a) { glDeleteTextures(1, &tc[i].id); tc[i].live = 0; }
}
static int bpp_x2(int f) { return f == 4 ? 1 : f == 5 ? 2 : f <= 2 ? 4 : 8; }   /* bytes*2 per texel */
static void unswz(uint8_t *dst, const uint8_t *src, int rowb, int h) {
  int bw = (rowb + 15) / 16, bh = (h + 7) / 8; int rb = rowb < 16 ? 16 : rowb; (void)bw; (void)bh;
  int bxn = rb / 16; const uint8_t *s = src;
  for (int by = 0; by < h; by += 8) for (int bx = 0; bx < bxn; bx++) for (int r = 0; r < 8; r++, s += 16) { if (by + r >= h) continue; if (bx * 16 + 16 <= rowb) memcpy(dst + (size_t)(by + r) * rowb + bx * 16, s, 16); else if (bx * 16 < rowb) memcpy(dst + (size_t)(by + r) * rowb + bx * 16, s, rowb - bx * 16); }
}
static uint32_t conv(uint32_t v, int f) {
  unsigned r, g, b, a;
  switch (f) { case 0: r = (v & 31) * 255 / 31; g = ((v >> 5) & 63) * 255 / 63; b = ((v >> 11) & 31) * 255 / 31; a = 255; break;
  case 1: r = (v & 31) * 255 / 31; g = ((v >> 5) & 31) * 255 / 31; b = ((v >> 10) & 31) * 255 / 31; a = (v >> 15) ? 255 : 0; break;
  case 2: r = (v & 15) * 17; g = ((v >> 4) & 15) * 17; b = ((v >> 8) & 15) * 17; a = ((v >> 12) & 15) * 17; break;
  default: return v; }
  return r | (g << 8) | (b << 16) | (a << 24);
}
static GLuint tex_get(void) {
  int fmt = S.texFmt, w = 1 << (S.tw[0] & 15), h = 1 << (S.th[0] & 15); uintptr_t p = S.slot[4]; if (!p || fmt > 5) return 0;
  uint32_t cl[256]; unsigned ch = 0; uintptr_t cp = S.slot[3];
  if (fmt >= 4) { if (!cp) return 0; int n = fmt == 4 ? 16 : 256; int cf = S.clutFmt & 3; unsigned sh = (S.clutFmt >> 2) & 31, mk = (S.clutFmt >> 8) & 255, st = (S.clutFmt >> 16) & 31;
    for (int i = 0; i < n; i++) { unsigned idx = (((unsigned)i >> sh) & mk) + st * 16; uint32_t v = cf == 3 ? ((const uint32_t *)cp)[idx & 255] : ((const uint16_t *)cp)[idx & 511]; cl[i] = conv(v, cf); ch = ch * 31 + cl[i]; } }
  int lv = (fmt == 4 || fmt == 5 || 1) ? S.texMips + 1 : 1; if (lv > 8) lv = 8;
  for (int i = 0; i < tcn; i++) if (tc[i].live && tc[i].p == p && tc[i].fmt == fmt && tc[i].w == w && tc[i].h == h && tc[i].swz == S.texSwz && tc[i].lv == lv && tc[i].clut == (fmt >= 4 ? cp : 0) && tc[i].chash == ch) return tc[i].id;
  GLuint id; glGenTextures(1, &id); glBindTexture(GL_TEXTURE_2D, id); size_t total = 0;
  for (int l = 0; l < lv; l++) {
    int lw = 1 << (S.tw[l] & 15), lh = 1 << (S.th[l] & 15); uintptr_t lp = S.slot[4 + l]; if (!lp) { lv = l; break; }
    int rowb = lw * bpp_x2(fmt) / 2; if (fmt == 4) rowb = (lw + 1) / 2; int tb = S.tbw[l] ? S.tbw[l] : lw; int stride = fmt == 4 ? tb / 2 : tb * bpp_x2(fmt) / 2; if (stride < rowb) stride = rowb;
    uint8_t *lin = (uint8_t *)malloc((size_t)stride * lh + 16); if (!lin) break;
    if (S.texSwz) { uint8_t *tmp = (uint8_t *)calloc((size_t)stride * (lh + 8), 1); unswz(tmp, (const uint8_t *)lp, stride, lh); memcpy(lin, tmp, (size_t)stride * lh); free(tmp); } else memcpy(lin, (const void *)lp, (size_t)stride * lh);
    uint32_t *o = (uint32_t *)malloc((size_t)lw * lh * 4);
    for (int y = 0; y < lh; y++) { const uint8_t *r = lin + (size_t)y * stride; uint32_t *d = o + (size_t)y * lw;
      for (int x = 0; x < lw; x++) { uint32_t v;
        if (fmt == 4) v = cl[(x & 1) ? r[x >> 1] >> 4 : r[x >> 1] & 15]; else if (fmt == 5) v = cl[r[x]]; else if (fmt == 3) v = ((const uint32_t *)r)[x]; else v = conv(((const uint16_t *)r)[x], fmt); d[x] = v; } }
    glTexImage2D(GL_TEXTURE_2D, l, GL_RGBA, lw, lh, 0, GL_RGBA, GL_UNSIGNED_BYTE, o); total += (size_t)lw * lh * 4; free(o); free(lin);
    if (lw == 1 && lh == 1) { lv = l + 1; break; }
  }
  int slot = -1; for (int i = 0; i < tcn; i++) if (!tc[i].live) { slot = i; break; }
  if (slot < 0) { if (tcn < 384) slot = tcn++; else { slot = 0; if (tc[0].live) glDeleteTextures(1, &tc[0].id); } }
  tc[slot] = (TC){ p, fmt >= 4 ? cp : 0, fmt, w, h, S.texSwz, S.texMips + 1, ch, total ? (size_t)(w * h * bpp_x2(fmt) / 2 + 64) : 64, id, 1 };
  tc[slot].lv = S.texMips + 1; (void)lv; return id;
}
static void tex_bind(void) {
  GLuint id = tex_get(); if (!id) { glUniform1f(uUseTex, 0); return; }
  glActiveTexture(GL_TEXTURE0); glBindTexture(GL_TEXTURE_2D, id);
  int mip = S.texMips > 0; int mn = S.minF; GLint f;
  if (!mip) f = (mn & 1) ? GL_LINEAR : GL_NEAREST; else f = (mn == 7 || mn == 6) ? GL_LINEAR_MIPMAP_LINEAR : (mn & 1) ? GL_LINEAR_MIPMAP_NEAREST : GL_NEAREST_MIPMAP_NEAREST;
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, f); glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, (S.magF & 1) ? GL_LINEAR : GL_NEAREST);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, S.wrapU ? GL_CLAMP_TO_EDGE : GL_REPEAT); glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, S.wrapV ? GL_CLAMP_TO_EDGE : GL_REPEAT);
  glUniform1f(uUseTex, 1);
}

/* ---------------- vertices ---------------- */
static float rd(const uint8_t *p, int t, int through, int isuv) { (void)isuv;
  switch (t) { case 1: return through ? (float)(int8_t)p[0] : (int8_t)p[0] / 128.f; case 2: return through ? (float)*(const int16_t *)p : *(const int16_t *)p / 32768.f; default: return *(const float *)p; } }
static void col(const uint8_t *p, int f, uint8_t *o) {
  uint32_t v = f == 7 ? *(const uint32_t *)p : *(const uint16_t *)p; uint32_t c = conv(v, f == 7 ? 3 : f - 4);
  if (f == 4) { c = conv(v, 0); } else if (f == 5) c = conv(v, 1); else if (f == 6) c = conv(v, 2);
  o[0] = c & 255; o[1] = (c >> 8) & 255; o[2] = (c >> 16) & 255; o[3] = c >> 24;
}
static int decode(Vtx *out, int n, const uint8_t *vp, const uint8_t *ip, int itype) {
  uint32_t vt = S.vtype; int tt = vt & 3, cf = (vt >> 2) & 7, nt = (vt >> 5) & 3, pt = (vt >> 7) & 3, wt = (vt >> 9) & 3; int wn = ((vt >> 14) & 7) + 1, thr = (vt >> 23) & 1;
  int off = 0, al = 1; int tsz[4] = { 0, 2, 4, 8 }, psz[4] = { 0, 3, 6, 12 }, nsz[4] = { 0, 3, 6, 12 }, wsz[4] = { 0, 1, 2, 4 }, csz[8] = { 0, 0, 0, 0, 2, 2, 2, 4 };
  int wa = wt ? wsz[wt] : 1, ta = tt ? (tt == 3 ? 4 : tt) : 1, ca = cf ? csz[cf] : 1, na = nt ? (nt == 3 ? 4 : nt) : 1, pa = pt ? (pt == 3 ? 4 : pt) : 1;
  #define AL(a) off = (off + (a) - 1) & ~((a) - 1); if ((a) > al) al = (a)
  int ow = 0, ot = 0, oc = 0, on = 0, op = 0;
  if (wt) { AL(wa); ow = off; off += wsz[wt] * wn; }   if (tt) { AL(ta); ot = off; off += tsz[tt]; }
  if (cf) { AL(ca); oc = off; off += csz[cf]; }
  if (nt) { AL(na); on = off; off += nsz[nt]; } (void)on;
  AL(pa); op = off; off += psz[pt]; AL(al); int vsz = (off + al - 1) & ~(al - 1);
  uint8_t dc[4] = { S.ambCol & 255, (S.ambCol >> 8) & 255, (S.ambCol >> 16) & 255, (uint8_t)S.ambA };
  for (int i = 0; i < n; i++) {
    int k = i; if (ip) k = itype == 1 ? ip[i] : ((const uint16_t *)ip)[i]; const uint8_t *v = vp + (size_t)k * vsz; Vtx *o = &out[i];
    o->x = rd(v + op, pt, thr, 0); o->y = rd(v + op + (pt == 3 ? 4 : pt), pt, thr, 0); o->z = rd(v + op + 2 * (pt == 3 ? 4 : pt), pt, thr, 0);
    if (wt && !thr) {   /* hardware skinning on the CPU: sum of weight * (pos * bone) */
      float px = o->x, py = o->y, pz = o->z, sx = 0, sy = 0, sz = 0;
      for (int b = 0; b < wn && b < 8; b++) { float w; const uint8_t *wp = v + ow + b * wsz[wt];
        w = wt == 1 ? wp[0] / 128.f : wt == 2 ? *(const uint16_t *)wp / 32768.f : *(const float *)wp; const float *m = S.bone[b];
        sx += w * (px * m[0] + py * m[3] + pz * m[6] + m[9]); sy += w * (px * m[1] + py * m[4] + pz * m[7] + m[10]); sz += w * (px * m[2] + py * m[5] + pz * m[8] + m[11]); }
      o->x = sx; o->y = sy; o->z = sz; }
    if (pt == 1 && !thr) { o->x *= 1; }
    if (tt) { o->u = rd(v + ot, tt, thr, 1); o->v = rd(v + ot + (tt == 3 ? 4 : tt), tt, thr, 1);
      if (thr && tt != 3) { o->u /= (float)(1 << (S.tw[0] & 15)); o->v /= (float)(1 << (S.th[0] & 15)); } } else o->u = o->v = 0;
    if (cf) col(v + oc, cf, o->c); else memcpy(o->c, dc, 4);
  }
  return thr;
}
static void state_apply(int thr) {
  #define EN(g, c) if (g) glEnable(c); else glDisable(c)
  EN(S.en[EN_BLEND], GL_BLEND); EN(S.en[EN_DEPTH], GL_DEPTH_TEST);
  if (S.en[EN_CULL] && !thr) { glEnable(GL_CULL_FACE); glFrontFace(S.cullFront ? GL_CW : GL_CCW); glCullFace(GL_BACK); } else glDisable(GL_CULL_FACE);
  static const GLenum df[8] = { GL_NEVER, GL_ALWAYS, GL_EQUAL, GL_NOTEQUAL, GL_LESS, GL_LEQUAL, GL_GREATER, GL_GEQUAL };
  glDepthFunc(df[S.zFunc & 7]); glDepthMask(S.zMask ? GL_FALSE : GL_TRUE);
  static const GLenum sf[11] = { GL_DST_COLOR, GL_ONE_MINUS_DST_COLOR, GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA, GL_DST_ALPHA, GL_ONE_MINUS_DST_ALPHA, 0, 0, 0, 0, GL_CONSTANT_COLOR };
  static const GLenum dfc[11] = { GL_SRC_COLOR, GL_ONE_MINUS_SRC_COLOR, GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA, GL_DST_ALPHA, GL_ONE_MINUS_DST_ALPHA, 0, 0, 0, 0, GL_CONSTANT_COLOR };
  int bs = S.blendS > 10 ? 2 : S.blendS, bd = S.blendD > 10 ? 3 : S.blendD; GLenum s_ = sf[bs] ? sf[bs] : GL_ONE, d_ = dfc[bd] ? dfc[bd] : GL_ZERO;
  if (bs == 10 && (S.fixS == 0xffffff)) s_ = GL_ONE; if (bs == 10 && S.fixS == 0) s_ = GL_ZERO; if (bd == 10 && S.fixD == 0xffffff) d_ = GL_ONE; if (bd == 10 && S.fixD == 0) d_ = GL_ZERO;
  glBlendFunc(s_, d_); glBlendEquation(S.blendOp == 1 ? GL_FUNC_SUBTRACT : S.blendOp == 2 ? GL_FUNC_REVERSE_SUBTRACT : GL_FUNC_ADD);
  glUniform1f(uAF, S.en[EN_ALPHA] ? (float)(S.aFunc + 1) : 0.f); glUniform1f(uARef, S.aRef / 255.f);
  glUniform1f(uFog, S.en[EN_FOG] && !thr); glUniform3f(uFogC, (S.fogCol & 255) / 255.f, ((S.fogCol >> 8) & 255) / 255.f, ((S.fogCol >> 16) & 255) / 255.f); glUniform2f(uFogE, S.fogEnd, S.fogSlope);
  glUniform3f(uEnv, (S.envCol & 255) / 255.f, ((S.envCol >> 8) & 255) / 255.f, ((S.envCol >> 16) & 255) / 255.f);
  glUniform1f(uFunc, (float)S.tfx); glUniform1f(uTcc, (float)S.tcc); glUniform1f(uThru, (float)thr);
  glUniform2f(uZ, S.vs[2], S.vp[2]); glUniform4f(uVP, S.vs[0], S.vs[1], S.vp[0], S.vp[1]); glUniform2f(uOff, S.off[0], S.off[1]);
  glUniform4f(uTS, S.tsu, S.tsv, 1, 1); glUniform4f(uTO, S.tou, S.tov, 0, 0);
  glEnable(GL_SCISSOR_TEST); int x1 = S.sx1, y1 = S.sy1, x2 = S.sx2 + 1, y2 = S.sy2 + 1;
  glScissor(vx + x1 * vw / GW, vy + (GH - y2) * vh / GH, (x2 - x1) * vw / GW + 1, (y2 - y1) * vh / GH + 1);
}
static void mmul4(float *r, const float *a, const float *b) { float t[16]; for (int i = 0; i < 4; i++) for (int j = 0; j < 4; j++) { float s = 0; for (int k = 0; k < 4; k++) s += a[i * 4 + k] * b[k * 4 + j]; t[i * 4 + j] = s; } memcpy(r, t, 64); }
static void do_prim(void) {
  int count = S.prim & 0xffff, pr = (S.prim >> 16) & 7; if (count <= 0 || !S.slot[0]) return;
  if (!glready) gl_init(); if (fresh) { setup_view(); fresh = 0; }
  int itype = (S.vtype >> 11) & 3; const uint8_t *ip = itype ? (const uint8_t *)S.slot[1] : 0;
  Vtx *src = (Vtx *)malloc(sizeof(Vtx) * (size_t)count); if (!src) return;
  int thr = decode(src, count, (const uint8_t *)S.slot[0], ip, itype);
  int n = 0; Vtx *o = (Vtx *)malloc(sizeof(Vtx) * (size_t)count * 6); if (!o) { free(src); return; }
  GLenum mode = GL_TRIANGLES;
  switch (pr) {
  case 0: memcpy(o, src, sizeof(Vtx) * count); n = count; mode = GL_POINTS; break;
  case 1: memcpy(o, src, sizeof(Vtx) * count); n = count & ~1; mode = GL_LINES; break;
  case 2: memcpy(o, src, sizeof(Vtx) * count); n = count; mode = GL_LINE_STRIP; break;
  case 3: memcpy(o, src, sizeof(Vtx) * count); n = count / 3 * 3; break;
  case 4: memcpy(o, src, sizeof(Vtx) * count); n = count; mode = GL_TRIANGLE_STRIP; break;
  case 5: memcpy(o, src, sizeof(Vtx) * count); n = count; mode = GL_TRIANGLE_FAN; break;
  case 6: for (int i = 0; i + 1 < count; i += 2) { Vtx a = src[i], b = src[i + 1], c = a, d = a; c.x = b.x; c.u = b.u; d.y = b.y; d.v = b.v; b.c[0] = b.c[0]; a.z = b.z; c.z = b.z; d.z = b.z;
      memcpy(b.c, b.c, 4); a.c[0] = b.c[0]; a.c[1] = b.c[1]; a.c[2] = b.c[2]; a.c[3] = b.c[3]; c.c[0] = a.c[0]; c.c[1] = a.c[1]; c.c[2] = a.c[2]; c.c[3] = a.c[3]; d.c[0] = a.c[0]; d.c[1] = a.c[1]; d.c[2] = a.c[2]; d.c[3] = a.c[3];
      Vtx q[6] = { a, c, b, a, b, d }; memcpy(o + n, q, sizeof q); n += 6; } break;
  }
  if (n > 0) {
    float W[16], V[16], P[16], M[16]; memcpy(W, S.world, 64); memcpy(V, S.view, 64); memcpy(P, S.proj, 64); mmul4(M, W, V); mmul4(M, M, P);
    glUseProgram(prog); glUniformMatrix4fv(uMVP, 1, GL_FALSE, M); state_apply(thr);
    if (S.en[EN_TEX]) { glUniform4f(uTS, S.tsu, S.tsv, 1, 1); tex_bind(); } else glUniform1f(uUseTex, 0);
    if (thr) glUniform4f(uTS, 1, 1, 1, 1), glUniform4f(uTO, 0, 0, 0, 0);
    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, sizeof(Vtx), &o[0].x); glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, sizeof(Vtx), &o[0].u); glVertexAttribPointer(2, 4, GL_UNSIGNED_BYTE, GL_TRUE, sizeof(Vtx), o[0].c);
    glDrawArrays(mode, 0, n);
  }
  free(o); free(src);
}
static void do_clear(unsigned flags) {
  if (!glready) gl_init(); if (fresh) { setup_view(); fresh = 0; }
  glEnable(GL_SCISSOR_TEST); int x1 = S.sx1, y1 = S.sy1, x2 = S.sx2 + 1, y2 = S.sy2 + 1; glScissor(vx + x1 * vw / GW, vy + (GH - y2) * vh / GH, (x2 - x1) * vw / GW + 1, (y2 - y1) * vh / GH + 1);
  GLbitfield m = 0;
  if (flags & GU_COLOR_BUFFER_BIT) { glClearColor((S.clearCol & 255) / 255.f, ((S.clearCol >> 8) & 255) / 255.f, ((S.clearCol >> 16) & 255) / 255.f, S.clearA / 255.f); glColorMask(1, 1, 1, 1); m |= GL_COLOR_BUFFER_BIT; }
  if (flags & GU_DEPTH_BUFFER_BIT) { glClearDepthf(S.clearDepth / 65535.f); glDepthMask(GL_TRUE); m |= GL_DEPTH_BUFFER_BIT; }
  if (m) glClear(m);
}
static inline float f24(uint32_t a) { union { uint32_t u; float f; } x; x.u = a << 8; return x.f; }
static void matpush(float *m, int *n, int total, float v, int cols) { int i = *n; if (cols == 3) { int r = i / 3, c = i % 3; if (r < 4) m[r * 4 + c] = v; } else if (i < total) m[i] = v; (*n)++; }
static void run(const uint32_t *l, int depth) {
  for (;;) {
    uint32_t w = *l++; unsigned op = w >> 24, a = w & 0xffffff;
    switch (op) {
    case 0x0c: case 0x0b: return;
    case 0x0a: if (depth < 8 && S.slot[2]) { uintptr_t c = S.slot[2]; run((const uint32_t *)c, depth + 1); } break;
    case 0xf2: l += a; break;
    case GE_PTRLO: { int s = a >> 16; S.slot[s] = (S.slot[s] & 0xffff0000u) | (a & 0xffff); } break;
    case GE_PTRHI: { int s = a >> 16; S.slot[s] = (S.slot[s] & 0xffffu) | ((uintptr_t)(a & 0xffff) << 16); } break;
    case 0x12: S.vtype = a; break;
    case 0x04: S.prim = a; do_prim(); break;
    case 0xf3: do_clear(a); break;
    case 0xf4: S.clearCol = a; break; case 0xf5: S.clearA = (int)a; break; case 0xf6: S.clearDepth = a; break;
    case 0x2a: S.bn = (int)a; break;
    case 0x2b: if (S.bn < 96) S.bone[S.bn / 12][S.bn % 12] = f24(a); S.bn++; break;
    case 0x3a: S.mn[0] = 0; break; case 0x3b: matpush(S.world, &S.mn[0], 12, f24(a), 3); break;
    case 0x3c: S.mn[1] = 0; break; case 0x3d: matpush(S.view, &S.mn[1], 12, f24(a), 3); break;
    case 0x3e: S.mn[2] = 0; break; case 0x3f: matpush(S.proj, &S.mn[2], 16, f24(a), 4); break;
    case 0x40: S.mn[3] = 0; break; case 0x41: matpush(S.tgen, &S.mn[3], 12, f24(a), 3); break;
    case 0x42: S.vs[0] = f24(a); break; case 0x43: S.vs[1] = f24(a); break; case 0x44: S.vs[2] = f24(a); break;
    case 0x45: S.vp[0] = f24(a); break; case 0x46: S.vp[1] = f24(a); break; case 0x47: S.vp[2] = f24(a); break;
    case 0x4c: S.off[0] = a / 16.f; break; case 0x4d: S.off[1] = a / 16.f; break;
    case 0x48: S.tsu = f24(a); break; case 0x49: S.tsv = f24(a); break; case 0x4a: S.tou = f24(a); break; case 0x4b: S.tov = f24(a); break;
    case 0x55: S.ambCol = a; break; case 0x58: S.ambA = (int)(a & 255); break;
    case 0x22: S.en[EN_ALPHA] = a & 1; break; case 0x23: S.en[EN_DEPTH] = a & 1; break; case 0x21: S.en[EN_BLEND] = a & 1; break;
    case 0x1d: S.en[EN_CULL] = a & 1; break; case 0x1f: S.en[EN_FOG] = a & 1; break; case 0x1e: S.en[EN_TEX] = a & 1; break;
    case 0x9b: S.cullFront = a & 1; break;
    case 0xde: S.zFunc = a & 7; break; case 0xe7: S.zMask = a & 1; break;
    case 0xdb: S.aFunc = a & 255; S.aRef = (a >> 8) & 255; break;
    case 0xdf: S.blendS = a & 15; S.blendD = (a >> 4) & 15; S.blendOp = (a >> 8) & 7; break; case 0xe0: S.fixS = a; break; case 0xe1: S.fixD = a; break;
    case 0xcd: S.fogEnd = f24(a); break; case 0xce: S.fogSlope = f24(a); break; case 0xcf: S.fogCol = a; break;
    case 0xd4: S.sx1 = a & 1023; S.sy1 = a >> 10; break; case 0xd5: S.sx2 = a & 1023; S.sy2 = a >> 10; break;
    case 0xc2: S.texSwz = a & 1; S.texMips = (a >> 16) & 7; break; case 0xc3: S.texFmt = a & 15; break;
    case 0xc5: S.clutFmt = a; break; case 0xc4: S.clutBlocks = a; break;
    case 0xc9: S.tfx = a & 7; S.tcc = (a >> 8) & 1; break; case 0xca: S.envCol = a; break;
    case 0xc6: S.minF = a & 255; S.magF = (a >> 8) & 255; break; case 0xc7: S.wrapU = a & 1; S.wrapV = (a >> 8) & 1; break;
    default:
      if (op >= 0xa8 && op <= 0xaf) S.tbw[op - 0xa8] = a & 0x7ff;
      else if (op >= 0xb8 && op <= 0xbf) { S.tw[op - 0xb8] = a & 15; S.th[op - 0xb8] = (a >> 8) & 15; }
      break;
    }
  }
}
void ge_exec(const uint32_t *list) { run(list, 0); }
void ge_frame_end(void) { fresh = 1; }
