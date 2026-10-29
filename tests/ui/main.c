// Standalone UI test (stage 7, audit phase F3 minimal HUD): the widescreen Scrooby HUD from
// build/ui.shr drawn over a still frame of level 1 (bg.raw) with animated values, the pause
// menu with RESET CAR and the main menu.  Does not touch the main engine.
//
// Buttons:  START    pause on/off (in the pause: UP/DOWN, X activates, START/O continue)
//           SELECT   next screen: HUD -> main menu        (main menu: UP/DOWN)
//           TRIANGLE message box on/off                   R+SELECT  timing line on/off
//           L/R      radar zoom out/in
// Files next to the EBOOT:
//   ui.shr     (required)  build/ui.shr
//   bg.raw     (optional)  480x272 RGBA8888 still frame of the level (tools: see docs/ui_integration.md)
//   autoshot   (optional)  scripted run for the emulator: 6 states, each dumps the exact 480x272
//              frame (GE block copy of the draw buffer) to shot_<name>.raw, logs "SHOT <name>" to
//              smoke.txt (tools/ppsspp_run.sh scenario mode), timings to ui_bench.txt, then exits.
//   radar.txt  (optional, with autoshot) lines "name x z heading": after the six states one HUD state per line with
//              the radar at that world point, shot_radar_<name>.raw (tests/ui/radar_clip.py: the map stays inside
//              the radar circle)
#include <pspkernel.h>
#include <pspdisplay.h>
#include <pspctrl.h>
#include <pspgu.h>
#include <pspge.h>
#include <psppower.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <malloc.h>
#include <math.h>
#include "../../viewer/ui.h"

PSP_MODULE_INFO("uitest", 0, 1, 0);
PSP_MAIN_THREAD_ATTR(THREAD_ATTR_USER | THREAD_ATTR_VFPU);
PSP_HEAP_SIZE_KB(-1024);

#define BUF_W 512
#define SCR_W 480
#define SCR_H 272
static unsigned int __attribute__((aligned(64))) list[65536];
static unsigned int __attribute__((aligned(64))) uilist[65536];
static int running = 1;

static int exitCb(int a, int b, void *c) { (void)a; (void)b; (void)c; running = 0; return 0; }
static int cbThread(SceSize a, void *b) {
  (void)a; (void)b;
  int id = sceKernelCreateCallback("exit", exitCb, NULL);
  sceKernelRegisterExitCallback(id);
  sceKernelSleepThreadCB();
  return 0;
}

static char dir[256];
static void pathOf(char *out, const char *name) { snprintf(out, 256, "%s%s", dir, name); }
static int fileExists(const char *name) {
  char p[256]; pathOf(p, name); SceUID f = sceIoOpen(p, PSP_O_RDONLY, 0);
  if (f < 0) return 0; sceIoClose(f); return 1;
}
static void appendText(const char *name, const char *s) {
  char p[256]; pathOf(p, name);
  SceUID f = sceIoOpen(p, PSP_O_WRONLY | PSP_O_CREAT | PSP_O_APPEND, 0777);
  if (f >= 0) { sceIoWrite(f, s, strlen(s)); sceIoClose(f); }
}

// plain stand-in when bg.raw is missing: sky gradient + checker ground (shows any stretching)
typedef struct { unsigned color; short x, y, z, pad; } V;
static void rect(int x0, int y0, int x1, int y1, unsigned top, unsigned bot) {
  V *v = (V *)sceGuGetMemory(4 * sizeof(V));
  v[0] = (V){top, (short)x0, (short)y0, 0, 0}; v[1] = (V){top, (short)x1, (short)y0, 0, 0};
  v[2] = (V){bot, (short)x0, (short)y1, 0, 0}; v[3] = (V){bot, (short)x1, (short)y1, 0, 0};
  sceGuDrawArray(GU_TRIANGLE_STRIP, GU_COLOR_8888 | GU_VERTEX_16BIT | GU_TRANSFORM_2D, 4, 0, v);
}
static void checker(void) {
  sceGuDisable(GU_TEXTURE_2D); sceGuDisable(GU_BLEND); sceGuShadeModel(GU_SMOOTH);
  rect(0, 0, SCR_W, 150, 0xffe6aa78, 0xffd2be96);
  for (int j = 0; j < 4; j++)
    for (int i = 0; i < 16; i++) {
      unsigned c = ((i + j) & 1) ? 0xff3c7a5a : 0xff366e51;
      rect(i * 30, 150 + j * 31, i * 30 + 30, 150 + j * 31 + 31, c, c);
    }
}

// state script (autoshot) --------------------------------------------------------------------
enum { S_DRIVE, S_DAMAGE, S_MESSAGE, S_PAUSE, S_PAUSE_RESET, S_MAIN, S_COUNT };
static const char *SNAME[S_COUNT] = {"hud_drive", "hud_damage", "hud_message", "pause", "pause_reset", "main_menu"};
#define STATE_FRAMES 90

#define MAX_RPOS 16
static char rname[MAX_RPOS][24];
static float rpos[MAX_RPOS][3];
static int nrpos;
static void loadRadarPos(void) {
  char p[256]; pathOf(p, "radar.txt");
  SceUID f = sceIoOpen(p, PSP_O_RDONLY, 0);
  if (f < 0) return;
  static char buf[2048];
  int n = sceIoRead(f, buf, sizeof buf - 1); sceIoClose(f);
  if (n <= 0) return;
  buf[n] = 0;
  for (char *line = buf; line && *line && nrpos < MAX_RPOS;) {
    char *nl = strchr(line, '\n'); if (nl) *nl = 0;
    if (sscanf(line, "%23s %f %f %f", rname[nrpos], &rpos[nrpos][0], &rpos[nrpos][1], &rpos[nrpos][2]) == 4) nrpos++;
    line = nl ? nl + 1 : NULL;
  }
}

int main(int argc, char **argv) {
  SceUID th = sceKernelCreateThread("cb", cbThread, 0x11, 0xFA0, 0, 0);
  if (th >= 0) sceKernelStartThread(th, 0, 0);
  scePowerSetClockFrequency(333, 333, 166);
  dir[0] = 0;
  if (argc > 0 && argv[0]) {
    strncpy(dir, argv[0], sizeof dir - 1);
    char *s = strrchr(dir, '/'); if (s) s[1] = 0; else dir[0] = 0;
  }
  char p[256];
  pathOf(p, "ui.shr");
  int rc = uiInit(p);
  int autoshot = fileExists("autoshot");

  // still frame of the level (480x272 RGBA8888), copied into the draw buffer by the GE each frame
  unsigned *bg = NULL;
  pathOf(p, "bg.raw");
  SceUID bf = sceIoOpen(p, PSP_O_RDONLY, 0);
  if (bf >= 0) {
    bg = (unsigned *)memalign(64, SCR_W * SCR_H * 4);
    if (bg && sceIoRead(bf, bg, SCR_W * SCR_H * 4) != SCR_W * SCR_H * 4) { free(bg); bg = NULL; }
    sceIoClose(bf);
    if (bg) sceKernelDcacheWritebackRange(bg, SCR_W * SCR_H * 4);
  }
  unsigned *grab = autoshot ? (unsigned *)memalign(64, BUF_W * SCR_H * 4) : NULL;

  // same buffer layout as main.c in 8888 mode (fb32): 2 colour buffers + 16-bit depth
  const unsigned FB = BUF_W * SCR_H * 4, ZB = BUF_W * SCR_H * 2;
  void *fbp0 = (void *)0, *fbp1 = (void *)FB, *zbp = (void *)(2 * FB);
  sceGuInit(); sceGuStart(GU_DIRECT, list);
  sceGuDrawBuffer(GU_PSM_8888, fbp0, BUF_W); sceGuDispBuffer(SCR_W, SCR_H, fbp1, BUF_W);
  sceGuDepthBuffer(zbp, BUF_W);
  sceGuOffset(2048 - SCR_W / 2, 2048 - SCR_H / 2); sceGuViewport(2048, 2048, SCR_W, SCR_H);
  sceGuScissor(0, 0, SCR_W, SCR_H); sceGuEnable(GU_SCISSOR_TEST);
  sceGuDisable(GU_DEPTH_TEST); sceGuDisable(GU_CULL_FACE);
  sceGuFinish(); sceGuSync(0, 0);
  sceDisplayWaitVblankStart(); sceGuDisplay(GU_TRUE);
  sceCtrlSetSamplingCycle(0); sceCtrlSetSamplingMode(PSP_CTRL_MODE_DIGITAL);

  // HUD textures -> VRAM right after the depth buffer (as docs/ui_integration.md does in main.c)
  int vramUsed = rc == 0 ? uiUseVram(2 * FB + ZB, 0x200000 - (2 * FB + ZB)) : 0;

  const float SX = 220.f, SZ = 172.f;              // level 1 spawn (engine coords)
  int mode = 0, msel = 5, dbg = 0, frame = 0, state = -1, msgOn = 0;
  unsigned prevBtn = 0;
  float zoom = 150.f, cpuUs = 0.f, geUs = 0.f;
  float sumCpu[S_COUNT] = {0}, sumGe[S_COUNT] = {0}, maxGe[S_COUNT] = {0}; int nSamp[S_COUNT] = {0};
  UiStats last[S_COUNT]; memset(last, 0, sizeof last);
  if (autoshot) { pathOf(p, "smoke.txt"); sceIoRemove(p); pathOf(p, "ui_bench.txt"); sceIoRemove(p); loadRadarPos(); }

  while (running) {
    SceCtrlData pad; sceCtrlPeekBufferPositive(&pad, 1);
    unsigned btn = pad.Buttons, hit = btn & ~prevBtn; prevBtn = btn;
    float t = frame / 60.f;

    if (autoshot) {                                   // scripted states, STATE_FRAMES each
      int s = frame / STATE_FRAMES;
      if (s >= S_COUNT + nrpos) break;
      if (s != state) {
        state = s;
        mode = s == S_MAIN ? 1 : 0;
        uiPause(s == S_PAUSE || s == S_PAUSE_RESET);
        if (s == S_PAUSE_RESET) uiPauseInput(PSP_CTRL_DOWN);          // cursor on RESET CAR
        if (s == S_MESSAGE || s == S_PAUSE || s == S_PAUSE_RESET) uiMessage("GET INTO THE VEHICLE", 12, 0.f);
        else uiMessage(NULL, 0, 0.f);
        msel = 5;
      }
    } else {
      if (uiPaused()) {
        int act = uiPauseInput(hit);
        if (act == UI_P_RESET_CAR) { uiSetDamage(0.f); }            // the engine: carPlace at spawn + repair
        if (act == UI_P_QUIT_GAME) running = 0;
      } else if (hit & PSP_CTRL_START && mode == 0) uiPause(1);
      else if (hit & PSP_CTRL_SELECT) { if (btn & PSP_CTRL_RTRIGGER) dbg = !dbg; else mode = !mode; }
      if (mode == 1) {
        int n = uiMenuCount(UI_MENU_MAIN);
        if (hit & PSP_CTRL_UP) msel = (msel + n - 1) % n;
        if (hit & PSP_CTRL_DOWN) msel = (msel + 1) % n;
      }
      if (hit & PSP_CTRL_TRIANGLE) { msgOn = !msgOn; uiMessage(msgOn ? "GET INTO THE VEHICLE" : NULL, 12, 0.f); }
      if (btn & PSP_CTRL_LTRIGGER) zoom *= 1.02f;
      if (btn & PSP_CTRL_RTRIGGER && !(btn & PSP_CTRL_SELECT)) zoom /= 1.02f;
    }

    // animated values (a drive around the spawn)
    uiRadarSetRange(zoom);
    if (autoshot && state >= S_COUNT) { const float *q = rpos[state - S_COUNT]; uiSetRadar(q[0], q[1], q[2]); }
    else uiSetRadar(SX + 20.f * sinf(t * 0.3f), SZ + 20.f * cosf(t * 0.3f), 1.5708f + 0.6f * sinf(t * 0.5f));
    uiSetSpeed(60.f + 40.f * sinf(t * 0.7f));
    uiSetHitAndRun(0.f, 0, t);                         // как main.c без наездов: пустая шкала, мигалка в покое
    uiSetCoins(state == S_DAMAGE ? 57 : 1234 + (int)(t * 3.f));
    if (autoshot) uiSetDamage(state == S_DAMAGE ? 0.65f : 0.f);
    else uiSetDamage(0.5f + 0.5f * sinf(t * 0.4f));
    if (state < 0) state = 0;

    // (1) background: the still level frame (or the checker)
    sceGuStart(GU_DIRECT, list);
    sceGuClearColor(0xff000000); sceGuClear(GU_COLOR_BUFFER_BIT);
    if (bg) sceGuCopyImage(GU_PSM_8888, 0, 0, SCR_W, SCR_H, SCR_W, bg, 0, 0, BUF_W,
                           (void *)((unsigned)sceGeEdramGetAddr() + (unsigned)fbp0));
    else checker();
    sceGuTexSync();
    sceGuFinish(); sceGuSync(0, 0);

    // (2) UI into a call list: CPU time of building it
    unsigned c0 = sceKernelGetSystemTimeLow();
    sceGuStart(GU_CALL, uilist);
    if (rc == 0) { if (mode == 1) uiDrawMenu(UI_MENU_MAIN, msel); else uiDraw(); }
    sceGuFinish();
    unsigned c1 = sceKernelGetSystemTimeLow();
    UiStats sts = uiLastStats();

    // (3) execute it alone: GE time of the UI
    unsigned g0 = sceKernelGetSystemTimeLow();
    sceGuStart(GU_DIRECT, list);
    sceGuCallList(uilist);
    sceGuFinish(); sceGuSync(0, 0);
    unsigned g1 = sceKernelGetSystemTimeLow();
    cpuUs = cpuUs * 0.9f + (c1 - c0) * 0.1f; geUs = geUs * 0.9f + (g1 - g0) * 0.1f;
    if (autoshot && state < S_COUNT && frame % STATE_FRAMES >= 30) {
      sumCpu[state] += c1 - c0; sumGe[state] += g1 - g0; nSamp[state]++;
      if (g1 - g0 > maxGe[state]) maxGe[state] = g1 - g0;
      last[state] = sts;
    }

    // (4) optional timing line (not in the screenshots)
    if (dbg || rc != 0) {
      char line[128];
      if (rc != 0) snprintf(line, sizeof line, "ui.shr not loaded (%d)", rc);
      else snprintf(line, sizeof line, "ui cpu %.0f us  ge %.0f us  draws %d binds %d px %d  vram %d KB",
                    cpuUs, geUs, sts.draws, sts.binds, sts.pixels, vramUsed / 1024);
      sceGuStart(GU_DIRECT, list);
      if (rc == 0) uiText(0, 4, SCR_H - 11, 0xffffffff, line);
      sceGuFinish(); sceGuSync(0, 0);
    }

    // (5) autoshot: exact 480x272 frame through a GE block copy (the emulator downloads it at 1x)
    if (autoshot && frame % STATE_FRAMES == STATE_FRAMES - 1 && grab) {
      sceGuStart(GU_DIRECT, list);
      sceGuCopyImage(GU_PSM_8888, 0, 0, SCR_W, SCR_H, BUF_W, (void *)((unsigned)sceGeEdramGetAddr() + (unsigned)fbp0),
                     0, 0, BUF_W, grab);
      sceGuTexSync();
      sceGuFinish(); sceGuSync(0, 0);
      sceKernelDcacheWritebackInvalidateRange(grab, BUF_W * SCR_H * 4);
      char sn[40];
      if (state < S_COUNT) snprintf(sn, sizeof sn, "%s", SNAME[state]);
      else snprintf(sn, sizeof sn, "radar_%s", rname[state - S_COUNT]);
      char name[64]; snprintf(name, sizeof name, "shot_%s.raw", sn);
      pathOf(p, name);
      SceUID f = sceIoOpen(p, PSP_O_WRONLY | PSP_O_CREAT | PSP_O_TRUNC, 0777);
      if (f >= 0) { for (int y = 0; y < SCR_H; y++) sceIoWrite(f, grab + y * BUF_W, SCR_W * 4); sceIoClose(f); }
      char s[96]; snprintf(s, sizeof s, "SHOT %s\n", sn); appendText("smoke.txt", s);
    }

    sceDisplayWaitVblankStart();
    fbp0 = sceGuSwapBuffers();
    frame++;
  }
  if (autoshot) {
    char s[256];
    for (int i = 0; i < S_COUNT; i++) {
      int n = nSamp[i] ? nSamp[i] : 1;
      snprintf(s, sizeof s, "%-12s cpu %5.0f us  ge avg %5.0f max %5.0f us  draws %2d binds %d verts %3d items %2d pixels %6d\n",
               SNAME[i], sumCpu[i] / n, sumGe[i] / n, maxGe[i], last[i].draws, last[i].binds, last[i].verts, last[i].items,
               last[i].pixels);
      appendText("ui_bench.txt", s);
    }
    snprintf(s, sizeof s, "vram %d bytes, bg %s\n", vramUsed, bg ? "bg.raw" : "checker"); appendText("ui_bench.txt", s);
    appendText("smoke.txt", "END\n");
  }
  uiShutdown();
  sceGuTerm();
  sceKernelExitGame();
  return 0;
}
