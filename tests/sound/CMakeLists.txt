cmake_minimum_required(VERSION 3.10)
project(sharsound C)
# stage 6 sound test: viewer/sound.c + viewer/audio.c unchanged, scenario shared with tests/sound/host
set(V ${CMAKE_CURRENT_SOURCE_DIR}/../../viewer)
add_executable(sharsound main.c ${V}/sound.c ${V}/audio.c)
target_include_directories(sharsound PRIVATE ${V} ${CMAKE_CURRENT_SOURCE_DIR})
target_compile_options(sharsound PRIVATE -O2 -Wall -Wno-misleading-indentation -Wno-unused-function -fno-math-errno -fsingle-precision-constant)
target_link_libraries(sharsound pspdebug pspdisplay pspge pspctrl pspaudio psppower m)
create_pbp_file(TARGET sharsound TITLE "SHAR Sound Test" BUILD_PRX)
