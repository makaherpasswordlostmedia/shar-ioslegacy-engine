// Exercise the lateral tyre collider actually called from carUpdate.
#include <stdio.h>
#include "../../viewer/car.c"

static void emit(Car *c) {
  M3 M=quatM(c->q);
  V3 model=add(v3(c->x,c->y,c->z),scl(M.U,carModelLift(c,c->p.modelLift)));
  printf("%s",c->p.name);
  for(int i=0;i<4;i++)printf(" %.9g",c->q[i]);
  printf(" %.9g %.9g %.9g %.9g %.9g",model.x,model.y,model.z,c->p.suspensionYOffset,c->lim);
  for(int i=0;i<4;i++)printf(" %.9g",c->comp[i]);
  printf(" %.9g",c->wheelSteer);
  for(int i=0;i<4;i++)printf(" %.9g",c->wheelSpin[i]);
  for(int i=0;i<4;i++) {
    float radius;V3 point=add(v3(c->x,c->y,c->z),mulM(&M,wheelColliderLocal(c,i,&radius)));
    printf(" %.9g %.9g %.9g %.9g",point.x,point.y,point.z,radius);
  }
  putchar('\n');
}

int main(int argc,char **argv) {
  if(argc==2&&!strcmp(argv[1],"--pose")) {
    Car c={0};float m[16],comp[4],spin[4],steer;char name[16];
    if(scanf("%15s",name)!=1||!carParamsFor(name,&c.p))return 2;
    for(int i=0;i<16;i++)if(scanf("%f",&m[i])!=1)return 2;
    for(int i=0;i<4;i++)if(scanf("%f",&comp[i])!=1)return 2;
    if(scanf("%f",&steer)!=1)return 2;
    for(int i=0;i<4;i++)if(scanf("%f",&spin[i])!=1)return 2;
    derive(&c);memcpy(c.comp,comp,sizeof comp);c.wheelSteer=steer;memcpy(c.wheelSpin,spin,sizeof spin);
    M3 M={v3(-m[0],-m[1],m[2]),v3(m[4],m[5],-m[6]),v3(m[8],m[9],-m[10])};
    mQuat(&M,c.q);quatNorm(c.q);
    V3 pos=sub(v3(m[12],m[13],-m[14]),scl(M.U,carModelLift(&c,c.p.modelLift)));
    c.x=pos.x;c.y=pos.y;c.z=pos.z;emit(&c);return 0;
  }
  // Steering covers both locks and centre; spin covers a quarter turn, a
  // half turn and an angle that leaves every wheel at a different phase.
  static const float steer[3]={0.f,.52f,-.37f};
  static const float spin[3][4]={{0,0,0,0},{1.5707964f,1.5707964f,3.1415927f,3.1415927f},{.7f,-2.1f,2.9f,-.4f}};
  for(unsigned k=0;k<sizeof carWheelCollision/sizeof *carWheelCollision;k++)
    for(int pose=0;pose<4;pose++)for(int motion=0;motion<6;motion++)for(int art=0;art<3;art++) {
      Car c={0};if(!carParamsFor(carWheelCollision[k].name,&c.p))return 2;derive(&c);
      c.x=11.f;c.y=3.f;c.z=-7.f;c.q[0]=1;c.q[1]=.19f*pose;c.q[2]=-.13f*pose;c.q[3]=.11f*pose;
      quatNorm(c.q);c.wheelSteer=steer[art];memcpy(c.wheelSpin,spin[art],sizeof c.wheelSpin);
      for(int i=0;i<4;i++)c.comp[i]=motion==0?0:motion==1?c.eq:motion==2?c.lim:motion==3?c.lim*(i+1)/4:motion==4?-c.eq:c.lim*2;
      emit(&c);
    }
  return 0;
}
