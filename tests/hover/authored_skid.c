// Exercise real audio.c selection, skid voices and DSP on an exported bank.
// Expected names come from observer c778803 / ps2-hover-sound-config.yaml.
#include "../../viewer/audio.c"
static int bad;
static void check(int ok, const char *what) { if (!ok) { printf("FAIL %s\n", what); bad++; } }
int main(int argc, char **argv) {
  if (argc != 6 || audioInit(argv[1])) return 2;
  const char *name=argv[2], *engine=argv[3], *expected[2]={argv[4],argv[5]};
  check(audioCarProfile(name)>=0,"profile present");
  audioPlayerCar(name);
  check(!strcmp(car->name,name),"selected player profile");
  check(car->engine>=0 && !strcmp(R[car->engine].name,engine),"authored engine");
  check(car->idle>=0 && !strcmp(R[car->idle].name,engine),"authored idle");
  for (int dirt=0;dirt<2;dirt++) {
    audioSkid(0,dirt);
    // audioStop fades the previous voice; drain it before measuring silence.
    short drain[1024]; for(int n=0;n<16;n++) audioHostMix(drain,512);
    audioSkid(.8f,dirt);
    int silent=(!strcmp(expected[dirt],"blank") || !strcmp(expected[dirt],"witchcar_v_skid"));
    if (silent) check(!audioPlaying(E.skid),"blank does not allocate voice");
    else {
      check(audioPlaying(E.skid),"skid voice starts");
      check(E.skidRes>=0 && !strcmp(R[E.skidRes].name,expected[dirt]),"authored skid resource");
    }
    int handle=E.skid,peak=0; short pcm[1024];
    for (int n=0;n<12;n++) {
      audioHostMix(pcm,512); audioSkid(.8f,dirt);
      for(int k=0;k<1024;k++) if(abs(pcm[k])>peak)peak=abs(pcm[k]);
    }
    check(E.skid==handle,"no per-frame voice restart");
    check(silent ? peak==0 : peak>0,"decoded skid PCM silence/nonzero");
    audioSkid(0,dirt); check(!audioPlaying(E.skid),"release stops skid");
    printf("%s surface=%d expected=%s peak=%d\n",name,dirt,expected[dirt],peak);
  }
  audioShutdown(); printf("%s failures=%d\n",bad?"FAIL":"PASS",bad); return bad?1:0;
}
