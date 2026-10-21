// HOMER TEST: standalone EBOOT for viewer/skin.c — Homer on a ground plane, orbit camera, all 67 original clips.
// Files next to EBOOT.PBP: homer.chr (tools/char_export.py). Optional (for the emulator checks):
//   shots.txt  lines "clip t yaw pitch dist" -> holds each pose for 20 frames, dumps shot_NN.raw (512x272 ABGR) and exits
//   demo       (empty file) -> cycles idle/walk/run/dash/walk/idle every 2.5 s with crossfades, 9 Homers after 15 s
// Controls: [] idle  /\ walk  O run  X dash  <- -> every clip  up/down speed  L/R zoom  stick orbit
//           START pause  SELECT crowd 1 / 9 / 25 Homers (CPU+GE cost check), then again with homer_b4.chr if present
#include <pspkernel.h>
#include <pspdisplay.h>
#include <pspctrl.h>
#include <pspgu.h>
#include <pspgum.h>
#include <psppower.h>
#include <pspdebug.h>
#include <pspge.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <malloc.h>
#include <math.h>
#include "skin.h"
#include "hud.h"

PSP_MODULE_INFO("HOMERTEST", 0, 1, 0);
PSP_MAIN_THREAD_ATTR(THREAD_ATTR_USER | THREAD_ATTR_VFPU);
PSP_HEAP_SIZE_KB(-1024);

#define BUF_W 512
#define SCR_W 480
#define SCR_H 272
#define SKY 0xffe0b070
#define MAXN 25

static unsigned int __attribute__((aligned(64))) list[65536];
static char dir[256];

static int exitCb(int a, int b, void *c) { sceKernelExitGame(); return 0; }
static int cbThread(SceSize a, void *b) {
  int id = sceKernelCreateCallback("exit", exitCb, NULL);
  sceKernelRegisterExitCallback(id); sceKernelSleepThreadCB(); return 0;
}
static void fail(const char *msg) {
  pspDebugScreenInit(); pspDebugScreenPrintf("HOMER TEST\n\n%s\n\nPress HOME to exit.", msg); sceKernelSleepThread();
}
static void sibling(char *out, const char *name) { strcpy(out, dir); strcat(out, name); }

// ground: 24 x 24 tiles of 1 m, checker with a 2 m period, scrolled by root motion (walk in place)
typedef struct { unsigned c; float x, y, z; } GVert;
#define GN 24
static GVert __attribute__((aligned(16))) ground[GN * GN * 6];
static void buildGround(void) {
  int k = 0;
  for (int i = 0; i < GN; i++) for (int j = 0; j < GN; j++) {
    unsigned c = ((i + j) & 1) ? 0xff5a8c6e : 0xff4f7a60;
    float x0 = i - GN / 2, z0 = j - GN / 2, x1 = x0 + 1, z1 = z0 + 1;
    GVert q[6] = {{c, x0, 0, z0}, {c, x1, 0, z0}, {c, x1, 0, z1}, {c, x0, 0, z0}, {c, x1, 0, z1}, {c, x0, 0, z1}};
    memcpy(&ground[k], q, sizeof q); k += 6;
  }
  sceKernelDcacheWritebackRange(ground, sizeof ground);
}

typedef struct { char clip[64]; float t, yaw, pitch, dist; } Shot;
static Shot shots[64]; static int nshots;
static void loadShots(void) {
  char fn[256]; sibling(fn, "shots.txt");
  SceUID f = sceIoOpen(fn, PSP_O_RDONLY, 0); if (f < 0) return;
  static char buf[8192]; int n = sceIoRead(f, buf, sizeof buf - 1); sceIoClose(f); if (n <= 0) return; buf[n] = 0;
  char *s = buf;
  while (*s && nshots < 64) {
    Shot *h = &shots[nshots];
    if (sscanf(s, "%63s %f %f %f %f", h->clip, &h->t, &h->yaw, &h->pitch, &h->dist) == 5 && h->clip[0] != '#') nshots++;
    while (*s && *s != '\n') s++;
    if (*s) s++;
  }
}
static void dumpFrame(void *fb, int k) {
  char fn[256], nm[32]; snprintf(nm, sizeof nm, "shot_%02d.raw", k); sibling(fn, nm);
  SceUID f = sceIoOpen(fn, PSP_O_WRONLY | PSP_O_CREAT | PSP_O_TRUNC, 0777);
  if (f >= 0) { sceIoWrite(f, fb, BUF_W * SCR_H * 4); sceIoClose(f); }
}

int main(int argc, char **argv) {
  int th = sceKernelCreateThread("cb", cbThread, 0x11, 0xFA0, 0, 0);
  if (th >= 0) sceKernelStartThread(th, 0, 0);
  scePowerSetClockFrequency(333, 333, 166);
  strncpy(dir, argv[0], sizeof dir - 32); dir[sizeof dir - 32] = 0;
  { char *sl = strrchr(dir, '/'); if (sl) sl[1] = 0; else dir[0] = 0; }

  char fn[256]; sibling(fn, "homer.chr");
  SkinModel *m8 = skinLoad(fn), *m = m8;
  if (!m) fail("homer.chr not found (or wrong version) next to EBOOT.PBP.");
  sibling(fn, "homer_b4.chr");
  SkinModel *m4 = skinLoad(fn);                     // optional: same Homer, <= 4 bones per draw (GE cost comparison)
  if (m4 && (m4->h->nClips != m8->h->nClips || m4->h->nJoints != m8->h->nJoints)) { skinFree(m4); m4 = 0; }
  int mode = 0;                                     // SELECT: 1 / 9 / 25 Homers, then the same with homer_b4.chr
  loadShots(); buildGround();
  int demo = 0; { char dn[256]; sibling(dn, "demo"); SceUID f = sceIoOpen(dn, PSP_O_RDONLY, 0); if (f >= 0) { sceIoClose(f); demo = 1; } }
  float demoT = 0;

  static SkinPlayer pl[MAXN];
  int cIdle = skinFindClip(m, "loco_idle_rest"), cWalk = skinFindClip(m, "loco_walk"), cRun = skinFindClip(m, "loco_run"),
      cDash = skinFindClip(m, "loco_dash");
  for (int i = 0; i < MAXN; i++) { skinInit(&pl[i], m); pl[i].seed += i * 7919u; skinPlay(&pl[i], cIdle, 1, 0); pl[i].t = i * .37f; }

  void *fbp0 = (void *)0, *fbp1 = (void *)(BUF_W * SCR_H * 4), *zbp = (void *)(BUF_W * SCR_H * 8);
  sceGuInit(); sceGuStart(GU_DIRECT, list);
  sceGuDrawBuffer(GU_PSM_8888, fbp0, BUF_W); sceGuDispBuffer(SCR_W, SCR_H, fbp1, BUF_W); sceGuDepthBuffer(zbp, BUF_W);
  sceGuOffset(2048 - SCR_W / 2, 2048 - SCR_H / 2); sceGuViewport(2048, 2048, SCR_W, SCR_H);
  sceGuDepthRange(65535, 0); sceGuScissor(0, 0, SCR_W, SCR_H); sceGuEnable(GU_SCISSOR_TEST);
  sceGuDepthFunc(GU_GEQUAL); sceGuEnable(GU_DEPTH_TEST); sceGuDisable(GU_CULL_FACE);
  sceGuShadeModel(GU_SMOOTH); sceGuEnable(GU_CLIP_PLANES);
  sceGuBlendFunc(GU_ADD, GU_SRC_ALPHA, GU_ONE_MINUS_SRC_ALPHA, 0, 0); sceGuAlphaFunc(GU_GREATER, 0x40, 0xff);
  sceGuFinish(); sceGuSync(0, 0);
  sceDisplayWaitVblankStart(); sceGuDisplay(GU_TRUE);
  hudInit();

  float yaw = .6f, pitch = .18f, dist = 4.2f, speed = 1.f, gx = 0, gz = 0, fps = 0, workMs = 0;
  float usUpd = 0, usDraw = 0; int n = 1, paused = 0, clip = cIdle, frames = 0, hudTick = 0, shot = 0, shotF = 0;
  unsigned prev = 0, last = sceKernelGetSystemTimeLow(), acc = last;
  float rootPrev[3]; skinRootMotion(m, clip, 0, rootPrev);
  sceCtrlSetSamplingCycle(0); sceCtrlSetSamplingMode(PSP_CTRL_MODE_ANALOG);
  SceCtrlData pad;

  for (;;) {
    unsigned t0 = sceKernelGetSystemTimeLow();
    float dt = (t0 - last) / 1e6f; last = t0; if (dt > .05f) dt = .05f;
    sceCtrlPeekBufferPositive(&pad, 1);
    unsigned hit = pad.Buttons & ~prev; prev = pad.Buttons;
    float ax = (pad.Lx - 128) / 128.f, ay = (pad.Ly - 128) / 128.f;
    if (fabsf(ax) < .2f) ax = 0; if (fabsf(ay) < .2f) ay = 0;

    int want = clip; float fade = .25f;
    if (hit & PSP_CTRL_SQUARE) want = cIdle;
    if (hit & PSP_CTRL_TRIANGLE) want = cWalk;
    if (hit & PSP_CTRL_CIRCLE) want = cRun;
    if (hit & PSP_CTRL_CROSS) want = cDash;
    if (hit & PSP_CTRL_RIGHT) { want = (clip + 1) % skinClipCount(m); fade = 0; }
    if (hit & PSP_CTRL_LEFT) { want = (clip + skinClipCount(m) - 1) % skinClipCount(m); fade = 0; }
    if (hit & PSP_CTRL_UP) speed = fminf(speed * 2.f, 2.f);
    if (hit & PSP_CTRL_DOWN) speed = fmaxf(speed * .5f, .125f);
    if (hit & PSP_CTRL_START) paused = !paused;
    if (hit & PSP_CTRL_SELECT) {
      mode = (mode + 1) % (m4 ? 6 : 3); n = mode % 3 == 0 ? 1 : mode % 3 == 1 ? 9 : 25;
      m = mode >= 3 ? m4 : m8; for (int i = 0; i < MAXN; i++) pl[i].m = m;
      dist = n == 1 ? 4.2f : n == 9 ? 9.f : 14.f;
    }
    yaw += ax * 2.f * dt; pitch += ay * 1.2f * dt;
    if (pitch < -.3f) pitch = -.3f; if (pitch > 1.3f) pitch = 1.3f;
    if (pad.Buttons & PSP_CTRL_LTRIGGER) dist = fmaxf(1.2f, dist - 3.f * dt);
    if (pad.Buttons & PSP_CTRL_RTRIGGER) dist = fminf(20.f, dist + 3.f * dt);

    if (demo) {                                      // emulator check of the real-time path: idle/walk/run/dash/crowd
      static const int order[] = {0, 1, 2, 3, 1, 0};
      int ph = (int)(demoT / 2.5f) % 6, cl[4] = {cIdle, cWalk, cRun, cDash};
      want = cl[order[ph]]; yaw = .9f + demoT * .12f; n = (int)(demoT / 15.f) % 2 ? 9 : 1; demoT += dt;
      dist = n == 1 ? 4.2f : 9.f;
    }
    float step = paused ? 0.f : dt;
    if (nshots) {                                    // emulator check: exact poses, one per 20 frames
      Shot *h = &shots[shot]; int c = skinFindClip(m, h->clip);
      want = c; yaw = h->yaw; pitch = h->pitch; dist = h->dist; n = 1; fade = 0; step = 0;
      for (int i = 0; i < MAXN; i++) { pl[i].clip = c; pl[i].prev = -1; pl[i].t = h->t; pl[i].loop = 0; pl[i].speed = 1; pl[i].blinkT = -1; }
    }
    if (want != clip) {
      clip = want; for (int i = 0; i < MAXN; i++) skinPlay(&pl[i], clip, 1, fade);
      skinRootMotion(m, clip, pl[0].t, rootPrev);
    }

    // animation for n characters (timed), root motion of Homer 0 scrolls the ground (walk in place)
    unsigned u0 = sceKernelGetSystemTimeLow();
    for (int i = 0; i < n; i++) { pl[i].speed = speed; skinUpdate(&pl[i], step); }
    unsigned u1 = sceKernelGetSystemTimeLow();
    if (!nshots && step > 0) {
      float r[3]; skinRootMotion(m, clip, pl[0].t, r);
      float dx = r[0] - rootPrev[0], dz = r[2] - rootPrev[2];
      if (fabsf(dx) + fabsf(dz) < 3.f) { gx -= dx; gz -= dz; }    // loop restart: skip the jump back
      memcpy(rootPrev, r, sizeof r);
      gx = fmodf(gx, 2.f); gz = fmodf(gz, 2.f);
    }

    sceGuStart(GU_DIRECT, list);
    sceGuEnable(GU_DEPTH_TEST); sceGuDepthFunc(GU_GEQUAL); sceGuShadeModel(GU_SMOOTH);
    sceGuTexWrap(GU_REPEAT, GU_REPEAT); sceGuTexFunc(GU_TFX_MODULATE, GU_TCC_RGBA);
    sceGuTexScale(128.f, 128.f); sceGuTexOffset(0.f, 0.f); sceGuTexLevelMode(GU_TEXTURE_AUTO, 0.f);
    sceGuClutMode(GU_PSM_8888, 0, 0xff, 0);
    sceGuFog(30.f, 60.f, SKY & 0xffffff);
    sceGuClearColor(SKY); sceGuClearDepth(0); sceGuDepthMask(GU_FALSE);
    sceGuClear(GU_COLOR_BUFFER_BIT | GU_DEPTH_BUFFER_BIT);
    sceGumMatrixMode(GU_PROJECTION); sceGumLoadIdentity(); sceGumPerspective(55.f, 16.f / 9.f, .2f, 80.f);
    sceGumMatrixMode(GU_VIEW); sceGumLoadIdentity();
    float ty = .95f;
    ScePspFVector3 eye = {sinf(yaw) * cosf(pitch) * dist, ty + sinf(pitch) * dist, cosf(yaw) * cosf(pitch) * dist}, at = {0, ty, 0}, up = {0, 1, 0};
    sceGumLookAt(&eye, &at, &up);
    sceGumMatrixMode(GU_MODEL); sceGumLoadIdentity(); sceGumUpdateMatrix();
    sceGuEnable(GU_FOG);

    // ground (untextured, vertex colours)
    sceGuDisable(GU_TEXTURE_2D); sceGuDisable(GU_BLEND); sceGuDisable(GU_ALPHA_TEST);
    { ScePspFMatrix4 g; skinPlace(&g, gx, 0, gz, 0); sceGuSetMatrix(GU_MODEL, &g); }
    sceGuDrawArray(GU_TRIANGLES, GU_COLOR_8888 | GU_VERTEX_32BITF | GU_TRANSFORM_3D, GN * GN * 6, 0, ground);

    // Homers (the crowd is a 5 x 5 grid, 2.2 m apart)
    unsigned d0 = sceKernelGetSystemTimeLow();
    for (int i = 0; i < n; i++) {
      int side = n == 1 ? 1 : n == 9 ? 3 : 5;
      float x = ((i % side) - side / 2) * 2.2f, z = ((i / side) - side / 2) * 2.2f;
      ScePspFMatrix4 w; skinPlace(&w, x, 0, z, 0); skinDraw(&pl[i], &w);
    }
    unsigned d1 = sceKernelGetSystemTimeLow();
    sceGuDepthMask(GU_TRUE);
    hudDraw();
    // shot mode: GE block transfer of the finished frame to RAM (PPSSPP downloads the framebuffer for it,
    // a plain CPU read of VRAM would see a stale copy in the hardware renderer)
    static unsigned *grab;
    int grabNow = nshots && shotF == 19;
    if (grabNow) {
      if (!grab) grab = memalign(64, BUF_W * SCR_H * 4);
      sceGuCopyImage(GU_PSM_8888, 0, 0, SCR_W, SCR_H, BUF_W, (void *)((unsigned)sceGeEdramGetAddr() + (unsigned)fbp0), 0, 0, BUF_W, grab);
      sceGuTexSync();
    }
    sceGuFinish();
    sceGuSync(0, 0);
    unsigned t4 = sceKernelGetSystemTimeLow();
    workMs = (t4 - t0) / 1000.f;
    float k = .05f; usUpd += ((u1 - u0) / (float)n - usUpd) * k; usDraw += ((d1 - d0) / (float)n - usDraw) * k;

    if (nshots) {
      if (grabNow) {                                  // pose held 20 frames: dump the finished frame
        sceKernelDcacheInvalidateRange(grab, BUF_W * SCR_H * 4);
        dumpFrame(grab, shot);
      }
      if (++shotF == 20) { shotF = 0; if (++shot >= nshots) sceKernelExitGame(); }
    }
    sceDisplayWaitVblankStart();
    fbp0 = sceGuSwapBuffers();

    frames++;
    if (t4 - acc >= 1000000) { fps = frames * 1e6f / (t4 - acc); frames = 0; acc = t4; }
    if (++hudTick >= 10 || nshots) {
      hudTick = 0; char s[96]; hudClear();
      snprintf(s, sizeof s, "HOMER TEST  FPS %4.1f  work %4.1f ms  homers %d", fps, workMs, n); hudLine(0, 0xffffffff, s);
      snprintf(s, sizeof s, "%2d/%d %s", clip + 1, skinClipCount(m), skinClipName(m, clip)); hudLine(1, 0xff80ffff, s);
      snprintf(s, sizeof s, "t %5.2f / %4.2f s  speed x%.3g %s", pl[0].t, skinClipLength(m, clip), speed, paused ? "PAUSED" : "");
      hudLine(2, 0xff80ffff, s);
      snprintf(s, sizeof s, "cpu/homer: anim %3.0f us  draw %3.0f us", usUpd, usDraw); hudLine(3, 0xffffffff, s);
      snprintf(s, sizeof s, "%s: %u verts %u draws  %u KB", m == m8 ? "homer.chr" : "homer_b4.chr", m->h->totalVerts, m->h->nBatches,
               m->h->size / 1024); hudLine(4, 0xffc0c0c0, s);
      if (nshots) { snprintf(s, sizeof s, "SHOT %d  %s t=%.3f", shot, shots[shot].clip, shots[shot].t); hudLine(6, 0xff40ffff, s); }
      hudLine(32, 0xffc0c0c0, "[]idle /\\walk Oran Xdash <->clips up/dn speed L/R zoom");
      hudLine(33, 0xffc0c0c0, "stick orbit  START pause  SELECT 1/9/25 homers");
    }
  }
  return 0;
}
