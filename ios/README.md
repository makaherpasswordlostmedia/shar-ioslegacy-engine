# SHAR на 32-bit iOS 7+ (armv7)

Порт движка SHAR-PSP (The Simpsons: Hit & Run) на iPhone 4S/5/5c, iPad 2/3/4/mini 1, iPod touch 5 (iOS 7.0 – 9.3.5).
Подход и сборка взяты из CrashBandicoot-iOS-32bit: Theos + iPhoneOS 9.3 SDK на Linux, OpenGL ES 2.0, AudioQueue, CI в GitHub Actions.

## Как это устроено

Движок написан на C прямо под PSP: пишет команды GE (display list'ы, CLUT-текстуры, свои буферы). Поэтому вместо замены
отдельных вызовов сделан слой совместимости `ios/shim` + `ios/src`:

| Файл | Что делает |
|---|---|
| `shim/psp_compat.h` (+ `pspgu.h`, `pspkernel.h`, … — просто include) | типы, константы и прототипы PSP SDK |
| `src/ge_list.c` | замена libpspgu/libpspgum: пишет настоящие слова GE в список движка |
| `src/ge_gles2.c` | интерпретатор GE → GLES2: вершины, T4/T8 CLUT, swizzle, мипы, blend, alpha-тест, fog, depth, scissor, CPU-скиннинг |
| `src/psp_sys.c` | файлы (`ms0:/PSP/GAME/SHARVIEW` → `Documents/SHARVIEW`), потоки, семафоры, время, сохранения, mallinfo |
| `src/me_stub.c` | Media Engine отсутствует: звук и частицы идут по CPU-ветке движка |
| `host/ios_host.m` | UIKit/EAGL, AudioQueue, ImageIO для JPEG-роликов, сенсорное управление |

В самом движке тронуто минимум: `fpuguard.h` (MIPS FCSR), uncached-алиасы `|0x40000000` → `PSP_UC()`,
сырые GE-адреса текстур/палитры (`geTexAddr`/`geClutAddr`), адрес «VRAM».

## Сборка

GitHub → Actions → **Build SHAR iOS armv7 (iOS 7+)** → Run workflow → артефакт `SHAR-armv7-iOS` (.ipa/.deb).
Локально: `cd ios && make package FINALPACKAGE=1` (нужны Theos и iPhoneOS9.3.sdk, как в workflow).
Диск не нужен для сборки: данные игры конвертируются отдельно (инструменты движка, см. корневой README) и кладутся в `Documents/SHARVIEW`.

## Статус — честно

Проверено: **весь движок и шим компилируются и линкуются по символам на x86_64** (CI-джоб `host-check`).
**Не проверено:** сборка Theos/armv7, запуск на устройстве, корректность картинки GE→GLES2, скорость.
Известные пробелы: освещение (GU_LIGHTING), stencil, морфинг, env-map и texture-matrix не эмулируются;
`sceGuCopyImage`/чтение кадра не реализованы (диагностика, скриншоты); сохранения — файлы вместо системного диалога PSP;
знак culling (`cullFront`) и UV в through-режиме сверены по памяти — первое, что смотреть на устройстве; 256 МБ ОЗУ (iPad mini 1, iPhone 4S) будет мало — оригинал для PSP-2000 с 64 МБ, но кэш текстур в RGBA8 тяжелее.
