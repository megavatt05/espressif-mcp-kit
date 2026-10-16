# espressif-mcp-kit

**Комплект для мгновенного восстановления подключения к MCP-серверам Espressif в любом AI-чате.**

Идея: вы показываете AI-агенту (Super Z / Claude / другой ассистент) этот репозиторий
или вставляете текст из [`restore_prompt.md`](restore_prompt.md) — и агент за минуту
восстанавливает рабочие подключения: скачивает клиент, проверяет серверы, знает,
какие из них требуют токен и что у каждого из них есть на борту.

> **Содержание:** [Состав](#состав-проекта) · [Навыки AI-агента (Skills)](#навыки-ai-агента-skills) · [Быстрый старт](#быстрый-старт-человек) · [Статус серверов](#статус-серверов-проверено-2026-09-27) · [OAuth Google](#вход-через-google-на-kapaai-lvgl--как-это-работает) · [Токены](#как-получить-токены-для-закрытых-серверов) · [Для AI-агента](#инструкция-для-ai-агента) · [Источники](#откуда-эти-знания)

## Состав проекта

| Файл / Папка | Назначение |
|---|---|
| `skills/` | База инженерных навыков (Skills) для AI-агентов (HMI верстка, LVGL, ESP32-P4, шрифты, ESP-IDF) |
| `mcp_client.py` | Универсальный MCP-клиент: один файл, ноль зависимостей (Python 3 stdlib). Команды `info`, `list`, `call`, `search`; опции `--url`, `--token` |
| `servers.json` | Реестр серверов: адреса, статусы, полный список инструментов, OAuth-эндпоинты, подсказки для агента |
| `kapa_login_helper.py` | Двухшаговый OAuth-вход на kapa.ai (LVGL) через Google/GitHub из чата без браузера |
| `restore_prompt.md` | Готовый текст для вставки в новый чат — агент сам всё развернёт |
| `oauth_flow_probe.py` | Диагностика OAuth: проверяет авторегистрацию клиента и автоодобрение авторизации |
| `docs/espressif_mcp_servers.md` | Подробный отчёт о проверке серверов от 2026-09-27 |

## Навыки AI-агента (Skills)

Каталог `skills/` содержит набор специализированных навыков (Agent Skills по стандарту Antigravity / Claude / Cursor), созданных на основе реальной промышленной разработки под ESP-IDF, LVGL 9 и аппаратные платы ESP32-P4:

| Навык (Skill) | Описание и назначение | Ключевые возможности |
|---|---|---|
| [`hmi-layout-budget-overflow`](skills/hmi-layout-budget-overflow/SKILL.md) | **Контроль переполнения экранов, наложений и проверка заполнения пространства в индустрии HMI** | AABB Collision Assertion (поиск перекрытий кнопок), W3C/ISO 9241 Touch Target (размер под палец ≥ 44–60 px), Screen Space Budgeting (оптимум 65–82%), защита от ловушки паддингов темы LVGL 9, Python-валидатор геометрии `verify_hmi_layout.py` |
| [`jc1060p470c-board`](skills/jc1060p470c-board/SKILL.md) | **Аппаратная база платы Guition JC1060P470C (ESP32-P4)** | Полная распиновка GPIO (MIPI-DSI дисплей JD9165, тач GT911, аудиокодек ES8311, microSD, Wi-Fi ESP32-C6 через esp_hosted, Ethernet), Kconfig-настройки, рецепты сборки/прошивки |
| [`lvgl-cyrillic-fonts`](skills/lvgl-cyrillic-fonts/SKILL.md) | **Генерация и оптимизация кириллических шрифтов для LVGL 9** | Точные команды `lv_font_conv`, диапазоны Unicode (Basic Russian + Ukrainian), бюджет Flash-памяти в зависимости от bpp/компрессии, FreeType-mmap / XIP-PSRAM, DMA2D/PPA выравнивание |
| [`esp-idf-commands`](skills/esp-idf-commands/SKILL.md) | **Справочник команд ESP-IDF v6.1 PowerShell на Windows 11** | Команды `idf.py`, `esptool.py`, `espefuse.py`, `otatool.py`, управление портами COM, перепрошивка, мониторинг |
| [`esp-idf-project-workflow`](skills/esp-idf-project-workflow/SKILL.md) | **Жизненный цикл проектов ESP-IDF v6.1 на Windows 11** | Создание проектов, шаблоны bmgr, ловушка MSYSTEM, venv окружения, реестр eim, интеграция с встроенным MCP-сервером ESP-IDF |
| [`russian-language`](skills/russian-language/SKILL.md) | **Правило русского языка** | Принудительное ведение всех диалогов, инженерных рассуждений, документации и комментариев на русском языке |

### Как использовать навыки в AI-ассистентах

1. **Antigravity IDE / Gemini CLI:** Скопируйте папку навыка в глобальный каталог `~/.gemini/config/skills/` или в рабочий проект в `.agents/skills/`.
2. **Claude Desktop / Cursor:** Подключите путь к репозиторию как Workspace или укажите папку навыков в системных инструкциях проекта.

---

## Быстрый старт (человек)

```bash
# Сводка по реестру компонентов Espressif (работает сразу, без токена)
python3 mcp_client.py info

# Сводка по ESP-Pilot (платы, скиллы, мультимедиа) — тоже без токена
python3 mcp_client.py --url https://mcp.esp-pilot.espressif.com/mcp info

# Поиск компонента в реестре
python3 mcp_client.py search jd9165

# Вызов инструмента с аргументами
python3 mcp_client.py --url https://mcp.esp-pilot.espressif.com/mcp \
    call catalog_list_bmgr_boards '{"chip":"esp32p4"}'

# Закрытый сервер: нужен OAuth-токен (см. ниже)
python3 mcp_client.py --url https://mcp.espressif.com/docs --token eyJ... list
```

## Статус серверов (проверено 2026-09-27)

| Сервер | URL | Статус | Авторизация |
|---|---|---|---|
| Components Registry | `https://components.espressif.com/mcp` | ✅ работает | не нужна |
| ESP-Pilot | `https://mcp.esp-pilot.espressif.com/mcp` | ✅ работает | не нужна |
| LVGL (kapa.ai) | `https://lvgl.mcp.kapa.ai/` | ✅ работает | Google/GitHub OAuth — готов помощник `kapa_login_helper.py` |
| Technical Support | `https://ts-mcp.espressif.com/mcp` | 🔑 нужен токен | аккаунт Espressif (OAuth, браузер) |
| RainMaker | `https://mcp.rainmaker.espressif.com/api/mcp` | 🔑 нужен токен | аккаунт RainMaker (Cognito) |
| Documentation | `https://mcp.espressif.com/docs` | 🔑 нужен токен | GitHub или WeChat |

## Вход через Google на kapa.ai (LVGL) — как это работает

У kapa.ai обычный OAuth, но с особенностью: параметр **`resource`** (RFC 8707)
обязателен и в `/authorize`, и в `/token` — без него сервер отдаёт `server_error`
(подтверждено сотрудником kapa в `openai/codex#11292`). Помощник делает всё сам:

```bash
python3 kapa_login_helper.py start --reuse   # 1) ссылка для браузера
# пользователь: открывает ссылку, входит через Google, копирует адрес
#   http://localhost:1455/callback?code=... из адресной строки
python3 kapa_login_helper.py finish '<вставленный-адрес>'   # 2) токен получен
python3 mcp_client.py --url https://lvgl.mcp.kapa.ai/ --token "$(head -1 kapa_token.txt)" info
```

Токен и PKCE-состояние сохраняются в `kapa_token.txt` / `kapa_oauth_state.json` —
оба в `.gitignore`, в репозиторий не попадают.

Важные детали OAuth (полностью — в `servers.json`):
- все три закрытых сервера поддерживают **только** grant `authorization_code` (+ refresh_token),
  т.е. токен выдаётся только после входа человека в браузере; `client_credentials` нет;
- `ts-mcp` отклоняет динамическую регистрацию посторонних клиентов (`invalid_redirect_uri`);
- `docs` — единственный, где анонимная регистрация клиента проходит, но дальше всё равно
  нужна страница входа;
- `rainmaker` — AWS Cognito (user pool `us-east-1_L9u4S0N1i`), есть эндпоинт `/api/mcp/reauthenticate`.

## Как получить токены для закрытых серверов

1. Добавьте URL сервера в MCP-клиент с браузером (Claude Desktop, Cursor, VS Code, Gemini CLI).
2. Пройдите вход (Espressif / RainMaker / GitHub).
3. Извлеките bearer-токен из конфигурации клиента (обычно в `mcp.json`/файле сессии)
   или из заголовка `Authorization` в логах.
4. Передайте токен нашему клиенту через `--token` или `export MCP_TOKEN=...`.

⚠️ **Никогда не коммитьте токены в этот репозиторий** — они передаются только в момент работы.

## Инструкция для AI-агента

Смотри [`restore_prompt.md`](restore_prompt.md) — короткий самодостаточный промпт.
Расширенная справка: `servers.json` → поле `recovery_hints.for_ai_agent`.

## Откуда эти знания

Комплект собран в ходе реальной работы над проектом
[`ESP32P4-JC1060P470C-I_W_Y`](https://github.com/megavatt05/ESP32P4-JC1060P470C-I_W_Y)
(плата Guition JC1060P470C, ESP32-P4): через реестр компонентов подбирались версии
`esp_lcd_jd9165` (драйвер экрана JD9165) и `esp_hosted` (Wi-Fi через сопроцессор ESP32-C6),
поэтому все примеры вызовов — из практики, не из документации.
