/* Fake game + autopilot for the mission system, plugged in through the typed API (msn_game.h). Pure C99. */
#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#include <math.h>
#include "fake_engine.h"

const char *const fake_group_name[FK_NGROUP] = { "player", "cars", "npc", "nav", "ui", "sound", "fx", "props", "shop", "traffic", "feature" };

void fake_printf(Fake *k, const char *fmt, ...)
{
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(k->line, sizeof k->line, fmt, ap);
    va_end(ap);
    k->print(k->pctx, k->line);
}

#define K Fake *k = (Fake *)u
#define V1(...) do { if (k->o.verbose >= 1) fake_printf(k, __VA_ARGS__); } while (0)

static void cpy(char *dst, const char *src, size_t n)
{
    if (!src) src = "";
    strncpy(dst, src, n - 1); dst[n - 1] = 0;
}

static FakeEnt *ent_find(Fake *k, const char *name)
{
    int i;
    if (!name) return NULL;
    for (i = 0; i < k->nent; i++) if (msn_streq(k->ent[i].name, name)) return &k->ent[i];
    return NULL;
}

static FakeEnt *ent_add(Fake *k, const char *name, const MsnPlace *at, int veh)
{
    FakeEnt *e = ent_find(k, name);
    if (!e) {
        if (k->nent >= FAKE_MAX_ENT) return NULL;
        e = &k->ent[k->nent++];
        memset(e, 0, sizeof *e);
        cpy(e->name, name, sizeof e->name);
    }
    e->alive = 1; e->is_vehicle = veh; e->t = 0;
    e->e.health = 1.0f; e->e.finished = 0; e->e.waypoint = -1;
    if (at && at->loc) e->e.pos = at->pos;
    return e;
}

static void put_player(Fake *k, const MsnPlace *at, int on_foot)
{
    if (at && at->loc) k->w.player = at->pos;
    k->w.on_foot = on_foot;
}

/* ------------------------------------------------------------------ typed API: world */
static int api_entity(void *u, const char *name, MsnEntity *out)
{
    K; FakeEnt *e = ent_find(k, name);
    if (!e || !e->alive) return 0;
    *out = e->e;
    return 1;
}

static void pl_reset(void *u, const MsnPlace *at, const MsnPlace *car, const char *car_name)
{
    K; k->s.calls[FK_PLAYER]++;
    if (at) put_player(k, at, 1); else put_player(k, car, 0);
    if (car_name && *car_name && !msn_streq(car_name, "current")) cpy(k->vehicle, car_name, sizeof k->vehicle);
    V1("        player.reset %s %s%s%s", at ? "on foot at" : "in car at", at ? at->locator : (car ? car->locator : "?"),
       at && car ? ", car at " : "", at && car ? car->locator : "");
}
static void pl_vehicle(void *u, const char *car, int forced, const MsnPlace *at)
{
    K; k->s.calls[FK_PLAYER]++;
    cpy(k->vehicle, car, sizeof k->vehicle);
    if (!forced) cpy(k->default_car, car, sizeof k->default_car);
    put_player(k, at, 0);
    V1("        player.vehicle %s%s at %s", car, forced ? " (forced)" : "", at->locator);
}
static void pl_place_car(void *u, const char *car, const MsnPlace *at)
{
    K; k->s.calls[FK_PLAYER]++;
    if (!k->w.on_foot) put_player(k, at, 0);
    V1("        player.place_car %s at %s", car, at->locator);
}
static void pl_enter(void *u) { K; k->s.calls[FK_PLAYER]++; k->w.on_foot = 0; V1("        player.enter_car"); }
static void pl_forced(void *u, int on) { K; k->s.calls[FK_PLAYER]++; V1("        player.forced_car %d", on); }
static void pl_swap(void *u, const MsnPlace *p, const MsnPlace *d, const MsnPlace *fc)
{
    K; k->s.calls[FK_PLAYER]++;
    cpy(k->vehicle, k->default_car, sizeof k->vehicle);
    if (p) put_player(k, p, 1);
    fake_printf(k, "      player: default car %s back at %s (forced car to %s)", k->default_car, d ? d->locator : "?", fc ? fc->locator : "?");
}
static void pl_walk(void *u, const MsnPlace *to) { K; k->s.calls[FK_PLAYER]++; put_player(k, to, 1); V1("        player.walk_to %s", to->locator); }
static void pl_char(void *u, const char *n, const char *m) { K; k->s.calls[FK_PLAYER]++; V1("        player.character %s (%s)", n, m); }

static void car_load(void *u, const char *n, const char *file, const char *slot) { K; k->s.calls[FK_CARS]++; V1("        cars.load %s %s [%s]", n, file, slot); }
static void car_spawn(void *u, const MsnCarSpawn *c)
{
    K; k->s.calls[FK_CARS]++;
    ent_add(k, c->name, &c->at, 1);
    V1("        cars.spawn %s at %s ai=%s con=%s driver=%s", c->name, c->at.locator, c->ai, c->con, c->driver);
}
static void car_wp(void *u, int i, const MsnPlace *at) { K; k->s.calls[FK_CARS]++; V1("        cars.waypoint #%d %s", i, at->locator); }
static void car_activate(void *u, const char *n, const MsnPlace *at, const char *ai)
{
    K; FakeEnt *e = ent_find(k, n);
    k->s.calls[FK_CARS]++;
    if (!e) e = ent_add(k, n, at, 1);
    if (e) { if (at && at->loc) e->e.pos = at->pos; e->e.finished = 0; e->e.waypoint = -1; e->t = 0; e->alive = 1; }
    V1("        cars.activate %s ai=%s", n, ai);
}
static void car_ai(void *u, const char *n, int a, int b) { K; k->s.calls[FK_CARS]++; V1("        cars.ai_params %s %d %d", n, a, b); }
static void car_catchup(void *u, const char *n, int kind, const float *p, int cnt) { K; (void)p; k->s.calls[FK_CARS]++; V1("        cars.catchup %s kind %d (%d values)", n, kind, cnt); }
static void car_nodriver(void *u, const char *n) { K; k->s.calls[FK_CARS]++; V1("        cars.suppress_driver %s", n); }

static void npc_spawn(void *u, const char *n, const MsnPlace *at, int kind, float r, const char *interior)
{
    K; k->s.calls[FK_NPC]++;
    ent_add(k, n, at, 0);
    V1("        npc.spawn %s at %s%s%s%s", n, at->locator, kind ? " (ambient)" : "", *interior ? " in " : "", interior);
    (void)r;
}
static void npc_wp(void *u, const char *n, const MsnPlace *at) { K; k->s.calls[FK_NPC]++; V1("        npc.waypoint %s %s", n, at->locator); }
static void npc_remove(void *u, const char *n) { K; FakeEnt *e = ent_find(k, n); k->s.calls[FK_NPC]++; if (e) e->alive = 0; V1("        npc.remove %s", n); }
static void npc_giver(void *u, const MsnGiver *g)
{
    K; k->s.calls[FK_NPC]++;
    ent_add(k, g->name, &g->at, 0);
    V1("        npc.giver %s at %s -> %s", g->name, g->at.locator, g->mission);
}
static void npc_talk(void *u, const char *n, int icon, float h, float r) { K; k->s.calls[FK_NPC]++; V1("        npc.talk_target %s icon %d h %.2f r %.1f", n, icon, h, r); }
static void npc_driver(void *u, const char *car, const char *who, int add) { K; k->s.calls[FK_NPC]++; V1("        npc.driver %s %s %s", who, add ? "into" : "out of", car); }

static void nav_marker(void *u, const MsnMarker *m)
{
    K; k->s.calls[FK_NAV]++;
    if (!m) return;
    k->s.markers++;
    if (k->o.verbose || m->mission_start || !k->g.marker_on)
        fake_printf(k, "      marker %s at (%.1f, %.1f, %.1f)%s%s%s", *m->drawable ? m->drawable : "arrow", m->pos.x, m->pos.y, m->pos.z,
                    m->loc ? " locator " : "", m->loc ? msn_str(k->f, m->loc->name) : "", m->mission_start ? "  [mission start]" : "");
}
static void nav_giver(void *u, const MsnGiver *g, int on)
{
    K; k->s.calls[FK_NAV]++;
    if (on) fake_printf(k, "  radar icon %-9s %-9s -> %-7s at %s%s", g->kind == MSN_GIVER_SELLER ? "seller" : g->kind == MSN_GIVER_STREETRACE ? "race" :
                        g->kind == MSN_GIVER_WAGER ? "wager" : "bonus", g->name, g->mission, g->at.locator, *g->icon ? "  icon " : "", g->icon);
    else V1("        nav.giver_icon %s off", g->name);
}

static void conds_str(const Fake *k, char *buf, size_t n)
{
    const MsnStage *st = k->rt->st; int i; size_t p = 0;
    buf[0] = 0;
    for (i = 0; st && i < st->ncond && p < n - 20; i++)
        p += (size_t)snprintf(buf + p, n - p, "%s%s", i ? "," : " fail-if:", msn_cond_name[k->f->conds[st->cond_first + i].type]);
}
static void ui_objective(void *u, const char *text, int msg, const char *icon)
{
    K; const MsnStage *st = k->rt->st; char c[128];
    k->s.calls[FK_UI]++; k->s.stages++;
    conds_str(k, c, sizeof c);
    fake_printf(k, "  [%d] %-10s %s%s%s%s%s%s%s%s", k->rt->stage, msn_objective_name[k->rt->obj], *text ? text : "(no text)",
                *icon ? "  icon=" : "", icon, k->rt->target ? "  target=" : "", k->rt->target ? k->rt->target : "",
                c, (st->flags & MSN_SF_FINAL) ? "  FINAL" : "", (st->flags & MSN_SF_LOCKED) ? "  LOCKED" : "");
    (void)msg;
    if (k->rt->timer_on && !k->rt->timer_up) fake_printf(k, "      timer %.0f s", k->rt->remaining);
}
static void ui_timer(void *u, int ms, int up) { K; k->s.calls[FK_UI]++; if (k->o.verbose >= 2 && ms >= 0) fake_printf(k, "      timer %d s%s", ms / 1000, up ? " (up)" : ""); }
static void ui_par(void *u, int ms) { K; k->s.calls[FK_UI]++; if (ms >= 0) fake_printf(k, "      time to beat %d s", ms / 1000); }
static void ui_counter(void *u, int d, int t) { K; k->s.calls[FK_UI]++; if (k->o.verbose && t) fake_printf(k, "      items %d/%d", d, t); }
static void ui_lap(void *u, int l, int n) { K; k->s.calls[FK_UI]++; if (k->o.verbose && n) fake_printf(k, "      lap %d/%d", l, n); }
static void ui_countdown(void *u, const char *t, float s) { K; k->s.calls[FK_UI]++; if (t) fake_printf(k, "      countdown \"%s\" %.1f s", t, s); }
static void ui_flash(void *u, int what, const char *t) { K; k->s.calls[FK_UI]++; (void)what; V1("      flash \"%s\"", t); }
static void ui_failed(void *u, int reason, const char *t, const char *h) { K; k->s.calls[FK_UI]++; fake_printf(k, "  !!! mission failed (%s): \"%s\"  %s", msn_fail_name[reason], t, h); }
static void ui_title(void *u, const char *id, const char *t, const char *info, int bonus) { K; k->s.calls[FK_UI]++; V1("      title %s \"%s\" %s%s", id, t, info, bonus ? " [bonus]" : ""); }
static void ui_pres(void *u, const char *b) { K; k->s.calls[FK_UI]++; V1("        ui.presentation %s", b); }

static void snd_dialogue(void *u, const MsnDialogue *d)
{
    K; k->s.calls[FK_SOUND]++; k->s.dialogues++; k->s.dialogue_lines += d->nlines;
    fake_printf(k, "      dialogue %s + %s \"%s\": %d lines%s%s", d->pc, d->npc, d->name, d->nlines,
                d->nlines ? ", first " : " (NO AUDIO FOUND)", d->nlines ? d->file[0] : "");
}
static void snd_oneliner(void *u, const MsnDialogue *d) { K; k->s.calls[FK_SOUND]++; fake_printf(k, "      line \"%s\"%s %s", d->name, d->nlines ? "" : " (no audio)", d->nlines ? d->file[0] : ""); }
static void snd_music(void *u, const char *e) { K; k->s.calls[FK_SOUND]++; V1("        sound.music_event %s", e); }
static void snd_change(void *u) { K; k->s.calls[FK_SOUND]++; V1("        sound.music_change"); }
static void snd_always(void *u) { K; k->s.calls[FK_SOUND]++; V1("        sound.music_always_on"); }

static void fx_fade(void *u, int out, float s) { K; k->s.calls[FK_FX]++; V1("        fx.fade %s %.1f s", out ? "out" : "in", s); }
static void fx_black(void *u) { K; k->s.calls[FK_FX]++; V1("        fx.stay_black"); }
static void fx_fmv(void *u, const char *f) { K; k->s.calls[FK_FX]++; fake_printf(k, "      FMV %s", f); }

static void pr_show(void *u, int i, const MsnItem *it)
{
    K; k->s.calls[FK_PROPS]++;
    if (it->breakable && k->nbrk < 16) cpy(k->brk[k->nbrk++], it->name, 32);
    if (it->dropped) fake_printf(k, "      target dropped item #%d", i);
    else if (it->breakable) fake_printf(k, "      break target #%d %s (tag %d)", i, it->name, it->tag);
    else V1("        props.item_show #%d %s %s", i, it->name, it->drawable);
}
static void pr_collected(void *u, int i, const MsnItem *it) { K; k->s.calls[FK_PROPS]++; k->s.collects++; V1("      collect #%d %s %s", i, it->name, it->effect); }
static void pr_clear(void *u) { K; k->s.calls[FK_PROPS]++; k->nbrk = 0; }
static int  pr_tag(void *u, int tag) { K; k->s.calls[FK_PROPS]++; k->s.tags_activated++; V1("        props.activate_tag %d", tag); return 1; }
static void pr_race(void *u, const char *n, int load) { K; k->s.calls[FK_PROPS]++; V1("        props.race_props %s %s", n, load ? "load" : "unload"); }
static void pr_state(void *u, const char *n, const MsnPlace *at) { K; k->s.calls[FK_PROPS]++; ent_add(k, n, at, 0); V1("        props.state_prop %s", n); }

static void sh_coins(void *u, int d, int why)
{
    K; k->s.calls[FK_SHOP]++; k->w.coins += d;
    fake_printf(k, "      coins %+d (%s) -> %d", d, why == MSN_COINS_WAGER_WIN ? "wager won" : "wager fee", k->w.coins);
}
static int sh_owns(void *u, int kind, const char *name)
{
    K; int i; (void)kind;
    for (i = 0; i < k->nowned; i++) if (msn_streq(k->owned[i], name)) return 1;
    return 0;
}
static void sh_unlock(void *u, const MsnReward *r)
{
    K; k->s.calls[FK_SHOP]++; k->s.unlocks++;
    if (k->nowned < 24) cpy(k->owned[k->nowned++], r->name, 32);
    fake_printf(k, "      reward: %s %s unlocked (%s)", r->kind == MSN_OWN_SKIN ? "costume" : "car", r->name, r->quest);
}
static void tr_max(void *u, int n) { K; k->s.calls[FK_TRAFFIC]++; if (k->o.verbose >= 2) fake_printf(k, "        traffic.max_cars %d", n); }

static void api_feature(void *u, int feat, const MsnCall *c)
{
    K; k->s.calls[FK_FEATURE]++;
    if (k->o.verbose >= 2) fake_printf(k, "        feature %s: %s", feat >= 0 ? msn_feature_name[feat] : "?", msn_op_name(c->cmd->op));
}
static void api_cleanup(void *u) { K; k->nbrk = 0; if (k->o.verbose) fake_printf(k, "      cleanup"); }

/* flow printing through the event tap */
static void api_event(void *u, const MsnEvent *e)
{
    K;
    k->s.events++;
    switch (e->type) {
    case MSN_EV_MISSION_START:
        fake_printf(k, "");
        fake_printf(k, "=== MISSION %s \"%s\"%s", e->name, e->text, e->value > 0 ? "  [bonus]" : "");
        break;
    case MSN_EV_PHASE_START: fake_printf(k, "  --- %s phase \"%s\"", e->index ? "main" : "intro", e->name); break;
    case MSN_EV_STAGE_SKIPPED: k->s.skipped++; fake_printf(k, "      skipped: player already owns %s", e->name); break;
    case MSN_EV_PAY: break;
    case MSN_EV_STAGE_COMPLETE: fake_printf(k, "      done%s", e->index ? " + \"TASK COMPLETE!\"" : ""); break;
    case MSN_EV_CHECKPOINT: fake_printf(k, "      checkpoint (retry restarts here)"); break;
    case MSN_EV_MISSION_COMPLETE:
        k->s.missions_done++;
        fake_printf(k, "  >>> mission %s complete: \"%s\"", e->name, k->g.hud.flash_text ? k->g.hud.flash_text : "");
        break;
    case MSN_EV_MISSION_FAILED: k->s.fails++; break;
    case MSN_EV_LEVEL_COMPLETE: fake_printf(k, ""); fake_printf(k, "=== %s", k->g.hud.flash_text); break;
    default: break;
    }
}

void fake_attach(Fake *k)
{
    MsnGameApi a;
    memset(&a, 0, sizeof a);
    a.user = k; a.entity = api_entity; a.feature = api_feature; a.cleanup = api_cleanup; a.on_event = api_event;
    a.player.reset = pl_reset; a.player.vehicle = pl_vehicle; a.player.place_car = pl_place_car; a.player.enter_car = pl_enter;
    a.player.forced_car = pl_forced; a.player.swap_default_car = pl_swap; a.player.walk_to = pl_walk; a.player.character = pl_char;
    a.cars.load = car_load; a.cars.spawn = car_spawn; a.cars.waypoint = car_wp; a.cars.activate = car_activate;
    a.cars.ai_params = car_ai; a.cars.catchup = car_catchup; a.cars.suppress_driver = car_nodriver;
    a.npc.spawn = npc_spawn; a.npc.waypoint = npc_wp; a.npc.remove = npc_remove; a.npc.giver = npc_giver;
    a.npc.talk_target = npc_talk; a.npc.driver = npc_driver;
    a.nav.marker = nav_marker; a.nav.giver_icon = nav_giver;
    a.ui.mission_title = ui_title; a.ui.objective = ui_objective; a.ui.timer = ui_timer; a.ui.par_time = ui_par;
    a.ui.counter = ui_counter; a.ui.lap = ui_lap; a.ui.countdown = ui_countdown; a.ui.flash = ui_flash; a.ui.failed = ui_failed;
    a.ui.presentation = ui_pres;
    if (!k->o.no_sound) { a.sound.dialogue = snd_dialogue; a.fx.fmv = fx_fmv; }
    a.sound.oneliner = snd_oneliner; a.sound.music_event = snd_music; a.sound.music_change = snd_change; a.sound.music_always_on = snd_always;
    a.fx.fade = fx_fade; a.fx.stay_black = fx_black;
    a.props.item_show = pr_show; a.props.item_collected = pr_collected; a.props.items_clear = pr_clear;
    a.props.activate_tag = pr_tag; a.props.race_props = pr_race; a.props.state_prop = pr_state;
    a.shop.coins_add = sh_coins; a.shop.owns = sh_owns; a.shop.unlock = sh_unlock;
    a.traffic.max_cars = tr_max;
    msn_game_init(&k->g, k->rt, k->f, &a);
}

void fake_init(Fake *k, MsnRuntime *rt, const MsnFile *f, const FakeOpts *o, FakePrint print, void *pctx)
{
    int i;
    memset(k, 0, sizeof *k);
    k->rt = rt; k->f = f; k->o = *o; k->print = print; k->pctx = pctx;
    if (k->o.dt <= 0) k->o.dt = 0.1f;
    cpy(k->vehicle, "famil_v", sizeof k->vehicle); cpy(k->default_car, "famil_v", sizeof k->default_car);
    k->w.vehicle_health = 1.0f; k->w.coins = 0;
    k->last_stage_key = -1; k->step_key = -1; k->want_bonus = -1;
    for (i = 0; i < o->nown && k->nowned < 24; i++) cpy(k->owned[k->nowned++], o->own[i], 32);
}

/* ------------------------------------------------------------------ autopilot */
static int stage_has_timeout(const MsnRuntime *rt)
{
    int i;
    if (!rt->st || !rt->timer_on || rt->timer_up) return 0;
    for (i = 0; i < rt->st->ncond; i++) if (rt->f->conds[rt->st->cond_first + i].type == MSN_COND_TIMEOUT) return 1;
    return 0;
}

static void autopilot(Fake *k, float dt)
{
    MsnRuntime *rt = k->rt;
    MsnObjInfo o; MsnVec3 p; int has; FakeEnt *e;
    int key = rt->cur * 10000 + rt->phase * 1000 + rt->stage * 2 + (rt->status == MSN_RUNNING);
    if (key != k->last_stage_key) {
        k->obj_t = 0; k->last_stage_key = key;
        if (k->o.fail_test && !k->fail_armed && !k->fail_seen && rt->status == MSN_RUNNING && stage_has_timeout(rt)) {
            k->fail_armed = 1;
            fake_printf(k, "      [fail-test] idling in this stage until its timer runs out");
        }
    } else k->obj_t += dt;
    k->w.action = 0;
    k->w.interior = k->interior[0] ? k->interior : NULL;
    k->w.vehicle = k->vehicle;
    if (k->want_bonus >= 0 && msn_free_roam(rt)) {
        /* free roam: walk up to the bonus giver and press action (msn_tick starts the mission) */
        const MsnMission *m = &k->f->missions[k->want_bonus];
        FakeEnt *g = ent_find(k, msn_arg_s(k->f, &k->f->cmds[m->bonus_npc], 0));
        k->interior[0] = 0; k->w.interior = NULL; k->w.on_foot = 1;
        if (g) k->w.player = g->e.pos;
        if (k->g.hud.talk_prompt == k->want_bonus) k->w.action = 1;
        return;
    }
    if (rt->status != MSN_RUNNING || k->fail_armed) return;
    msn_objective_info(rt, &o);
    has = msn_nav_target(rt, &k->w, &p);
    {   /* drive into the trigger volume, not to the marker */
        const MsnLoc *l = msn_nav_locator(rt, &k->w);
        if (has && l && l->ntrig) {
            const MsnTrig *t = &k->f->trigs[l->first_trig];
            p.x = t->center[0]; p.y = t->center[1]; p.z = t->center[2];
        }
    }
    switch (o.obj) {
    case MSN_OBJ_GOTO:
        k->w.on_foot = (o.flags & MSN_SF_MUSTACTION) || k->interior[0] ? 1 : 0;
        if (has) k->w.player = p;
        if (o.need_action) k->w.action = 1;
        break;
    case MSN_OBJ_GETIN:
        k->w.on_foot = 0;
        if (o.target && *o.target && !msn_streq(o.target, "current") && !msn_streq(o.target, "default")) cpy(k->vehicle, o.target, sizeof k->vehicle);
        break;
    case MSN_OBJ_TALKTO:
        k->w.on_foot = 1;
        if (has) k->w.player = p;
        k->w.action = 1;
        break;
    case MSN_OBJ_DIALOGUE: if (!k->o.no_sound && k->obj_t > 0.3f) msn_notify(rt, MSN_IN_DIALOGUE_DONE, NULL, 0); break;
    case MSN_OBJ_FMV: if (!k->o.no_sound && k->obj_t > 0.3f) msn_notify(rt, MSN_IN_FMV_DONE, NULL, 0); break;
    case MSN_OBJ_INTERIOR:
        k->w.on_foot = 1;
        if (has) k->w.player = p;
        if (k->obj_t > 0.1f && o.dest) cpy(k->interior, o.dest, sizeof k->interior);
        break;
    case MSN_OBJ_GOOUTSIDE:
        k->w.on_foot = 1; k->interior[0] = 0;
        if (has) k->w.player = p;
        break;
    case MSN_OBJ_DELIVERY:
        k->w.on_foot = 0; k->interior[0] = 0;
        if (k->nbrk > 0) {                           /* power boxes: drive up to one and smash it */
            int i;
            for (i = 0; i < rt->nitems; i++)
                if (msn_streq(msn_arg_s(k->f, rt->items[i], 0), k->brk[0]) && msn_arg_loc(k->f, rt->items[i], 0)) {
                    const MsnLoc *l = msn_arg_loc(k->f, rt->items[i], 0);
                    k->w.player.x = l->pos[0]; k->w.player.y = l->pos[1]; k->w.player.z = l->pos[2];
                }
            if (k->obj_t > 0.3f) {
                const char *n = k->brk[0];
                if ((n[0] == 'P' || n[0] == 'p') && n[2] == '_') n += 3;       /* engine reports the world object name */
                if (k->o.verbose) fake_printf(k, "      [autopilot] smashed %s", n);
                msn_notify(rt, MSN_IN_DESTROYED, n, 0);
                k->s.breaks++; k->obj_t = 0;
                memmove(k->brk[0], k->brk[1], (size_t)(k->nbrk - 1) * 32); k->nbrk--;
            }
            break;
        }
        if (has) k->w.player = p;
        break;
    case MSN_OBJ_RACE: case MSN_OBJ_PICKUPITEM:
        k->w.on_foot = 0; k->interior[0] = 0;
        if (has) k->w.player = p;
        break;
    case MSN_OBJ_DUMP:
        k->w.on_foot = 0;
        e = ent_find(k, o.target);
        if (e) {
            e->t += dt;
            if (e->t > 0.5f) { e->t = 0; e->e.waypoint++; msn_notify(rt, MSN_IN_HIT_VEHICLE, e->name, 0); }
        }
        if (has) k->w.player = p;
        break;
    case MSN_OBJ_FOLLOW:
        k->w.on_foot = 0;
        if ((e = ent_find(k, o.target)) != NULL) { if (k->obj_t > 1.0f) e->e.finished = 1; k->w.player = e->e.pos; }
        break;
    case MSN_OBJ_LOSETAIL:
        k->w.on_foot = 0;
        if ((e = ent_find(k, o.target)) != NULL) { e->e.pos.x = k->w.player.x + 1000.0f; e->e.pos.z = k->w.player.z; }
        break;
    case MSN_OBJ_DESTROY:
        k->w.on_foot = 0;
        if ((e = ent_find(k, o.target)) != NULL) { k->w.player = e->e.pos; if (k->obj_t > 0.5f) e->e.health = 0; }
        break;
    case MSN_OBJ_DESTROYBOSS: if (k->obj_t > 0.5f) msn_notify(rt, MSN_IN_BOSS_HIT, NULL, 0); break;
    case MSN_OBJ_BUYCAR: case MSN_OBJ_BUYSKIN:
        k->w.on_foot = 1;
        if (has) k->w.player = p;
        if (k->obj_t > 0.5f && k->nowned < 24 && o.arg) {
            cpy(k->owned[k->nowned++], o.arg, 32);
            fake_printf(k, "      [autopilot] bought %s%s", o.arg, has ? " from the seller" : " (seller position unknown)");
        }
        break;
    case MSN_OBJ_COINS:
        k->w.on_foot = 1; if (k->w.coins < 100) k->w.coins = 100;
        if (has) k->w.player = p;
        k->w.action = 1;
        break;
    default: break;
    }
    k->w.interior = k->interior[0] ? k->interior : NULL;
    k->w.vehicle = k->vehicle;
}

/* one frame: autopilot, msn_game_tick, failure handling. Returns -1 when stuck. */
int fake_step(Fake *k)
{
    MsnRuntime *rt = k->rt;
    int key = rt->cur * 10000 + rt->phase * 1000 + rt->stage;
    autopilot(k, k->o.dt);
    msn_game_tick(&k->g, k->o.dt, &k->w);
    k->s.ticks++; k->s.sim_seconds += k->o.dt;
    if (key != k->step_key) { k->step_key = key; k->stage_t = 0; } else k->stage_t += k->o.dt;
    if (rt->status == MSN_FAILED) {
        if (k->fail_armed) {
            int want_phase = rt->cp_phase, want_stage = rt->cp_stage, ok;
            ok = rt->fail == MSN_FAIL_TIMEOUT && k->g.hud.failed && k->g.hud.fail_text && *k->g.hud.fail_text;
            k->fail_armed = 0; k->fail_seen = 1;
            msn_retry(rt, 0); k->s.retries++;
            ok = ok && rt->phase == want_phase && rt->stage == want_stage && rt->status != MSN_FAILED;
            k->s.fail_test_ok = ok;
            fake_printf(k, "      [fail-test] %s: failed by timeout, retried at checkpoint phase %d stage %d -> now phase %d stage %d",
                        ok ? "OK" : "WRONG", want_phase, want_stage, rt->phase, rt->stage);
        } else {
            fake_printf(k, "      [autopilot] unexpected failure, retrying from checkpoint");
            msn_retry(rt, 0); k->s.retries++;
            if (k->s.retries > 50) return -1;
        }
    }
    if (k->o.save_test && !k->save_done && rt->status == MSN_RUNNING && rt->cur >= 0 && rt->phase == 1 && rt->stage >= 2 &&
        !(k->f->missions[rt->cur].flags & MSN_MF_BONUS)) {
        /* save -> fresh runtime + adapter -> resume: must come back in the same mission at its checkpoint */
        MsnProgress p; int cur = rt->cur, cph = rt->cp_phase, cst = rt->cp_stage;
        msn_get_progress(rt, &p);
        fake_printf(k, "      [save-test] saving: mission %d checkpoint phase %d stage %d, completed mask %08x", cur, cph, cst, (unsigned)p.completed);
        {
            MsnGameApi a = k->g.api;
            msn_game_init(&k->g, rt, k->f, &a);
        }
        rt->trace = k->trace_keep;
        msn_resume(rt, &p);
        k->save_done = 1;
        k->s.save_test_ok = rt->cur == cur && rt->phase == cph && rt->stage == cst && rt->completed == p.completed;
        fake_printf(k, "      [save-test] %s: resumed in mission %d phase %d stage %d", k->s.save_test_ok ? "OK" : "WRONG", rt->cur, rt->phase, rt->stage);
    }
    if (k->stage_t > 900.0) {
        MsnObjInfo o; msn_objective_info(rt, &o);
        fake_printf(k, "  STUCK in %s phase %d stage %d objective %s target %s", o.mission_id ? o.mission_id : "?", rt->phase, rt->stage,
                    msn_objective_name[o.obj], o.target ? o.target : "-");
        k->s.stuck++;
        return -1;
    }
    return 0;
}

static int run_until(Fake *k, double budget_s, int until_bonus_done)
{
    double t0 = k->s.sim_seconds;
    uint32_t want = k->want_bonus >= 0 ? 1u << k->want_bonus : 0;
    while (until_bonus_done ? !(k->rt->completed & want) || k->rt->cur == k->want_bonus
                            : (k->rt->status != MSN_LEVEL_DONE && k->rt->status != MSN_IDLE)) {
        if (fake_step(k) != 0) return -1;
        if (k->s.sim_seconds - t0 > budget_s) { fake_printf(k, "  time budget exceeded"); return -1; }
    }
    return 0;
}

int fake_run_level(Fake *k)
{
    MsnRuntime *rt = k->rt; uint32_t i; int err = 0;
    k->trace_keep = rt->trace;
    msn_level_start(rt);
    if (run_until(k, 36000.0, 0) != 0) err = 1;
    if (k->o.bonus) {
        for (i = 0; i < k->f->nmissions; i++) {
            const MsnMission *m = &k->f->missions[i];
            if (!(m->flags & MSN_MF_BONUS)) continue;
            if (m->bonus_npc == 0xFFFFFFFFu || (m->flags & MSN_MF_NOSCRIPT)) {    /* no giver: start directly */
                if (!msn_start_bonus(rt, (int)i)) { fake_printf(k, "  bonus %s could not be started", msn_str(k->f, m->id)); err = 1; continue; }
                if (run_until(k, 36000.0, 0) != 0) err = 1;
                continue;
            }
            k->want_bonus = (int)i;
            fake_printf(k, "");
            fake_printf(k, "  [autopilot] free roam: walking to %s for %s", msn_arg_s(k->f, &k->f->cmds[m->bonus_npc], 0), msn_str(k->f, m->id));
            if (run_until(k, 36000.0, 1) != 0) err = 1;
            k->want_bonus = -1;
            if (run_until(k, 36000.0, 0) != 0) err = 1;
        }
    }
    return err;
}
