// №390: actual shared DSP, moving listener / stationary source, camera rotation, distance and kernel-copy equality
#include <stdio.h>
#include <string.h>
#include "mixdsp.h"
static MixJob job,copy,kernel;
static unsigned char bank[16]={0,0,0x77,0x77,0x77,0x77,0x77,0x77,0x77,0x77,0x77,0x77,0x77,0x77,0x77,0x77};
static void setup(int x,int z,int red) {
  memset(&job,0,sizeof job);job.data=bank;job.right[0]=32767;
  MixVoice *v=&job.v[0];v->on=1;v->ch=1;v->stream=-1;v->loop=1;v->loopEnd=v->end=28;
  v->bufLen=1;v->pos=1u<<16;v->tstep=v->step=65536;v->tgl=v->tgr=32768;v->spatialStart=1;
  v->point=(MixPoint){!red,{x,0,z},64,960};
}
int main(int argc,char **argv) {
  int red=argc>1&&!strcmp(argv[1],"--red"),copyred=argc>1&&!strcmp(argv[1],"--copy-red"),fail=0;
  setup(160,0,red);mixDspRun(&job);int rightL=job.v[0].gl,rightR=job.v[0].gr;
  if(!(rightR>4*rightL && rightR>20000))fail++;
  job.listener[0]=320;mixDspRun(&job); // same voice keeps playing while listener walks past the source
  if(!(job.v[0].gl>4*job.v[0].gr && job.v[0].gl==rightR))fail++;
  job.right[0]=-32767;mixDspRun(&job);
  if(!(job.v[0].gr>4*job.v[0].gl))fail++;
  setup(0,160,red);mixDspRun(&job);if(job.v[0].gl!=job.v[0].gr)fail++;
  setup(960,0,red);mixDspRun(&job);if(job.v[0].gl || job.v[0].gr)fail++;
  for(int i=0;i<MIX_FRAMES*2;i++)if(job.acc[i]){fail++;break;}
  setup(160,0,0);job.listener[0]=320;job.right[0]=-32767;copy=job;memset(&kernel,0,sizeof kernel);
  mixJobIn(&kernel,&copy);
  if(copyred)kernel.listener[0]=0; // negative: omitted listener transfer, as an incomplete old header copy would do
  mixDspRun(&job);mixDspRun(&kernel);mixJobOut(&copy,&kernel);
  if(memcmp(job.acc,copy.acc,sizeof job.acc) || job.v[0].gl!=copy.v[0].gl || job.v[0].gr!=copy.v[0].gr)fail++;
  setup(0,0,0);job.v[0].point.on=0;mixDspRun(&job);
  if(job.v[0].gl!=32768 || job.v[0].gr!=32768)fail++;
  // Walk away in 25 cm increments: continuous roll-off, no loud/silent cliff
  setup(0,0,red);int previous=32768,levels=0;
  for(int metresQ4=0;metresQ4<=976;metresQ4+=4) {
    job.v[0].point.p[2]=metresQ4;mixDspRun(&job);int gain=job.v[0].gl;
    if(gain>previous || previous-gain>384 || gain!=job.v[0].gr)fail++;
    levels+=gain!=previous;previous=gain;
    if(metresQ4==64 || metresQ4==160 || metresQ4==320 || metresQ4==640 || metresQ4==960)
      printf("distance %.2f m gain %.5f\n",metresQ4/16.,gain/32768.);
  }
  if(levels<100 || previous!=0)fail++;
  printf("%s failures%d: stationary source / moving listener / rotated camera / cutoff / copied kernel / 2D\n",fail?"FAIL":"PASS",fail);
  return fail?1:0;
}
