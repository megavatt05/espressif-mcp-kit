---
name: esp-idf-project-workflow
description: ESP-IDF 6.1.0 project lifecycle on this Windows 11 PC - creating projects (empty via idf.py create-project, from built-in examples, from ESP Component Registry examples via create-project-from-example, board-based via idf.py bmgr), the full idf.py command map (build/flash/monitor/menuconfig/size/efuse/secure/merge-bin/uf2/qemu), companion tools (esptool/espefuse/espsecure/parttool/otatool/compote), built-in idf.py mcp-server, and the hard rules for running any of it here (idf.ps1 wrapper, MSYSTEM trap, per-version venvs, eim registry). Use when creating, building, flashing, or managing ESP-IDF projects, when the user mentions idf.py commands, ESP-IDF examples, or asks how to start a new project for esp32/esp32p4/etc.
---

# ESP-IDF 6.1.0 project workflow (this machine)

## Install facts (verified 2026-10-13 against `C:\esp\v6.1\esp-idf`)

- IDF **6.1.0** (all targets) at `C:\esp\v6.1\esp-idf`; secondary **5.5.5** (esp32p4) at `C:\esp\v5.5.5\esp-idf`.
- Tools root `C:\Espressif\tools`; per-version venv `C:\Espressif\tools\python\v6.1\venv`
  (component manager 3.1.2, esp_idf_monitor 1.10, kconfig 3.13; CLI shims in `venv\Scripts\`:
  `esptool.exe`, `espefuse.exe`, `espsecure.exe`, `compote.exe`).
- **Authoritative SDK registry is `C:\Espressif\tools\eim_idf.json`** — `C:\Users\megav\.espressif\idf-env.json` is stale (v6.0.3), ignore it.
- `idf.py --version` prints 6.1.0. New vs classic CMake: template uses `include($ENV{IDF_PATH}/tools/cmake/project.cmake)`;
  a new v2 build system lives in `tools/cmakev2/idf.cmake` — never mix both lines in one project.

## Golden rule: how to run idf.py here

Raw `idf.py` from any git-bash/MSYS session is **broken on this box**, and it cannot be fixed from inside bash:
MSYS2's coreutils are patched so `MSYSTEM=MINGW64` is re-injected into every child process — even
`env -i venv\Scripts\python.exe` still sees it, and idf.py then aborts with "MSys/Mingw is no longer supported".

- From an agent/bash session always use the PowerShell wrapper:
  `powershell -NoProfile -File C:\Users\megav\.espressif\hermes\idf.ps1 -Idf v6.1 -Dir <project_dir> -Task "<idf.py args>"`
  - `-Idf` accepts `v6.1 | 61 | v5.5.5 | 555`; `-Dir` is the project dir; `-Task` is one quoted string —
    every option starting with a dash goes **inside** `-Task` (`-Task "-p COM10 flash"`). PowerShell `--`
    stop-parsing does not survive `-File`.
  - Exit code propagates. After an IDF version or component-set change run `-Task "fullclean"` first.
- Interactive `menuconfig` / `monitor` belong in a real console: `Desktop\IDF_v6.1_Powershell.lnk`.
- Non-interactive logs: `C:\Users\megav\.espressif\hermes\serial-log.ps1 -Port COM<x> -Seconds N`;
  for reset/send/expect semantics use the scripted monitor instead (see "IDF Monitor" below).
- Do **not** dot-source the eim activation profiles without `-e` — they end with `eim select <ver>`,
  which silently repoints the SDK the IDE extension uses.

## Creating a project — pick one of four routes

### A. Empty project (idf.py create-project)

```
idf.ps1 -Idf v6.1 -Dir <parent> -Task "create-project my_app"        # C template
idf.ps1 -Idf v6.1 -Dir <parent> -Task "create-project my_app --cpp" # C++ app_main (extern "C")
idf.ps1 -Idf v6.1 -Dir <parent> -Task "create-project my_app -p D:\target\folder"
```

- Copies `tools/templates/sample_project` (or `sample_project_cpp`): root `CMakeLists.txt`
  (`cmake_minimum_required(VERSION 3.22)` + `project.cmake` include), `main/CMakeLists.txt`,
  `main/main.c` renamed to the project name; `main` string replaced in both CMakeLists.
- Target dir must be empty → exit 3; not a dir → exit 4. The command exits idf.py — run it alone.
- Inside a project, `idf.py create-component my_comp` scaffolds a component from
  `tools/templates/sample_component` (`CMakeLists.txt`, `main.c`, `include/main.h`, renamed).

### B. From a built-in example ($IDF_PATH/examples)

~20 categories: `get-started` (blink, hello_world), `wifi`, `bluetooth`, `peripherals`, `storage`,
`protocols`, `system`, `security`, `ethernet`, `mesh`, `zigbee`, `openthread`, `cxx`, `lowpower`, `phy`, ...

1. **Copy the example folder somewhere writable — never build inside `$IDF_PATH/examples`** (the tree is a template source).
2. `idf.ps1 ... -Task "set-target esp32p4"` then `-Task "build"`, then `-Task "-p COM<x> flash"`.
3. Many examples carry `README.md` with the exact menuconfig options and wiring; read it first.
4. ESP-IDF VS Code extension equivalent: "ESP-IDF: Show Examples Projects" → pick → "Create project from example".

### C. From an ESP Component Registry example (idf.py create-project-from-example)

```
idf.ps1 -Idf v6.1 -Dir <parent> -Task "create-project-from-example \"espressif/ble_conn_mgr=*:spp_client\""
```

- Format `namespace/name=version_spec:example` — namespace and version are optional
  (`espressif/esp-dl:hand_gesture_recognition` = latest). Version spec follows idf-component-manager
  rules (`=3.3.8` exact-ish, `^3.3.8` compatible, `*` any).
- Downloads the example from the registry and pre-wires `main/idf_component.yml` dependencies.
- Standalone CLI equivalent: `venv\Scripts\compote.exe project create-from-example EXAMPLE`
  (see `compote --help`; also `compote project remove-managed-components`).
- **Discovery via MCP** (preferred over guessing names): `mcp__espressif_components__search_components`
  with a keyword, then `mcp__espressif_components__fetch_component_detailed_information` — the detail
  payload lists each example with its exact `create-project-from-example` command. Or browse
  components.espressif.com.

### D. Board-based project (esp_board_manager / bmgr)

For Espressif-managed boards (see `mcp__esp_pilot_mcp__catalog_list_bmgr_boards` — esp32_p4_function_ev_board,
esp32_s3_box_3, lyrat, korvo, vocat, ...; the JC1060P470C is **not** in the stock catalog, it has its own skill):

```
idf.py add-dependency "espressif/esp_board_manager"
idf.py bmgr -l            # list boards visible in the project
idf.py bmgr -b <board>    # generate components/gen_bmgr_codes
```

Re-run `bmgr -b` after any board YAML/amend change — generation is not incremental. Full flow and
runtime API (`esp_board_manager_init`, `get_device_handle`, ...) live in the esp-pilot skill
`board-manager-use` (fetch via `mcp__esp_pilot_mcp__catalog_get_skill`); authoring a new board is
`board-manager-create-board`. For the GUITION JC1060P470C use the `jc1060p470c-board` skill instead.

## The idf.py command map (6.1.0)

Run alone/terminating: `create-project`, `create-component`, `create-project-from-example`, `mcp-server`.
Global options: `-C/--project-dir`, `-B/--build-dir`, `-p/--port` (env `ESPPORT`), `-b/--baud` (`ESPBAUD`),
`-D/--define-cache-entry`, `-G/--generator` (Ninja), `--ccache/--no-ccache` (default off; `IDF_CCACHE_ENABLE`),
`--preset` (CMakePresets.json / `IDF_PRESET`), `--preview`, `-v/--verbose`, `--list-targets`.

| Area | Commands |
|------|----------|
| Build | `build` (alias `all`), `app`, `bootloader`, `partition-table`, `reconfigure`, `refresh-config`, `clean`, `fullclean` (also wipes sdkconfig-derived state), `python-clean` |
| Flash | `flash`, `app-flash`, `bootloader-flash`, `partition-table-flash`, `erase-flash`, `erase-otadata`, `read-otadata`, `encrypted-flash`, `encrypted-app-flash`, `merge-bin`, `uf2`, `uf2-app`, `dfu`, `dfu-flash`, `dfu-list` |
| Run | `monitor` (needs TTY — use real console or `serial-log.ps1`), `qemu` |
| Config | `menuconfig`, `confserver` (JSON config server), `save-defconfig`, `config-report` |
| Info | `size`, `size-components`, `size-files`, `show-efuse-table`, `build-system-targets`, `docs` (opens API docs in browser) |
| Target | `set-target <chip>` (esp32, esp32s2/s3/s31, esp32c2/c3/c5/c6/c61, esp32h2/h21/h4, esp32p4 — `idf.py --list-targets`) |
| Debug | `openocd`, `gdb`, `gdbtui`, `gdbgui`, `post-debug`, `coredump-info`, `coredump-debug` |
| Components | `add-dependency`, `remove-dependency` (≥6.0.1), `update-dependencies`, `create-manifest` |
| eFuse | `efuse-summary`, `efuse-dump`, `efuse-burn`, `efuse-burn-key`, `efuse-read-protect`, `efuse-write-protect`, `efuse-common-table`, `efuse-custom-table` |
| Secure boot/flash enc | `secure-generate-signing-key`, `secure-generate-key-digest`, `secure-sign-data`, `secure-verify-signature`, `secure-generate-flash-encryption-key`, `secure-encrypt-flash-data`, `secure-decrypt-flash-data`, `secure-encrypt-nvs-partition`, `secure-generate-nvs-partition-key`, `secure-digest-secure-bootloader` |
| Quality | `clang-check`, `clang-html-report`, `diag` (uses `esp-idf-diag`: create/list/check/zip), `sbom-create`, `sbom-check` |
| AI | `mcp-server` — see below |

Any unknown command is tried as a raw CMake/ninja target (`idf.py ninja --version` trick, custom targets from `idf_component_register(... ADD_CUSTOM_TARGETS)`).

Flash flags (verified in `serial_ext.py` 6.1): `-a/--all` forces full flash rewrite — mutually
exclusive with `-t/--trust-flash-content` (skips MD5 verify of unchanged sectors); `--extra-args "…"`
passes options through to esptool. `idf.py merge-bin` emits `.bin`/`.hex`/`.uf2`;
`idf.py refresh-config --policy=sdkconfig|interactive|kconfig` re-syncs sdkconfig against Kconfig defaults.

## IDF Monitor

Interactive hotkeys (real console only; VS Code launches `idf_monitor.py` itself with
`--ws ws://localhost:<port>` to stream into its UI): quit `Ctrl+]`, `Ctrl+C` halts the app / attaches
gdb via gdbstub; `Ctrl+T` menu prefix — `P` reset-to-bootloader (RTS/DTR), `R` reset (RTS), `F` fast
reflash, `E` full flash, `A` app-flash, `Y` toggle output, `L` toggle log-to-file, `I` timestamps, `H` help.

**Scripted (no-TTY) mode — the agent-friendly path** (esp_idf_monitor ≥1.10, verified in this venv;
it is a plain python module, not idf.py, so the MSYSTEM trap does not apply):

```
printf 'reset\nsend hi\nexpect --timeout 10 READY\nexit\n' | \
  "C:/Espressif/tools/python/v6.1/venv/Scripts/python.exe" -m esp_idf_monitor -p COM10 build/app.elf
```

Line commands read from piped stdin: `reset`, `flash` (fast reflash), `flash-all`, `app-flash`,
`send <text>`, `sleep <sec>`, `expect [--timeout N] <regex>` (blocks until match; also scans a bounded
look-back buffer of already-received lines), `output`, `log`, `timestamps`, `bootloader`, `exit`
(carries an exit code). Each command echoes to stderr. Prefer this over `serial-log.ps1` whenever you
need reset/expect semantics or a pass/fail signal.

Device→host automation: a firmware log line `IDF_MONITOR_EXECUTE_ESPEFUSE_SUMMARY <token>` or
`IDF_MONITOR_EXECUTE_ESPEFUSE_DUMP <token>` makes the monitor run
`espefuse --token <token> summary --active` / `dump` on the host (strict allowlist,
`base/monitor_secure_exec.py`).

## Companion CLIs (all in `C:\Espressif\tools\python\v6.1\venv\Scripts\`)

- `esptool.exe` — flash read/write/erase, image info, `write_flash`, `read_flash`, `erase_region`,
  chip id; underlying flasher for `idf.py flash`.
- `espefuse.exe` — eFuse burning/summary (CLI twin of `idf.py efuse-*`).
- `espsecure.exe` — signing/encryption helpers (twin of `idf.py secure-*`).
- `parttool.py` — direct partition ops on the connected device: `read_partition`, `write_partition`,
  `erase_partition`, `get_partition_info` (name/offset/size/flags). Partition-table CSV↔bin conversion:
  `components/partition_table/gen_esp32part.py`.
- `eim` — ESP-IDF Installation Manager (`eim run "idf.py <cmd>"` wraps any command with the
  activated env); on this box `idf.ps1` / the MCP launcher already do this job side-effect free.
- `compote.exe` — component manager CLI: registry login/upload, `compote project create-from-example`,
  manifest ops. `IDF_COMPONENT_MANAGER=0` disables the manager entirely.
- `esp-idf-diag` — diagnostic reports behind `idf.py diag`.

## MCP integration

### Already-connected Qoder servers (use these)

| Server | Tools | Use for |
|--------|-------|---------|
| `esp_pilot_mcp` | `catalog_list_socs`, `catalog_list_skills`, `catalog_get_skill`, `catalog_list_bmgr_boards`, `catalog_list_bmgr_devices/peripherals`, `catalog_get_bmgr_doc`, `catalog_list_adf_gmf_*` | SDK support matrix, board/device YAML facts, bmgr + ADF/GMF flows |
| `espressif_components` | `search_components`, `fetch_component_detailed_information` | Find components and their **examples** (route C) |
| `espressif_docs` | `search_espressif_sources` (en/cn) | Semantic search over ESP-IDF/ADF docs; after a query call `give_feedback` with the `interaction_id` |
| `esp_vision` | `get_capabilities`, `list_modules`, `search_docs`, ... | esp_vision APIs per chip/board before generating vision code |
| `lvgl` | `search_lvgl_light_and_versatile_graphics_library_knowledge_sources` | LVGL 9 questions |

### Built-in: `idf.py mcp-server` (registered in Qoder as `esp-idf`)

`idf.ps1 -Idf v6.1 -Dir <project> -Task "mcp-server"` starts a stdio MCP server exposing
tools `build_project`, `set_target`, `flash_project`, `create_project`, `clean_project` and resources
`project://config`, `project://status`, `project://devices`. Project resolution:
`IDF_MCP_WORKSPACE_FOLDER` env var → launch dir → explicit `project_dir` per call.

**Registered on this box (2026-10-13)** in user-scope `C:\Users\megav\.qoder\settings.json` as
server `esp-idf` (stdio → tools surface `mcp__esp-idf__*`). It launches through
`C:\Users\megav\.espressif\hermes\idf_mcp_launcher.py` (args `--idf v6.1`): the launcher captures
the eim env side-effect free, strips MSYSTEM/MINGW_*, then `exec()`s the venv python on
`tools/idf.py mcp-server`, so no PowerShell sits in the stdio chain. Two install facts that make
it work:
- The venv needed the `mcp` package: `venv\Scripts\pip install "mcp[cli]<2"` — **must be mcp 1.x**;
  mcp 2.x renamed `mcp.server.fastmcp.FastMCP` to `MCPServer` and IDF 6.1's `mcp_ext.py` then
  reports "MCP dependencies not available".
- The server shells out to `idf.py`, so the launching process must have a clean (non-MSYS)
  environment — the launcher guarantees this; launching from git-bash does not.
- For v5.5.5 add another entry pointing at the launcher with `--idf v5.5.5`.

## Defaults that bite

- `set-target` wipes and regenerates the build dir and sdkconfig for the new chip — commit sdkconfig.defaults first.
- `fullclean` deletes the whole build directory; `clean` only build outputs. Neither touches sdkconfig.
- `create-project*` refuses non-empty target dirs (exit 3) — point `-p` at a fresh folder.
- `monitor` in interactive mode requires a TTY; in agent sessions use the scripted monitor (piped
  stdin commands) or `serial-log.ps1 -Port COM<x> -Seconds N`.
- Baud: default flash 460800; `ESPBAUD`/`ESPPORT` env vars are honored by every subcommand.
- Component registry hits the network on first build of projects with `idf_component.yml`
  (Russia network: DNS-AI/Nova proxy env — see user memory; the registry itself is reachable, GitHub asset CDNs may not be).

## Related skills

- `jc1060p470c-board` — the GUITION ESP32-P4 board actually on this desk (pins, bring-up recipe).
- `lvgl-cyrillic-fonts` — LVGL 9 Cyrillic font generation for ESP32-P4.
- esp-pilot catalog skills `board-manager-use` / `board-manager-create-board` (via `catalog_get_skill`) —
  board-manager flows referenced in route D.
