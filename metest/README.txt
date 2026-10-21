SHAR ME Test v1.6, 2026-10-07 (spatial Simpsons main-menu theme)

XMB: Game > Memory Stick > SHAR ME Test
TRIANGLE at start: PLAY MUSIC, native boot/heartbeat/size guard only
No need to repeat the benchmark; listen 10-20 seconds, toggle ME/CPU, then CIRCLE
MUSIC ONLY displays 0/10, which means DSP matrix was not run in this mode
Two alternating PCM buffers protect samples still queued by sceAudio
PCM stats: empty-at-submit, clipped samples, peak amplitude, saved on exit
Audio producer priority 0x12; UI at 10Hz in another thread, no screen/file I/O in producer
v1.4 hardware measured empty queues 591/2291 with no clipping, clicks reported
START during audition: Simpsons melody / clean 400Hz reference carrier
Reference carrier is CPU-generated; gains use selected DSP, native decode keeps running
Continuous phase across 512-frame packets; source changes crossfade over128 samples
Empty queues are logged separately for melody/tone and ME/CPU
Quick check: TRIANGLE at menu, move melody with D-pad and L/R; TRIANGLE for ME/CPU; CIRCLE
Reference: https://github.com/pspdev/pspsdk/blob/master/src/audio/pspaudiolib.c
CROSS starts 10 hardware cases (64 jobs per case), then 4 joint loads (32 pairs)
Joint loads: 8 voices + 128 FX, 24 + 32, 24 + 128, 24 + 400
Every audio/FX result must match the CPU exactly; real audio priority chain required
audio-budget=OVER means that workload cannot be jointly enabled within 11.61 ms
An OVER is a scheduling limit, not a fake DSP PASS or a lost-job exception
CPU references are computed before timing to avoid artificial deadline misses
Keep PSP awake during the test. Audio audition follows automatically on PASS

In audio audition:
UP/DOWN: source nearer/farther, 1 metre per press
LEFT/RIGHT: source to either side, 2 metres per press
Hold D-pad to keep moving; any manual movement stops automatic sweep
L/R shoulder buttons: source to left/right (-20/+20 metres)
SELECT: source centre, 10 metres ahead
TRIANGLE during music: actual ME / main CPU A-B
Both routes MUST sound identical; route label and timings change
CROSS: automatic distance and side sweep
SQUARE: mute
START: Simpsons melody / clean tone reference
CIRCLE: finish audition and save
HOME: exit

Log: PSP/GAME/SHARME/me-test.txt
The log is saved before each case, after every result, and on exit
After testing, return to XMB and connect USB to retrieve this file

Capabilities tested on identical game DSP:
1, 8, 24, 128 spatial sources: distance attenuation and stereo gains
1, 8, 24 ADPCM voices: decode, resample, spatial gains, mix and decoder state
32, 128, 400 particles: simulation, FPU, sorting and billboard vertex generation
Native heartbeat and malformed-size rejection precede these cases
Melody mode uses the full recognizable Simpsons theme from the original main menu
Native stereo ADPCM is copied bit for bit; original loop/history, no re-encoding
The same ME/CPU decoder, resampler, distance/pan, PCM producer are used
Original engine fixture is retained solely for comparable full DSP benchmarks
Tone mode is a labelled diagnostic reference; it is not an engine asset or new ME capability

PASS means native responses and byte-for-byte agreement with the main CPU
It does not mean all workloads are faster, nor that the game was updated
candidate=YES requires less main-thread runClocks and no 11.61 ms deadline miss
This is a microbenchmark, not proof of whole-game FPS gains
me-wall includes cache handoff, dispatch, scheduling, polling and retrieval
runClocks is reported in native SDK units (ticks), not converted to microseconds
No emulator result or CPU fallback is reported as hardware ME PASS
PPSSPP is SKIP. Missing kernel service is FAIL, not an invented result

Only PSP/GAME/SHARME is installed. SHARVIEW and SHARTOUR are separate
CFW kubridge + firmware MIST service are needed, as in the current game
This tester does not test simultaneous firmware movie/codec playback,
GE rendering, VFPU physics, pathfinding, or decompression offload
v1.3 joint measured: 24 voices+128 FX worst 8537us, late0;
24+400 worst12515us, late25/32. Game source now sends >128 FX elements to CPU
All particles/billboards/sprites remain rendered; only execution processor changes

If it freezes: the last saved BEGIN identifies the active hardware case
On suspend/timeout, restart the tester. Results remain on the card
