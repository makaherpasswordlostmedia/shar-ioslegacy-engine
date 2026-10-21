// SHAR PSP: город подгружается кусками по мере езды (как в Crash на PS1), машина, туман.
#include <pspkernel.h>
#include <pspdisplay.h>
#include <pspdebug.h>
#include <pspctrl.h>
#include <pspgu.h>
#include <pspgum.h>
#include <psprtc.h>
#include <psppower.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <malloc.h>
#include <math.h>

PSP_MODULE_INFO("SHARVIEW", 0, 1, 0);
PSP_MAIN_THREAD_ATTR(THREAD_ATTR_USER | THREAD_ATTR_VFPU);
PSP_HEAP_SIZE_KB(-1024);

#define BUF_W 512
#define SCR_W 480
#define SCR_H 272
#define DRAW_DIST 115.f
#define LOAD_DIST 150.f
#define DROP_DIST 200.f
#define FOG_NEAR 60.f
#define LOD_DIST 50.f
#define CONE_COS 0.60f
#define CONE_SIN 0.80f
#define SKY 0xffe0b070
static unsigned int __attribute__((aligned(16))) list[262144];

typedef struct { short u, v; unsigned int c; short x, y, z, pad; } Vert;
typedef struct { int w, h, levels; void *pal; void *lv[8]; } Tex;
typedef struct {
  float bb[6]; int tex, flags, nv, ni, owner; float ox, oy, oz, sc; unsigned off, nf, pad[3];
} Rec;
typedef struct {
  Rec r; float cx, cy, cz, rad; unsigned size;
  volatile int state;           // 0 нет, 1 грузится, 2 готов, 3 нет памяти
  void *mem; Vert *v; unsigned short *idx, *fidx;
} Chunk;

static Tex *tex; static unsigned ntex, nch;
static Chunk *ch;
static short *hm, *wl; static float hox, hoz, hcell; static int hw, hh;
static char path[256];
static SceUID sema; static volatile int req = -1; static volatile unsigned loadedBytes = 0;

static int exitCb(int a, int b, void *c) { sceKernelExitGame(); return 0; }
static int cbThread(SceSize a, void *b) {
  int id = sceKernelCreateCallback("exit", exitCb, NULL);
  sceKernelRegisterExitCallback(id); sceKernelSleepThreadCB(); return 0;
}
static void fail(const char *msg) {
  pspDebugScreenInit(); pspDebugScreenPrintf("SHAR PSP\n\n%s\n\nPress HOME to exit.", msg);
  sceKernelSleepThread();
}

static void loadChunk(SceUID fd, int i) {
  Chunk *c = &ch[i];
  void *m = memalign(16, c->size);
  if (!m) { c->state = 3; return; }
  sceIoLseek32(fd, c->r.off, PSP_SEEK_SET);
  if (sceIoRead(fd, m, c->size) != (int)c->size) { free(m); c->state = 3; return; }
  sceKernelDcacheWritebackRange(m, c->size);
  c->mem = m; c->v = (Vert *)m;
  c->idx = (unsigned short *)((char *)m + ((c->r.nv * sizeof(Vert) + 15) & ~15));
  c->fidx = (unsigned short *)((char *)c->idx + ((c->r.ni * 2 + 15) & ~15));
  loadedBytes += c->size;
  c->state = 2;
}
static int loaderThread(SceSize a, void *b) {
  SceUID fd = sceIoOpen(path, PSP_O_RDONLY, 0);
  for (;;) {
    sceKernelWaitSema(sema, 1, NULL);
    int i = req; if (i >= 0 && fd >= 0) loadChunk(fd, i);
    req = -1;
  }
  return 0;
}
static void unloadChunk(Chunk *c) {
  if (c->state == 2) { loadedBytes -= c->size; free(c->mem); c->mem = 0; }
  c->state = 0;
}

static int ground(float x, float z, float y, float step, float *out) {
  int gx = (int)((x - hox) / hcell), gz = (int)((z - hoz) / hcell);
  if (gx < 0 || gz < 0 || gx >= hw || gz >= hh) return 0;
  short *c = hm + ((size_t)gz * hw + gx) * 4; int found = 0; float best = -1e9f;
  for (int i = 0; i < 4; i++) {
    if (c[i] == -32768) continue;
    float h = c[i] * .01f;
    if (h <= y + step && h > best) { best = h; found = 1; }
  }
  if (found) *out = best;
  return found;
}

// стена в клетке перекрывает высоты кузова машины?
static int wallAt(float x, float z, float y) {
  int gx = (int)((x - hox) / hcell), gz = (int)((z - hoz) / hcell);
  if (gx < 0 || gz < 0 || gx >= hw || gz >= hh) return 1;
  short *w = wl + ((size_t)gz * hw + gx) * 2;
  if (w[0] > w[1]) return 0;
  float lo = w[0] * .01f, hi = w[1] * .01f;
  return hi > y + 0.45f && lo < y + 1.6f;
}

static int bound = -2;
static void bindTex(int t) {
  if (t == bound) return; bound = t;
  if (t < 0 || t >= (int)ntex) { sceGuDisable(GU_TEXTURE_2D); return; }
  Tex *x = &tex[t];
  sceGuEnable(GU_TEXTURE_2D);
  sceGuClutMode(GU_PSM_8888, 0, 0xff, 0); sceGuClutLoad(32, x->pal);
  sceGuTexMode(GU_PSM_T8, x->levels - 1, 0, 0);
  int lw = x->w, lh = x->h;
  for (int l = 0; l < x->levels; l++) { sceGuTexImage(l, lw, lh, lw, x->lv[l]); lw >>= 1; lh = lh > 1 ? lh >> 1 : 1; }
  sceGuTexLevelMode(GU_TEXTURE_AUTO, 0.f);
  sceGuTexFilter(x->levels > 1 ? GU_LINEAR_MIPMAP_LINEAR : GU_LINEAR, GU_LINEAR);
  sceGuTexOffset(0.f, 0.f);
}

static long drawnTris;
static void drawChunk(Chunk *d, int far) {
  if (d->state != 2) return;
  unsigned short *ix = far ? d->fidx : d->idx; int cnt = far ? (int)d->r.nf : d->r.ni;
  if (cnt <= 0) return; drawnTris += cnt / 3;
  bindTex(d->r.tex); sceGuTexScale(128.f, 128.f);
  if (d->r.flags & 1) sceGuEnable(GU_ALPHA_TEST); else sceGuDisable(GU_ALPHA_TEST);
  if (d->r.flags & 2) { sceGuEnable(GU_BLEND); sceGuDepthMask(GU_TRUE); }
  else { sceGuDisable(GU_BLEND); sceGuDepthMask(GU_FALSE); }
  sceGumPushMatrix();
  ScePspFVector3 o = {d->r.ox, d->r.oy, d->r.oz}, s = {d->r.sc, d->r.sc, d->r.sc};
  sceGumTranslate(&o); sceGumScale(&s);
  for (int k = 0; k < cnt; k += 65532) {
    int n = cnt - k; if (n > 65532) n = 65532;
    sceGumDrawArray(GU_TRIANGLES, GU_INDEX_16BIT | GU_TEXTURE_16BIT | GU_COLOR_8888 | GU_VERTEX_16BIT | GU_TRANSFORM_3D,
                    n, ix + k, d->v);
  }
  sceGumPopMatrix();
}

static float chunkDist(Chunk *c, float x, float y, float z) {
  float dx = c->cx - x, dy = c->cy - y, dz = c->cz - z;
  return sqrtf(dx * dx + dy * dy + dz * dz) - c->rad;
}

// планировщик: выгрузить далёкое, отдать загрузчику ближайший нужный кусок
static void stream(float x, float y, float z) {
  for (unsigned i = 0; i < nch; i++)
    if (!ch[i].r.owner && ch[i].state >= 2 && chunkDist(&ch[i], x, y, z) > DROP_DIST) unloadChunk(&ch[i]);
  if (req >= 0) return;
  int best = -1; float bd = LOAD_DIST;
  for (unsigned i = 0; i < nch; i++) {
    if (ch[i].state != 0) continue;
    float d = chunkDist(&ch[i], x, y, z);
    if (d < bd) { bd = d; best = i; }
  }
  if (best >= 0) { ch[best].state = 1; req = best; sceKernelSignalSema(sema, 1); }
}

int main(int argc, char **argv) {
  int th = sceKernelCreateThread("cb", cbThread, 0x11, 0xFA0, 0, 0);
  if (th >= 0) sceKernelStartThread(th, 0, 0);
  scePowerSetClockFrequency(333, 333, 166);
  pspDebugScreenInit(); pspDebugScreenPrintf("Loading Springfield...\n");

  strncpy(path, argv[0], sizeof(path) - 16); path[sizeof(path) - 16] = 0;
  char *slash = strrchr(path, '/'); if (slash) slash[1] = 0; else path[0] = 0;
  strcat(path, "level.shr");

  // резидентная часть: заголовок, карта высот, текстуры, таблица кусков
  SceUID fd = sceIoOpen(path, PSP_O_RDONLY, 0);
  if (fd < 0) fail("level.shr not found next to EBOOT.PBP.");
  unsigned char hdr[80];
  if (sceIoRead(fd, hdr, 80) != 80 || memcmp(hdr, "SHR6", 4)) fail("level.shr is an old version. Run the export again.");
  ntex = *(unsigned *)(hdr + 4); nch = *(unsigned *)(hdr + 8);
  float *hd = (float *)(hdr + 12);
  float spx = hd[6], spy = hd[7], spz = hd[8], sph = hd[9], lift = hd[10];
  hox = hd[11]; hoz = hd[12]; hcell = hd[13]; hw = *(int *)(hd + 14); hh = *(int *)(hd + 15);
  unsigned tableOff = *(unsigned *)(hdr + 76);
  unsigned residentSize = tableOff + 80 * nch;
  unsigned char *data = memalign(16, residentSize);
  if (!data) {
    char m[160]; snprintf(m, sizeof m, "Not enough memory: %.1f MB needed, %.1f MB free.",
      residentSize / 1048576.f, sceKernelMaxFreeMemSize() / 1048576.f); fail(m);
  }
  sceIoLseek32(fd, 0, PSP_SEEK_SET);
  if (sceIoRead(fd, data, residentSize) != (int)residentSize) fail("Read error.");
  sceIoClose(fd);

  size_t p = 80;
  hm = (short *)(data + p); p += (size_t)hw * hh * 4 * 2; p = (p + 15) & ~15;
  wl = (short *)(data + p); p += (size_t)hw * hh * 2 * 2; p = (p + 15) & ~15;
  tex = calloc(ntex ? ntex : 1, sizeof(Tex));
  for (unsigned i = 0; i < ntex; i++) {
    unsigned short *t2 = (unsigned short *)(data + p);
    tex[i].w = t2[0]; tex[i].h = t2[1]; tex[i].levels = t2[2];
    tex[i].pal = data + p + 16; p += 16 + 1024;
    int lw = tex[i].w, lh = tex[i].h;
    for (int l = 0; l < tex[i].levels; l++) { tex[i].lv[l] = data + p; p += lw * lh; p = (p + 15) & ~15; lw >>= 1; lh = lh > 1 ? lh >> 1 : 1; }
  }
  ch = calloc(nch ? nch : 1, sizeof(Chunk)); long tris = 0;
  for (unsigned i = 0; i < nch; i++) {
    memcpy(&ch[i].r, data + tableOff + 80 * i, 80);
    float *b = ch[i].r.bb;
    ch[i].cx = (b[0] + b[3]) * .5f; ch[i].cy = (b[1] + b[4]) * .5f; ch[i].cz = (b[2] + b[5]) * .5f;
    float dx = b[3] - b[0], dy = b[4] - b[1], dz = b[5] - b[2]; ch[i].rad = .5f * sqrtf(dx * dx + dy * dy + dz * dz);
    ch[i].size = ((ch[i].r.nv * sizeof(Vert) + 15) & ~15) + ((ch[i].r.ni * 2 + 15) & ~15) + ((ch[i].r.nf * 2 + 15) & ~15);
    if (!ch[i].r.owner) tris += ch[i].r.ni / 3;
  }
  sceKernelDcacheWritebackAll();

  // машина и всё вокруг старта — сразу, остальное фоном
  SceUID lfd = sceIoOpen(path, PSP_O_RDONLY, 0);
  for (unsigned i = 0; i < nch; i++)
    if (ch[i].r.owner || chunkDist(&ch[i], spx, spy, spz) < DRAW_DIST * .6f) loadChunk(lfd, i);
  sceIoClose(lfd);
  sema = sceKernelCreateSema("load", 0, 0, 1, NULL);
  SceUID lt = sceKernelCreateThread("loader", loaderThread, 0x18, 0x4000, 0, 0);
  if (lt >= 0) sceKernelStartThread(lt, 0, 0);

  void *fbp0 = (void *)0, *fbp1 = (void *)(BUF_W * SCR_H * 4), *zbp = (void *)(BUF_W * SCR_H * 8);
  sceGuInit(); sceGuStart(GU_DIRECT, list);
  sceGuDrawBuffer(GU_PSM_8888, fbp0, BUF_W); sceGuDispBuffer(SCR_W, SCR_H, fbp1, BUF_W);
  sceGuDepthBuffer(zbp, BUF_W);
  sceGuOffset(2048 - SCR_W / 2, 2048 - SCR_H / 2); sceGuViewport(2048, 2048, SCR_W, SCR_H);
  sceGuDepthRange(65535, 0); sceGuScissor(0, 0, SCR_W, SCR_H); sceGuEnable(GU_SCISSOR_TEST);
  sceGuDepthFunc(GU_GEQUAL); sceGuEnable(GU_DEPTH_TEST); sceGuDisable(GU_CULL_FACE);
  sceGuShadeModel(GU_SMOOTH); sceGuEnable(GU_CLIP_PLANES);
  sceGuTexWrap(GU_REPEAT, GU_REPEAT); sceGuTexFunc(GU_TFX_MODULATE, GU_TCC_RGBA);
  sceGuBlendFunc(GU_ADD, GU_SRC_ALPHA, GU_ONE_MINUS_SRC_ALPHA, 0, 0);
  sceGuAlphaFunc(GU_GREATER, 0x40, 0xff);
  sceGuFog(FOG_NEAR, DRAW_DIST, SKY & 0xffffff); sceGuEnable(GU_FOG);
  sceGuFinish(); sceGuSync(0, 0);
  sceDisplayWaitVblankStart(); sceGuDisplay(GU_TRUE);

  float x = spx, y = spy, z = spz, h = sph, v = 0, vy = 0, steer = 0;
  { float g; if (ground(x, z, y + 2.f, 0.f, &g)) y = g; }
  int fly = 0, hud = 1; unsigned prev = 0;
  float fx = x, fy = y + 3, fz = z, fyaw = 0, fpitch = -.2f;
  float camx = x - sinf(h) * 7, camy = y + 3, camz = z - cosf(h) * 7;
  sceCtrlSetSamplingCycle(0); sceCtrlSetSamplingMode(PSP_CTRL_MODE_ANALOG);
  u64 last, now, acc; sceRtcGetCurrentTick(&last); acc = last; float fps = 0; int frames = 0, drawn = 0;
  SceCtrlData pad;

  for (;;) {
    sceCtrlPeekBufferPositive(&pad, 1);
    sceRtcGetCurrentTick(&now); float dt = (now - last) / 1000000.f; last = now; if (dt > .05f) dt = .05f;
    unsigned hit = pad.Buttons & ~prev; prev = pad.Buttons;
    float ax = (pad.Lx - 128) / 128.f, ay = (pad.Ly - 128) / 128.f;
    if (fabsf(ax) < .2f) ax = 0; if (fabsf(ay) < .2f) ay = 0;
    if (hit & PSP_CTRL_SELECT) hud = !hud;
    if (hit & PSP_CTRL_TRIANGLE) { fly = !fly; fx = camx; fy = camy; fz = camz; fyaw = atan2f(x - camx, -(z - camz)); fpitch = -.2f; }
    if (hit & PSP_CTRL_START) { x = spx; y = spy; z = spz; h = sph; v = vy = 0; float g; if (ground(x, z, y + 2.f, 0.f, &g)) y = g; }

    float cfx, cfy, cfz, eyex, eyey, eyez;
    if (!fly) {
      float st = ax;
      if (pad.Buttons & PSP_CTRL_LEFT) st = -1; if (pad.Buttons & PSP_CTRL_RIGHT) st = 1;
      steer += (st - steer) * fminf(1.f, dt * 8.f);
      int gas = pad.Buttons & (PSP_CTRL_CROSS | PSP_CTRL_RTRIGGER);
      int brake = pad.Buttons & (PSP_CTRL_SQUARE | PSP_CTRL_LTRIGGER);
      if (gas) v += (v < 0 ? 30.f : 14.f) * dt;
      else if (brake) v -= (v > 0 ? 30.f : 8.f) * dt;
      else v -= v * 1.2f * dt;
      if (v > 30.f) v = 30.f; if (v < -9.f) v = -9.f;
      float turn = steer * 2.1f * fminf(1.f, fabsf(v) / 6.f) / (1.f + fabsf(v) / 25.f);
      h -= turn * dt * (v >= 0 ? 1.f : -1.f);
      float nx = x + sinf(h) * v * dt, nz = z + cosf(h) * v * dt, g;
      float bump = v >= 0 ? 2.2f : -2.2f;   // нос/багажник машины
      float px = nx + sinf(h) * bump, pz = nz + cosf(h) * bump;
      int stuck = wallAt(x, z, y);          // если застряли в стене — выпускаем
      if (ground(nx, nz, y, 1.0f, &g) && g > y - 25.f && (stuck || (!wallAt(px, pz, y) && !wallAt(nx, nz, y)))) { x = nx; z = nz; }
      else v = -v * .2f;
      if (ground(x, z, y, 1.0f, &g)) {
        if (g >= y - .35f && vy <= 0) { y = g; vy = 0; }
        else { vy -= 22.f * dt; y += vy * dt; if (y < g) { y = g; vy = 0; } }
      } else { vy -= 22.f * dt; y += vy * dt; }
      if (y < -200) { x = spx; y = spy; z = spz; v = vy = 0; }
      float tx = x - sinf(h) * 7.5f, tz = z - cosf(h) * 7.5f, ty = y + 3.2f, k = fminf(1.f, dt * 5.f);
      camx += (tx - camx) * k; camy += (ty - camy) * k; camz += (tz - camz) * k;
      eyex = camx; eyey = camy; eyez = camz;
      cfx = x - camx; cfy = (y + 1.4f) - camy; cfz = z - camz;
      float l = sqrtf(cfx * cfx + cfy * cfy + cfz * cfz); cfx /= l; cfy /= l; cfz /= l;
    } else {
      fyaw += ax * 2.f * dt; fpitch -= ay * 1.5f * dt;
      if (fpitch > 1.5f) fpitch = 1.5f; if (fpitch < -1.5f) fpitch = -1.5f;
      float sp = (pad.Buttons & PSP_CTRL_CROSS) ? 60.f : 15.f;
      cfx = sinf(fyaw) * cosf(fpitch); cfy = sinf(fpitch); cfz = -cosf(fyaw) * cosf(fpitch);
      float rx = cosf(fyaw), rz = sinf(fyaw);
      if (pad.Buttons & PSP_CTRL_UP) { fx += cfx * sp * dt; fy += cfy * sp * dt; fz += cfz * sp * dt; }
      if (pad.Buttons & PSP_CTRL_DOWN) { fx -= cfx * sp * dt; fy -= cfy * sp * dt; fz -= cfz * sp * dt; }
      if (pad.Buttons & PSP_CTRL_RIGHT) { fx += rx * sp * dt; fz += rz * sp * dt; }
      if (pad.Buttons & PSP_CTRL_LEFT) { fx -= rx * sp * dt; fz -= rz * sp * dt; }
      if (pad.Buttons & PSP_CTRL_RTRIGGER) fy += sp * dt;
      if (pad.Buttons & PSP_CTRL_LTRIGGER) fy -= sp * dt;
      eyex = fx; eyey = fy; eyez = fz;
    }

    stream(eyex, eyey, eyez);

    sceGuStart(GU_DIRECT, list);
    sceGuClearColor(SKY); sceGuClearDepth(0);
    sceGuClear(GU_COLOR_BUFFER_BIT | GU_DEPTH_BUFFER_BIT);
    sceGumMatrixMode(GU_PROJECTION); sceGumLoadIdentity();
    sceGumPerspective(62.f, 16.f / 9.f, 0.7f, DRAW_DIST + 10.f);
    sceGumMatrixMode(GU_VIEW); sceGumLoadIdentity();
    ScePspFVector3 eye = {eyex, eyey, eyez}, at = {eyex + cfx, eyey + cfy, eyez + cfz}, up = {0, 1, 0};
    sceGumLookAt(&eye, &at, &up);
    sceGumMatrixMode(GU_MODEL); sceGumLoadIdentity();

    drawn = 0; drawnTris = 0; bound = -2;
    for (unsigned i = 0; i < nch; i++) {
      Chunk *d = &ch[i]; if (d->r.owner || d->state != 2) continue;
      float dx = d->cx - eyex, dy = d->cy - eyey, dz = d->cz - eyez;
      float dist2 = dx * dx + dy * dy + dz * dz, dist = sqrtf(dist2);
      if (dist - d->rad > DRAW_DIST) continue;
      float f = dx * cfx + dy * cfy + dz * cfz;                 // вдоль взгляда
      float l = sqrtf(fmaxf(0.f, dist2 - f * f));               // вбок от взгляда
      if (l * CONE_COS - f * CONE_SIN > d->rad) continue;       // вне конуса обзора
      drawChunk(d, dist - d->rad > LOD_DIST); drawn++;
    }
    sceGumMatrixMode(GU_MODEL); sceGumLoadIdentity();
    ScePspFVector3 cp = {x, y + lift, z}; sceGumTranslate(&cp); sceGumRotateY(h + GU_PI);
    for (unsigned i = 0; i < nch; i++) if (ch[i].r.owner == 1) drawChunk(&ch[i], 0);
    sceGumLoadIdentity();
    sceGuDepthMask(GU_FALSE);
    sceGuFinish(); sceGuSync(0, 0);

    frames++; if (now - acc >= 1000000) { fps = frames * 1000000.f / (now - acc); frames = 0; acc = now; }
    if (hud) {
      pspDebugScreenSetOffset((int)fbp0); pspDebugScreenSetXY(0, 0);
      pspDebugScreenPrintf("FPS %4.1f  tris %ldk  RAM %.1fMB  %s %3.0f km/h\n", fps, drawnTris / 1000, loadedBytes / 1048576.f,
                           fly ? "FLY" : "CAR", fabsf(v) * 3.6f);
      pspDebugScreenPrintf(fly ? "stick:look dpad:move L/R:down/up X:fast  /\\:car START:reset"
                               : "X/R:gas []/L:brake stick/dpad:steer  /\\:fly  START:reset");
    }
    sceDisplayWaitVblankStart(); fbp0 = sceGuSwapBuffers();
  }
  return 0;
}
