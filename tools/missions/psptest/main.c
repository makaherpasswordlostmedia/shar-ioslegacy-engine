/* SHAR mission runtime - standalone PSP test EBOOT.
 * Loads level01.msn .. level07.msn from the EBOOT folder, plays every mission of every level with the
 * fake engine's autopilot (same code as the Mac dry run), and measures on real hardware:
 *   - msn_open (validate) time per pack,
 *   - per-frame cost of msn_tick (+ autopilot) average / worst,
 *   - memory (pack size + runtime struct).
 * Writes the full level-1 flow + a summary to missions_psp.txt next to the EBOOT.
 * Screen: summary per level. X or HOME = exit. If a file "autoexit" is present, exits by itself. */
#include <pspkernel.h>
#include <pspdebug.h>
#include <pspctrl.h>
#include <psprtc.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <malloc.h>
#include "fake_engine.h"

PSP_MODULE_INFO("SHARMSN", 0, 1, 0);
PSP_MAIN_THREAD_ATTR(THREAD_ATTR_USER | THREAD_ATTR_VFPU);
PSP_HEAP_SIZE_KB(-1024);

static int exit_cb(int a, int b, void *c) { (void)a; (void)b; (void)c; sceKernelExitGame(); return 0; }
static int cb_thread(SceSize args, void *argp)
{
    int id = sceKernelCreateCallback("exit", exit_cb, NULL);
    (void)args; (void)argp;
    sceKernelRegisterExitCallback(id);
    sceKernelSleepThreadCB();
    return 0;
}

static FILE *logf;
static void to_log(void *ctx, const char *line) { (void)ctx; if (logf) { fputs(line, logf); fputc('\n', logf); } }
static void to_null(void *ctx, const char *line) { (void)ctx; (void)line; }

#define P(...) do { pspDebugScreenPrintf(__VA_ARGS__); if (logf) fprintf(logf, __VA_ARGS__); } while (0)

static void *load(const char *path, long *size)
{
    FILE *fp = fopen(path, "rb"); void *buf; long n;
    if (!fp) return NULL;
    fseek(fp, 0, SEEK_END); n = ftell(fp); fseek(fp, 0, SEEK_SET);
    buf = memalign(16, (size_t)n);
    if (buf && fread(buf, 1, (size_t)n, fp) != (size_t)n) { free(buf); buf = NULL; }
    fclose(fp);
    *size = n;
    return buf;
}

static MsnRuntime rt;
static Fake fk;

int main(void)
{
    int lv, all_ok = 1, autoexit = 0; FILE *t;
    SceUID th = sceKernelCreateThread("cb", cb_thread, 0x11, 0xFA0, 0, 0);
    if (th >= 0) sceKernelStartThread(th, 0, 0);
    pspDebugScreenInit();
    t = fopen("autoexit", "rb"); if (t) { autoexit = 1; fclose(t); }
    logf = fopen("missions_psp.txt", "w");
    P("SHAR mission runtime test (PSP)  runtime struct %u B\n\n", (unsigned)sizeof(MsnRuntime));
    for (lv = 1; lv <= 7; lv++) {
        char path[32], err[128]; long size = 0; void *buf; MsnFile f; FakeOpts o;
        uint8_t *trace; uint32_t c, visited = 0, structural = 0, unknown = 0;
        u32 t0, t1, worst = 0, sum = 0, ticks = 0;
        int rc, pass;
        snprintf(path, sizeof path, "level%02d.msn", lv);
        buf = load(path, &size);
        if (!buf) { P("L%d: %s missing\n", lv, path); all_ok = 0; continue; }
        t0 = sceKernelGetSystemTimeLow();
        rc = msn_open(&f, buf, (size_t)size, err, sizeof err);
        t1 = sceKernelGetSystemTimeLow();
        if (rc) { P("L%d: msn_open failed: %s\n", lv, err); all_ok = 0; free(buf); continue; }
        trace = calloc(f.ncmds, 1);
        /* pass 0: level 1 flow into the log (with printing); pass 1: timing without printing */
        for (pass = (lv == 1 ? 0 : 1); pass < 2; pass++) {
            memset(&o, 0, sizeof o); o.dt = 1.0f / 60.0f; o.bonus = 1; o.fail_test = 1;
            fake_init(&fk, &rt, &f, &o, pass == 0 ? to_log : to_null, NULL);
            fake_attach(&fk);
            rt.trace = trace;
            if (pass == 0) { rc = fake_run_level(&fk); continue; }
            /* timed run: same loop as fake_run_level but measuring each frame */
            {
                u32 a, b; uint32_t i; int guard = 0;
                a = sceKernelGetSystemTimeLow(); msn_level_start(&rt); b = sceKernelGetSystemTimeLow();
                sum += b - a; if (b - a > worst) worst = b - a;
                for (i = 0; ; ) {
                    while (rt.status != MSN_LEVEL_DONE && guard < 2000000) {
                        a = sceKernelGetSystemTimeLow();
                        if (fake_step(&fk) != 0) { guard = 2000000; break; }
                        b = sceKernelGetSystemTimeLow();
                        sum += b - a; if (b - a > worst) worst = b - a; ticks++; guard++;
                    }
                    for (; i < f.nmissions; i++) if (f.missions[i].flags & MSN_MF_BONUS) break;
                    if (i >= f.nmissions) break;
                    a = sceKernelGetSystemTimeLow(); msn_start_bonus(&rt, (int)i); b = sceKernelGetSystemTimeLow();
                    sum += b - a; if (b - a > worst) worst = b - a;
                    i++;
                }
                rc = guard >= 2000000 ? 1 : 0;
            }
        }
        for (c = 0; c < f.ncmds; c++) {
            if (msn_opinfo[f.cmds[c].op].route == 0) unknown++;
            if (trace[c]) visited++; else if (f.cmds[c].op == MSN_OP_CLOSEMISSION) structural++;
        }
        {
            int ok = !rc && !unknown && visited + structural == f.ncmds && fk.s.fail_test_ok && !fk.s.stuck;
            all_ok &= ok;
            P("L%d %s %ldKB open %.2fms  m%d st%d cmd %u/%u unk %u\n   frame avg %.1fus worst %.0fus (%lu frames)\n",
              lv, ok ? "OK  " : "FAIL", size / 1024, (t1 - t0) / 1000.0, fk.s.missions_done, fk.s.stages,
              (unsigned)(visited + structural), (unsigned)f.ncmds, (unsigned)unknown,
              ticks ? (double)sum / ticks : 0.0, (double)worst, (unsigned long)ticks);
        }
        free(trace); free(buf);
    }
    P("\n%s\n", all_ok ? "ALL LEVELS OK" : "SOME LEVELS FAILED");
    if (logf) { fclose(logf); logf = NULL; }
    pspDebugScreenPrintf("log: missions_psp.txt   X = exit\n");
    if (autoexit) { sceKernelDelayThread(1500000); sceKernelExitGame(); return 0; }
    for (;;) {
        SceCtrlData pad;
        sceCtrlReadBufferPositive(&pad, 1);
        if (pad.Buttons & PSP_CTRL_CROSS) break;
        sceKernelDelayThread(50000);
    }
    sceKernelExitGame();
    return 0;
}
