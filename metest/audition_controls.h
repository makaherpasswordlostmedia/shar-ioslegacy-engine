#pragma once
// Portable input state shared with the exact host regression
enum {AU_NEAR=1,AU_FAR=2,AU_LEFT=4,AU_RIGHT=8,AU_ROUTE=16,AU_SWEEP=32,
      AU_MUTE=64,AU_CENTER=128,AU_SNAP_LEFT=256,AU_SNAP_RIGHT=512,AU_EXIT=1024};
typedef struct {int dist,side,useME,autoSweep,muted;unsigned previous,repeatAt,heldMoves;} AudControls;
static unsigned audControlsStep(AudControls *a,unsigned keys,unsigned time,unsigned frame){
  unsigned hit=keys&~a->previous,dir=keys&15;
  a->previous=keys;
  if(hit&AU_ROUTE)a->useME=!a->useME;
  if(hit&AU_SWEEP)a->autoSweep=!a->autoSweep;
  if(hit&AU_MUTE)a->muted=!a->muted;
  if(hit&AU_CENTER){a->dist=10;a->side=0;a->autoSweep=0;}
  if(hit&AU_SNAP_LEFT){a->side=-20;a->autoSweep=0;}
  if(hit&AU_SNAP_RIGHT){a->side=20;a->autoSweep=0;}
  if(dir){
    a->autoSweep=0; // Manual movement takes ownership, never overwritten by sweep
    int move=(hit&15)!=0;
    if(move)a->repeatAt=time+250000;
    else if((int)(time-a->repeatAt)>=0){move=1;a->repeatAt=time+70000;a->heldMoves++;}
    if(move){
      if(dir&AU_NEAR)a->dist--;if(dir&AU_FAR)a->dist++;
      if(dir&AU_LEFT)a->side-=2;if(dir&AU_RIGHT)a->side+=2;
    }
  }
  if(a->dist<1)a->dist=1;if(a->dist>65)a->dist=65;
  if(a->side<-30)a->side=-30;if(a->side>30)a->side=30;
  if(a->autoSweep){unsigned q=frame%1040;a->dist=1+(q<520?q:1040-q)/8;a->side=(int)((frame/8)%61)-30;}
  return hit;
}
