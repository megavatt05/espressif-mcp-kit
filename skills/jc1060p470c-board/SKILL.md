---
name: jc1060p470c-board
description: How to use the GUITION JC1060P470C (_I_W/_Y) ESP32-P4 7-inch board - MIPI-DSI display and backlight, capacitive touch, ES8311 audio and volume control, microSD, Wi-Fi via onboard ESP32-C6, Ethernet - with exact GPIOs, Kconfig knobs, C API entry points, the build/flash/serial-verify recipe on this PC, and board gotchas cross-checked against BOTH firmwares for this board (CamBrowser `JC1060P470C-camera-photo-app` and the xiaozhi-esp32 fork `Downloads\xiaozhi-work\xiaozhi-esp32`); audio and touch pins are hardware-verified. Use when writing, building, flashing or debugging firmware for this board, or when the user mentions JC1060P470, JC1060P470C, GUITION 7 inch ESP32-P4 display, xiaozhi, or asks about its display, touch, sound, microphone, volume, SD card, camera or Wi-Fi wiring.
---

# GUITION JC1060P470C board usage

## Overview

Board: GUITION JC1060P470C_I_W/_Y - ESP32-P4 (silicon v1.3, 32 MB PSRAM) + onboard ESP32-C6
(Wi-Fi 6 2.4 GHz / BLE, SDIO), 7" IPS 1024x600 MIPI-DSI panel with capacitive touch, ES8311
codec + speaker amplifier, microSD slot, Ethernet PHY. Two reference firmwares live on this
PC: CamBrowser (`JC1060P470C-camera-photo-app`, branch `feature/wifi-c6`, LVGL-free overlay)
and the voice assistant fork `Downloads\xiaozhi-work\xiaozhi-esp32` (LVGL 9.5 + esp_lvgl_port,
board dir `main/boards/guition/guition-jc1060p470`). Pins below are verified in
`main/Kconfig.projbuild` and the driver sources, not copied from marketing pages; audio,
touch, display and Wi-Fi are confirmed on hardware.

## Build & flash (this machine)

- Build/flash only via the wrapper (raw `idf.py` breaks in git-bash/MSYS sessions):
  `powershell -NoProfile -File C:\Users\megav\.espressif\hermes\idf.ps1 -Idf v6.1 -Dir <proj> -Task "build"`
  (options with dashes go inside `-Task`, e.g. `-Task "-p COM10 flash"`). Board UART: COM10, 115200.
- Target `esp32p4`, IDF 6.1.0. After switching IDF version or component set: `-Task "fullclean"` first.
- IDF 6.1 note: registry `espressif/esp_lcd_jd9365` 1.0.4 does not compile (field `color_space`
  removed, now `rgb_ele_order`). The project keeps a patched copy in `components/espressif__esp_lcd_jd9365`,
  wired via `EXTRA_COMPONENT_DIRS` + `PRIV_REQUIRES` in `main/CMakeLists.txt`; do not re-add the
  registry dependency to `main/idf_component.yml`.
- Interactive `menuconfig`/`monitor` belong in a real console (`Desktop\IDF_v6.1_Powershell.lnk`);
  for logs use `serial-log.ps1 -Port COM10 -Seconds N`.
- Serial verification recipe (works for both firmwares): `serial-log.ps1` deliberately does
  **not** reset the board, so to see a boot log from 0 re-run the flash command - esptool
  compares and skips every unchanged image in ~5 s and ends with `--after=hard-reset` - then
  capture immediately:
  `idf.ps1 ... -Task "-p COM10 flash" > /dev/null && serial-log.ps1 -Port COM10 -Seconds 16`.
  Markers of a healthy bring-up: `Дисплей ... инициализирован` / `LVGL: Starting LVGL task`,
  `GT911 инициализирован (адрес 0x5D)` + `Тач GT911 зарегистрирован`, `sdio_wrapper: SDIO
  master: Slot 1`, `H_SDIO_DRV: Card init success`, `Station mode: Connected`, `Got IP:`,
  `Open codec device OK`, wake-net `MC Quantized wakenet9...`. Flash is Dio 80 MHz, 16 MB,
  app at `0x20000`, assets at `0x800000`; `revision v1.3` in the esptool banner confirms the
  eng-sample flags are correct.

## Pin map (defaults in main/Kconfig.projbuild)

| Function | GPIO / config |
|---|---|
| LCD backlight | GPIO23, LEDC ch0 timer1 5 kHz 10-bit (`main/main.c`) |
| Touch I2C | port 1, SCL=8, SDA=7 (`EB_TOUCH_I2C_*`) |
| Touch RST / INT | CamBrowser defaults RST=5, INT=-1 (floating; GT911 addr select). The official Guition port uses **RST=22, INT=21** - see the cross-check below; RST=5 is the likely source of the `gpio: conflict found for GPIO[5]` warning |
| LCD reset | GPIO27 (`DISPLAY_RESET_PIN` in the Guition port) |
| BOOT button | GPIO35 (GPIO34..38 are P4 strapping pins; the vendor xiaozhi template's BOOT=GPIO21 is wrong - 21 is touch INT) |
| ES8311 I2C | same bus as touch (SDA7/SCL8), 8-bit write addr 0x30 (`EB_AUDIO_CODEC_ADDR`) |
| I2S to codec | DOUT=9, LRCK=10, BCLK=12, MCLK=13 (`EB_AUDIO_I2S_*`) |
| I2S from codec (mic) | ES8311 ASDOUT on **GPIO48** - schematic net is named `ES7210_SDOUT` but there is no ES7210 chip on the board, that line is the ES8311's own ADC output. **Hardware-verified 2026-10-11** (xiaozhi firmware: wake word + upload work off GPIO48). DIN=11/PA=20 (older vendor templates) are swapped: DIN=11 reads the PA line (10 K pull-down -> permanent silence, wake word never triggers) and PA=20 is not connected |
| Speaker PA enable | GPIO11, active high (`EB_AUDIO_PA_GPIO`) |
| microSD | SDMMC slot 0, 4-bit: CLK=43, CMD=44, D0..D3=39..42; IO power = on-chip LDO ch4; no CD/WP lines |
| Ethernet IP101 RMII | MDC=31, MDIO=52, REF_CLK=50, RST=51, PHY addr 1 (`EB_ETH_*`, internal EMAC) |
| Wi-Fi | no P4 radio: ESP32-C6 over SDIO (esp_hosted + esp_wifi_remote), 2.4 GHz only |

README's W5500-over-SPI Ethernet (CS10/SCLK12/MOSI11/MISO13) describes the old
`feature/ethernet-browser` branch; this branch uses IP101 + internal EMAC per Kconfig.

## Display & backlight

- Panel drivers: `espressif__esp_lcd_jd9365` (local patched copy) and `espressif/esp_lcd_jd9165`;
  DPI over MIPI-DSI, RGB565 by default (`CONFIG_LCD_PIXEL_FORMAT_RGB565`), 2 frame buffers.
- **LVGL / esp_lvgl_port `swap_bytes`**: в конфигурации `lvgl_port_display_cfg_t.flags` флаг `swap_bytes`
  **ОБЯЗАТЕЛЬНО должен быть `false`**. В отличие от SPI-дисплеев (где байты идут старшим вперёд),
  контроллер MIPI-DSI на ESP32-P4 читает память напрямую как 16-битные Little-Endian полуслова.
  Если включить `swap_bytes = true`, происходит циклический сдвиг RGB565 каналов:
  красный (`0xF800` -> `0x00F8`) отображается как **синий**, зелёный (`0x07E0` -> `0xE007`) — как **красный**,
  а синий (`0x001F` -> `0x1F00`) — как **зелёный**.
- API (`main/app_lcd.h`): `app_lcd_init(&panel)`, `app_lcd_get_fb(idx, &ptr)`, `app_lcd_flush(idx)`,
  `app_lcd_get_panel()`, `app_lcd_get_io()`, `app_lcd_dpi_clear_callbacks()`.
- Resolution macros `EXAMPLE_LCD_H_RES/V_RES` (1024x600 for `BOARD_TYPE_JC1060P470`) MUST equal the
  DPI `video_timing` size in `app_lcd.c`; a mismatch makes PPA write past every frame buffer
  (heap corruption, flickering band).
- Backlight: `bsp_display_brightness_init/set(percent)` in `main/main.c` (LEDC); call after
  `app_lcd_init()`.
- After destroying an `esp_video_render` LCD backend call `app_lcd_dpi_clear_callbacks()`: the
  backend leaves a stale `on_color_trans_done` callback that crashes the next flush.

## Touch

- `touch_init()` probes GT911 (0x5D/0x14), FT5x06 (0x38), CST816 (0x15); board ships GT911.
- `touch_poll(out, TOUCH_MAX_POINTS)` returns normalized points (swap/mirror flags in Kconfig);
  `touch_chip_name()` for status bar; `touch_get_i2c_bus()` exposes the I2C master bus handle -
  the ES8311 audio codec shares this bus, so audio must reuse it instead of re-claiming port 1.
- Boot warning `gpio: conflict found for GPIO[5]` right before touch init (RST pin
  double-claimed). Unresolved as of 2026-10-11, and the official Guition port suggests the
  cause is the pin itself: GT911 RST is wired to **GPIO22** with INT on **GPIO21**, not to
  GPIO5.
- **Ориентация тачскрина GT911**: при стандартной ориентации дисплея (0,0 в левом верхнем углу,
  без программного поворота дисплея `rotation.swap_xy/mirror_x/mirror_y = false`) флаги в
  `esp_lcd_touch_config_t.flags` **ОБЯЗАТЕЛЬНО должны быть `swap_xy = 0, mirror_x = 0, mirror_y = 0`**.
  Вендорский порт xiaozhi-esp32 использовал `mirror_x=1, mirror_y=1` только потому, что их настольная
  подставка монтировала плату в перевёрнутом на 180° виде (разъёмами USB наверх). Если установить
  `mirror_x = 1, mirror_y = 1` при прямой ориентации экрана, драйвер `esp_lcd_touch` инвертирует
  координаты: X_out = X_max - X, Y_out = Y_max - Y, из-за чего касания в левом верхнем углу
  срабатывают в правом нижнем.

## Audio & volume

- Chain: decoder -> esp_audio_render (resample) -> I2S TX -> ES8311 DAC -> NS4150-class PA (GPIO11).
- Fixed output format 48 kHz / 16-bit / stereo; I2S `auto_clear = true` (silence on underrun).
- 400 ms linear fade-in on every playback start: the PA current spike on first samples trips the
  P4 brownout detector on weak 5 V supplies without it. Keep it when touching `media_audio.c`.
- Volume: `media_audio_set_volume(0..100)` / `media_audio_get_volume()` (`main/media/media_audio.c`),
  applied via `esp_codec_dev_set_out_vol`; default 10 %. Wrappers `media_set_volume/media_get_volume`
  in `main/media/media_player.h`.
- On-screen control: browser UI buttons `BTN_VOLUP`/`BTN_VOLDN` step +/-10 (`main/browser/browser.c`),
  volume bar drawn under the state text; persists across open/close.
- Brownout reset right after audio start = weak 5 V source under PA load; advise 5 V/2 A adapter,
- The xiaozhi codec diagnostic prints `PA: GPIO11 уровень=0 (активный HIGH)` +
  `вывод включён, но PA=0 - усилитель ВЫКЛЮЧЕН (пин/полярность?)` right after
  `Adev_Codec: Open codec device OK`. Guaranteed false alarm: inside
  `Es8311AudioCodec::UpdateDeviceState()` the one-shot `LogDiagnostics()` runs *before* the
  trailing `gpio_set_level(pa_pin_, output_enabled_ ? 1 : 0)` in the same function, so the PA
  has not been raised yet when the dump is taken (diag call `es8311_audio_codec.cc:134`, PA
  write `:141-143`). Speaker
  output and microphone on GPIO48 were confirmed on hardware 2026-10-11 with those exact
  pins - do not "fix" the polarity or move the PA pin.
  short thick cable (firmware logs this hint itself).

## Panel bring-up facts (independent cross-check, not CamBrowser code)

`C:\Users\megav\Downloads\xiaozhi-work\xiaozhi-esp32` is a xiaozhi-esp32 fork with a
first-class board for this exact panel (`main/boards/guition/guition-jc1060p470/`, pins
traced to the vendor schematic and to `guitionofficial/P4-series`). It confirms and extends:

- MIPI-DSI PHY power: `esp_ldo_acquire_channel()` on **channel 3 @ 2500 mV before** any DSI
  bus/panel init, otherwise the panel stays dark.
- Verified DPI timings: pixel clock **52 MHz**, h_total porch 160 / pw 24 / fp 160,
  v 21 / 2 / 12, **2 lanes @ 750 Mbit/s** (vendor says 900; if the screen is black try
  550/750/900).
- JD9165 needs the vendor ~45-command init table passed as
  `jd9165_vendor_config_t.init_cmds` or some panels show a **grey** screen (generic init).
- `espressif/esp_lcd_jd9165: ^2.0.2` is the version that compiles against IDF 6
  (`rgb_ele_order` rename); GT911 mirror_x/mirror_y are FALSE (0) in normal landscape orientation (only true if panel is physically mounted upside-down).
- DMA2D is used in production there exactly as the `lvgl-cyrillic-fonts` skill says, with a
  version guard: `dpi_config.flags.use_dma2d = true` on IDF < 6.0, and
  `esp_lcd_dpi_panel_enable_dma2d(panel)` right after `esp_lcd_new_panel_jd9165()` and before
  `esp_lcd_panel_reset()/init()` on IDF >= 6.0.
- esp_hosted SDIO needs `CONFIG_ESP_HOSTED_MEMPOOL_PREFER_SPIRAM=y` on a PSRAM-heavy P4
  build, else after LVGL+audio allocation it aborts with
  `assert failed: sdio_mempool_create sdio_drv.c:258 (buf_mp_g)` (~31 x 1536 B of contiguous
  internal DMA RAM is what it cannot find).
- GT911 intermittently returns `ESP_ERR_INVALID_RESPONSE` on a poll with no valid report;
  `lvgl_port_touchpad_read()` wraps `esp_lcd_touch_read_data()` in `ESP_ERROR_CHECK`, so one
  transient NACK becomes `abort()` of the whole app. Fix: swap `tp->read_data` with a
  wrapper that turns that error into "0 touch points" and rate-limits the log
  (`guition-jc1060p470.cc`, `TouchReadDataLog`).
- Their README claims microSD has to stay unused because "SDMMC slot 0 is taken by
  ESP-Hosted (C6)". That is wrong - esp_hosted runs on **SDMMC slot 1**
  (CLK18/CMD19/D0..D3=14..17, slave reset GPIO54, seen in the 2026-10-11 boot log) - and CamBrowser
  mounts SD on slot 0 and uses Wi-Fi at the same time (hardware-verified 2026-10-11).
- ES8311 via esp_codec_dev 1.x wants the **8-bit** address `0x30` even though
  `i2c_master_probe()` and the bus use the 7-bit `0x18`; mic gain is settable up to 42 dB
  (`esp_codec_dev_set_in_gain`, 6 dB steps, default 30).

## SD card

- `sdcard_mount()` (lazy, idempotent) mounts FAT32 at `CONFIG_EB_SD_MOUNT` (default `/sdcard`);
  `sdcard_reprobe()` after hot-plug or a failed attempt; `sdcard_mounted()`, `sdcard_mp()`.
- 4-bit SDMMC slot 0 at 20 MHz max (`EB_SD_MAX_FREQ_KHZ`), internal pullups, LDO ch4 for card IO.
- Mount failure message hints FAT32: exFAT/NTFS cards are not supported.
- Resource conflict: microSD and Wi-Fi(C6) can contend on SDIO - prefer Ethernet+SD for movies from
  card, or Wi-Fi without SD (noted in `EB_WIFI_ENABLE` help).

## Wi-Fi (ESP32-C6) & Ethernet

- Stack: `esp_hosted` + `esp_wifi_remote` over SDIO; normal `esp_wifi_*` API on the P4 host.
  Slave target must be `esp32c6` (`CONFIG_SLAVE_IDF_TARGET_ESP32C6`).
- Measured on hardware (xiaozhi-esp32 boot log, 2026-10-11): ESP-Hosted attaches to **SDMMC
  Slot 1**, 4-bit @ 40 MHz, CLK=18 CMD=19 D0..D3=14..17, slave reset **GPIO54**
  (`H_SDIO_DRV: Reset slave using GPIO[54]`). It does NOT touch slot 0, which is why the
  microSD on 43/44/39..42 and Wi-Fi coexist. GPIO54 is therefore reserved for the C6 reset.
- Simple mode: `EB_WIFI_ENABLE` + `EB_WIFI_SSID/PASSWORD`, then `app_wifi_start()`,
  `app_wifi_ready()`, `app_wifi_ip_str()`.
- Manager mode (`main/net/wifi_mgr.c`): `wifi_mgr_init/scan/scan_count/scan_get`,
  `wifi_mgr_connect(ssid, pass)`, SoftAP captive portal `wifi_mgr_start_portal[_ssid]()`
  (open AP `CamBrowser-Setup`, page `http://192.168.4.1:8080/`, port 8080 to avoid clashing with
  the log server on 80), credentials in NVS namespace `wifi_mgr` keys `ssid`/`pass`,
  `wifi_mgr_test_internet()` (generate_204 + speed test). On-device UI: Wi-Fi screen with
  scan/connect/portal/test and an on-board password keyboard (`ST_WIFI_PASS`).
- Ethernet: `EB_ETH_ENABLE` (IP101 RMII pins above) via `main/net/app_eth.c`; can run with Wi-Fi;
  `wifi_mgr` sets STA as default netif after GOT_IP.
- HTTP endpoints on the board: `http://<STA_IP>/log` (live logs), `http://<STA_IP>/speed` (history).

## Board gotchas

- **Цвета RGB перепутаны (красный стал синим, зелёный — красным, синий — зелёным)**:
  типичный симптом включённого `flags.swap_bytes = true` в `esp_lvgl_port`. На MIPI-DSI шине
  ESP32-P4 перестановка байт не требуется — устанавливайте `.flags.swap_bytes = false`.
- **Координаты тачскрина инвертированы (нажатие в левом верхнем углу срабатывает в правом нижнем)**:
  причина — включённые флаги `.mirror_x = 1, .mirror_y = 1` в `esp_lcd_touch_config_t.flags`.
  Матрица GT911 на данной панели 1024x600 аппаратно согласована с дисплеем JD9165: точка (0,0) —
  левый верхний угол. Устанавливайте `.swap_xy = 0, .mirror_x = 0, .mirror_y = 0`. Флаги зеркалирования
  нужны только в случае, если сам дисплей перевёрнут аппаратно на 180° (`rotation.mirror_x = true, rotation.mirror_y = true`).
- No H.264 hardware decode on P4: video is software-decoded (~320x240@68 fps, 640x480@18 fps);
  prepare content with `tools/convert_movie` (see `docs/PLAYBACK_PERF_PLAN.md`).
- P4 has H.264 HW *encode*, JPEG HW, PPA/DMA2D color convert - use those, not SW paths, for capture.
- `sdkconfig.defaults` applies only when sdkconfig is regenerated; runtime log level is forced by
  `CONFIG_EXAMPLE_QUIET_LOGS` in `app_main` (menuconfig -> Example Configuration -> Quiet logs).
- C6 Wi-Fi is 2.4 GHz only; 5 GHz SSIDs will never connect.
- Revision range in sdkconfig (`REV_MIN_FULL=0..REV_MAX_FULL=199`, `less_v3` profile) covers the
  board's P4 v1.3; keep it when regenerating configs.

## Code map

`main/main.c` boot+backlight - `main/app_lcd.c` DPI/panel/fb - `main/camos/touch.c` touch -
`main/camos/ui.c` RGB565 primitives - `main/media/media_audio.c` codec/volume -
`main/media/media_player.c` radio+video wrapper - `main/media/sdcard.c` mount -
`main/net/app_wifi.c`, `main/net/wifi_mgr.c` Wi-Fi - `main/net/app_eth.c` Ethernet -
`main/net/log_server.c`, `main/net/speed_test.c` HTTP tools - `main/browser/browser.c` UI states
incl. volume buttons - `main/browser/films.c` SD/URL movie list - `main/Kconfig.projbuild` all pins.
Docs: `docs/WIFI_C6.md`, `docs/WIFI_MGR.md`, `docs/PLAYBACK_PERF_PLAN.md`, `docs/ETHERNET_BROWSER.md`.
