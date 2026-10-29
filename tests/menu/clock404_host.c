#include <stdio.h>
#include "fe_gag_clock.h"
static unsigned calls, value;
static unsigned rnd(void) { calls++; return value; }
static int bad;
static void check(const char *n,int ok) { printf("CHECK %s %s\n",n,ok?"PASS":"FAIL"); bad+=!ok; }
int main(void) {
  FeGagClock s; feGagClockInit(&s); value=70;
  unsigned prep=0,play=0;
  for(unsigned t=20;t<=15000;t+=20) {
    unsigned e=feGagClockStep(&s,20,1,0,8,rnd);
    if(e&FE_GAG_PREPARE)prep=t;
    if(e&FE_GAG_PLAY)play=t;
  }
  check("PS2_first_15000ms",play==15000);
  check("PS2_prepare_13000ms",prep==13000);
  check("same_pending_index_at_play",s.pending==7&&calls==1);
  feGagClockStarted(&s,rnd);
  check("reset_after_play",s.elapsed==0&&s.pending==-1&&s.next>=15000&&s.next<=30000);
  // V100 return retained exactly12238ms; wall time on another screen is irrelevant.
  s.elapsed=12238; s.next=30000;
  for(int i=0;i<1000;i++)feGagClockStep(&s,20,0,0,8,rnd);
  check("LoadGame_Options_retained_12238",s.elapsed==12238);
  feGagClockStep(&s,20,1,0,8,rnd);
  check("Back_resumes_without_reset",s.elapsed==12258);
  unsigned keep=s.elapsed;
  for(int i=0;i<100;i++)feGagClockStep(&s,20,0,1,8,rnd);
  check("flight_clock_frozen",s.elapsed==keep);
  // A prepared request survives a round trip; RNG is not consumed a second time.
  feGagClockInit(&s);calls=0;value=0;
  for(int i=0;i<650;i++)feGagClockStep(&s,20,1,0,8,rnd);
  check("Homer_segment_preselected",s.pending==0&&s.segment==0&&calls==2);
  unsigned n=calls;
  for(int i=0;i<1000;i++)feGagClockStep(&s,20,0,0,8,rnd);
  check("pending_survives_pause",s.elapsed==13000&&s.pending==0&&calls==n);
  unsigned e=0;for(int i=0;i<100;i++)e=feGagClockStep(&s,20,1,0,8,rnd);
  check("prepared_Homer_starts_after_remaining_2s",(e&FE_GAG_PLAY)&&s.elapsed==15000&&calls==n);
  printf("RESULT failures=%d\n",bad);return bad?1:0;
}
