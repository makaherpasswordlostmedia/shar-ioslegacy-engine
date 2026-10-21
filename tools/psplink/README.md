# PSPLink (pspdev/psplinkusb v3.2.1, официальный релиз)
- `psplink-v3.2.1.zip` — архив релиза, SHA-256 721be3c1dd4f82f9ac9b76183651af993de23cd8dfdcd0b85ece109697a92bec
- На PSP установлено 28.09.2026 в `PSP/GAME/PSPLINK` (разрешение Роба). PSP-сторона: запустить PSPLink из меню «Игра».
- Мак-сторона: `pspdev/bin/usbhostfs_pc` + `pspdev/bin/pspsh` (arm64, нужна Homebrew libusb). Двойной клик `Подключить PSP.command`.
- Режим USB-флешки и PSPLink одновременно не работают: для копирования на карту — USB-режим, для запуска с Мака — PSPLink.
- EBOOT игры уже с MEMSIZE=1 (расширенная память PSP-2000), поэтому ARK highmem для нашей игры не нужен и не включался.
- Не проверено на железе: первый запуск — пункт Л1а очереди (стенд tools/psplink_run.sh, гейт «падающий EBOOT → стенд сообщает падение»).
