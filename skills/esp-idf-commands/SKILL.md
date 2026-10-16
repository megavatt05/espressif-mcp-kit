---
name: esp-idf-commands
description: >-
  Reference for ESP-IDF v6.1 PowerShell environment commands on Windows.
  Use this skill when the user needs to build, flash, monitor, configure, or
  manage partitions for ESP32 projects. Covers idf.py, esptool.py, espefuse.py,
  espsecure.py, otatool.py, and parttool.py. Relevant for the xiaozhi-esp32
  project and any ESP-IDF-based firmware development.
---

# ESP-IDF v6.1 — Команды и среда (Windows PowerShell)

## Переменные окружения и активация среды

| Переменная | Значение |
|---|---|
| `IDF_PATH` | `C:\esp\v6.1\esp-idf` |
| `IDF_TOOLS_PATH` | `C:\Espressif\tools` |
| `IDF_PYTHON_ENV_PATH` | `C:\Espressif\tools\python\v6.1\venv` |

> [!WARNING]
> В «голом» окне PowerShell простое присвоение `$env:IDF_PATH = 'C:\esp\v6.1\esp-idf'` **НЕ добавляет** команду `idf.py` в PATH!
> При попытке вызвать `idf.py build` система выдаст:
> `idf.py: Термин "idf.py" не распознается как имя...`

### Как правильно запускать команды на этой машине:

#### Вариант 1: Через проверенный PowerShell-враппер (рекомендуется для агента и скриптов)
```powershell
powershell -NoProfile -File C:\Users\megav\.espressif\hermes\idf.ps1 -Idf v6.1 -Dir <путь_к_проекту> -Task "build"
# Прошивка (параметры с тире передаются внутри строки -Task):
powershell -NoProfile -File C:\Users\megav\.espressif\hermes\idf.ps1 -Idf v6.1 -Dir <путь_к_проекту> -Task "-p COM10 flash"
```

#### Вариант 2: Активация окружения в текущей сессии PowerShell
```powershell
& "C:\Espressif\tools\Microsoft.v6.1.PowerShell_profile.ps1"
# После выполнения этой строки переменные PATH и venv активированы, и idf.py доступен напрямую:
idf.py build
idf.py -p COM10 flash
```

#### Вариант 3: Прямой вызов через Python окружения v6.1
```powershell
& "C:\Espressif\tools\python\v6.1\venv\Scripts\python.exe" "C:\esp\v6.1\esp-idf\tools\idf.py" build
```

---

## idf.py — основной инструмент сборки

```powershell
idf.py build                        # Сборка проекта
idf.py flash                        # Прошивка устройства (порт автоматически)
idf.py monitor                      # Открыть серийный монитор
idf.py flash monitor                # Прошить + сразу открыть монитор
idf.py -p COM3 flash monitor        # Указать конкретный COM-порт
idf.py menuconfig                   # Графическая конфигурация (Kconfig/menuconfig)
idf.py fullclean                    # Полная очистка папки build/
idf.py clean                        # Частичная очистка (без CMake кэша)
idf.py size                         # Анализ размера прошивки
idf.py size-components              # Размер по компонентам
idf.py size-files                   # Размер по файлам
idf.py set-target esp32s3           # Сменить целевой чип
idf.py reconfigure                  # Пересоздать CMake конфигурацию
idf.py app-flash                    # Прошить только app
idf.py bootloader-flash             # Прошить только bootloader
idf.py partition-table-flash        # Прошить только таблицу разделов
```

---

## esptool.py — низкоуровневая работа с чипом

```powershell
esptool.py --port COM3 flash_id                         # Идентификация чипа и flash
esptool.py --port COM3 chip_id                          # ID чипа
esptool.py --port COM3 read_flash 0 0x400000 dump.bin   # Читать 4MB flash в файл
esptool.py --port COM3 erase_flash                      # Стереть всю flash
esptool.py --port COM3 erase_region 0x9000 0x6000       # Стереть регион
esptool.py --port COM3 write_flash 0x0 bootloader.bin   # Записать бинарник по адресу
esptool.py --port COM3 --baud 921600 flash_id           # Увеличить скорость
esptool.py image_info firmware.bin                      # Информация о бинарнике
```

---

## espefuse.py — работа с eFuse (НЕОБРАТИМО!)

```powershell
espefuse.py --port COM3 summary                         # Показать все eFuse значения
espefuse.py --port COM3 summary --format json           # В формате JSON
espefuse.py --port COM3 burn_efuse <EFUSE_NAME>         # Записать eFuse (необратимо!)
espefuse.py --port COM3 burn_key BLOCK1 key.bin         # Записать ключ в блок
espefuse.py --port COM3 get_custom_mac                  # Получить кастомный MAC
```

---

## espsecure.py — безопасная загрузка и шифрование

```powershell
espsecure.py generate_flash_encryption_key key.bin
espsecure.py encrypt_flash_data --keyfile key.bin --address 0x0 -o out.bin in.bin
espsecure.py decrypt_flash_data --keyfile key.bin --address 0x0 -o out.bin in.bin
espsecure.py sign_data --version 2 --keyfile signing_key.pem -o signed.bin unsigned.bin
espsecure.py verify_signature --version 2 --keyfile pub_key.pem firmware.bin
espsecure.py generate_signing_key --version 2 signing_key.pem
```

---

## otatool.py — управление OTA разделами

```powershell
otatool.py --port COM3 read-otadata
otatool.py --port COM3 erase-otadata
otatool.py --port COM3 switch-ota-partition --slot 0
otatool.py --port COM3 switch-ota-partition --slot 1
otatool.py --port COM3 read-ota-partition --slot 0 -o ota0.bin
```

---

## parttool.py — работа с таблицей разделов

```powershell
parttool.py --port COM3 get-partition-info --partition-name nvs
parttool.py --port COM3 get-partition-info --partition-name ota_0
parttool.py --port COM3 read-partition --partition-name nvs -o nvs.bin
parttool.py --port COM3 write-partition --partition-name nvs --input nvs.bin
parttool.py --port COM3 erase-partition --partition-name nvs
```

---

## Типичный рабочий цикл для xiaozhi-esp32

```powershell
cd C:\xiaozhi-esp32
python scripts/build.py --list-boards
idf.py set-target esp32s3
idf.py menuconfig
python scripts/build.py <board-directory> --name <variant-name>
idf.py -p COM3 flash monitor
clang-format -i <files>
```

---

## Полезные флаги idf.py

```powershell
idf.py -p COM3 -b 921600 flash              # Порт и скорость
idf.py --no-ccache build                    # Без ccache
idf.py -v build                             # Verbose вывод
idf.py build 2>&1 | Tee-Object build.log   # Сохранить лог
```

---

## Замечания

- Минимальная поддерживаемая версия: **ESP-IDF v6.0.1**; текущая: **v6.1**
- IDF 5.x **не поддерживается** в проекте xiaozhi-esp32
- Всегда указывайте `-p COMx` если автоопределение порта не работает
- `idf.py fullclean` удаляет весь `build/` — использовать перед сменой таргета
