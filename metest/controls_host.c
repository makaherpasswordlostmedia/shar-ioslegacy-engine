#include <stdio.h>
#include "audition_controls.h"
static int red,fail,cases;
static unsigned step(AudControls *a,unsigned keys,unsigned t,unsigned frame){
  unsigned result=audControlsStep(a,keys,t,frame);
  if(red && (keys&15)){unsigned q=frame%1040;a->autoSweep=1;a->dist=1+(q<520?q:1040-q)/8;a->side=(int)((frame/8)%61)-30;}
  return result;
}
static void check(int ok){cases++;fail+=!ok;}
int main(int argc,char **argv){
  (void)argv;red=argc>1;AudControls a={10,0,1,0,0,AU_SWEEP,0,0};
  step(&a,AU_SWEEP,0,0);check(!a.autoSweep); // held CROSS from suite start ignored
  step(&a,0,10,1);step(&a,AU_SWEEP,20,2);check(a.autoSweep);
  int d=a.dist;step(&a,AU_FAR,30,3);check(!a.autoSweep && a.dist==d+1);
  d=a.dist;step(&a,AU_FAR,100000,4);check(a.dist==d);
  step(&a,AU_FAR,260000,5);check(a.dist==d+1 && a.heldMoves==1);
  step(&a,AU_FAR,330000,6);check(a.dist==d+2 && a.heldMoves==2);
  step(&a,0,340000,7);step(&a,AU_SNAP_LEFT,350000,8);check(a.side==-20&&!a.autoSweep);
  step(&a,0,360000,9);step(&a,AU_SNAP_RIGHT,370000,10);check(a.side==20);
  step(&a,0,380000,11);step(&a,AU_CENTER,390000,12);check(a.side==0&&a.dist==10&&!a.autoSweep);
  step(&a,AU_ROUTE,400000,13);check(!a.useME);step(&a,AU_ROUTE,410000,14);check(!a.useME);
  step(&a,AU_MUTE,420000,15);check(a.muted);
  for(int i=0;i<200;i++)step(&a,AU_NEAR|AU_LEFT,500000+i*70000,16+i);
  check(a.dist==1&&a.side==-30);
  for(int i=0;i<200;i++)step(&a,AU_FAR|AU_RIGHT,15000000+i*70000,216+i);
  check(a.dist==65&&a.side==30);
  step(&a,0,30000000,500);check(step(&a,AU_EXIT,30000100,501)&AU_EXIT);
  printf("%s controls checks=%d failures=%d negative=%d\n",fail?"FAIL":"PASS",cases,fail,red);return fail?1:0;
}
