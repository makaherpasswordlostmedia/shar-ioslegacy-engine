/* Fake game for the mission system: implements the typed plug-in API (viewer/mission/msn_game.h) with a
 * tiny world model and an "autopilot" that completes every objective (teleports to targets, presses
 * action, finishes dialogue/FMV, breaks power boxes, wrecks targets, buys cars ...).
 * Used by the Mac dry run and the PSP test EBOOT. It is also the reference for how real modules plug in. */
#ifndef FAKE_ENGINE_H
#define FAKE_ENGINE_H
#include "../../../viewer/mission/msn_game.h"

#define FAKE_MAX_ENT 96

typedef struct FakeEnt {
    char name[32];
    MsnEntity e;
    int alive, is_vehicle;
    float t;
} FakeEnt;

typedef void (*FakePrint)(void *ctx, const char *line);

typedef struct FakeOpts {
    int verbose;          /* 0 flow, 1 + every typed call, 2 + timers */
    int fail_test;        /* 1: in the first stage with a timeout condition, idle until it fails, then retry */
    int bonus;            /* also run the bonus missions (started by walking up to the giver + action) */
    int save_test;        /* save progress mid-mission, re-init the runtime, resume, compare */
    int no_sound;         /* leave sound.dialogue / fx.fmv NULL: the adapter must auto-finish them */
    const char *own[8]; int nown;   /* cars/skins the player already owns (tests locked stages) */
    float dt;
} FakeOpts;

enum { FK_PLAYER, FK_CARS, FK_NPC, FK_NAV, FK_UI, FK_SOUND, FK_FX, FK_PROPS, FK_SHOP, FK_TRAFFIC, FK_FEATURE, FK_NGROUP };

typedef struct FakeStats {
    int missions_done, stages, fails, retries, skipped, dialogues, dialogue_lines, markers, collects, stuck;
    int breaks, tags_activated, unlocks;
    int fail_test_ok;     /* 1 = failed with the expected reason and resumed at the checkpoint */
    int save_test_ok;
    double sim_seconds;
    unsigned long ticks;
    unsigned long calls[FK_NGROUP];   /* typed calls received, by module */
    unsigned long events;
} FakeStats;

typedef struct Fake {
    MsnRuntime *rt;
    const MsnFile *f;
    MsnGame g;
    FakeOpts o;
    FakeStats s;
    FakePrint print; void *pctx;
    FakeEnt ent[FAKE_MAX_ENT]; int nent;
    MsnWorld w;
    char vehicle[32], default_car[32], interior[32];
    char owned[24][32]; int nowned;
    char brk[16][32]; int nbrk;          /* power boxes still standing (from props.item_show) */
    float obj_t; int last_stage_key;
    int fail_armed, fail_seen;
    int step_key; double stage_t; int save_done; uint8_t *trace_keep;
    int want_bonus;                      /* bonus mission the autopilot walks to (-1 none) */
    char line[512];
} Fake;

void fake_init(Fake *k, MsnRuntime *rt, const MsnFile *f, const FakeOpts *o, FakePrint print, void *pctx);
/* builds the MsnGameApi and installs it (msn_game_init -> msn_init) */
void fake_attach(Fake *k);
/* runs the whole level (story, then bonus missions if requested); returns 0 when everything completed */
int  fake_run_level(Fake *k);
/* one frame (autopilot + msn_game_tick + retry on failure); -1 = stuck */
int  fake_step(Fake *k);
void fake_printf(Fake *k, const char *fmt, ...);
extern const char *const fake_group_name[FK_NGROUP];

#endif
