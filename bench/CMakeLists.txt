cmake_minimum_required(VERSION 3.10)
project(sharbench C)
# Стенд SHARBENCH (Роб 03.10: «бенчи, которые прогонишь на PSP: что можно оптимизировать, что проверить только на железе»).
# Отдельная папка PSP/GAME/SHARBENCH, игра SHARVIEW не трогается. Отчёт bench.txt рядом с EBOOT
add_executable(sharbench main.c ../viewer/audio.c)
target_compile_definitions(sharbench PRIVATE AUDIO_HOST)   # микшер игры без своих потоков: стенд зовёт смешивание сам и меряет
target_compile_options(sharbench PRIVATE -O2 -Wall -Wno-misleading-indentation -fno-math-errno -fsingle-precision-constant)
target_link_libraries(sharbench pspgum pspgu pspdebug pspdisplay pspctrl psprtc psppower pspge psputility m)
create_pbp_file(TARGET sharbench TITLE "SHAR bench" BUILD_PRX)
