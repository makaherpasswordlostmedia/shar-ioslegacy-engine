// FE main-menu clock. SLES 0x1b9088..0x1b952c and ps2-main-menu-runtime:
// pending at next-2000ms, play at next, pause outside the main-menu screen.
#ifndef FE_GAG_CLOCK_H
#define FE_GAG_CLOCK_H
#ifndef FE_GAG_CLOCK_OLD
#define FE_GAG_CLOCK_OLD 0
#endif
#ifndef FE_GAG_PREP_OLD
#define FE_GAG_PREP_OLD 0
#endif
typedef struct { unsigned elapsed, next; int pending, segment; } FeGagClock;
enum { FE_GAG_PREPARE = 1, FE_GAG_PLAY = 2 };
static inline void feGagClockInit(FeGagClock *s) {
  s->elapsed = 0; s->next = 15000; s->pending = s->segment = -1;
}
static inline void feGagClockStarted(FeGagClock *s, unsigned (*rnd)(void)) {
  s->elapsed = 0; s->next = (15u + (rnd() & 15u)) * 1000u;
  s->pending = s->segment = -1;
}
static inline unsigned feGagClockStep(FeGagClock *s, unsigned ms, int active, int flying,
                                     int count, unsigned (*rnd)(void)) {
  if (count <= 0 || (!active && !FE_GAG_CLOCK_OLD)) return 0;
  s->elapsed += ms;
  int mayPlay = FE_GAG_CLOCK_OLD ? !flying : active;
  if (!mayPlay) return 0;
  if (FE_GAG_PREP_OLD) return s->elapsed > s->next ? FE_GAG_PLAY : 0;
  unsigned ev = 0;
  if (s->pending < 0 && s->elapsed >= s->next - 2000u) {
    s->pending = (int)((rnd() / 10u % 97u) % (unsigned)count);
    s->segment = s->pending == 0 ? (int)((rnd() / 10u % 97u) % 5u) : -1;
    ev |= FE_GAG_PREPARE;
  }
  if (s->elapsed >= s->next) ev |= FE_GAG_PLAY;
  return ev;
}
#endif
