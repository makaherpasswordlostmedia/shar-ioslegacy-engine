// Ten actual collisions without trafficReset between them, then normal distance culling/refill
#define main historicalHitlaneMain
#include "hitlane.c"
#undef main
int main(int argc,char **argv){
 const char *lvl=argc>1?argv[1]:"build/level.shr",*trf=argc>2?argv[2]:"build/traffic.shr";
 FILE*f=fopen(lvl,"rb");if(!f)return 2;unsigned char hdr[104];if(fread(hdr,1,104,f)!=104)return 2;
 unsigned co=*(unsigned*)(hdr+92),po=*(unsigned*)(hdr+96),pv=*(unsigned*)(hdr+88);fseek(f,0,SEEK_END);unsigned end=ftell(f);
 if(po>co&&po<end)end=po;if(pv>co&&pv<end)end=pv;unsigned char*col=readAt(f,co,end-co);fclose(f);if(!col||colInit(&world,col,end-co))return 2;
 f=fopen(trf,"rb");if(!f)return 2;fseek(f,0,SEEK_END);unsigned sz=ftell(f);unsigned char*data=readAt(f,0,sz);fclose(f);if(!data||trafficInitMem(&T,data,sz,0))return 2;T.maxPeds=0;
 const float spots[2][2]={{220,172},{193.8f,570}};int collisions=0,culls=0;trafficReset(&T,&world);
 for(int turn=0;turn<10;turn++){
  const float*at=spots[turn&1];carInit(&player,NULL,&world,at[0],ground(at[0],at[1],50),at[1],0);
  int drv=-1;
  for(int fr=0;fr<300&&drv<0;fr++){
   step();for(int i=0;i<T.maxCars;i++)if(T.car[i].mode==TRM_DRIVE&&T.car[i].v>3){drv=i;break;}
  }
  if(drv<0){printf("FAIL pool depleted after %d collisions\n",collisions);return 1;}
  Car*k=&T.car[drv].car;float h=k->h+3.14159265f,sx=k->x+sinf(k->h)*9,sz=k->z+cosf(k->h)*9;
  carInit(&player,NULL,&world,sx,k->y+.5f,sz,h);carSetSpeed(&player,8);
  int impact=0;
  for(int fr=0;fr<60&&!impact;fr++){
   CarInput in={0};carUpdate(&player,&world,&in,DT);
   float pp[3]={player.x,player.y,player.z},eye[3]={player.x,player.y+3,player.z},fw[3]={sinf(h),0,cosf(h)};
   trafficUpdate(&T,&world,&player,1,pp,eye,fw,DT);impact=T.car[drv].mode==TRM_PHYS;
  }
  if(!impact){printf("FAIL collision setup turn%d\n",turn);return 1;}collisions++;
  float oldx=k->x,oldz=k->z;
  carInit(&player,NULL,&world,player.x-sinf(h)*12,player.y+.5f,player.z-cosf(h)*12,h);
  for(int fr=0;fr<90;fr++){step();if(T.car[drv].mode==TRM_DRIVE){puts("FAIL unexpected lane restart");return 1;}}
  const float*far=spots[(turn+1)&1];carInit(&player,NULL,&world,far[0],ground(far[0],far[1],50),far[1],0);
  // Observe the actual culling phase before it can immediately reuse the same slot
  T.scanT=1000;T.fresh=0;step();
  if(T.car[drv].mode!=TRM_OFF){printf("FAIL old hit car not culled turn%d distance%.1f\n",turn,hypotf(oldx-player.x,oldz-player.z));return 1;}
  culls++;T.scanT=0;int drive=0;
  for(int fr=0;fr<60&&!drive;fr++){step();for(int i=0;i<T.maxCars;i++)drive+=T.car[i].mode==TRM_DRIVE;}
  if(!drive){puts("FAIL no refill after normal cull");return 1;}
  printf("PASS turn%d collision/cull/refill drive%d\n",turn,drive);
 }
 printf("PASS pool collisions%d culled%d refilled10 no reset between collisions\n",collisions,culls);trafficFree(&T);colFree(&world);free(col);free(data);return 0;
}
