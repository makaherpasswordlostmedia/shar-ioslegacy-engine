/* Mac dry run of the mission runtime: loads a compiled level pack, plays every mission with the
 * fake engine's autopilot and prints the flow + coverage.
 *   dryrun build/missions/level01.msn [-v|-vv] [--bonus] [--fail-test] [--save-test] [--no-sound] [--own plowk_v] [--quiet] */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "fake_engine.h"

static int quiet;
static void out(void *ctx, const char *line) { (void)ctx; if (!quiet) puts(line); }

int main(int argc, char **argv)
{
    const char *path = NULL; FakeOpts o; int i; FILE *fp; long n; void *buf; char err[160];
    MsnFile f; static MsnRuntime rt; static Fake k; uint8_t *trace;
    uint32_t c, visited = 0, unknown = 0, structural = 0; unsigned long feat_calls[MSN_FEAT_COUNT] = { 0 };
    int rc; clock_t t0;
    memset(&o, 0, sizeof o); o.dt = 0.1f;
    for (i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "-v")) o.verbose = 1;
        else if (!strcmp(argv[i], "-vv")) o.verbose = 2;
        else if (!strcmp(argv[i], "--bonus")) o.bonus = 1;
        else if (!strcmp(argv[i], "--fail-test")) o.fail_test = 1;
        else if (!strcmp(argv[i], "--quiet")) quiet = 1;
        else if (!strcmp(argv[i], "--save-test")) o.save_test = 1;
        else if (!strcmp(argv[i], "--no-sound")) o.no_sound = 1;
        else if (!strcmp(argv[i], "--own") && i + 1 < argc && o.nown < 8) o.own[o.nown++] = argv[++i];
        else path = argv[i];
    }
    if (!path) { fprintf(stderr, "usage: dryrun levelNN.msn [-v|-vv] [--bonus] [--fail-test] [--save-test] [--own car] [--quiet]\n"); return 2; }
    fp = fopen(path, "rb");
    if (!fp) { perror(path); return 2; }
    fseek(fp, 0, SEEK_END); n = ftell(fp); fseek(fp, 0, SEEK_SET);
    buf = malloc((size_t)n);
    if (!buf || fread(buf, 1, (size_t)n, fp) != (size_t)n) { fprintf(stderr, "read failed\n"); return 2; }
    fclose(fp);
    t0 = clock();
    if (msn_open(&f, buf, (size_t)n, err, sizeof err) != 0) { fprintf(stderr, "msn_open: %s\n", err); return 1; }
    printf("pack %s: level %u, %u bytes, %u missions, %u stages, %u commands, %u locators, %u conversations (%u lines); open+validate %.3f ms\n",
           path, f.hdr->level, f.size, f.nmissions, f.nstages, f.ncmds, f.nlocs, f.nconvs, f.nclips,
           1000.0 * (double)(clock() - t0) / CLOCKS_PER_SEC);
    trace = calloc(f.ncmds, 1);
    fake_init(&k, &rt, &f, &o, out, NULL);
    fake_attach(&k);
    rt.trace = trace;
    t0 = clock();
    rc = fake_run_level(&k);
    {
        double ms = 1000.0 * (double)(clock() - t0) / CLOCKS_PER_SEC;
        printf("\nsimulated %.0f s of play in %lu ticks, %.1f ms CPU on this Mac (%.2f us/tick incl. printing)\n",
               k.s.sim_seconds, k.s.ticks, ms, k.s.ticks ? 1000.0 * ms / (double)k.s.ticks : 0.0);
    }
    /* coverage: every command of the pack must be known and (for scripted content) processed */
    for (c = 0; c < f.ncmds; c++) {
        const MsnCmd *cmd = &f.cmds[c];
        if (msn_opinfo[cmd->op].route == 0) unknown++;
        if (trace[c]) visited++;
        else if (cmd->op == MSN_OP_CLOSEMISSION) structural++;   /* end marker, consumed by the compiler */
    }
    for (c = 1; c < MSN_OP_COUNT; c++)
        if (msn_opinfo[c].route & MSN_ROUTE_ENG) feat_calls[msn_opinfo[c].feature] += rt.n_dispatch[c];
    printf("missions completed %d, stages entered %d, locked stages skipped %d, dialogues %d (%d audio lines), markers %d, items collected %d\n",
           k.s.missions_done, k.s.stages, k.s.skipped, k.s.dialogues, k.s.dialogue_lines, k.s.markers, k.s.collects);
    printf("failures %d, retries %d, stuck %d%s%s\n", k.s.fails, k.s.retries, k.s.stuck,
           o.fail_test ? (k.s.fail_test_ok ? ", fail-test OK" : ", fail-test NOT OK") : "",
           o.save_test ? (k.s.save_test_ok ? ", save-test OK" : ", save-test NOT OK") : "");
    printf("commands: %u in pack, %u processed, %u structural end markers, %u never reached, UNKNOWN %u\n",
           f.ncmds, visited, structural, f.ncmds - visited - structural, unknown);
    if (f.ncmds - visited - structural) {
        unsigned shown = 0;
        for (c = 0; c < f.ncmds && shown < 20; c++)
            if (!trace[c] && f.cmds[c].op != MSN_OP_CLOSEMISSION) {
                printf("   not reached: %s at %s:%u\n", msn_op_name(f.cmds[c].op), msn_str(&f, f.files[f.cmds[c].file]), f.cmds[c].line);
                shown++;
            }
    }
    {   /* adapter coverage: every engine command of the pack must be typed, pass-through or runtime */
        unsigned cnt[4] = { 0 }, op, nunsup = 0;
        static uint32_t per_op[MSN_OP_COUNT];
        memset(per_op, 0, sizeof per_op);
        for (c = 0; c < f.ncmds; c++) { per_op[f.cmds[c].op]++; cnt[msn_game_route(f.cmds[c].op)]++; }
        printf("commands by adapter route: typed %u, pass-through %u, runtime %u, UNSUPPORTED %u\n", cnt[MSN_GR_TYPED], cnt[MSN_GR_PASS], cnt[MSN_GR_RUNTIME], cnt[MSN_GR_NONE]);
        for (op = 1; op < MSN_OP_COUNT; op++)
            if (per_op[op] && msn_game_route(op) == MSN_GR_NONE) { printf("   unsupported: %s x%u\n", msn_op_name(op), per_op[op]); nunsup++; }
        printf("typed calls received by module:");
        for (op = 0; op < FK_NGROUP; op++) printf(" %s=%lu", fake_group_name[op], k.s.calls[op]);
        printf("\npower boxes smashed %d (tags activated %d), rewards unlocked %d\n", k.s.breaks, k.s.tags_activated, k.s.unlocks);
        if (nunsup) rc = 1;
    }
    printf("engine calls by feature:");
    for (c = 0; c < MSN_FEAT_COUNT; c++) if (feat_calls[c]) printf(" %s=%lu", msn_feature_name[c], feat_calls[c]);
    printf("\ndistinct opcodes processed: ");
    {
        unsigned d = 0;
        for (c = 1; c < MSN_OP_COUNT; c++) if (rt.n_dispatch[c]) d++;
        printf("%u\n", d);
    }
    printf("runtime struct %u bytes, pack %u bytes\n", (unsigned)sizeof(MsnRuntime), f.size);
    free(trace); free(buf);
    if (unknown || rc || k.s.stuck || (o.fail_test && !k.s.fail_test_ok) || (o.save_test && !k.s.save_test_ok)) { printf("RESULT: FAIL\n"); return 1; }
    printf("RESULT: OK\n");
    return 0;
}
