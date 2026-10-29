// Лучи полиции (правка 495): углы квадов лежат у машины (<= 10 м от крыши), конечны, движутся по кадрам; выключатели _OLD
#include <stdio.h>
#include <stdlib.h>
#include "../../viewer/police_fx.c"
int main(void){
 McCar c={0};c.on=c.police=1;strcpy(c.name,"cPolice");c.car.q[0]=1;float eye[3]={0,3,10};PfQuad q[PF_BEAMS];
 float lo=1e9,hi=-1e9,moved=0,prev[PB_COUNT][3]={{0}};
 for(int i=0;i<84;i++){
  float t=i/(24.f*2);int n=policeFxBeams(&c,t,eye,q);if(n!=PF_BEAMS){printf("FAIL n=%d\n",n);return 1;}
  for(int j=0;j<n;j++){for(int k=0;k<6;k++){float x=q[j].v[k].x,y=q[j].v[k].y,z=q[j].v[k].z;
    if(!isfinite(x+y+z)||fabsf(x)>17||fabsf(z)>17||y<-3||y>6){printf("FAIL v %d %d %g %g %g\n",j,k,x,y,z);return 1;}
    lo=fminf(lo,x);hi=fmaxf(hi,x);}
   if(i&&(fabsf(q[j].v[1].x-prev[j][0])+fabsf(q[j].v[1].z-prev[j][2]))>1e-3f)moved+=1;
   prev[j][0]=q[j].v[1].x;prev[j][2]=q[j].v[1].z;}
 }
 if(moved<80){printf("FAIL beams do not move %g\n",moved);return 1;}
 policeBeamOld=1;if(policeFxBeams(&c,0,eye,q))return 1;policeBeamOld=0;
 c.police=0;if(policeFxBeams(&c,0,eye,q))return 1;c.police=1;c.car.destroyed=1;if(policeFxBeams(&c,0,eye,q))return 1;
 c.car.destroyed=0;strcpy(c.name,"cHears");if(policeFxBeams(&c,0,eye,q))return 1;
 strcpy(c.name,"cPolice");float far[3]={0,3,200};if(policeFxBeams(&c,0,far,q))return 1;
 { // №538: затухание по углу — гладкое, без скачка альфы между соседними кадрами; в стороне от ребра полная яркость; ребром — ноль
  float eye2[3]={0,3,10};float aprev[PB_COUNT]={0},amax=0,jump=0,amin=1;int full=0,zero=0,tot=0;
  for(int i=0;i<=840;i++){float tt=i/(24.f*20);PfQuad qq[PF_BEAMS];policeFxBeams(&c,tt,eye2,qq);
   for(int j=0;j<PB_COUNT;j++){float a=(qq[j].v[0].color>>24)/255.f;if(i){float d=fabsf(a-aprev[j]);if(d>jump)jump=d;}aprev[j]=a;if(a>amax)amax=a;if(a<amin)amin=a;full+=a>0.99f;zero+=a<0.01f;tot++;}}
  if(jump>0.25f){printf("FAIL alpha jump %g\n",jump);return 1;}
  if(!(full>tot/5)||!(zero>0)||amax<0.99f){printf("FAIL fade range full %d zero %d of %d\n",full,zero,tot);return 1;}
  policeSirenFadeOld=1;PfQuad q0[PF_BEAMS];policeFxBeams(&c,0.37f,eye2,q0);for(int j=0;j<PB_COUNT;j++)if((q0[j].v[0].color>>24)!=(pbDefs[j].color>>24)){printf("FAIL old path alpha\n");return 1;}policeSirenFadeOld=0;
  printf("fade: max alpha step per 1/480 s %.3f, full %d%%, zero %d%% of samples\n",jump,100*full/tot,100*zero/tot);
 }
 printf("PASS x %.2f..%.2f moved %g\n",lo,hi,moved);return 0;
}
