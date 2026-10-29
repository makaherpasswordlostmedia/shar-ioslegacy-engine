/* ios_host.m - UIKit / EAGL / AudioQueue / touch host for the SHAR engine.
 * iOS 7.0+ armv7, ARC on, OpenGL ES 2.0. The engine runs on its own thread (shar_main). */
#import <UIKit/UIKit.h>
#import <QuartzCore/QuartzCore.h>
#import <OpenGLES/EAGL.h>
#import <OpenGLES/ES2/gl.h>
#import <OpenGLES/ES2/glext.h>
#import <AudioToolbox/AudioToolbox.h>
#import <AVFoundation/AVFoundation.h>
#import <ImageIO/ImageIO.h>
#import <GameController/GameController.h>
#include <pthread.h>
#include <stdarg.h>
#include "psp_compat.h"

extern int shar_main(int argc, char **argv);

/* ---------------- paths / log ---------------- */
static char g_docs[512]; static FILE *g_log; static pthread_mutex_t g_lm = PTHREAD_MUTEX_INITIALIZER;
const char *ios_docs_dir(void) { return g_docs; }
void ios_log(const char *f, ...) { pthread_mutex_lock(&g_lm); if (!g_log) { char p[600]; snprintf(p, sizeof p, "%s/shar_ios.log", g_docs); g_log = fopen(p, "a"); }
  va_list a; va_start(a, f); if (g_log) { vfprintf(g_log, f, a); fputc('\n', g_log); fflush(g_log); } va_end(a); pthread_mutex_unlock(&g_lm); }
void ios_exit_requested(void) { ios_log("exit requested"); }

/* ---------------- GL view ---------------- */
@interface GLView : UIView @end
@implementation GLView + (Class)layerClass { return [CAEAGLLayer class]; } @end
static GLView *g_view; static EAGLContext *g_ctx; static GLuint g_fbo, g_rbo, g_zrb; static GLint g_w, g_h;

void ios_gl_make_current(void) {
  if (!g_ctx) {
    __block CAEAGLLayer *l = nil;
    dispatch_sync(dispatch_get_main_queue(), ^{ l = (CAEAGLLayer *)g_view.layer; l.opaque = YES; l.contentsScale = [UIScreen mainScreen].scale > 1.0 ? 1.0 : 1.0;
      l.drawableProperties = @{ kEAGLDrawablePropertyRetainedBacking: @NO, kEAGLDrawablePropertyColorFormat: kEAGLColorFormatRGBA8 }; });
    g_ctx = [[EAGLContext alloc] initWithAPI:kEAGLRenderingAPIOpenGLES2]; [EAGLContext setCurrentContext:g_ctx];
    glGenFramebuffers(1, &g_fbo); glGenRenderbuffers(1, &g_rbo); glBindFramebuffer(GL_FRAMEBUFFER, g_fbo); glBindRenderbuffer(GL_RENDERBUFFER, g_rbo);
    [g_ctx renderbufferStorage:GL_RENDERBUFFER fromDrawable:l]; glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_RENDERBUFFER, g_rbo);
    glGetRenderbufferParameteriv(GL_RENDERBUFFER, GL_RENDERBUFFER_WIDTH, &g_w); glGetRenderbufferParameteriv(GL_RENDERBUFFER, GL_RENDERBUFFER_HEIGHT, &g_h);
    glGenRenderbuffers(1, &g_zrb); glBindRenderbuffer(GL_RENDERBUFFER, g_zrb); glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH_COMPONENT16, g_w, g_h);
    glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_RENDERBUFFER, g_zrb); glBindRenderbuffer(GL_RENDERBUFFER, g_rbo);
    ios_log("GL %dx%d status=%x", g_w, g_h, glCheckFramebufferStatus(GL_FRAMEBUFFER));
  } else [EAGLContext setCurrentContext:g_ctx];
}
void ios_screen_size(int *w, int *h) { ios_gl_make_current(); *w = g_w; *h = g_h; }
void ios_present(void) { ios_gl_make_current(); glBindFramebuffer(GL_FRAMEBUFFER, g_fbo); glBindRenderbuffer(GL_RENDERBUFFER, g_rbo); [g_ctx presentRenderbuffer:GL_RENDERBUFFER]; glBindFramebuffer(GL_FRAMEBUFFER, g_fbo); }

/* ---------------- audio: ring buffer + AudioQueue (44.1k stereo s16) ---------------- */
#define RING 16384
static int16_t g_ring[RING * 2]; static volatile unsigned g_rw, g_rr; static AudioQueueRef g_aq; static int g_chan = -1;
static void aq_cb(void *u, AudioQueueRef q, AudioQueueBufferRef b) { (void)u; int16_t *o = (int16_t *)b->mAudioData; unsigned n = b->mAudioDataBytesCapacity / 4;
  for (unsigned i = 0; i < n; i++) { if (g_rr != g_rw) { o[i * 2] = g_ring[(g_rr % RING) * 2]; o[i * 2 + 1] = g_ring[(g_rr % RING) * 2 + 1]; g_rr++; } else { o[i * 2] = o[i * 2 + 1] = 0; } }
  b->mAudioDataByteSize = n * 4; AudioQueueEnqueueBuffer(q, b, 0, 0); }
static void audio_start(void) {
  AVAudioSession *s = [AVAudioSession sharedInstance]; [s setCategory:AVAudioSessionCategoryPlayback error:nil]; [s setActive:YES error:nil];
  AudioStreamBasicDescription f = { 44100, kAudioFormatLinearPCM, kAudioFormatFlagIsSignedInteger | kAudioFormatFlagIsPacked, 4, 1, 4, 2, 16, 0 };
  if (AudioQueueNewOutput(&f, aq_cb, 0, 0, 0, 0, &g_aq)) { ios_log("audio queue failed"); return; }
  for (int i = 0; i < 3; i++) { AudioQueueBufferRef b; AudioQueueAllocateBuffer(g_aq, 1024 * 4, &b); aq_cb(0, g_aq, b); } AudioQueueStart(g_aq, 0);
}
int sceAudioChReserve(int c, int n, int f) { (void)n; (void)f; if (!g_aq) audio_start(); g_chan = c < 0 ? 0 : c; return g_chan; }
int sceAudioChRelease(int c) { (void)c; return 0; }
int sceAudioGetChannelRestLen(int c) { (void)c; return (int)(g_rw - g_rr); }
int sceAudioOutputPannedBlocking(int c, int l, int r, void *buf) { (void)c; const int16_t *s = buf; int n = 512;
  while ((g_rw - g_rr) + (unsigned)n > RING) usleep(1000);
  for (int i = 0; i < n; i++) { g_ring[(g_rw % RING) * 2] = (int16_t)((s[i * 2] * l) >> 15); g_ring[(g_rw % RING) * 2 + 1] = (int16_t)((s[i * 2 + 1] * r) >> 15); g_rw++; } return 0; }
int sceAudioOutputBlocking(int c, int v, void *buf) { return sceAudioOutputPannedBlocking(c, v, v, buf); }

/* ---------------- MJPEG via ImageIO (cutscenes) ---------------- */
int sceJpegInitMJpeg(void) { return 0; } int sceJpegFinishMJpeg(void) { return 0; } int sceJpegCreateMJpeg(int w, int h) { (void)w; (void)h; return 0; } int sceJpegDeleteMJpeg(void) { return 0; }
int sceJpegDecodeMJpeg(unsigned char *j, unsigned size, void *rgba, unsigned dht) { (void)dht;
  @autoreleasepool { CFDataRef d = CFDataCreateWithBytesNoCopy(0, j, size, kCFAllocatorNull); CGImageSourceRef src = CGImageSourceCreateWithData(d, 0); if (!src) { CFRelease(d); return -1; }
    CGImageRef im = CGImageSourceCreateImageAtIndex(src, 0, 0); int w = 0, h = 0; if (im) { w = (int)CGImageGetWidth(im); h = (int)CGImageGetHeight(im);
      CGColorSpaceRef cs = CGColorSpaceCreateDeviceRGB(); CGContextRef cx = CGBitmapContextCreate(rgba, w, h, 8, w * 4, cs, kCGImageAlphaNoneSkipLast | kCGBitmapByteOrder32Big);
      CGContextDrawImage(cx, CGRectMake(0, 0, w, h), im); CGContextRelease(cx); CGColorSpaceRelease(cs); CGImageRelease(im); }
    CFRelease(src); CFRelease(d); return (w << 16) | h; } }

/* ---------------- touch pad (PSP layout) ---------------- */
@interface PadView : UIView @end
@implementation PadView
- (instancetype)initWithFrame:(CGRect)f { self = [super initWithFrame:f]; self.multipleTouchEnabled = YES; self.backgroundColor = [UIColor clearColor]; return self; }
- (void)recompute:(NSSet *)all {
  CGSize s = self.bounds.size; unsigned b = 0; float lx = 0, ly = 0; CGFloat u = s.height / 6.f;
  for (UITouch *t in all) { if (t.phase == UITouchPhaseEnded || t.phase == UITouchPhaseCancelled) continue; CGPoint p = [t locationInView:self]; CGFloat x = p.x, y = p.y;
    if (x < s.width * 0.34 && y > s.height * 0.25) { static CGPoint c; CGPoint o = [t previousLocationInView:self]; (void)o; c = CGPointMake(s.width * 0.17, s.height * 0.68);
      float dx = (float)((x - c.x) / (u * 1.4)), dy = (float)((y - c.y) / (u * 1.4)); dx = fmaxf(-1, fminf(1, dx)); dy = fmaxf(-1, fminf(1, dy)); lx = dx; ly = dy;
      if (dx < -0.4) b |= PSP_CTRL_LEFT; if (dx > 0.4) b |= PSP_CTRL_RIGHT; if (dy < -0.4) b |= PSP_CTRL_UP; if (dy > 0.4) b |= PSP_CTRL_DOWN; continue; }
    CGPoint bc = CGPointMake(s.width * 0.84, s.height * 0.66); CGFloat r = u * 0.95;
    if (x > s.width * 0.62 && y > s.height * 0.25) { CGFloat dx = x - bc.x, dy = y - bc.y; if (dx * dx + dy * dy < r * r * 6.f) {
        if (fabs(dx) > fabs(dy)) b |= dx < 0 ? PSP_CTRL_SQUARE : PSP_CTRL_CIRCLE; else b |= dy < 0 ? PSP_CTRL_TRIANGLE : PSP_CTRL_CROSS; continue; } }
    if (y < s.height * 0.22) { if (x < s.width * 0.2) b |= PSP_CTRL_LTRIGGER; else if (x > s.width * 0.8) b |= PSP_CTRL_RTRIGGER; continue; }
    if (y > s.height * 0.85 && x > s.width * 0.38 && x < s.width * 0.62) b |= x < s.width * 0.5 ? PSP_CTRL_SELECT : PSP_CTRL_START;
  }
  ios_pad_buttons = b; ios_pad_lx = (signed char)(lx * 127); ios_pad_ly = (signed char)(ly * 127);
}
- (void)touchesBegan:(NSSet *)t withEvent:(UIEvent *)e { [self recompute:[e allTouches]]; }
- (void)touchesMoved:(NSSet *)t withEvent:(UIEvent *)e { [self recompute:[e allTouches]]; }
- (void)touchesEnded:(NSSet *)t withEvent:(UIEvent *)e { [self recompute:[e allTouches]]; }
- (void)touchesCancelled:(NSSet *)t withEvent:(UIEvent *)e { [self recompute:[e allTouches]]; }
- (void)drawRect:(CGRect)r { CGSize s = self.bounds.size; CGFloat u = s.height / 6.f; CGContextRef c = UIGraphicsGetCurrentContext(); CGContextSetStrokeColorWithColor(c, [UIColor colorWithWhite:1 alpha:0.25].CGColor);
  CGContextStrokeEllipseInRect(c, CGRectMake(s.width * 0.17 - u * 1.4, s.height * 0.68 - u * 1.4, u * 2.8, u * 2.8));
  NSString *lab[4] = { @"△", @"○", @"✕", @"□" }; CGPoint bc = CGPointMake(s.width * 0.84, s.height * 0.66); CGFloat off[4][2] = { {0, -1}, {1, 0}, {0, 1}, {-1, 0} };
  for (int i = 0; i < 4; i++) { CGRect rr = CGRectMake(bc.x + off[i][0] * u * 1.1 - u * 0.4, bc.y + off[i][1] * u * 1.1 - u * 0.4, u * 0.8, u * 0.8); CGContextStrokeEllipseInRect(c, rr);
    [lab[i] drawInRect:CGRectOffset(rr, 0, u * 0.12) withFont:[UIFont systemFontOfSize:u * 0.45] lineBreakMode:NSLineBreakByClipping alignment:NSTextAlignmentCenter]; }
  [[UIColor colorWithWhite:1 alpha:0.3] set]; [@"L" drawAtPoint:CGPointMake(8, 8) withFont:[UIFont systemFontOfSize:18]]; [@"R" drawAtPoint:CGPointMake(s.width - 24, 8) withFont:[UIFont systemFontOfSize:18]];
  [@"SELECT   START" drawAtPoint:CGPointMake(s.width * 0.41, s.height - 24) withFont:[UIFont systemFontOfSize:14]]; }
@end

@interface VC : UIViewController @end
@implementation VC
- (BOOL)prefersStatusBarHidden { return YES; }
- (BOOL)shouldAutorotate { return YES; }
- (NSUInteger)supportedInterfaceOrientations { return UIInterfaceOrientationMaskLandscape; }
@end

static void *game_thread(void *a) { (void)a; ios_gl_make_current(); char *argv[] = { (char *)"SHARVIEW", 0 }; ios_log("shar_main start"); int r = shar_main(1, argv); ios_log("shar_main returned %d", r); return 0; }

@interface AppDelegate : UIResponder <UIApplicationDelegate> @property (strong) UIWindow *window; @end
@implementation AppDelegate
- (BOOL)application:(UIApplication *)app didFinishLaunchingWithOptions:(NSDictionary *)o {
  NSString *d = NSSearchPathForDirectoriesInDomains(NSDocumentDirectory, NSUserDomainMask, YES)[0]; strlcpy(g_docs, d.UTF8String, sizeof g_docs);
  [[NSFileManager defaultManager] createDirectoryAtPath:[d stringByAppendingPathComponent:@"SHARVIEW"] withIntermediateDirectories:YES attributes:nil error:nil];
  self.window = [[UIWindow alloc] initWithFrame:[UIScreen mainScreen].bounds]; VC *vc = [VC new]; self.window.rootViewController = vc;
  g_view = [[GLView alloc] initWithFrame:self.window.bounds]; g_view.contentScaleFactor = 1.0; g_view.multipleTouchEnabled = YES; g_view.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight; [vc.view addSubview:g_view];
  PadView *pv = [[PadView alloc] initWithFrame:self.window.bounds]; pv.autoresizingMask = g_view.autoresizingMask; [vc.view addSubview:pv];
  [self.window makeKeyAndVisible]; [UIApplication sharedApplication].idleTimerDisabled = YES;
  pthread_attr_t at; pthread_attr_init(&at); pthread_attr_setstacksize(&at, 8u << 20); pthread_t t; pthread_create(&t, &at, game_thread, 0); return YES; }
@end

int main(int argc, char **argv) { @autoreleasepool { return UIApplicationMain(argc, argv, nil, NSStringFromClass([AppDelegate class])); } }
