---
name: lvgl-cyrillic-fonts
description: Generate, size-budget and wire Cyrillic-capable fonts for LVGL 9 on ESP32 (incl. ESP32-P4) - exact lv_font_conv commands and Unicode ranges for Russian/Ukrainian, measured flash cost per size/bpp/compression, LVGL9 Kconfig knobs (static fmt_txt fonts have no glyph cache; tiny_ttf/freetype do), keeping large fonts out of .rodata via binfont/FreeType-mmap/XIP-PSRAM, render and core-load levers (draw-buffer size, DMA2D on MIPI-DSI, PPA, esp_lvgl_adapter FPS data, IRAM), the fonts/ folder convention, the 8x8 PSF bitmap pipeline for custom non-LVGL overlays, and which MCP servers to query for authoritative LVGL/Espressif answers. Use when adding or shrinking fonts, rendering Russian text on a display, debugging missing squares/tofu, choosing bpp, enabling LV_USE_FONT_COMPRESSED, aligning buffers for DMA2D/PPA, or integrating LVGL9 into an ESP-IDF project.
---

# Cyrillic fonts for LVGL 9 on ESP32

## Overview

Two independent pipelines, both verified on this machine:

1. **LVGL 9 vector fonts** - `lv_font_conv` (npm, run via `npx`) turns a TTF into a
   C file with an `lv_font_t`. Use for any LVGL UI, sizes >= 12 px.
2. **8x8 bitmap fonts from PSF** - a Python converter turns a hand-drawn console PSF
   into a `[N][8]` byte table for a *custom* framebuffer renderer (no LVGL). Use only
   for tiny overlay/HUD text where an 8-px TTF is unreadable.

Reference projects on disk (real, buildable, not docs):
- `~/Downloads/esp32P4` - XiaoZhi chatbot, **LVGL 9.5 + esp_lvgl_port 2.9.0 on ESP32-P4**,
  board `guition-jc1060p470` (same 1024x600 MIPI-DSI panel). Fonts: component
  `78/xiaozhi-fonts`, Cyrillic ranges in `managed_components/78__xiaozhi-fonts/src/font_noto_sans_basic_14_1.c:4`.
- `~/Downloads/JC1060P470C-camera-photo-app/fonts` - the PSF + `lvgl_convert.sh` tooling.

## The Cyrillic ranges (get these right first)

Minimum Russian set, 161 glyphs (ASCII + Ё/ё + А-я):

```
-r 0x20-0x7F -r 0x401 -r 0x410-0x44F -r 0x451
```

**Ё (U+0401) and ё (U+0451) are NOT inside 0x410-0x44F** - they must be listed
separately or the money-sign-looking box appears only in words like "Ёлка".

Wider set (Ukrainian/Bulgarian/Serbian) as used by the working P4 project -
`-r` with a comma list, note it deliberately skips U+0402-U+0405 etc.:

```
-r 0x406,0x408,0x410-0x413,0x417-0x418,0x41A,0x41C-0x423,0x427,0x430-0x44C,0x44E-0x44F,0x452,0x456-0x45B
```

Also required at runtime: `CONFIG_LV_TXT_ENC_UTF8=y` (LVGL default) - Cyrillic source
strings must be UTF-8, and `CONFIG_LV_USE_FONT_PLACEHOLDER=n` is worth setting so a
missing glyph is visible as nothing rather than a dot-box you ignore during review.

## Generate a font (verified command)

```bash
npx --yes lv_font_conv --font DejaVuSansMono.ttf \
    -r 0x20-0x7F -r 0x401 -r 0x451 -r 0x410-0x44F \
    --size 16 --bpp 4 --format lvgl --no-compress \
    --lv-font-name lv_font_mono_16 -o lvgl/lv_font_mono_16.c
```

Useful flags (`npx lv_font_conv --help`): `--bpp {1,2,3,4,8}`, `--no-compress`,
`--no-kerning`, `--force-fast-kern-format` (kern classes: larger but faster),
`--symbols` instead of ranges, `--lv-fallback NAME` (fallback font chain),
`--format bin` (LVGL 9 binary font file, loaded from a filesystem/partition instead
of compiled in), `--lv-include` for a non-default `lvgl.h` path. Multiple `--font`
options merge glyphs from several faces into one font.

Output is an ordinary `lv_font_t`: declare with `LV_FONT_DECLARE(lv_font_mono_16);`
and assign `lv_obj_set_style_text_font(obj, &lv_font_mono_16, 0);`. The generated file
includes `"lvgl/lvgl.h"` unless you build with `LV_LVGL_H_INCLUDE_SIMPLE`.

## Real flash cost: .c size is a lie

Measured: compiled with the IDF 6.1 RISC-V toolchain (`-Os`, target esp32p4), `.rodata`
section of the object = what actually occupies flash. Same DejaVu Sans Mono subset:

| Size | bpp | compression | `.c` file | `.rodata` (flash) |
|------|-----|-------------|-----------|-------------------|
| 16 px | 1 | none | 32 695 B | **3 147 B** |
| 16 px | 4 | RLE (default) | 56 444 B | **6 953 B** |
| 16 px | 4 | `--no-compress` | 66 443 B | **8 755 B** |
| 24 px | 4 | RLE | 118 980 B | **17 476 B** |

Reproduce with `scripts/measure-font.sh fonts/lvgl/*.c` (needs the toolchain + a
`lvgl.h` include dir; set `GCC=` / `LVGL_DIR=` to override).

Read-outs: a full Russian set costs single-digit KB, **not** tens of KB - "fonts are
heavy" is only true when you add many sizes or a CJK range. Budget ~9 KB per
16 px/bpp4 subset, ~17 KB per 24 px. Growth is roughly quadratic in pixel size
(16->24 px = ~2.3x, the 1.5x height ratio squared is 2.25). RLE saves ~20 % of the
bitmap payload. If a UI needs 4 sizes, generate exactly the 4 subsets rather than one
huge font plus fallbacks.

## Compression / bpp decisions

- `--bpp 1` - no antialiasing, smallest and fastest to blit; fine for monospace HUD
  text at >= 16 px on a 7" 1024x600 panel, ugly for thin serifs.
- `--bpp 4` - the normal choice (LVGL supports 1/2/3/4/8). `--bpp 8` doubles bitmaps
  for no visible gain at these sizes.
- Font RLE: `lv_font_conv` compresses **by default**; to actually *use* compressed
  data you must have `CONFIG_LV_USE_FONT_COMPRESSED=y`. Mismatch is a classic
  silent failure: with the option off and a compressed font compiled in, glyphs render
  as garbage/nothing. The working P4 project turns it off deliberately
  (`esp32P4/sdkconfig.defaults:57` `CONFIG_LV_USE_FONT_COMPRESSED=n`) and generates with
  `--no-compress` - trading ~1.8 KB flash per font for cheaper per-glyph decode.
- `CONFIG_LV_FONT_FMT_TXT_LARGE=y` - enable if a font exceeds ~10 000 glyphs
  (only relevant for CJK); costs nothing for Latin+Cyrillic. Upstream wording:
  "the limit depends on font size, font face and bpp; a compiler error will be
  triggered if a font needs it".
- `--bpp 3` works **only with compression** (the C-format converter errors out
  otherwise; `--format bin` prints no warning at all, and bpp3 through the runtime
  binfont loader has a history of broken rendering, so treat 3 as compression-only in C).
- Upstream's own size-reduction ladder (official answer, forum thread 11235): 1) only the
  characters you need via `--symbols`, 2) lower bpp (4 -> 2), 3) enable compression,
  4) switch to a runtime TTF engine.
- Compression is documented as **~30 % slower to render**, and "more effective with
  larger fonts and higher bpp". Both LVGL and Espressif recommend compressing only the
  *largest* fonts of a UI (they cost the most flash, compress best, and are used less
  often than the body size). Against the table above that is a concrete trade: 1 802 B
  saved per 16 px/bpp4 font, 30 % decode tax on every glyph drawn.
- The decode path is not free of RAM churn: `decompress()` does `lv_malloc(w)` per
  glyph plus a second `lv_malloc(w)` when the bitmap uses the XOR prefilter
  (`lv_font_fmt_txt.c`, confirmed in LVGL master). On a text-heavy screen that is
  1-2 heap alloc/free pairs *per glyph per frame* - another argument for `--no-compress`
  on MCU targets. `decompress()` sits only on the compressed branch, so uncompressed
  glyphs skip those allocations entirely.

## LVGL 9 runtime facts that change font cost

Verified against `managed_components/lvgl__lvgl` 9.5:

- **No glyph cache for *static* (`fmt_txt`) fonts in LVGL 9.** `lv_font_conv` emits
  `lv_font_fmt_txt_glyph_cache_t cache; .cache = &cache` only inside
  `#if LVGL_VERSION_MAJOR == 8` (see generated file, and `lv_font_fmt_txt_dsc_t` in
  `src/font/fmt_txt/lv_font_fmt_txt.h:150-194` has no `cache` member in v9). So under
  v9 every glyph lookup walks `cmaps` and decodes the bitmap from flash each time it is
  drawn - which is why `--no-compress` is the sane default on MCU builds.
  Scope the claim precisely: LVGL 9 has four font engines - `fmt_txt` (C array),
  `binfont` (`.bin` from file), `tiny_ttf`, `freetype` - and only the last two cache
  glyphs. `tiny_ttf` caches 256 glyphs by default and creates three LRU caches
  (`TINY_TTF_GLYPH`, `TINY_TTF_DRAW_DATA`, `TINY_TTF_KERNING_DATA`,
  `lv_tiny_ttf.c:443-466`); tune with `lv_tiny_ttf_create_data_ex(data, size, px,
  kerning, cache_size)` or `LV_TINY_TTF_CACHE_GLYPH_CNT` / `LV_TINY_TTF_CACHE_KERNING_CNT`.
  `freetype` uses `LV_FREETYPE_CACHE_SIZE` (16 KB default) + `LV_FREETYPE_CACHE_FT_GLYPH_CNT`
  (256) and gained an optional 2-way set-associative L1 in 9.6
  (`LV_FREETYPE_CACHE_FT_GLYPH_L1`; `LV_FREETYPE_CACHE_FT_GLYPH_CNT` must be a power of 2).
  Caveat for tiny_ttf on ESP-IDF: open lvgl issue 9765 - random invisible letters with
  the *default* cache counts on LVGL 9.5 / ESP32-C5; setting both to 0 worked around it.
  Neither engine belongs in a Cyrillic UI that must just work: static `fmt_txt` is the
  predictable choice.
- `CONFIG_LV_CACHE_DEF_SIZE` is the **image** cache (Kconfig text: "Default image cache
  size"), not a font cache; the reference projects keep it `0`. Do not expect it to
  speed up text.
- Font data is `LV_ATTRIBUTE_LARGE_CONST` = flash `.rodata`, not RAM. It is safe on
  PSRAM-less parts; the cost is flash reads during draw, mitigated by the flash cache
  and by `CONFIG_COMPILER_OPTIMIZATION_PERF=y`.

## Rendering / core load levers

From `esp_lvgl_port` 2.9.0 headers (`include/esp_lvgl_port.h:53-73`) and the P4 project:

- LVGL runs in its own task: `lvgl_port_cfg_t port_cfg = ESP_LVGL_PORT_INIT_CONFIG();`
  gives `.task_priority = 4`, `.task_stack = 7168`, `.task_affinity = -1` (any core),
  `.task_stack_caps = MALLOC_CAP_INTERNAL|MALLOC_CAP_DEFAULT`, `.timer_period_ms = 5`.
  The SPI-display path in the reference project lowers it to `.task_priority = 1` and
  pins `.task_affinity = 1` so audio/wifi keep core 0
  (`esp32P4/main/display/lcd_display.cc:165-169`). If text redraws stutter a camera
  preview or audio, that pinning - not the font - is usually the fix.
- **Multicore software rendering**: `CONFIG_LV_DRAW_SW_DRAW_UNIT_CNT>1` *requires*
  `LV_USE_OS != LV_OS_NONE` (Kconfig help at `lvgl/Kconfig:296-303`). Both reference
  projects use `LV_OS_NONE` + `DRAW_UNIT_CNT=1`, i.e. single-threaded rendering; there
  is no core-affinity knob for the extra draw units.
- MIPI-DSI/P4 buffers: `lvgl_port_display_cfg_t` with `.buffer_size = width * 50`,
  `.double_buffer = false`, `flags.buff_dma = true`, `flags.buff_spiram = false`,
  `flags.sw_rotate = true`, plus `lvgl_port_display_dsi_cfg_t.flags.avoid_tearing`
  (`esp32P4/main/display/lcd_display.cc:274-322`). Small partial buffers + sw_rotate is
  what keeps font blits off the PSRAM bandwidth budget.
- **PPA (ESP32-P4 pixel accelerator)**: `CONFIG_LV_USE_PPA`, `CONFIG_LV_USE_PPA_IMG`,
  `CONFIG_LV_PPA_BURST_LENGTH` exist in LVGL 9.5's Kconfig (`:550-564`);
  `CONFIG_LVGL_PORT_ENABLE_PPA` in esp_lvgl_port is only for *screen rotation*.
  The reference P4 build keeps both **off** (proven path). If you enable PPA and get
  crashes, set `CONFIG_LV_DRAW_BUF_ALIGN=64` (LVGL Espressif "tips and tricks" page);
  the working config there is `=4`.
- Generic speed flags from the same page: `CONFIG_COMPILER_OPTIMIZATION_PERF=y`,
  `CONFIG_LV_ATTRIBUTE_FAST_MEM_USE_IRAM=y`, max CPU freq, `CONFIG_SPIRAM=y` +
  `CONFIG_SPIRAM_SPEED_200M=y`.

### DMA2D: the free win on a P4 MIPI-DSI panel (esp_lvgl_port does not use it)

The DPI panel driver ships a **built-in DMA2D `draw_bitmap` hook** - the copy from
LVGL's draw buffer into the frame buffer moves off the CPU with one call
(`docs.espressif.com/.../esp32p4/api-reference/peripherals/lcd/dsi_lcd.html`).
Verified present on the local IDF 6.1 tree: declared `esp_lcd_mipi_dsi.h:296`,
implemented `components/esp_lcd/dsi/esp_lcd_panel_dpi.c:524`, exercised by
`esp_lcd/test_apps/mipi_dsi_lcd/main/test_mipi_dsi_panel.c:261`.
Vendored `espressif__esp_lvgl_port` 2.9.0 has **zero** `dma2d` references, so you must
call it yourself after the panel is created:

```c
ESP_ERROR_CHECK(esp_lcd_dpi_panel_enable_dma2d(mipi_dpi_panel));
```

Migration trap: IDF `components/esp_lcd/hints.yml` says the `use_dma2d` **struct member was
removed in ESP-IDF v6.0** in favour of this function - old BSP code that set it no longer
compiles.

Alignment rules, and they bite quietly: with **flash encryption or PSRAM ECC enabled**,
MSPI requires every AXI access aligned, so DMA2D needs all four of these to be a multiple
of 16 bytes - buffer base, bytes-per-line (`pic_width * bpp/8`), transfer width
(`blk_width * bpp/8`) and the horizontal window offset (`offset_x * bpp/8`)
(`dma2d_check_transaction_alignment_constraint()` in IDF master,
`components/esp_driver_dma/src/dma2d.c`). The IDF example handles the LVGL side by rounding
the redrawn area in a `LV_EVENT_INVALIDATE_AREA` callback - on **IDF 6.1** that is
`examples/peripherals/lcd/mipi_dsi/main/mipi_dsi_lcd_example_main.c:96-100`, guarded by
`CONFIG_EXAMPLE_USE_DMA2D_COPY_FRAME`, and it uses the older macro names:

```c
lv_area_t * area = lv_event_get_invalidated_area(event);
area->x1 = ALIGN_DOWN(area->x1, 16);
area->x2 = ALIGN_UP(area->x2, 16) - 1;   /* master uses ESP_ALIGN_UP(x2 + 1, 16) - 1 */
```

Call `esp_lcd_dpi_panel_enable_dma2d()` right after the panel is created and **before**
`esp_lcd_panel_reset()/init()` (example line 277-281). Version notes for IDF 6.1 specifically:
`esp_lcd_dpi_panel_disable_dma2d()` also exists; the backend is
`esp_async_color_convert_install_dma2d()` with `dma_burst_size = 128` and same-format window
copy only (CSC deliberately disabled, `esp_lcd_panel_dpi.c:500-539`); 6.1 still allocates the
frame buffers with plain `heap_caps_calloc` - the `dma2d_get_alloc_alignment()` allocation
that guarantees a DMA2D-legal FB address is master-only, so on 6.1 keep your own buffers
16-byte aligned (`heap_caps_aligned_calloc(16, ...)`) if you turn it on.
Also from `esp_lcd_panel_dpi.c` (both verified on 6.1): default `in_color_format` is
**RGB888** (`:199-203`), and if the draw buffer *is* inside a frame buffer the driver skips
the copy entirely and only does a cache write-back (`:626`) - that is what
`flags.direct_mode` / full-screen buffers buy you (esp_lvgl_port asserts
`hres * vres == buffer_size` for both). For PPA beyond a plain copy, register your own
`esp_lcd_panel_hooks_t.draw_bitmap_hook` (`esp_lcd_dpi_panel_register_hooks()`); the panel
does **not** serialise draws for you - call `hook_data.on_hook_end()` only from the
accelerator completion callback.

### esp_lvgl_adapter beats esp_lvgl_port on this exact panel

`esp_lvgl_adapter` (esp-iot-solution) is Espressif's newer LVGL adaptation layer and the
component they now recommend in the GUI-optimization guide for tearing, FPS, image decode
and FreeType. Published benchmark on **ESP32-P4, MIPI-DSI 1024x600** - the resolution of
the GUITION board - under IDF v6.0 / LVGL 9 `lv_demo_benchmark`:
**55 fps vs 39 fps** for esp_lvgl_port; rotated full-screen **52 fps with anti-tearing vs
42 fps without**; PNG 512x512 4.28 ms vs 47.32 ms; JPG 512x512 2.57 ms vs 66 ms.
It adds three-buffer partial mode (anti-tearing without losing FPS), `esp_lv_fs` mmap
asset access, `esp_lv_decoder`, Dummy Draw and built-in FPS counters.
Known landmine: PPA freezes when rotation is combined with anti-tearing - esp-iot-solution
ships `0001-bugfix-lcd-Fixed-PPA-freeze.patch` (targets the IDF v5.5 register config on the
PPA SRM path) and the example README requires applying it.

### Authoritative FPS lever list (`esp-bsp/components/esp_lvgl_port/docs/performance.md`)

- **Draw buffer size and double buffering are by far the biggest lever.** >25 % of the
  screen adds no measurable gain; <10 % hurts severely; the graph assumes internal SRAM -
  PSRAM buffers measure worse.
- `CONFIG_COMPILER_OPTIMIZATION_PERF=y`, CPU at max frequency,
  flash `QIO` + `FLASHFREQ_120M` (or octal PSRAM/`SPIRAM_SPEED_200M` on P4).
- `CONFIG_LV_ATTRIBUTE_FAST_MEM_USE_IRAM=y` puts the hot LVGL functions in IRAM.
- `CONFIG_ESP_MAIN_TASK_AFFINITY_CPU1=y` to pin UI work to core 1 (dual-core parts).
- `CONFIG_LV_DEF_REFR_PERIOD=10` (v9; `LV_DISP_DEF_REFR_PERIOD` in v8) for subjective
  smoothness during scrolling.

## Keeping big fonts out of the code section

Three documented options once `.rodata` stops fitting, all supported on P4:

1. **binfont**: `lv_font_conv --format bin --no-compress -r 0x20-0x7F --symbols "..."` then
   `lv_binfont_create("A:/storage/font.bin")` from SPIFFS/LittleFS/FATFS. Espressif's
   worked example is `esp-iot-solution/examples/display/gui/lvgl_fs_assets` (ships
   `kaiti_24.bin`, a *subset* font, and warns the subset must cover your UI text).
   Note `--format bin` is stricter than `--format lvgl`: bpp3 silently accepted there,
   unsupported in C.
2. **FreeType + `esp_mmap_assets`**: fonts live in a dedicated partition (their layout is
   `factory 2000 KB` + `fonts 800 KB`) and are read through the LVGL virtual FS as
   `"F:name.ttf"` with `esp_lv_adapter_ft_font_init()` when `ESP_LV_ADAPTER_ENABLE_FREETYPE`
   is on. Trade-off stated by Espressif: one file serves every size, but rendering costs
   CPU and needs caching. `ESP_LVGL_ADAPTER_FREETYPE_SMALL_RENDER_POOL` shrinks the render
   pool 16 KB -> 4 KB, `..._FREETYPE_MINIMAL_BUILD` drops legacy font drivers from flash.
   With LVGL 9 the font render runs on **draw threads**, so stack sizing moves from your
   calling task to the draw threads (32 KB recommendation;
   `ESP_LVGL_ADAPTER_LVGL_THREAD_STACK_IN_PSRAM` is experimental).
3. **`CONFIG_SPIRAM_XIP_FROM_PSRAM=y`** on P4 relocates `.text` *and* `.rodata` (so all your
   C fonts) into PSRAM. Because P4 drives flash and PSRAM on separate SPI buses, this can
   *help*: a HEX 16-line PSRAM at 200 MHz beats quad flash at 80 MHz, and glyph reads stop
   contending with code fetches. Espressif still says profile it - if the relocated data is
   cold, you just spent PSRAM bandwidth.

MMU granularity matters for any mmap approach: flash maps in **64 KB pages**, so a 9 KB
font partition still consumes a page's worth of mapping and `spi_flash_mmap()` needs a
64 KB-aligned physical address (`esp_partition_mmap()` tolerates an arbitrary offset).

A fourth, production-proven shape exists: LVGL's own `fmt_txt` struct chain serialized as a
relocatable `.bin` in an mmap'd assets partition (no `lv_binfont`, no FreeType, no glyph
cache) - documented under "Very large scripts (CJK)" below with measured sizes.

## ESP-IDF / integration gotchas

- Add LVGL via `main/idf_component.yml`: `espressif/esp_lvgl_port: ^2.9.0` pulls
  `lvgl/lvgl >=8,<10`; pin `lvgl/lvgl: ~9.5.0` explicitly if you need v9 behaviour.
- esp_lvgl_port is sensitive to IDF's esp_lcd renames: the DPI/RGB callbacks
  `on_refresh_done` vs `on_frame_buf_complete` - in IDF 6.1 they are a **union** in
  `esp_lcd_mipi_dsi.h:204-208`, so both compile; IDF 6.0.2 needed the patch script
  `esp32P4/scripts/fix_esp_lvgl_port_idf602.sh`. IDF 6.1 also renamed
  `esp_lcd_panel_dev_config_t.color_space` to `rgb_ele_order`.
- IDF 6.1 + esp_lvgl_port 2.9.0 compiles clean for esp32p4 (verified: fonts and the
  port's version guards, `src/lvgl9/esp_lvgl_port_disp.c:159-162`).

## Fonts folder convention in a project

Keep the tooling and the artifacts out of `main/` source noise, in one dedicated dir
(what `JC1060P470C-camera-photo-app/fonts` does):

```
fonts/
  ttf/            source TTFs (DejaVu, Liberation, FreeMono - all ship Cyrillic)
  psf/            source 8x8 console PSFs for the bitmap path
  lvgl/           GENERATED LVGL C fonts - committed, since npx may be offline
  gen_cyr_from_psf.py, lvgl_convert.sh, README.md, cyr_font_table.c
```

The generated `lvgl/*.c` files must still be *compiled* by the firmware: either add
`fonts/lvgl` to `SRC_DIRS` in `main/CMakeLists.txt`, or keep LVGL fonts under the
component that uses them. Tooling dirs that ESP-IDF must not scan (like the PSF
converter) stay outside `main/` and `components/` - IDF only builds those two.
Regenerate + diff before committing; a byte-identical diff proves the pipeline is
reproducible (`fonts/gen_cyr_from_psf.py` reproduces `cyr_font_table.c` exactly).

## 8x8 bitmap path (no LVGL renderer)

For an overlay drawn straight into an RGB565 framebuffer: use a hand-drawn console PSF
(`Cyr_a8x8.psfu` from the `kbd` package, GPL-2.0+), **not** a TTF rasterised at 8 px -
TTF at that size smears ш/щ/ж/л/д into unreadable blobs. Convert with
`fonts/gen_cyr_from_psf.py`; it emits `app_overlay_font8x8_cyr[66][8]`
(0..31 = А..Я, 32..63 = а..я, 64/65 = Ё/ё) and composes Ё/ё from Е/е + dots in row 0
because cp866 PSFs have no Ё. Per-glyph fixes live in the converter's `OVERRIDES`
dict (ASCII-art). Metrics match LVGL's/Kernel's built-in 8x8 ASCII so the two tables
tile together.

## Very large scripts (CJK): binary/asset fonts

If you ever need thousands of glyphs, compiled-in C arrays are the wrong shape. Read
`C:\Users\megav\Downloads\xiaozhi-work\xiaozhi-esp32` (or `~/Downloads/esp32P4`) - both ship the
production component `78/xiaozhi-fonts` v2.0.0 (`github.com/78/noto-fonts`, LVGL `~9.5.0`,
IDF `>=5.5.2`), which is the most complete worked example of everything above:

- **Two tiers, two transports.** `basic` (about 890 glyphs) is built with
  `--format lvgl` and linked into `.rodata` (`src/font_noto_sans_basic_*.c`,
  204/540/749/1464 KB of source for 14_1/16_4/20_4/30_4). `common` (about 7400 glyphs,
  `basic union deepseek-BPE-core`) is built with `--format cbin` and shipped as a
  **`.bin` in the 8 MB `assets` partition** (`partitions/v2/16m.csv`, spiffs subtype at
  `0x800000`, read through `espressif/esp_mmap_assets ^1.4.0`). Measured `.bin` sizes,
  uncompressed: 263 KB (14_1), 865 KB (16_4), 1.23 MB (20_4), 2.49 MB (30_4) - use these as
  the budget oracle for any Cyrillic `common`-sized set.
- **Converter flags actually used in production** (`scripts/build.py:381-410`):
  `--no-compress --no-prefilter --force-fast-kern-format --format {lvgl|cbin} --bpp {1|4}
  --size N -r <compact ranges>`, plus `--autohint-off` for the 1 bpp extra-light profile.
  Nobody compresses: the CPU cost per glyph is what the skill warns about. bpp is only ever
  1 or 4 - `--bpp` choices in their CLI are literally `(1, 4)`.
- **Charset comes from your own UI strings**: `build_basic_charset(locale_dir)` = ASCII +
  Latin-1 + the static strings of the one selected locale (`main/assets/locales/*`).
  Cyrillic therefore needs no extra ranges at all - building with `CONFIG_LANGUAGE_RU_RU=y`
  (ru-RU, uk-UA, bg-BG, sr-RS all exist) puts exactly the needed Cyrillic into the subset.
  Uncovered code points are written to `build/basic-missing.json` instead of silently
  rendering tofu.
- **cbin = relocatable fmt_txt, not `lv_binfont`**: `src/cbin_font.c:34-99` memcpy's only the
  `lv_font_t`, the `lv_font_fmt_txt_dsc_t` and the `cmap` array out of mmap'd flash into RAM,
  re-bases every stored offset to the live address, and keeps
  `get_glyph_dsc/get_glyph_bitmap = lv_font_get_glyph_dsc/bitmap_fmt_txt` reading the glyph
  bitmaps **in place from flash**. So you get the static-fmt-txt behaviour (no glyph cache,
  predictable) with zero `.rodata` cost. `--format bin` (upstream) is the same idea with a
  different container.
- **Missing glyphs without reflashing**: `main/display/lvgl_display/dynamic_glyph_cache.h`
  assembles a runtime fmt_txt fallback font from bitmaps the server pushes
  (`DynamicGlyphCache::kMaxGlyphs = 256`, `kMaxBitmapBytes = 64 KiB`, LRU by `last_use`;
  protocol + `examples/glyph_push_server.py`). The device advertises its bundle/charset/size/bpp
  at registration, the server extracts only missing glyphs from the full CBIN bundle.
- Multi-script merging (latin + CJK + Thai + Arabic Noto sources into one font) is done with
  `fonttools==4.56.0`: subset -> deterministic font -> `cap_glyph_heights` -> then the
  generated `.c`/`.bin` is post-processed to re-fit every `ofs_y` into a fixed
  `line_height`/`base_line` box, which is what makes mixed-height fonts line up in LVGL.

## Checklist before calling a font done

1. `npx lv_font_conv` exit 0; header comment shows the exact `Opts:` line.
2. Ranges include 0x401/0x451 explicitly; test string has Ё, ъ, й, ш, щ, ж, №-free.
3. `CONFIG_LV_USE_FONT_COMPRESSED` matches how the font was generated.
4. `measure-font.sh` output reviewed; total font KB vs free app-partition space.
5. Build, then check the real flash delta (`idf.py build` app size before/after) -
   not the .c file size.
6. On-screen: no tofu, no half-height glyphs, no smear at the chosen size.
7. If any accelerator is on (PPA/DMA2D): buffer address, stride, width and x-offset all
   16-byte aligned (64-byte for PPA), and the UI still renders with flash encryption on.

## Answering the next font question with authority

Four MCP servers are configured for user scope (`~/.qoder/settings.json`) and are what
produced the facts above - prefer them over recall:

- `espressif_docs` → `search_espressif_sources(query)` — one focused natural-language
  query per call; returns ranked doc/source chunks with `file:line` URLs across ESP-IDF,
  esp-bsp, esp-iot-solution and techpedia. Needs a one-time browser OAuth (GitHub or
  WeChat) via `/mcp`; no API key. Has a companion `give_feedback(interaction_id)` —
  call it only if the user wants feedback sent to Espressif.
- `lvgl` → `search_lvgl_light_and_versatile_graphics_library_knowledge_sources(query)` —
  LVGL docs, `lv_conf_internal.h` macro reference, source blobs, forum threads and GitHub
  issues. Best for "does v9 cache glyphs", converter flag semantics, changelog per release.
- `espressif_components` → `search_components` / `fetch_component_detailed_information` —
  registry versions and dependencies (this is how esp_lvgl_port 2.9.0 was pinned; the
  `docs.espressif.com/projects/esp-lvgl-port` URL is 404).
- `esp_pilot_mcp` / `esp_vision` — board+SoC catalog and a docs/examples/symbols API
  (`list_examples`, `search_docs`, `list_symbols`, `catalog_list_bmgr_boards`) for pin
  and API lookup when the local board skill is not enough.

Two caveats learned the hard way: `mcp_list` only shows what the *current session* loaded,
so after adding or authenticating a server run `/mcp reload` and start a new chat; and these
servers return documentation as it is *today* - re-verify any file:line they cite against the
local tree before you rely on it.
