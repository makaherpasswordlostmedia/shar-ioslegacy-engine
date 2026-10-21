// Карточки, осы-камеры и гэги (см. collect.h: данные, правила порта). Чистый C99, без malloc в кадре.
#include <math.h>
#include <string.h>
#include <stdlib.h>
#include "collect.h"
#include "bolt_math.h"
#include "ticket.h"
static int gmDirty = 1;   // №637: таблица экземпляр->гэг (collectGagOf) строится заново после collectInit/collectFree

_Static_assert(sizeof(CollCard) == 32, "CollCard 32");
_Static_assert(sizeof(CollWasp) == 80, "CollWasp 80");
_Static_assert(sizeof(CollGag) == 128, "CollGag 128");

#define ALIGN16(x) (((x) + 15u) & ~15u)
#define CARD_REACH_FOOT .6f      // правило порта: досягаемость карточки сверх радиуса триггера
#define CARD_REACH_CAR 1.4f
#define WASP_DESPAWN 15.f        // оса исчезает дальше дистанции появления + 15 м
#define WASP_HEAD_FOOT 2.f       // высота полёта к игроку над его ступнями: пешком — в досягаемости прыжка с пинком
#define WASP_HEAD_CAR 1.f        // в машине — в слое кузова (0.35–1.6 м), машина может сбить
#define WASP_ZAP_ARC 15.f        // выстрел попадает в дуге ±15° и дальности x1.2
#define WASP_HIT_R 1.f           // досягаемость пинка по осе (как у стейтпропов в game.c)
// щит осы (правило порта, см. collect.h): ударов до пролома, погасание после пролома, радиус шара удара машиной —
// половина билборда shield_bbShape в состоянии «держит» (2.97 м, l05_fx.p3d BQG кадр 40)
#ifndef COLL_SHIELD_HP
#define COLL_SHIELD_HP 2
#endif
#ifndef COLL_SHIELD_ON
#define COLL_SHIELD_ON 1   // отрицательный контроль гейта tests/levelmech/shield.sh: 0 — щит не держит удар
#endif
#define COLL_SHIELD_GONE_S 1.f
#define COLL_SHIELD_R 1.5f
enum { WS_APPEAR = 0, WS_FLY = 1, WS_CHARGE = 2, WS_CHARGED = 3, WS_FIRE = 4, WS_DEAD = 5 };   // состояния beecamera в данных

static const char *ROOMN[] = {"SpringfieldElementary", "KwikEMart", "SimpsonsHouse", "DMV", "Moes", "AndroidsDungeon",
                              "Observatory", "BartRoom"};   // как NAMES в tools/interior_export.py

const char *collectError(int code) {
  switch (code) {
    case -1: return "short or unaligned pack"; case -2: return "not CLT1"; case -3: return "table out of file";
    case -4: return "SPR1 rejected"; case -5: return "bad instance index"; default: return "?";
  }
}

int collectRoomId(const char *s) {
  if (!s) return -1;
  for (int i = 0; i < (int)(sizeof ROOMN / sizeof *ROOMN); i++) {
    const char *a = ROOMN[i], *b = s;
    while (*a && *b && ((*a | 32) == (*b | 32))) { a++; b++; }
    if (!*a && !*b) return i;
  }
  return -1;
}

static unsigned rnd(CollState *s) { s->rng = s->rng * 1664525u + 1013904223u; return s->rng >> 8; }

static void push(Collect *c, int type, int idx, float x, float y, float z) {
  CollState *s = &c->st;
  if (s->nev >= COLL_EVQ) { s->evDropped++; return; }
  CollEvent *e = &s->evq[s->nev++]; e->type = type; e->idx = idx; e->x = x; e->y = y; e->z = z;
}

int collectPop(Collect *c, CollEvent *e) {
  CollState *s = &c->st;
  if (!s->nev) return 0;
  *e = s->evq[0]; memmove(s->evq, s->evq + 1, --s->nev * sizeof *e);   // по порядку появления
  return 1;
}

int collectInitResident(Collect *c, const void *pak, unsigned size, int detachedKeys) {
  gmDirty = 1;
  memset(c, 0, sizeof *c); c->kickFx = c->shockFx = c->bolt0 = -1;
  const unsigned char *h = pak;
  if (!pak || size < 64 || ((uintptr_t)pak & 15)) return -1;
  if (memcmp(h, "CLT1", 4)) return -2;
  const uint32_t *u = (const uint32_t *)(h + 4);
  unsigned level = u[1], ntex = u[2], texOff = u[3], sprOff = u[4], sprSize = u[5], ncard = u[6], cardOff = u[7],
           nwasp = u[8], waspOff = u[9], ngag = u[10], gagOff = u[11], alive = u[12];
  if ((uint64_t)sprOff + sprSize > size || (uint64_t)cardOff + ncard * 32ull > size || (uint64_t)waspOff + nwasp * 80ull > size ||
      (uint64_t)gagOff + ngag * 128ull > size || texOff > size || ncard > COLL_MAXCARD || nwasp > COLL_MAXWASP || ngag > COLL_MAXGAG ||
      (sprOff & 15) || (cardOff & 3) || (waspOff & 3) || (gagOff & 3)) return -3;
  c->level = (int)level; c->maxAlive = alive ? alive : 3; c->pak = h; c->size = size;
  c->card = (const CollCard *)(h + cardOff); c->ncard = ncard;
  c->wasp = (const CollWasp *)(h + waspOff); c->nwasp = nwasp;
  c->gag = (const CollGag *)(h + gagOff); c->ngag = ngag;
  c->tex = h + texOff; c->ntex = ntex;
  if (sprSize) {
    if (spInitResident(&c->sp, h + sprOff, sprSize, detachedKeys)) return -4;
    c->haveSp = 1;
  }
  for (unsigned i = 0; i < ncard; i++) if (c->haveSp && c->card[i].inst >= c->sp.ninst) { collectFree(c); return -5; }
  for (unsigned i = 0; i < nwasp; i++) if (c->haveSp && c->wasp[i].inst >= c->sp.ninst) { collectFree(c); return -5; }
  for (unsigned i = 0; i < ngag; i++) if (c->gag[i].inst >= 0 && (!c->haveSp || (unsigned)c->gag[i].inst >= c->sp.ninst)) { collectFree(c); return -5; }
#ifndef FOOT_FX_OLD
  if (u[0] >= 2) {
    if (size < 80) { collectFree(c); return -3; }
    c->kickFx = (int)((const uint32_t *)h)[16]; c->shockFx = (int)((const uint32_t *)h)[17];
    if ((c->kickFx >= 0 && (!c->haveSp || (unsigned)c->kickFx >= c->sp.ninst)) ||
        (c->shockFx >= 0 && (!c->haveSp || (unsigned)c->shockFx >= c->sp.ninst))) { collectFree(c); return -5; }
  }
#endif
#ifndef WASP_BOLT_OLD
  if (u[0] >= 3) {
    if (size < 80) { collectFree(c); return -3; }
    c->bolt0 = (int)((const uint32_t *)h)[18]; c->nbolt = ((const uint32_t *)h)[19];
    if (c->nbolt > COLL_MAXBOLT || (c->nbolt && (c->bolt0 < 0 || !c->haveSp || (unsigned)c->bolt0 > c->sp.ninst ||
        c->nbolt > c->sp.ninst - (unsigned)c->bolt0))) { collectFree(c); return -5; }
    for(unsigned i=0;i<c->nwasp;i++) if(c->nbolt && (!(c->wasp[i].boltSpeed>0) || !(c->wasp[i].boltLife>0) ||
      !isfinite(c->wasp[i].boltSpeed) || !isfinite(c->wasp[i].boltLife))) { collectFree(c); return -3; }
  }
#endif
  collectNewGame(c);
  return 0;
}

int collectInit(Collect *c, const void *pak, unsigned size) { return collectInitResident(c, pak, size, 0); }

void collectFree(Collect *c) { gmDirty = 1; if (c->haveSp) spFree(&c->sp); c->haveSp = 0; }

static void hide(Collect *c, int inst) { if (c->haveSp && inst >= 0 && (unsigned)inst < c->sp.ninst) { c->sp.run[inst].alive = 0; c->sp.run[inst].colOn = c->sp.run[inst].col2On = 0; } }

void collectNewGame(Collect *c) {
  CollState *s = &c->st;
  memset(s, 0, sizeof *s);
  s->lastRoom = -2; s->rng = 0x5eed1u + (unsigned)c->level; s->pRoom = -1;
  hide(c, c->kickFx); hide(c, c->shockFx);
  for(unsigned i=0;i<c->nbolt;i++) hide(c,c->bolt0+i);
  for (unsigned i = 0; i < c->nwasp; i++) { hide(c, c->wasp[i].inst); if (c->wasp[i].flags & COLL_WASP_SHIELD) hide(c, c->wasp[i].shield); }   // осы появляются по близости
  for (unsigned i = 0; i < c->ncard; i++) if (c->haveSp) spEnter(&c->sp, c->card[i].inst, 0);
  for (unsigned g = 0; g < c->ngag; g++) if (c->gag[g].inst >= 0) spEnter(&c->sp, (unsigned)c->gag[g].inst, 0);
}

int collectInstRoom(const Collect *c, unsigned inst) {
  if ((int)inst == c->kickFx || (int)inst == c->shockFx) return c->st.pRoom;
  int g = collectGagOf(c, inst);
  return g < 0 ? -1 : c->gag[g].room;
}
#ifndef COLL_GAGMAP_OLD
#define COLL_GAGMAP_OLD 0
#endif
// №637: обратная таблица «экземпляр -> гэг» (collDraw спрашивал на каждый экземпляр дважды за кадр, линейный поиск по всем гэгам: 126 × 33 × 2 × 2 циклов); gag[] лежит в пакете и после загрузки не меняется
static const CollGag *gmKeyG; static unsigned gmKeyN, gmKeyI; static signed char *gmTab;   // tab[inst] = индекс гэга или -1 (гэгов < 128); gmDirty — после collectInit/collectFree
int collectGagOf(const Collect *c, unsigned inst) {
#if !COLL_GAGMAP_OLD
#define keyG gmKeyG
#define keyN gmKeyN
#define keyI gmKeyI
#define tab gmTab
  if (c->haveSp && c->ngag < 127 && (gmDirty || c->gag != keyG || c->ngag != keyN || c->sp.ninst != keyI || !tab)) {
    free(tab); tab = (signed char *)malloc(c->sp.ninst ? c->sp.ninst : 1);
    if (tab) { memset(tab, -1, c->sp.ninst ? c->sp.ninst : 1); for (unsigned g = c->ngag; g-- > 0;) if (c->gag[g].inst >= 0 && (unsigned)c->gag[g].inst < c->sp.ninst) tab[c->gag[g].inst] = (signed char)g; }
    keyG = c->gag; keyN = c->ngag; keyI = c->sp.ninst; gmDirty = 0;
  }
  if (tab && c->haveSp && c->ngag < 127 && c->gag == keyG && c->ngag == keyN && c->sp.ninst == keyI) return inst < keyI ? tab[inst] : -1;
#undef keyG
#undef keyN
#undef keyI
#undef tab
#endif
  for (unsigned g = 0; g < c->ngag; g++) if (c->gag[g].inst == (int)inst) return (int)g;
  return -1;
}
int collectSparkle(const Collect *c, unsigned g) { return g < c->ngag && c->gag[g].sparkle && !c->st.gagFound[g]; }

// ---------------------------------------------------------------- прогресс
unsigned collectCards(const Collect *c, int level) { return level > 0 && level < COLL_LEVELS ? c->st.cards[level] : 0; }
uint32_t collectWasps(const Collect *c, int level) { return level > 0 && level < COLL_LEVELS ? c->st.wasps[level] : 0; }
uint64_t collectGags(const Collect *c, int level) { return level > 0 && level < COLL_LEVELS ? c->st.gags[level] : 0; }
static int pop64(uint64_t v) { int n = 0; while (v) { v &= v - 1; n++; } return n; }
int collectCount(const Collect *c, int level, int what, int *total) {
  int t = 0, n = 0;
  if (level == c->level) {
    if (what == COLL_CARDS) t = (int)c->ncard;
    else if (what == COLL_WASPS) t = (int)c->nwasp;
    else for (unsigned g = 0; g < c->ngag; g++) t += c->gag[g].coins > 0;
  }
  if (level > 0 && level < COLL_LEVELS)
    n = what == COLL_CARDS ? pop64(c->st.cards[level]) : what == COLL_WASPS ? pop64(c->st.wasps[level]) : pop64(c->st.gags[level]);
  if (total) *total = t;
  return n;
}
void collectSetProgress(Collect *c, int level, unsigned cards, uint32_t wasps, uint64_t gags) {
  if (level <= 0 || level >= COLL_LEVELS) return;
  CollState *s = &c->st;
  s->cards[level] = (uint8_t)cards; s->wasps[level] = wasps; s->gags[level] = gags;
  if (level != c->level) return;
  for (unsigned i = 0; i < c->ncard; i++) {   // собранные карточки не висят в мире
    unsigned k = c->card[i].id % 10; s->cardGot[i] = k >= 1 && (cards >> (k - 1) & 1);
    if (s->cardGot[i]) hide(c, c->card[i].inst); else if (c->haveSp) spEnter(&c->sp, c->card[i].inst, 0);
  }
  for (unsigned i = 0; i < c->nwasp; i++) { s->waspSt[i] = (wasps >> i & 1) ? 2 : 0; hide(c, c->wasp[i].inst); }
  for (unsigned g = 0; g < c->ngag; g++) {
    s->gagFound[g] = (uint8_t)(gags >> g & 1); s->gagCoin[g] = s->gagFound[g];
    if (s->gagFound[g] && c->gag[g].persist && c->gag[g].cycle == COLL_SINGLE) {   // сыгранный single остаётся на последнем кадре
      s->gagSt[g] = 2; if (c->gag[g].inst >= 0) spEnter(&c->sp, (unsigned)c->gag[g].inst, 2);
    }
  }
}

// ---------------------------------------------------------------- карточки
static void cardsStep(Collect *c, const CollPlayer *p) {
  CollState *s = &c->st;
  if (p->room >= 0) return;
  for (unsigned i = 0; i < c->ncard; i++) {
    if (s->cardGot[i]) continue;
    const CollCard *k = &c->card[i];
    float dx = p->x - k->x, dy = p->y + .9f - k->y, dz = p->z - k->z, r = k->r + (p->onFoot ? CARD_REACH_FOOT : CARD_REACH_CAR);   // центр игрока: ступни + 0.9 м
    if (dx * dx + dy * dy + dz * dz > r * r) continue;
    s->cardGot[i] = 1; hide(c, k->inst);
    unsigned lv = k->id / 10, n = k->id % 10;
    if (lv > 0 && lv < COLL_LEVELS && n >= 1 && n <= 8) s->cards[lv] |= (uint8_t)(1u << (n - 1));
    push(c, CE_CARD, (int)i, k->x, k->y, k->z);
    int tot, got = collectCount(c, c->level, COLL_CARDS, &tot);
    if (got == tot && tot) push(c, CE_CARDS_DONE, (int)i, k->x, k->y, k->z);
  }
}

// ---------------------------------------------------------------- осы
static float angDiff(float a, float b) { float d = fmodf(a - b + 3.14159265f, 6.2831853f); if (d < 0) d += 6.2831853f; return d - 3.14159265f; }
static void setYaw(SpRun *r, float yaw) {   // поворот вокруг Y: R по столбцам, модель смотрит в +Z
  float cs = cosf(yaw), sn = sinf(yaw);
  r->R[0] = cs; r->R[1] = 0; r->R[2] = -sn; r->R[3] = 0; r->R[4] = 1; r->R[5] = 0; r->R[6] = sn; r->R[7] = 0; r->R[8] = cs;
  r->poseValid = 0;
}

static void shieldFollow(Collect *c, unsigned i) {   // щит — на осе: то же место и поворот
  const CollWasp *w = &c->wasp[i]; const SpRun *r = &c->sp.run[w->inst]; SpRun *q = &c->sp.run[w->shield];
  q->x = r->x; q->y = r->y; q->z = r->z; memcpy(q->R, r->R, sizeof q->R); q->poseValid = 0;
}
static void boltImpact(Collect *c, unsigned k, int hit, const CollPlayer *p, Homer *h) {
  unsigned owner=c->st.boltOwner[k]; SpRun *r=c->sp.run+c->bolt0+k;
  c->st.boltOn[k]=2;  // source FEATHER_TOUCH -> explosion, KILL SPEED, REMOVE_FROM_WORLD
  if(!spEvent(&c->sp,c->bolt0+k,9)) hide(c,c->bolt0+k);
  if(hit) {
    c->st.zaps++; push(c,CE_WASP_ZAP,owner,p->x,p->y,p->z);
    if(h) homerHurt(h,r->x,r->z,1.f);
#ifndef FOOT_FX_OLD
    if(c->shockFx>=0 && h) {spEnter(&c->sp,c->shockFx,1);c->sp.run[c->shockFx].alive=1;c->st.shockOn=1;}
#endif
  } else {c->st.boltMissed++;push(c,CE_WASP_MISS,owner,r->x,r->y,r->z);}
}
static void boltsStep(Collect *c,const CollPlayer *p,Homer *h,const ColWorld *world,float dt) {
#ifndef WASP_BOLT_OLD
  for(unsigned k=0;k<c->nbolt;k++) {
    if(!c->st.boltOn[k]) continue;
    SpRun *r=c->sp.run+c->bolt0+k;
    if(!r->alive) {c->st.boltOn[k]=0;continue;}
    if(c->st.boltOn[k]==2) continue;
    const CollWasp *w=c->wasp+c->st.boltOwner[k];
    c->st.boltT[k]+=dt;
    if(c->st.boltT[k]>=w->boltLife || p->room>=0) {hide(c,c->bolt0+k);c->st.boltOn[k]=0;c->st.boltMissed++;continue;}
    const SpType *t=c->sp.type+c->sp.inst[c->bolt0+k].type;
    const SpCol *shape=t->nCol ? c->sp.col+t->firstCol : 0;
    float off[3]={0,0,0};
    if(shape) for(int j=0;j<3;j++) off[j]=r->R[j]*shape->c[0]+r->R[j+3]*shape->c[1]+r->R[j+6]*shape->c[2];
    float a[3]={r->x+off[0],r->y+off[1],r->z+off[2]}, b[3];
    for(int j=0;j<3;j++) b[j]=a[j]+c->st.boltV[k][j]*dt;
    float old[3]={c->st.px,c->st.py,c->st.pz}, now[3]={p->x,p->y,p->z};
    float radius=shape && shape->kind==1 ? shape->h[0] : 0;
    float hit=p->onFoot ? boltCapsule(a,b,old,now,HOMER_RADIUS,HOMER_HEIGHT,radius) : 2;
    float wall=world ? colRayFrac(world,a,b,0) : 1;
    float at=hit<=wall && hit<=1 ? hit : wall;
    r->x+=c->st.boltV[k][0]*dt*at;r->y+=c->st.boltV[k][1]*dt*at;r->z+=c->st.boltV[k][2]*dt*at;
    if(hit<=wall && hit<=1) boltImpact(c,k,1,p,h);
    else if(wall<1) boltImpact(c,k,0,p,h);
  }
#endif
}
static void boltFire(Collect *c,unsigned owner,const CollPlayer *p) {
  const CollWasp *w=c->wasp+owner; const SpRun *from=c->sp.run+w->inst;
  for(unsigned k=0;k<c->nbolt;k++) if(!c->st.boltOn[k]) {
    SpRun *r=c->sp.run+c->bolt0+k;spEnter(&c->sp,c->bolt0+k,0);r->alive=1;r->colOn=r->col2On=0;
    r->x=from->x;r->y=from->y;r->z=from->z;memcpy(r->R,from->R,sizeof r->R);
    float aim[3]={p->x-r->x,p->y+1.f-r->y,p->z-r->z},len=sqrtf(aim[0]*aim[0]+aim[1]*aim[1]+aim[2]*aim[2]);
    if(len<1e-6f) {hide(c,c->bolt0+k);return;}
    for(int j=0;j<3;j++) c->st.boltV[k][j]=aim[j]/len*w->boltSpeed;
    c->st.boltOn[k]=1;c->st.boltOwner[k]=owner;c->st.boltT[k]=0;c->st.boltFired++;return;
  }
  c->st.boltFull++;
}
static void shieldHit(Collect *c, unsigned i) {   // удар достался щиту: s2 (держит) или s3 (пролом) — машина состояний рисунка
  CollState *s = &c->st; const CollWasp *w = &c->wasp[i];
  if (!s->shieldHp[i]) return;
  s->shieldHits++;
  if (--s->shieldHp[i]) { spEnter(&c->sp, w->shield, 2); return; }
  spEnter(&c->sp, w->shield, 3); s->shieldBreaks++; s->shieldT[i] = 0.f;
  SpRun *r = &c->sp.run[w->inst]; r->colOn = r->col2On = 1;   // оса снова бьётся машиной
}
static void shieldStep(Collect *c, unsigned i, const Car *car, float dt) {
  CollState *s = &c->st; const CollWasp *w = &c->wasp[i]; SpRun *r = &c->sp.run[w->inst];
  if (w->shield >= c->sp.ninst) return;
  shieldFollow(c, i);
  if (!s->shieldHp[i]) {   // пробит: вспышка пролома и погасание
    if (c->sp.run[w->shield].alive && (s->shieldT[i] += dt) >= COLL_SHIELD_GONE_S) hide(c, w->shield);
    return;
  }
  r->colOn = r->col2On = 0;   // пока щит цел, машина бьёт щит, не осу (spEnter состояний осы включает объём — гасим каждый кадр)
  if (s->shieldT[i] > 0.f) { s->shieldT[i] -= dt; return; }
  if (!car) return;
  float dx = r->x - car->x, dz = r->z - car->z, dy = r->y - (car->y + .8f), d = sqrtf(dx * dx + dz * dz), rr = COLL_SHIELD_R + 1.5f;
  if (d >= rr || fabsf(dy) >= COLL_SHIELD_R + 1.f || d < 1e-3f) return;
  if ((car->vel[0] * dx + car->vel[2] * dz) / d < 2.f) return;   // сближение от 2 м/с (как удар стейтпропа, SP_HIT_SPEED)
  shieldHit(c, i); s->shieldT[i] = .3f;
}

static float waspSpawnDistance(const CollWasp *w) {
#ifndef COLLECT_SPAWN_OLD
  // L2/L5 disc scripts use -1 for this parameter. Squaring the sentinel made these
  // wasps appear only inside 1 m. Port rule until PS2 measurement: use the disc's
  // positive roaming radius for proximity activation, never treat -1 as metres.
  if (w->dist <= 0.f) return fmaxf(w->roam, 0.f);
#endif
  return w->dist;
}

static void waspsStep(Collect *c, const CollPlayer *p, Homer *homer, const Car *car, const ColWorld *world, float dt) {
  CollState *s = &c->st;
  if (!c->haveSp) return;
  unsigned alive = 0;
  for (unsigned i = 0; i < c->nwasp; i++) if (s->waspSt[i] == 1) alive++;
  // появление: ближайшая спящая в дистанции, пока живых меньше предела (в комнате — нет: осы в городе)
  while (alive < c->maxAlive && p->room < 0) {
    int best = -1; float bd = 1e30f;
    for (unsigned i = 0; i < c->nwasp; i++) {
      if (s->waspSt[i]) continue;
      const CollWasp *w = &c->wasp[i];
      float dx = p->x - w->x, dz = p->z - w->z, d = dx * dx + dz * dz;
      if (d < waspSpawnDistance(w) * waspSpawnDistance(w) && d < bd) { bd = d; best = (int)i; }
    }
    if (best < 0) break;
    const CollWasp *w = &c->wasp[best]; SpRun *r = &c->sp.run[w->inst];
    spEnter(&c->sp, w->inst, WS_APPEAR); r->x = w->x; r->y = w->y; r->z = w->z;
    s->waspYaw[best] = atan2f(p->x - w->x, p->z - w->z); setYaw(r, s->waspYaw[best]);
    s->waspSt[best] = 1; s->waspShot[best] = 0; alive++;
    s->shieldHp[best] = 0; s->shieldT[best] = 0.f;
    if (COLL_SHIELD_ON && (w->flags & COLL_WASP_SHIELD) && w->shield < c->sp.ninst) {   // AddShield: щит с появления, на осе
      s->shieldHp[best] = COLL_SHIELD_HP; spEnter(&c->sp, w->shield, 0); shieldFollow(c, (unsigned)best);
    }
    push(c, CE_WASP_SPAWN, best, w->x, w->y, w->z);
  }
  for (unsigned i = 0; i < c->nwasp; i++) {
    if (s->waspSt[i] != 1) continue;
    const CollWasp *w = &c->wasp[i]; SpRun *r = &c->sp.run[w->inst];
    if (r->state == WS_DEAD) {   // машина или пинок: засчитана; монеты и исчезновение — вызовы состояния из данных
      s->waspSt[i] = 2; s->kills++; if (c->level > 0 && c->level < COLL_LEVELS) s->wasps[c->level] |= 1u << i;
      if (w->flags & COLL_WASP_SHIELD) hide(c, w->shield);
      push(c, CE_WASP_DEAD, (int)i, r->x, r->y + .5f, r->z);
      int tot, got = collectCount(c, c->level, COLL_WASPS, &tot);
      if (got == tot && tot) push(c, CE_WASPS_DONE, (int)i, r->x, r->y, r->z);
      continue;
    }
    float dx = p->x - r->x, dz = p->z - r->z, dh = sqrtf(dx * dx + dz * dz);
    float sx = p->x - w->x, sz = p->z - w->z;
    if (p->room >= 0 || sx * sx + sz * sz > (waspSpawnDistance(w) + WASP_DESPAWN) * (waspSpawnDistance(w) + WASP_DESPAWN)) {   // ушёл далеко: уснула
      s->waspSt[i] = 0; hide(c, w->inst); if (w->flags & COLL_WASP_SHIELD) hide(c, w->shield); continue;
    }
    // поворот к игроку
    float want = atan2f(dx, dz), turn = w->rot * 0.01745329f * dt, da = angDiff(want, s->waspYaw[i]);
    s->waspYaw[i] += da > turn ? turn : da < -turn ? -turn : da; setYaw(r, s->waspYaw[i]);
    // ATTRACTION
    if (!(w->flags & 1) && w->attrSpeed > 0.f && r->state != WS_APPEAR) {
      float ty = p->y + (p->onFoot ? WASP_HEAD_FOOT : WASP_HEAD_CAR);
      float d3 = sqrtf(dx * dx + (ty - r->y) * (ty - r->y) + dz * dz);
      if (d3 > w->attrMax && dh > 1e-3f) {
        float v = w->attrSpeed / 3.6f * dt, k = v / d3;
        float nx = r->x + dx * k, nz = r->z + dz * k, ny = r->y + (ty - r->y) * k;
        float ox = nx - w->x, oz = nz - w->z, od = sqrtf(ox * ox + oz * oz);
        if (od > w->roam) { nx = w->x + ox / od * w->roam; nz = w->z + oz / od * w->roam; }   // не дальше радиуса полёта
        float g;
        if (world && colGround(world, nx, nz, ny + 2.f, ny - 30.f, &g, 0) && ny < g + 1.f) ny = g + 1.f;
        r->x = nx; r->y = ny; r->z = nz;
      }
    }
    // ATTACK_PLAYER: пешком, в дальности и в дуге
    float d3 = sqrtf(dx * dx + (p->y + 1.f - r->y) * (p->y + 1.f - r->y) + dz * dz);
    float off = fabsf(angDiff(atan2f(dx, dz), s->waspYaw[i])) * 57.29578f;
    int inArc = off <= fmaxf(w->atkArc, 1.f), inRange = d3 <= w->atkRange;
    if (r->state == WS_FLY && p->onFoot && inRange && inArc) { spEnter(&c->sp, w->inst, WS_CHARGE); push(c, CE_WASP_CHARGE, (int)i, r->x, r->y, r->z); }
    else if (r->state == WS_CHARGED) {
      if (p->onFoot && d3 <= w->atkRange * 1.2f) { spEnter(&c->sp, w->inst, WS_FIRE); s->waspShot[i] = 0; }
      else spEnter(&c->sp, w->inst, WS_FLY);
    } else if (r->state == WS_FIRE && !s->waspShot[i]) {
      // момент выстрела — вызов FIRE_ENERGY_BOLT состояния в данных (op SP_OP_BOLT, время в секундах)
      const SpType *T = &c->sp.type[c->sp.inst[w->inst].type]; const SpState *S = &c->sp.state[T->firstState + r->state];
      float at = 1.f;
      for (unsigned k = 0; k < S->nCall; k++) if (c->sp.call[S->firstCall + k].op == SP_OP_BOLT) at = c->sp.call[S->firstCall + k].time;
      if (r->t >= at) {
        s->waspShot[i] = 1; push(c, CE_WASP_FIRE, (int)i, r->x, r->y, r->z);
#ifndef WASP_BOLT_OLD
        if(c->nbolt) boltFire(c,i,p);
        else
#endif
        if (p->onFoot && d3 <= w->atkRange * 1.2f && off <= WASP_ZAP_ARC) {
          s->zaps++; push(c, CE_WASP_ZAP, (int)i, p->x, p->y, p->z);
          if (homer) homerHurt(homer, r->x, r->z, 1.f);
#ifndef FOOT_FX_OLD
          if (c->shockFx >= 0 && homer) { spEnter(&c->sp, c->shockFx, 1); c->sp.run[c->shockFx].alive = 1; s->shockOn = 1; }
#endif
        }
      }
    }
    if (w->flags & COLL_WASP_SHIELD) shieldStep(c, i, car, dt);
  }
}

void collectHomerHit(Collect *c, const HomerEvent *e) {
  if (!c->haveSp || (e->type != HOMER_EV_HIT && e->type != HOMER_EV_STOMP)) return;
  for (unsigned i = 0; i < c->nwasp; i++) {
    if (c->st.waspSt[i] != 1) continue;
    unsigned in = c->wasp[i].inst; SpRun *r = &c->sp.run[in];
    if (!r->alive || r->state == WS_DEAD) continue;
    float cc[3], rr; spBounds(&c->sp, in, cc, &rr);
    if (homerHitTest(e, cc[0], cc[1], cc[2], fminf(rr, WASP_HIT_R))) {
      if (COLL_SHIELD_ON && c->st.shieldHp[i]) { shieldHit(c, i); continue; }   // щит цел — удар ему
      if (!spEvent(&c->sp, in, e->type == HOMER_EV_HIT ? SP_EV_HIT : SP_EV_STOMP)) spEvent(&c->sp, in, SP_EV_DESTROYED);
    }
  }
}

// ---------------------------------------------------------------- гэги
static int gagHere(const Collect *c, unsigned g, const CollPlayer *p) {
  const CollGag *G = &c->gag[g];
  if (G->room != p->room) return 0;
  if (G->random && !c->st.gagPick[g]) return 0;
  return 1;
}
static int gagInside(const CollGag *G, float x, float y, float z) {
  float dx = x - G->tx, dy = y - G->ty, dz = z - G->tz; return dx * dx + dy * dy + dz * dz <= G->tr * G->tr;
}
static int gagFree(const Collect *c, unsigned g) {   // можно запустить сейчас
  const CollState *s = &c->st;
  if (s->gagSt[g] == 1) return 0;
  if (s->gagSt[g] == 2 && c->gag[g].cycle == COLL_SINGLE) return 0;
  return 1;
}

static int actionGag(const Collect *c, const CollPlayer *p) {   // ближайший action-гэг, в чьей сфере стоит Гомер пешком
  if (!p->onFoot) return -1;
  int best = -1; float bd = 1e30f;
  for (unsigned g = 0; g < c->ngag; g++) {
    const CollGag *G = &c->gag[g];
    if (!TICKET_CONTENT_C3_OLD && G->pad==1 && (c->st.ticketFlags&TICKET_OWNED)) continue;
    if (G->trig != COLL_ACTION || !gagHere(c, g, p) || !gagFree(c, g) || !gagInside(G, p->x, p->y, p->z)) continue;
    float dx = p->x - G->tx, dz = p->z - G->tz, d = dx * dx + dz * dz;
    if (d < bd) { bd = d; best = (int)g; }
  }
  return best;
}
int collectWantsAction(const Collect *c) {
  const CollState *s = &c->st;
  CollPlayer p = {s->px, s->py, s->pz, s->pOnFoot, s->pRoom, 0};
  return actionGag(c, &p);
}

static void gagCoins(Collect *c, unsigned g, Coins *coins, const ColWorld *world) {
  const CollGag *G = &c->gag[g];
  if (!G->coins || !coins) return;
  if (G->room >= 0) { coins->collected += G->coins; return; }   // в комнате монеты не рисуются: сразу в кошелёк (правило порта)
  float fl = G->y, gy;
  if (world && colGround(world, G->x, G->z, G->y + 2.f, G->y - 6.f, &gy, 0)) fl = gy;
  coinsDrop(coins, G->coins, G->x, G->y + .6f, G->z, fl);
}

static void gagStart(Collect *c, unsigned g) {
  CollState *s = &c->st; const CollGag *G = &c->gag[g];
  if(!TICKET_CONTENT_C3_OLD && G->pad){push(c,CE_TICKET,(int)g,G->x,G->y,G->z);return;}
  s->gagSt[g] = 1; s->gagT[g] = 0.f; s->gagRuns++;
  if (G->inst >= 0) spEnter(&c->sp, (unsigned)G->inst, 1);
  push(c, CE_GAG_START, (int)g, G->x, G->y, G->z);
  if (!s->gagFound[g] && G->coins) {   // засчитывается один раз
    s->gagFound[g] = 1;
    if (c->level > 0 && c->level < COLL_LEVELS) s->gags[c->level] |= 1ull << g;
    push(c, CE_GAG_FOUND, (int)g, G->x, G->y, G->z);
    int tot, got = collectCount(c, c->level, COLL_GAGS, &tot);
    if (got == tot && tot) push(c, CE_GAGS_DONE, (int)g, G->x, G->y, G->z);
  }
}

static void gagsStep(Collect *c, const CollPlayer *p, Coins *coins, const ColWorld *world, float dt) {
  CollState *s = &c->st;
  if (p->room != s->lastRoom) {   // вход в комнату (или в город): выбор random-гэгов и сброс непостоянных
    if (p->room >= 0) {
      unsigned idx[COLL_MAXGAG], n = 0;
      for (unsigned g = 0; g < c->ngag; g++) if (c->gag[g].room == p->room && c->gag[g].random) { s->gagPick[g] = 0; idx[n++] = g; }
      if (n) s->gagPick[idx[rnd(s) % n]] = 1;
    }
    for (unsigned g = 0; g < c->ngag; g++) {
      const CollGag *G = &c->gag[g];
      if (G->room != p->room || G->persist) continue;
      s->gagSt[g] = 0; s->gagT[g] = 0.f;
      if (G->inst >= 0) spEnter(&c->sp, (unsigned)G->inst, 0);
    }
    for (unsigned g = 0; g < c->ngag; g++) s->gagIn[g] = c->gag[g].room == p->room && gagInside(&c->gag[g], p->x, p->y, p->z);   // стоял в триггере при входе — не срабатывает, пока не выйдет
    s->lastRoom = p->room;
  }
  int act = p->action ? actionGag(c, p) : -1;
  for (unsigned g = 0; g < c->ngag; g++) {
    const CollGag *G = &c->gag[g];
    if (s->gagSt[g] == 1) {   // играет: конец по длительности данных (сцена SPR1 сама уходит в «сыграл»/«ждёт»)
      s->gagT[g] += dt;
      float cd = G->coinDelay < 0.f ? G->len : G->coinDelay;
      if (!s->gagCoin[g] && s->gagFound[g] && G->coins && s->gagT[g] >= cd) { s->gagCoin[g] = 1; gagCoins(c, g, coins, world); }
      if (G->cycle != COLL_CYCLE && s->gagT[g] >= G->len) {
        s->gagSt[g] = G->cycle == COLL_SINGLE ? 2 : 0;
        push(c, CE_GAG_END, (int)g, G->x, G->y, G->z);
      }
    }
    if (!gagHere(c, g, p)) { s->gagIn[g] = 0; continue; }
    int in = gagInside(G, p->x, p->y, p->z);
    if (G->trig == COLL_TOUCH) { if (in && !s->gagIn[g] && gagFree(c, g)) gagStart(c, g); }
    else if ((int)g == act) gagStart(c, g);
    s->gagIn[g] = (uint8_t)in;
  }
}

// Attachment and visibility while HS_HURT are port rules. The sprite geometry,
// colours and kick's 14 frames / 30 fps are authored on the disc.
static void footFxPlace(Collect *c, int inst, const Homer *h) {
  if (inst < 0 || !h) return;
  SpRun *r = c->sp.run + inst; r->x = h->x; r->y = h->y; r->z = h->z; setYaw(r, h->h);
}
void collectFootKick(Collect *c, const Homer *h) {
#ifndef FOOT_FX_OLD
  if (c && c->haveSp && c->kickFx >= 0) { spEnter(&c->sp, c->kickFx, 1); c->sp.run[c->kickFx].alive = 1; footFxPlace(c, c->kickFx, h); }
#endif
}
static void footFxStep(Collect *c, const Homer *h) {
#ifndef FOOT_FX_OLD
  if (!h) return;
  footFxPlace(c, c->kickFx, h); footFxPlace(c, c->shockFx, h);
  if (c->st.shockOn && h->state != HS_HURT) { c->st.shockOn = 0; hide(c, c->shockFx); }
#endif
}
void collectStep(Collect *c, const CollPlayer *p, Homer *homer, Car *car, const ColWorld *world, Coins *coins, float dt) {
  CollState *s = &c->st;
  if (dt <= 0.f) return;
  cardsStep(c, p);
  boltsStep(c, p, homer, world, dt);
  waspsStep(c, p, homer, car, world, dt);
  gagsStep(c, p, coins, world, dt);
  footFxStep(c, homer);
  if (c->haveSp) spUpdate(&c->sp, world, car, coins, dt);   // карточки крутятся, осы летают/умирают (удар машины — там же), сцены гэгов
  // частицы окон EFX копятся в c->sp (spFxPop): main.c забирает после кадра; без вызывающего очередь просто полна (SP_FXQ)
  s->px = p->x; s->py = p->y; s->pz = p->z; s->pOnFoot = p->onFoot; s->pRoom = p->room;
}
