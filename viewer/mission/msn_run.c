/* Mission runtime state machine (pure C99). See msn.h for the model and the engine contract.
 *
 * Semantics follow the disc scripts; where the original behaviour lives in executable code we follow
 * the open reimplementation hit-and-run-web (MIT, src/campaign/engine.ts) and document the choice
 * in docs/missions.md ("assumptions"). */
#include <string.h>
#include <math.h>
#include "msn.h"
#ifndef MSN_BREAK_PARTIME
#define MSN_BREAK_PARTIME 0
#endif
#ifndef MSN_INTERIOR_ALIAS_OLD
#define MSN_INTERIOR_ALIAS_OLD 0
#endif

#define F (rt->f)

/* ------------------------------------------------------------------ helpers */
static const MsnMission *cur_mission(const MsnRuntime *rt) { return &F->missions[rt->cur]; }
static const MsnPhase *cur_phase(const MsnRuntime *rt)
{
    const MsnMission *m = cur_mission(rt);
    unsigned idx = rt->phase == 0 ? m->intro : m->main;
    return idx == MSN_NONE16 ? NULL : &F->phases[idx];
}
static float dist3(MsnVec3 a, MsnVec3 b)
{
    float dx = a.x - b.x, dy = a.y - b.y, dz = a.z - b.z;
    return sqrtf(dx * dx + dy * dy + dz * dz);
}
static MsnVec3 locpos(const MsnLoc *l) { MsnVec3 v; v.x = l->pos[0]; v.y = l->pos[1]; v.z = l->pos[2]; return v; }

static void emit(MsnRuntime *rt, MsnEvent *e)
{
    e->mission = rt->cur; e->stage = rt->stage;
    if (rt->host.event) rt->host.event(rt->host.user, e);
}
static void ev(MsnRuntime *rt, int type, int index, float value, const char *name, const char *text)
{
    MsnEvent e; memset(&e, 0, sizeof e);
    e.type = type; e.index = index; e.value = value; e.name = name; e.text = text;
    emit(rt, &e);
}

/* ------------------------------------------------------------------ registry */
static void reg_set(MsnRuntime *rt, int kind, const MsnCmd *c, int name_arg, int loc_arg, int extra_arg, int level)
{
    const MsnArg *a = msn_arg(F, c, name_arg), *l = msn_arg(F, c, loc_arg);
    int i;
    if (!a || (a->type != MSN_ARG_STR && a->type != MSN_ARG_BARE)) return;
    for (i = 0; i < rt->nreg; i++)
        if (rt->reg[i].kind == kind && msn_streq(msn_str(F, rt->reg[i].name), msn_str(F, a->v.s))) break;
    if (i == rt->nreg) {
        if (rt->nreg >= MSN_MAX_REG) return;
        rt->nreg++;
    }
    rt->reg[i].kind = (uint8_t)kind; rt->reg[i].name = a->v.s; rt->reg[i].level = (uint8_t)level;
    rt->reg[i].loc = l ? l->loc : 0;
    {
        const MsnArg *x = extra_arg >= 0 ? msn_arg(F, c, extra_arg) : NULL;
        rt->reg[i].extra = (x && (x->type == MSN_ARG_STR || x->type == MSN_ARG_BARE)) ? x->v.s : 0;
    }
}
static int reg_find(const MsnRuntime *rt, int kind, const char *name, const char *extra)
{
    int i;
    for (i = 0; i < rt->nreg; i++) {
        if (kind && rt->reg[i].kind != kind) continue;
        if (name && !msn_streq(msn_str(F, rt->reg[i].name), name)) continue;
        if (extra && !msn_streq(msn_str(F, rt->reg[i].extra), extra)) continue;
        return i;
    }
    return -1;
}
static const MsnLoc *reg_loc(const MsnRuntime *rt, int i) { return (i >= 0 && rt->reg[i].loc) ? &F->locs[rt->reg[i].loc - 1] : NULL; }
static void reg_clear_mission(MsnRuntime *rt)
{
    int i, n = 0;
    for (i = 0; i < rt->nreg; i++) if (rt->reg[i].level) rt->reg[n++] = rt->reg[i];
    rt->nreg = n;
}

/* ------------------------------------------------------------------ dispatch */
static void dispatch(MsnRuntime *rt, const MsnCmd *c, int when)
{
    const MsnOpInfo *info = &msn_opinfo[c->op];
    int level = when == MSN_AT_LEVEL || when == MSN_AT_LEVEL_INIT || when == MSN_AT_REWARDS;
    rt->n_dispatch[c->op]++;
    if (rt->trace) rt->trace[c - F->cmds] = 1;
    switch (c->op) {                                  /* registries (route BOTH) */
    case MSN_OP_ADDNPC:                  reg_set(rt, MSN_REG_NPC, c, 0, 1, 2, level); break;
    case MSN_OP_ADDAMBIENTCHARACTER:     reg_set(rt, MSN_REG_NPC, c, 0, 1, -1, 1); break;
    case MSN_OP_ADDNPCCHARACTERBONUSMISSION: reg_set(rt, MSN_REG_BONUS, c, 0, 2, 3, 1); break;
    case MSN_OP_ADDPURCHASECARREWARD:    reg_set(rt, MSN_REG_SELLER, c, 1, 3, 0, 1); break;
    case MSN_OP_ADDSTAGEVEHICLE:         reg_set(rt, MSN_REG_VEHICLE, c, 0, 1, 2, level); break;
    case MSN_OP_ADDCOLLECTIBLESTATEPROP: reg_set(rt, MSN_REG_PROP, c, 0, 1, -1, level); break;
    default: break;
    }
    if ((info->route & MSN_ROUTE_ENG) && rt->host.command) {
        MsnCall call;
        call.f = F; call.cmd = c; call.when = when;
        call.mission = level ? -1 : rt->cur; call.stage = level ? -1 : rt->stage;
        rt->host.command(rt->host.user, &call);
    }
}
static void dispatch_range(MsnRuntime *rt, uint32_t first, uint32_t count, int when)
{
    uint32_t i;
    for (i = 0; i < count; i++) dispatch(rt, &F->cmds[first + i], when);
}

/* ------------------------------------------------------------------ init / level */
void msn_init(MsnRuntime *rt, const MsnFile *f, const MsnHost *host)
{
    memset(rt, 0, sizeof *rt);
    rt->f = f;
    if (host) rt->host = *host;
    rt->delay_stage = 0.2f; rt->delay_stage_flourish = 0.8f; rt->delay_mission = 3.0f;
    rt->radius_car = 6.5f; rt->radius_foot = 2.6f; rt->talk_radius = MSN_TALK_R;   /* правка 345: было 3.0 (msn_talk_reach) */
    rt->cur = -1; rt->story = -1; rt->status = MSN_IDLE;
    rt->auto_bonus = 1;
}

static int next_story(const MsnRuntime *rt, int after)
{
    uint32_t i;
    for (i = (uint32_t)(after + 1); i < F->nmissions; i++) {
        const MsnMission *m = &F->missions[i];
        if (m->flags & (MSN_MF_BONUS | MSN_MF_NOSCRIPT)) continue;
        if (rt->completed & (1u << i)) continue;
        return (int)i;
    }
    return -1;
}

static void start_phase(MsnRuntime *rt, int restore);

void msn_level_start(MsnRuntime *rt)
{
    const MsnLevelInfo *L = F->level;
    uint32_t i;
    rt->cur = -1; rt->stage = -1;
    dispatch_range(rt, L->lvl_first, L->lvl_count, MSN_AT_LEVEL);
    dispatch_range(rt, L->init_first, L->init_count, MSN_AT_LEVEL_INIT);
    dispatch_range(rt, L->rew_first, L->rew_count, MSN_AT_REWARDS);
    for (i = 0; i < F->nmissions; i++) {
        const MsnMission *m = &F->missions[i];
        if ((m->flags & MSN_MF_BONUS) && m->bonus_npc != 0xFFFFFFFFu) {
            MsnEvent e; memset(&e, 0, sizeof e);
            e.type = MSN_EV_BONUS_AVAILABLE; e.index = (int)i;
            e.name = msn_arg_s(F, &F->cmds[m->bonus_npc], 0); e.name2 = msn_str(F, m->id);
            e.loc = msn_arg_loc(F, &F->cmds[m->bonus_npc], 2);
            if (rt->host.event) rt->host.event(rt->host.user, &e);
        }
    }
    {
        int s = next_story(rt, -1);
        if (s >= 0) msn_start_mission(rt, s, 0);
        else { rt->status = MSN_LEVEL_DONE; ev(rt, MSN_EV_LEVEL_COMPLETE, 0, 0, NULL, NULL); }
    }
}

/* ------------------------------------------------------------------ stage entry */
static void timer_event(MsnRuntime *rt)
{
    int sec = rt->timer_up ? (int)floorf(rt->remaining) : (int)ceilf(rt->remaining);
    if (sec != rt->timer_last) {
        rt->timer_last = sec;
        ev(rt, MSN_EV_TIMER, rt->timer_up, (float)sec, NULL, NULL);
    }
}

static MsnVec3 item_pos(const MsnRuntime *rt, int i)
{
    const MsnLoc *l;
    if (rt->released[i]) return rt->relpos[i];
    l = msn_arg_loc(F, rt->items[i], 0);
    if (l) return locpos(l);
    { MsnVec3 z = { 0, 0, 0 }; return z; }
}

/* delivery item without a drawable = a world object that must be broken (L1 m4 power boxes, as hit-and-run-web) */
static int item_breakable(const MsnRuntime *rt, int i)
{
    return rt->obj == MSN_OBJ_DELIVERY && msn_argc(rt->items[i]) == 1;
}

static int entity(MsnRuntime *rt, const char *name, MsnEntity *e)
{
    int r;
    memset(e, 0, sizeof *e); e->health = 1.0f; e->waypoint = -1;
    if (!name || !*name) return 0;
    if (rt->host.entity && rt->host.entity(rt->host.user, name, e)) return 1;
    r = reg_find(rt, 0, name, NULL);
    if (r >= 0 && reg_loc(rt, r)) { e->pos = locpos(reg_loc(rt, r)); return 2; }  /* only a position */
    return 0;
}

static int bonus_entity(MsnRuntime *rt, int mission, const char *name, MsnEntity *e)
{   /* the giver at his bonus spot (port, edit 180); fallback: by name */
    memset(e, 0, sizeof *e); e->health = 1.0f; e->waypoint = -1;
    if (rt->host.bonus_entity && rt->host.bonus_entity(rt->host.user, mission, name, e)) return 1;
    return entity(rt, name, e);
}

static void begin_objective(MsnRuntime *rt)
{
    const MsnStage *st = rt->st;
    MsnEvent e;
    rt->status = MSN_RUNNING;
    switch (st->obj) {
    case MSN_OBJ_DIALOGUE:
        memset(&e, 0, sizeof e); e.type = MSN_EV_DIALOGUE;
        if (rt->c_dialog) {
            e.name = msn_arg_s(F, rt->c_dialog, 0); e.name2 = msn_arg_s(F, rt->c_dialog, 1);
            e.text = msn_arg_s(F, rt->c_dialog, 2);
            e.conv = msn_find_conv(F, e.text, msn_str(F, cur_mission(rt)->id));
        }
        emit(rt, &e);
        break;
    case MSN_OBJ_FMV:
        ev(rt, MSN_EV_FMV, 0, 0, rt->c_fmv ? msn_arg_s(F, rt->c_fmv, 0) : "", NULL);
        break;
    case MSN_OBJ_RACE: case MSN_OBJ_DELIVERY: case MSN_OBJ_DUMP: {
        int i;
        if (st->obj != MSN_OBJ_DUMP)                 /* dump items appear when the target drops them (MSN_EV_DROP) */
            for (i = 0; i < rt->nitems; i++) {
                memset(&e, 0, sizeof e); e.type = MSN_EV_ITEM_SHOW; e.index = i;
                e.loc = msn_arg_loc(F, rt->items[i], 0); e.pos = item_pos(rt, i);
                e.name = msn_arg_s(F, rt->items[i], 1); e.name2 = msn_arg_s(F, rt->items[i], 0);
                e.value = item_breakable(rt, i) ? 1.0f : 0.0f;
                emit(rt, &e);
            }
        ev(rt, MSN_EV_ITEMS, 0, (float)(rt->nitems * (st->obj == MSN_OBJ_RACE ? rt->laps : 1)), NULL, NULL);
        break; }
    default: break;
    }
    {   /* initial marker */
        MsnVec3 p; MsnWorld w; memset(&w, 0, sizeof w);
        if (msn_nav_target(rt, &w, &p)) {
            memset(&e, 0, sizeof e); e.type = MSN_EV_MARKER; e.pos = p; e.index = st->nav;
            e.name = rt->c_dest ? msn_arg_s(F, rt->c_dest, 1) : "";
            e.loc = rt->c_dest ? msn_arg_loc(F, rt->c_dest, 0) : NULL;
            emit(rt, &e);
        }
    }
    if (rt->timer_on) { rt->timer_last = -99999; timer_event(rt); }
}

static void enter_stage(MsnRuntime *rt);

static void phase_done(MsnRuntime *rt);

static void enter_stage(MsnRuntime *rt)
{
    const MsnPhase *ph = cur_phase(rt);
    const MsnStage *st;
    uint32_t i;
    int had_timer = rt->timer_on, has_time = 0;
    float carry = rt->remaining;
    if (!ph || rt->stage >= ph->stage_count) { phase_done(rt); return; }
    st = &F->stages[ph->first_stage + rt->stage];
    /* locked stage: skipped when the car / costume is already owned (with the following buy stage) */
    if ((st->flags & MSN_SF_LOCKED) && rt->host.owns && rt->host.owns(rt->host.user, st->lock_kind, msn_str(F, st->lock_name))) {
        ev(rt, MSN_EV_STAGE_SKIPPED, st->lock_kind, 0, msn_str(F, st->lock_name), NULL);
        rt->stage++;
        if (rt->stage < ph->stage_count) {
            const MsnStage *nx = &F->stages[ph->first_stage + rt->stage];
            if ((nx->obj == MSN_OBJ_BUYCAR || nx->obj == MSN_OBJ_BUYSKIN) && msn_streq(msn_str(F, nx->obj_arg), msn_str(F, st->lock_name))) {
                ev(rt, MSN_EV_STAGE_SKIPPED, st->lock_kind, 0, msn_str(F, st->lock_name), NULL);
                rt->stage++;
            }
        }
        enter_stage(rt);
        return;
    }
    rt->st = st; rt->st_index = ph->first_stage + rt->stage; rt->obj = st->obj;
    rt->t_stage = 0; rt->out_time = rt->follow_time = rt->escape_time = rt->hit_cooldown = 0;
    rt->flag_dialogue = rt->flag_fmv = rt->flag_boss = rt->flag_cargo_lost = rt->items_changed = 0; rt->hit_vehicle = NULL;
    rt->c_dest = rt->c_target = rt->c_talk = rt->c_dialog = rt->c_fmv = rt->c_completion = rt->c_pickup_prop = NULL;
    rt->target = NULL; rt->objdist = 0; rt->duration = 0; rt->fee = 0; rt->laps = 1;
    rt->nitems = 0; rt->ncollected = 0; rt->lap = 0; rt->next_item = 0; rt->nbind = 0; rt->cd_count = 0;
    memset(rt->done, 0, sizeof rt->done); memset(rt->released, 0, sizeof rt->released);
    rt->timer_up = 0; rt->par = 0;
    /* scan stage commands once: objective parameters, timers, countdown */
    for (i = 0; i < st->cmd_count; i++) {
        const MsnCmd *c = &F->cmds[st->cmd_first + i];
        switch (c->op) {
        case MSN_OP_SETDESTINATION: if (!rt->c_dest) rt->c_dest = c; break;
        case MSN_OP_SETOBJTARGETVEHICLE: case MSN_OP_SETOBJTARGETBOSS: case MSN_OP_SETPICKUPTARGET:
            rt->c_target = c; rt->target = msn_arg_s(F, c, 0); break;
        case MSN_OP_SETTALKTOTARGET: rt->c_talk = c; rt->target = msn_arg_s(F, c, 0); break;
        case MSN_OP_SETDIALOGUEINFO: rt->c_dialog = c; break;
        case MSN_OP_SETFMVINFO: rt->c_fmv = c; break;
        case MSN_OP_SETCOMPLETIONDIALOG: rt->c_completion = c; break;
        case MSN_OP_SETOBJDISTANCE: rt->objdist = msn_arg_f(F, c, 0); break;
        case MSN_OP_SETDURATIONTIME: rt->duration = msn_arg_f(F, c, 0); break;
        case MSN_OP_SETCOINFEE: rt->fee = msn_arg_i(F, c, 0); break;
        case MSN_OP_SETRACELAPS: rt->laps = msn_arg_i(F, c, 0) > 0 ? msn_arg_i(F, c, 0) : 1; break;
        case MSN_OP_SETPARTIME: rt->par = msn_arg_f(F, c, 0); break;
        case MSN_OP_ADDCOLLECTIBLE: if (rt->nitems < MSN_MAX_ITEMS) rt->items[rt->nitems++] = c; break;
        case MSN_OP_BINDCOLLECTIBLETO:
            if (rt->nbind < MSN_MAX_ITEMS) { rt->bind_item[rt->nbind] = msn_arg_i(F, c, 0); rt->bind_wp[rt->nbind++] = msn_arg_i(F, c, 1); }
            break;
        case MSN_OP_SETSTAGETIME: rt->remaining = msn_arg_f(F, c, 0); has_time = 1; break;
        case MSN_OP_ADDSTAGETIME:
            rt->remaining = (had_timer || has_time ? rt->remaining : 0) + msn_arg_f(F, c, 0); has_time = 1; break;
        case MSN_OP_ADDTOCOUNTDOWNSEQUENCE: if (rt->cd_count < 12) rt->cd_cmds[rt->cd_count++] = c; break;
        default: break;
        }
    }
    if (st->flags & MSN_SF_ELAPSED) { rt->timer_up = 1; rt->remaining = 0; has_time = 1; }
    rt->timer_on = has_time;
    if (st->obj == MSN_OBJ_PICKUPITEM && rt->target) {       /* the prop is defined in setup or in the stage */
        const MsnPhase *ph2 = cur_phase(rt);
        uint32_t a, b;
        for (a = 0; a < 2 && !rt->c_pickup_prop; a++) {
            uint32_t first = a == 0 ? st->cmd_first : ph2->setup_first, n = a == 0 ? st->cmd_count : ph2->setup_count;
            for (b = 0; b < n; b++) {
                const MsnCmd *c = &F->cmds[first + b];
                if (c->op == MSN_OP_ADDCOLLECTIBLESTATEPROP && msn_streq(msn_arg_s(F, c, 0), rt->target)) { rt->c_pickup_prop = c; break; }
            }
        }
    }
    if ((st->flags & MSN_SF_CHECKPOINT) && !rt->restoring) {
        rt->cp_phase = rt->phase; rt->cp_stage = rt->stage;
        rt->cp_timer = had_timer; rt->cp_remaining = carry;     /* timer carried into the checkpoint stage */
        ev(rt, MSN_EV_CHECKPOINT, rt->stage, 0, NULL, NULL);
    }
    rt->restoring = 0;
    {
        MsnEvent e; memset(&e, 0, sizeof e);
        e.type = MSN_EV_STAGE_START; e.index = st->obj; e.text = msn_str(F, st->text); e.name = msn_str(F, st->icon);
        e.name2 = rt->target; e.value = rt->timer_on && !rt->timer_up ? rt->remaining : 0;
        emit(rt, &e);
    }
    for (i = 0; i < st->cmd_count; i++) {
        const MsnCmd *c = &F->cmds[st->cmd_first + i];
        if (!(msn_opinfo[c->op].flags & MSN_OPF_END)) dispatch(rt, c, MSN_AT_STAGE);
    }
    if (rt->cd_count > 0) {
        rt->status = MSN_COUNTDOWN; rt->cd_step = 0;
        rt->cd_left = msn_arg_f(F, rt->cd_cmds[0], 1) / 1000.0f;
        ev(rt, MSN_EV_COUNTDOWN, 0, rt->cd_left, NULL, msn_arg_s(F, rt->cd_cmds[0], 0));
        return;
    }
    begin_objective(rt);
}

static void start_phase(MsnRuntime *rt, int restore)
{
    const MsnPhase *ph = cur_phase(rt);
    MsnEvent e;
    if (!ph) { phase_done(rt); return; }
    memset(&e, 0, sizeof e); e.type = MSN_EV_PHASE_START; e.index = rt->phase; e.name = msn_str(F, ph->name);
    rt->stage = restore ? rt->stage : 0;
    emit(rt, &e);
    dispatch_range(rt, ph->load_first, ph->load_count, MSN_AT_LOAD);
    dispatch_range(rt, ph->setup_first, ph->setup_count, MSN_AT_SETUP);
    if (restore && rt->stage > 0) {
        int s; uint32_t i;
        for (s = 0; s < rt->stage && s < ph->stage_count; s++) {
            const MsnStage *st = &F->stages[ph->first_stage + s];
            for (i = 0; i < st->cmd_count; i++) {
                const MsnCmd *c = &F->cmds[st->cmd_first + i];
                if (msn_opinfo[c->op].flags & MSN_OPF_REPLAY) dispatch(rt, c, MSN_AT_REPLAY);
            }
        }
    }
    enter_stage(rt);
}

/* правка Роба 61: старт следующей миссии сразу после пройденной (next_mission) — «продолжение», игрока не переносят */
static int g_continuing;
void msn_start_mission(MsnRuntime *rt, int mission, int restore)
{
    const MsnMission *m;
    MsnEvent e;
    if (mission < 0 || (uint32_t)mission >= F->nmissions) return;
    m = &F->missions[mission];
    rt->cur = mission;
    if (!(m->flags & MSN_MF_BONUS)) rt->story = mission;
    rt->timer_on = 0; rt->remaining = 0; rt->cargo = 0; rt->fail = 0;
    memset(&e, 0, sizeof e); e.type = MSN_EV_MISSION_START; e.name = msn_str(F, m->id); e.text = msn_str(F, m->title);
    e.value = (m->flags & MSN_MF_BONUS) ? 1.0f : 0.0f; e.index = m->flags;
    e.name2 = g_continuing ? "continue" : NULL;
    rt->stage = 0;
    emit(rt, &e);
    if (m->flags & MSN_MF_NOSCRIPT) {              /* engine-coded mission (ismovie) or empty file on the disc */
        rt->status = MSN_MISSION_DONE; rt->delay = 0;
        rt->completed |= 1u << mission;
        ev(rt, MSN_EV_MISSION_COMPLETE, 0, 0, msn_str(F, m->id), msn_str(F, m->title));
        return;
    }
    if (restore) { rt->phase = rt->cp_phase; rt->stage = rt->cp_stage; rt->restoring = 1; }
    else { rt->phase = m->intro != MSN_NONE16 ? 0 : 1; rt->stage = 0; rt->cp_phase = rt->phase; rt->cp_stage = 0; }
    start_phase(rt, restore);
}

static void collect(MsnRuntime *rt, int i);

/* ------------------------------------------------------------------ completion / failure */
static void complete_stage(MsnRuntime *rt)
{
    const MsnStage *st = rt->st;
    MsnEvent e; uint32_t i;
    ev(rt, MSN_EV_MARKER_CLEAR, 0, 0, NULL, NULL);
    memset(&e, 0, sizeof e); e.type = MSN_EV_STAGE_COMPLETE; e.index = (st->flags & MSN_SF_SHOWCOMPLETE) ? 1 : 0;
    if (rt->c_completion) {
        e.text = msn_arg_s(F, rt->c_completion, 0); e.name2 = msn_arg_s(F, rt->c_completion, 1);
        e.conv = msn_find_conv(F, e.text, msn_str(F, cur_mission(rt)->id));
    }
    emit(rt, &e);
    for (i = 0; i < st->cmd_count; i++) {
        const MsnCmd *c = &F->cmds[st->cmd_first + i];
        if (msn_opinfo[c->op].flags & MSN_OPF_END) dispatch(rt, c, MSN_AT_STAGE_END);
    }
    rt->status = MSN_BETWEEN;
    rt->delay = (st->flags & MSN_SF_SHOWCOMPLETE) ? rt->delay_stage_flourish : rt->delay_stage;
    for (i = 0; i < st->cmd_count; i++) {   /* правка 122: SetFadeOut(t) — следующий этап не раньше, чем экран уйдёт в чёрное */
        const MsnCmd *c = &F->cmds[st->cmd_first + i];
        if (c->op == MSN_OP_SETFADEOUT) { float t = msn_arg_f(F, c, 0); if (t > rt->delay) rt->delay = t; }
    }
}

static void mission_done(MsnRuntime *rt)
{
    const MsnMission *m = cur_mission(rt);
    int quest = 0; float coins = 0;
    rt->completed |= 1u << rt->cur;
    if (m->flags & MSN_MF_BONUSMISSION) quest = 1;
    if (m->flags & MSN_MF_STREETRACE) {
        uint32_t i; int all = 1;
        for (i = 0; i < F->nmissions; i++)
            if ((F->missions[i].flags & MSN_MF_STREETRACE) && !(F->missions[i].flags & MSN_MF_NOSCRIPT) && !(rt->completed & (1u << i))) all = 0;
        if (all) quest = 2;
    }
    if (m->flags & MSN_MF_GAMBLE) {
        const MsnPhase *ph = &F->phases[m->main]; uint32_t s, i;
        quest = 3;
        for (s = 0; s < ph->stage_count; s++) {
            const MsnStage *st = &F->stages[ph->first_stage + s];
            for (i = 0; i < st->cmd_count; i++)
                if (F->cmds[st->cmd_first + i].op == MSN_OP_SETRACEENTERYFEE) coins = 2.0f * (float)msn_arg_i(F, &F->cmds[st->cmd_first + i], 0);
        }
    }
    ev(rt, MSN_EV_MARKER_CLEAR, 0, 0, NULL, NULL);
    ev(rt, MSN_EV_MISSION_COMPLETE, quest, coins, msn_str(F, m->id), msn_str(F, m->title));
    rt->status = MSN_MISSION_DONE; rt->delay = rt->delay_mission;
}

static void phase_done(MsnRuntime *rt)
{
    if (rt->phase == 0 && cur_mission(rt)->main != MSN_NONE16) {
        rt->phase = 1; rt->stage = 0; rt->cp_phase = 1; rt->cp_stage = 0; rt->timer_on = 0;
        start_phase(rt, 0);
        return;
    }
    mission_done(rt);
}

static void advance(MsnRuntime *rt)
{
    const MsnPhase *ph = cur_phase(rt);
    if ((rt->st->flags & MSN_SF_FINAL) && rt->phase == 1) { mission_done(rt); return; }
    rt->stage++;
    if (!ph || rt->stage >= ph->stage_count) { phase_done(rt); return; }
    enter_stage(rt);
}

static void next_mission(MsnRuntime *rt)
{
    const MsnMission *m = cur_mission(rt);
    int was_bonus = (m->flags & MSN_MF_BONUS) != 0;
    ev(rt, MSN_EV_CLEANUP, 0, 0, NULL, NULL);
    reg_clear_mission(rt);
    if (was_bonus) {
        if (rt->story >= 0 && !(rt->completed & (1u << rt->story))) { g_continuing = 1; msn_start_mission(rt, rt->story, 0); g_continuing = 0; return; }
        rt->status = MSN_LEVEL_DONE; rt->cur = -1;
        return;
    }
    if (m->flags & (MSN_MF_LEVELOVER | MSN_MF_GAMEOVER)) {
        rt->status = MSN_LEVEL_DONE;
        ev(rt, MSN_EV_LEVEL_COMPLETE, (m->flags & MSN_MF_GAMEOVER) ? 1 : 0, 0, NULL, NULL);
        return;
    }
    {
        int s = next_story(rt, rt->cur);
        if (s < 0) s = next_story(rt, -1);
        if (s >= 0) { g_continuing = 1; msn_start_mission(rt, s, 0); g_continuing = 0; return; }
    }
    rt->status = MSN_LEVEL_DONE;
    ev(rt, MSN_EV_LEVEL_COMPLETE, 0, 0, NULL, NULL);
}

/* SetNumValidFailureHints(n) of the running mission (setup of either phase), 0 = not set */
static int mission_hints(const MsnRuntime *rt)
{
    const MsnMission *m = cur_mission(rt); int k; uint32_t i;
    for (k = 0; k < 2; k++) {
        unsigned idx = k == 0 ? m->main : m->intro;
        const MsnPhase *ph;
        if (idx == MSN_NONE16) continue;
        ph = &F->phases[idx];
        for (i = 0; i < ph->setup_count; i++)
            if (F->cmds[ph->setup_first + i].op == MSN_OP_SETNUMVALIDFAILUREHINTS) return msn_arg_i(F, &F->cmds[ph->setup_first + i], 0);
    }
    return 0;
}

static void fail(MsnRuntime *rt, int reason)
{
    MsnEvent e; int n = mission_hints(rt), avail = 0;
    const char *hint = "";
    while (avail < 8 && *msn_fail_hint(F, reason, avail)) avail++;
    if (n <= 0 || n > avail) n = avail;                /* not set: rotate over every hint the bible has */
    if (n > 0) hint = msn_fail_hint(F, reason, rt->fail_count % n);
    rt->fail_count++;
    rt->status = MSN_FAILED; rt->fail = reason;
    ev(rt, MSN_EV_MARKER_CLEAR, 0, 0, NULL, NULL);
    memset(&e, 0, sizeof e); e.type = MSN_EV_MISSION_FAILED; e.index = reason;
    e.name = msn_fail_name[reason]; e.text = msn_fail_text(F, reason); e.name2 = hint;
    emit(rt, &e);
}

void msn_retry(MsnRuntime *rt, int from_start)
{
    const MsnMission *m;
    if (rt->cur < 0) return;
    m = cur_mission(rt);
    ev(rt, MSN_EV_CLEANUP, 0, 0, NULL, NULL);
    reg_clear_mission(rt);
    rt->timer_on = 0; rt->remaining = 0; rt->cargo = 0; rt->fail = 0;
    if (from_start) { rt->phase = m->intro != MSN_NONE16 ? 0 : 1; rt->stage = 0; rt->cp_phase = rt->phase; rt->cp_stage = 0; }
    else { rt->phase = rt->cp_phase; rt->stage = rt->cp_stage; rt->timer_on = rt->cp_timer; rt->remaining = rt->cp_remaining; rt->restoring = 1; }
    start_phase(rt, 1);
}

void msn_abort(MsnRuntime *rt)
{
    const MsnMission *m;
    if (rt->cur < 0) return;
    m = cur_mission(rt);
    ev(rt, MSN_EV_MARKER_CLEAR, 0, 0, NULL, NULL);
    ev(rt, MSN_EV_CLEANUP, 0, 0, NULL, NULL);
    reg_clear_mission(rt);
    if ((m->flags & MSN_MF_BONUS) && rt->story >= 0) { msn_start_mission(rt, rt->story, 0); return; }
    msn_start_mission(rt, rt->cur, 0);           /* back to free roam: the mission's intro phase from the start */
}

int msn_start_bonus(MsnRuntime *rt, int mission)
{
    if (mission < 0 || (uint32_t)mission >= F->nmissions || !(F->missions[mission].flags & MSN_MF_BONUS)) return 0;
    /* only from free roam: level done, or the story mission is still in the first stage of its intro */
    if (!(rt->status == MSN_LEVEL_DONE || (rt->cur == rt->story && rt->phase == 0 && rt->stage == 0 && rt->status == MSN_RUNNING)))
        return 0;
    ev(rt, MSN_EV_MARKER_CLEAR, 0, 0, NULL, NULL);
    ev(rt, MSN_EV_CLEANUP, 0, 0, NULL, NULL);
    reg_clear_mission(rt);
    msn_start_mission(rt, mission, 0);
    return 1;
}

int msn_free_roam(const MsnRuntime *rt)
{
    return rt->status == MSN_LEVEL_DONE ||
           (rt->cur >= 0 && rt->cur == rt->story && rt->phase == 0 && rt->stage == 0 && rt->status == MSN_RUNNING &&
            cur_mission(rt)->intro != MSN_NONE16);
}

/* Правка 345 (атлас миссий 332, Роб: «всё как в оригинале»). [PS2] своя pcsx2-twins без окна, 05.10 (agent345/ps2): Мардж (m0sd,
   SetTalkToTarget без 4-го аргумента) — △ на 1,310 м от её точки не открывает разговор, на 1,295 м открывает; с другой стороны
   (Гомер с −z) — 1,304 нет, 1,291 да: круг ~1,30 м вокруг персонажа. Апу (m0i, аргумент "3.0") — 3,022 нет, 2,959 да: аргумент
   = радиус. [диск] 4-й аргумент есть только у Апу и Продавца комиксов cbg ("3.0", за прилавком) и Мо ("2.0", за стойкой);
   радиус триггера персонажа 1.3 записан в данных у AddPurchaseCarReward (gil, zmale1) — то же число. [порт] до правки 3,0 + 1 м
   (бот закрывал разговор у Мардж за 0,2 с со старта). Бонус-персонаж (AddNPCCharacterBonusMission, аргумента радиуса нет) —
   тот же радиус по умолчанию ([правило порта]: у оригинала не замерен — Ральф sr3 на △ не ответил, вопрос близнецу) */
#ifndef MSN_TALK_OLD
#define MSN_TALK_OLD 0   /* сборка -DMSN_TALK_OLD=1 — прежнее с самого старта (боты, красный без флага) */
#endif
int msnTalkOld = MSN_TALK_OLD;
float msn_talk_reach(const MsnRuntime *rt, const MsnCmd *c_talk)
{
    float rad = msnTalkOld ? 3.0f : rt->talk_radius;
    if (c_talk && msn_argc(c_talk) > 3 && msn_arg_f(rt->f, c_talk, 3) > 0) rad = msn_arg_f(rt->f, c_talk, 3);
    return rad + (msnTalkOld ? 1.0f : 0.0f);
}

int msn_bonus_near(MsnRuntime *rt, const MsnWorld *w)
{
    uint32_t i;
    if (!w || !w->on_foot || w->interior || !msn_free_roam(rt)) return -1;
    for (i = 0; i < F->nmissions; i++) {
        const MsnMission *m = &F->missions[i];
        MsnEntity e;
        if (!(m->flags & MSN_MF_BONUS) || m->bonus_npc == 0xFFFFFFFFu || ((rt->completed & (1u << i)) && !rt->dev_bonus_replay)) continue;
        if (!bonus_entity(rt, (int)i, msn_arg_s(F, &F->cmds[m->bonus_npc], 0), &e)) continue;
        if (dist3(w->player, e.pos) < msn_talk_reach(rt, NULL)) return (int)i;
    }
    return -1;
}

void msn_notify(MsnRuntime *rt, int input, const char *name, int value)
{
    switch (input) {
    case MSN_IN_DIALOGUE_DONE: rt->flag_dialogue = 1; break;
    case MSN_IN_FMV_DONE: rt->flag_fmv = 1; break;
    case MSN_IN_BOSS_HIT: rt->flag_boss = 1; break;
    case MSN_IN_CARGO_LOST: rt->flag_cargo_lost = 1; rt->cargo = 0; break;
    case MSN_IN_BUSTED: if (rt->status == MSN_RUNNING) fail(rt, MSN_FAIL_HITNRUN); break;   /* данные: MISSION_FAILED_HIT_N_RUN */
    case MSN_IN_HIT_VEHICLE:
        if (name) { strncpy(rt->hitbuf, name, sizeof rt->hitbuf - 1); rt->hitbuf[sizeof rt->hitbuf - 1] = 0; rt->hit_vehicle = rt->hitbuf; }
        break;
    case MSN_IN_COLLECTED:
        if (rt->status == MSN_RUNNING && value >= 0 && value < rt->nitems && !rt->done[value]) { collect(rt, value); rt->items_changed = 1; }
        break;
    case MSN_IN_DESTROYED: {
        int i;
        if (!name || rt->status != MSN_RUNNING) break;
        if ((name[0] == 'P' || name[0] == 'p') && (name[1] == 'P' || name[1] == 'p') && name[2] == '_') name += 3;
        for (i = 0; i < rt->nitems; i++) {
            const char *n = msn_arg_s(F, rt->items[i], 0);
            if ((n[0] == 'P' || n[0] == 'p') && (n[1] == 'P' || n[1] == 'p') && n[2] == '_') n += 3;
            if (!rt->done[i] && msn_streq(n, name)) { collect(rt, i); rt->items_changed = 1; break; }
        }
        break; }
    default: break;
    }
}

/* ------------------------------------------------------------------ navigation */
static const MsnLoc *seller_for(MsnRuntime *rt, const char *item)
{
    const MsnLevelInfo *L = F->level; uint32_t i;
    for (i = 0; i < L->rew_count; i++) {
        const MsnCmd *c = &F->cmds[L->rew_first + i];
        if (msn_streq(msn_arg_s(F, c, 0), item) && msn_argc(c) > 6) {
            int r = reg_find(rt, MSN_REG_SELLER, NULL, msn_arg_s(F, c, 6));
            return reg_loc(rt, r);
        }
    }
    return NULL;
}

/* Имя продавца этапа «купи» (AddPurchaseCarReward: магазин, продавец, ...) по магазину этапа; NULL — нет. Продавец уходит по маршруту AddPurchaseCarNPCWaypoint и стоит у его конца
   (L1: Барни barney_loc -> barney_walk1, 9,8 м), △ — у него самого; метка у локатора вела туда, где его уже нет. */
static const char *seller_npc_for(MsnRuntime *rt, const char *item)
{
    const MsnLevelInfo *L = F->level; uint32_t i;
    for (i = 0; i < L->rew_count; i++) {
        const MsnCmd *c = &F->cmds[L->rew_first + i];
        if (msn_streq(msn_arg_s(F, c, 0), item) && msn_argc(c) > 6) {   /* BindReward: цена и магазин (arg 6); продавец реестра — по магазину, имя реестра = персонаж */
            int r = reg_find(rt, MSN_REG_SELLER, NULL, msn_arg_s(F, c, 6));
            return r >= 0 ? msn_str(F, rt->reg[r].name) : NULL;
        }
    }
    return NULL;
}
#ifndef MSN_BUYMARK_OLD
#define MSN_BUYMARK_OLD 0   /* =1 — метка покупки на локаторе продавца, как раньше */
#endif

static int nav(MsnRuntime *rt, const MsnWorld *w, MsnVec3 *out, const MsnLoc **lout)
{
    MsnEntity e; const MsnLoc *l = NULL; int i, best = -1; float bd = 1e30f;
    if (lout) *lout = NULL;
    if (!rt->st || rt->status == MSN_IDLE || rt->status == MSN_FAILED || rt->status == MSN_LEVEL_DONE) return 0;
    switch (rt->obj) {
    case MSN_OBJ_GOTO: case MSN_OBJ_INTERIOR: case MSN_OBJ_GOOUTSIDE:
        l = rt->c_dest ? msn_arg_loc(F, rt->c_dest, 0) : NULL; break;
    case MSN_OBJ_TALKTO: case MSN_OBJ_FOLLOW: case MSN_OBJ_LOSETAIL: case MSN_OBJ_DESTROY: case MSN_OBJ_DESTROYBOSS:
        if (entity(rt, rt->target, &e)) { *out = e.pos; return 1; }
        return 0;
    case MSN_OBJ_GETIN:
        if (rt->target && !msn_streq(rt->target, "current") && !msn_streq(rt->target, "default") && entity(rt, rt->target, &e)) { *out = e.pos; return 1; }
        return 0;
    case MSN_OBJ_PICKUPITEM:
        l = rt->c_pickup_prop ? msn_arg_loc(F, rt->c_pickup_prop, 1) : NULL; break;
    case MSN_OBJ_BUYCAR: case MSN_OBJ_BUYSKIN:
#ifndef MSN_BUYSKIN_MARK_OLD
        if (rt->obj == MSN_OBJ_BUYSKIN) {   /* костюмы продаёт гардероб в комнате, не NPC: метка к ближайшему (в комнате — к его двери), не прежняя метка этапа */
            if (rt->host.skin_spot && rt->host.skin_spot(rt->host.user, out)) return 1;
            return 0;
        }
#endif
        if (!MSN_BUYMARK_OLD) {   /* метка едет к самому продавцу (как у TALKTO), пока он есть в мире; иначе локатор */
            const char *sn = seller_npc_for(rt, msn_str(F, rt->st->obj_arg));
            if (sn && entity(rt, sn, &e)) { *out = e.pos; return 1; }
        }
        l = seller_for(rt, msn_str(F, rt->st->obj_arg)); break;
    case MSN_OBJ_COINS: {
        int r = reg_find(rt, MSN_REG_BONUS, NULL, msn_str(F, cur_mission(rt)->id));
        l = reg_loc(rt, r); break; }
    case MSN_OBJ_RACE:
        if (rt->next_item < rt->nitems) {
            *out = item_pos(rt, rt->next_item);
            if (lout) *lout = msn_arg_loc(F, rt->items[rt->next_item], 0);
            return 1;
        }
        return 0;
    case MSN_OBJ_DELIVERY: case MSN_OBJ_DUMP:
        for (i = 0; i < rt->nitems; i++) {
            float d;
            if (rt->done[i] || (rt->obj == MSN_OBJ_DUMP && !rt->released[i])) continue;
            d = w ? dist3(w->player, item_pos(rt, i)) : (float)i;
            if (d < bd) { bd = d; best = i; }
        }
        if (best >= 0) {
            *out = item_pos(rt, best);
            if (lout && !rt->released[best]) *lout = msn_arg_loc(F, rt->items[best], 0);
            return 1;
        }
        if (rt->obj == MSN_OBJ_DUMP && entity(rt, rt->target, &e)) { *out = e.pos; return 1; }
        return 0;
    default: return 0;
    }
    if (!l) return 0;
    *out = locpos(l);
    if (lout) *lout = l;
    return 1;
}

int msn_nav_target(MsnRuntime *rt, const MsnWorld *w, MsnVec3 *out) { return nav(rt, w, out, NULL); }

const MsnLoc *msn_nav_locator(MsnRuntime *rt, const MsnWorld *w)
{
    MsnVec3 p; const MsnLoc *l = NULL;
    nav(rt, w, &p, &l);
    return l;
}

/* ------------------------------------------------------------------ per-frame */
static int vehicle_health(MsnRuntime *rt, const MsnWorld *w, const char *name, float *h)
{
    MsnEntity e;
    if (!name || !*name || msn_streq(name, "current") || msn_streq(name, "default") || (w->vehicle && msn_streq(name, w->vehicle))) {
        *h = w->vehicle_health; return 1;
    }
    if (entity(rt, name, &e) == 1) { *h = e.health; return 1; }
    return 0;
}

static int check_conditions(MsnRuntime *rt, const MsnWorld *w, float dt)
{
    const MsnStage *st = rt->st;
    int k;
    /* ставка gr1: UseElapsedTime + SetParTime 195 — опоздал, провал (ставка пропала). MSN_BREAK_PARTIME=1 — красный контроль
       tests/shop (часть race 30.09): без проверки пар-времени опоздавший забирает выигрыш */
    if (!MSN_BREAK_PARTIME && rt->timer_on && rt->timer_up && rt->par > 0 && rt->remaining > rt->par && msn_streq(msn_str(F, st->obj_arg), "gamble"))
        return MSN_FAIL_PARTIME;
    for (k = 0; k < st->ncond; k++) {
        const MsnCond *cd = &F->conds[st->cond_first + k];
        const char *target = NULL; float minh = 0.0f, ctime = 10.0f, fmin = 0, fmax = 150.0f; int pos = 1, hasmin = 0;
        uint32_t i;
        for (i = 0; i < cd->cmd_count; i++) {
            const MsnCmd *c = &F->cmds[cd->cmd_first + i];
            switch (c->op) {
            case MSN_OP_SETCONDTARGETVEHICLE: target = msn_arg_s(F, c, 0); break;
            case MSN_OP_SETCONDMINHEALTH: minh = msn_arg_f(F, c, 0); hasmin = 1; break;
            case MSN_OP_SETCONDTIME: ctime = msn_arg_f(F, c, 0) / 1000.0f; break;
            case MSN_OP_SETFOLLOWDISTANCES: fmin = msn_arg_f(F, c, 0); fmax = msn_arg_f(F, c, 1); break;
            case MSN_OP_SETCONDITIONPOSITION: pos = msn_arg_i(F, c, 0); break;
            default: break;
            }
        }
        (void)hasmin;
        switch (cd->type) {
        case MSN_COND_TIMEOUT:
            if (rt->timer_on && !rt->timer_up && rt->remaining <= 0) return MSN_FAIL_TIMEOUT;
            break;
        case MSN_COND_OUTOFVEHICLE:
            rt->out_time = w->on_foot ? rt->out_time + dt : 0;
            if (rt->out_time >= ctime) return MSN_FAIL_OUTOFVEHICLE;
            break;
        case MSN_COND_DAMAGE: {
            float h;
            if (vehicle_health(rt, w, target, &h) && h <= minh + 1e-6f) return MSN_FAIL_DAMAGE;
            break; }
        case MSN_COND_POSITION: {
            int r, ahead = 0; MsnEntity e;
            for (r = 0; r < rt->nreg; r++)
                if (rt->reg[r].kind == MSN_REG_VEHICLE && !rt->reg[r].level &&
                    entity(rt, msn_str(F, rt->reg[r].name), &e) == 1 && e.finished) ahead++;
            if (ahead >= pos) return MSN_FAIL_POSITION;
            break; }
        case MSN_COND_RACE: {
            MsnEntity e;
            if (target && entity(rt, target, &e) == 1 && e.finished) return MSN_FAIL_RACE;
            break; }
        case MSN_COND_FOLLOWDISTANCE: {
            MsnEntity e;
            if (target && entity(rt, target, &e) == 1) {
                float d = dist3(w->player, e.pos);
                rt->follow_time = (d > fmax || (fmin > 0 && d < fmin)) ? rt->follow_time + dt : 0;
                if (rt->follow_time > 1.0f) return MSN_FAIL_FOLLOWDISTANCE;
            }
            break; }
        case MSN_COND_KEEPBARREL:
            if (rt->flag_cargo_lost) return MSN_FAIL_KEEPBARREL;
            break;
        default: break;
        }
    }
    return 0;
}

static void collect(MsnRuntime *rt, int i)
{
    MsnEvent e; memset(&e, 0, sizeof e);
    rt->done[i] = 1; rt->ncollected++;
    e.type = MSN_EV_COLLECT; e.index = i; e.loc = msn_arg_loc(F, rt->items[i], 0); e.pos = item_pos(rt, i);
    e.name = msn_arg_s(F, rt->items[i], 1); e.name2 = msn_arg_s(F, rt->items[i], 2);
    emit(rt, &e);
}

static int check_objective(MsnRuntime *rt, const MsnWorld *w, float dt)
{
    const MsnStage *st = rt->st;
    MsnEntity e;
    float r = w->on_foot ? rt->radius_foot : rt->radius_car;
    switch (st->obj) {
    case MSN_OBJ_GOTO: {
        const MsnLoc *l = rt->c_dest ? msn_arg_loc(F, rt->c_dest, 0) : NULL;
        if (!l) return 0;
        if (!msn_loc_contains(F, l, w->player, r)) return 0;
        return (st->flags & MSN_SF_MUSTACTION) ? w->action : 1; }
    case MSN_OBJ_GETIN:
        if (w->on_foot) return 0;
        return !rt->target || !*rt->target || msn_streq(rt->target, "current") || msn_streq(rt->target, "default") ||
               msn_streq(rt->target, w->vehicle);
    case MSN_OBJ_TALKTO: {
        if (!w->on_foot || !w->action || !entity(rt, rt->target, &e)) return 0;
        return dist3(w->player, e.pos) < msn_talk_reach(rt, rt->c_talk); }   /* правка 345 */
    case MSN_OBJ_DIALOGUE: return rt->flag_dialogue;
    case MSN_OBJ_FMV: return rt->flag_fmv;
    case MSN_OBJ_TIMER: return rt->t_stage >= rt->duration;
    case MSN_OBJ_INTERIOR: {
        const char *want = rt->c_dest ? msn_arg_s(F, rt->c_dest, 0) : "";
        if (!w->interior) return 0;
        if (msn_streq(w->interior, want)) return 1;
        /* Disc doors use full resource names; mission destinations use script aliases. */
        if (!MSN_INTERIOR_ALIAS_OLD && ((msn_streq(w->interior, "AndroidsDungeon") && msn_streq(want, "Android")) ||
            (msn_streq(w->interior, "Moes") && strncmp(want, "moe", 3) == 0 &&
             (!want[3] || (want[3] >= '0' && want[3] <= '9'))))) return 1;
        {   /* "moe1" (scripts) vs "moe" (door data) */
            size_t n = strlen(w->interior);
            return n > 0 && strncmp(want, w->interior, n) == 0 && want[n] >= '0' && want[n] <= '9';
        } }
    case MSN_OBJ_GOOUTSIDE: return w->interior == NULL;
    case MSN_OBJ_FOLLOW:
        if (entity(rt, rt->target, &e) != 1 || !e.finished) return 0;
        return rt->objdist <= 0 || dist3(w->player, e.pos) < rt->objdist;
    case MSN_OBJ_LOSETAIL: {
        float range = rt->objdist > 0 ? rt->objdist : 150.0f;
        if (entity(rt, rt->target, &e) != 1) return 0;
        rt->escape_time = dist3(w->player, e.pos) > range ? rt->escape_time + dt : 0;
        return rt->escape_time >= 1.0f; }
    case MSN_OBJ_DESTROY:
        return entity(rt, rt->target, &e) == 1 && e.health <= 0.0f;
    case MSN_OBJ_PICKUPITEM: {
        const MsnLoc *l = rt->c_pickup_prop ? msn_arg_loc(F, rt->c_pickup_prop, 1) : NULL;
        if (w->on_foot || !l || dist3(w->player, locpos(l)) > 5.0f) return 0;
        rt->cargo = 1; rt->flag_cargo_lost = 0; return 1; }
    case MSN_OBJ_DESTROYBOSS: return rt->flag_boss;
    case MSN_OBJ_BUYCAR: case MSN_OBJ_BUYSKIN:
        return rt->host.owns && rt->host.owns(rt->host.user, st->obj == MSN_OBJ_BUYCAR ? MSN_OWN_CAR : MSN_OWN_SKIN, msn_str(F, st->obj_arg));
    case MSN_OBJ_COINS:
        if (w->action && w->coins >= rt->fee) { ev(rt, MSN_EV_PAY, 0, (float)rt->fee, NULL, NULL); return 1; }
        return 0;
    case MSN_OBJ_DUMMY: return 1;
    case MSN_OBJ_RACE: {
        int i = rt->next_item;
        if (i < rt->nitems && msn_loc_contains(F, msn_arg_loc(F, rt->items[i], 0), w->player, r)) {
            collect(rt, i);
            rt->next_item++;
            if (rt->next_item >= rt->nitems) {
                rt->lap++;
                if (rt->lap >= rt->laps) return 1;
                rt->next_item = 0; memset(rt->done, 0, sizeof rt->done);
            }
            ev(rt, MSN_EV_ITEMS, rt->lap * rt->nitems + rt->next_item, (float)(rt->nitems * rt->laps), NULL, NULL);
        }
        return 0; }
    case MSN_OBJ_DELIVERY: case MSN_OBJ_DUMP: {
        int i, got = 0;
        if (st->obj == MSN_OBJ_DUMP && entity(rt, rt->target, &e) == 1) {
            int b;
            for (b = 0; b < rt->nbind; b++) {         /* BindCollectibleTo(item, waypoint) */
                int it = rt->bind_item[b];
                /* entity.waypoint is the last passed index, not the next target. */
                if (it >= 0 && it < rt->nitems && !rt->released[it] && e.waypoint >= rt->bind_wp[b]) {
                    MsnEvent d; memset(&d, 0, sizeof d);
                    rt->released[it] = 1; rt->relpos[it] = e.pos;
                    d.type = MSN_EV_DROP; d.index = it; d.pos = e.pos; emit(rt, &d);
                }
            }
            if (rt->nbind == 0 && rt->hit_vehicle && msn_streq(rt->hit_vehicle, rt->target) && rt->hit_cooldown <= 0) {
                for (i = 0; i < rt->nitems; i++) if (!rt->released[i] && !rt->done[i]) break;
                if (i < rt->nitems) {
                    MsnEvent d; memset(&d, 0, sizeof d);
                    rt->released[i] = 1; rt->relpos[i] = e.pos; rt->hit_cooldown = 1.5f;
                    d.type = MSN_EV_DROP; d.index = i; d.pos = e.pos; emit(rt, &d);
                }
            }
        }
        rt->hit_vehicle = NULL;
        for (i = 0; i < rt->nitems; i++) {
            if (rt->done[i] || item_breakable(rt, i)) continue;      /* breakables: msn_notify(MSN_IN_DESTROYED) */
            if (st->obj == MSN_OBJ_DUMP && !rt->released[i]) continue;
            if (rt->released[i] ? dist3(w->player, rt->relpos[i]) < r
                                : msn_loc_contains(F, msn_arg_loc(F, rt->items[i], 0), w->player, r)) {
                collect(rt, i); got = 1;
            }
        }
        if (got || rt->items_changed) ev(rt, MSN_EV_ITEMS, rt->ncollected, (float)rt->nitems, NULL, NULL);
        rt->items_changed = 0;
        return rt->nitems > 0 && rt->ncollected >= rt->nitems; }
    default: return 0;
    }
}

void msn_tick(MsnRuntime *rt, float dt, const MsnWorld *w)
{
    int reason;
    if (rt->auto_bonus && w->action) {               /* free roam: talk to a bonus giver -> its mission */
        int b = msn_bonus_near(rt, w);
        if (b >= 0 && msn_start_bonus(rt, b)) return;
    }
    switch (rt->status) {
    case MSN_BETWEEN:
        rt->delay -= dt;
        if (rt->delay <= 0) advance(rt);
        return;
    case MSN_MISSION_DONE:
        rt->delay -= dt;
        if (rt->delay <= 0) next_mission(rt);
        return;
    case MSN_COUNTDOWN:
        rt->cd_left -= dt;
        if (rt->cd_left <= 0) {
            rt->cd_step++;
            if (rt->cd_step >= rt->cd_count) { begin_objective(rt); return; }
            rt->cd_left = msn_arg_f(F, rt->cd_cmds[rt->cd_step], 1) / 1000.0f;
            ev(rt, MSN_EV_COUNTDOWN, rt->cd_step, rt->cd_left, NULL, msn_arg_s(F, rt->cd_cmds[rt->cd_step], 0));
        }
        return;
    case MSN_RUNNING: break;
    default: return;
    }
    rt->t_stage += dt;
    if (rt->hit_cooldown > 0) rt->hit_cooldown -= dt;
    if (rt->timer_on && rt->obj != MSN_OBJ_DIALOGUE && rt->obj != MSN_OBJ_FMV) {
        rt->remaining += rt->timer_up ? dt : -dt;
        timer_event(rt);
    }
    if (rt->obj != MSN_OBJ_DIALOGUE && rt->obj != MSN_OBJ_FMV) {
        reason = check_conditions(rt, w, dt);
        if (reason) { fail(rt, reason); return; }
    }
    if (check_objective(rt, w, dt)) complete_stage(rt);
}

/* ------------------------------------------------------------------ info / save */
void msn_objective_info(const MsnRuntime *rt, MsnObjInfo *o)
{
    memset(o, 0, sizeof *o);
    o->mission = rt->cur; o->phase = rt->phase; o->stage = rt->stage;
    if (rt->cur < 0 || !rt->st) return;
    o->mission_id = msn_str(F, F->missions[rt->cur].id);
    o->obj = rt->obj; o->flags = rt->st->flags; o->nav = rt->st->nav;
    o->text = msn_str(F, rt->st->text); o->icon = msn_str(F, rt->st->icon); o->target = rt->target;
    o->arg = msn_str(F, rt->st->obj_arg);
    o->items_total = rt->nitems; o->items_done = rt->ncollected; o->lap = rt->lap; o->laps = rt->laps;
    o->remaining = rt->remaining; o->timer_on = rt->timer_on; o->timer_up = rt->timer_up;
    o->need_action = (rt->st->flags & MSN_SF_MUSTACTION) || rt->obj == MSN_OBJ_TALKTO || rt->obj == MSN_OBJ_COINS;
    o->dest = rt->c_dest ? msn_arg_s(F, rt->c_dest, 0) : NULL;
    o->need_on_foot = rt->obj == MSN_OBJ_TALKTO;
}

void msn_get_progress(const MsnRuntime *rt, MsnProgress *p)
{
    memset(p, 0, sizeof *p);
    p->version = 1; p->level = (uint8_t)F->hdr->level;
    p->story = (uint8_t)(rt->story < 0 ? 0xFF : rt->story);
    p->phase = (uint8_t)rt->cp_phase; p->stage = (uint8_t)rt->cp_stage; p->completed = rt->completed;
}

void msn_resume(MsnRuntime *rt, const MsnProgress *p)
{
    rt->completed = p->completed;
    if (p->story == 0xFF || p->story >= F->nmissions) { msn_level_start(rt); return; }
    {
        const MsnLevelInfo *L = F->level;
        dispatch_range(rt, L->lvl_first, L->lvl_count, MSN_AT_LEVEL);
        dispatch_range(rt, L->init_first, L->init_count, MSN_AT_LEVEL_INIT);
        dispatch_range(rt, L->rew_first, L->rew_count, MSN_AT_REWARDS);
    }
    rt->cp_phase = p->phase; rt->cp_stage = p->stage;
    msn_start_mission(rt, p->story, 1);
}
