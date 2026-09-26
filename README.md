# espressif-mcp-kit

**Комплект для мгновенного восстановления подключения к MCP-серверам Espressif в любом AI-чате.**

Идея: вы показываете AI-агенту (Super Z / Claude / другой ассистент) этот репозиторий
или вставляете текст из [`restore_prompt.md`](restore_prompt.md) — и агент за минуту
восстанавливает рабочие подключения: скачивает клиент, проверяет серверы, знает,
какие из них требуют токен и что у каждого из них есть на борту.

## Состав проекта

| Файл | Назначение |
|---|---|
| `mcp_client.py` | Универсальный MCP-клиент: один файл, ноль зависимостей (Python 3 stdlib). Команды `info`, `list`, `call`, `search`; опции `--url`, `--token` |
| `servers.json` | Реестр серверов: адреса, статусы, полный список инструментов, OAuth-эндпоинты, подсказки для агента |
| `restore_prompt.md` | Готовый текст для вставки в новый чат — агент сам всё развернёт |
| `oauth_flow_probe.py` | Диагностика OAuth: проверяет авторегистрацию клиента и автоодобрение авторизации |
| `docs/espressif_mcp_servers.md` | Подробный отчёт о проверке серверов от 2026-09-27 |

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
| Technical Support | `https://ts-mcp.espressif.com/mcp` | 🔑 нужен токен | аккаунт Espressif (OAuth, браузер) |
| RainMaker | `https://mcp.rainmaker.espressif.com/api/mcp` | 🔑 нужен токен | аккаунт RainMaker (Cognito) |
| Documentation | `https://mcp.espressif.com/docs` | 🔑 нужен токен | GitHub или WeChat |

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
