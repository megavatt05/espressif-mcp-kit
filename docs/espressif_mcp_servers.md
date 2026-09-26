# MCP-серверы Espressif — статус подключения и справка

Дата проверки: 2026-09-27. Клиент: `scripts/mcp_registry_client.py` (опция `--url <адрес>`).

## Сводная таблица

| Сервер | URL | Статус | Авторизация |
|---|---|---|---|
| Components Registry | https://components.espressif.com/mcp | РАБОТАЕТ (давно) | не нужна |
| ESP-Pilot | https://mcp.esp-pilot.espressif.com/mcp | РАБОТАЕТ | не нужна |
| Technical Support | https://ts-mcp.espressif.com/mcp | НУЖЕН ТОКЕН | OAuth (аккаунт Espressif), только authorization_code |
| RainMaker | https://mcp.rainmaker.espressif.com/api/mcp | НУЖЕН ТОКЕН | OAuth Cognito (аккаунт RainMaker), только authorization_code |
| Documentation | https://mcp.espressif.com/docs | НУЖЕН ТОКЕН | OAuth, вход GitHub или WeChat |

## 1. ESP-Pilot (mcp.esp-pilot.espressif.com/mcp) — v0.5.0

Подключён без авторизации, tools/call проверен. Stateless-сервер (Mcp-Session-Id не выдаёт).

Каталог из 11 инструментов:
- `catalog_list_bmgr_devices` — устройства из каталога ESP Board Manager (фильтр по чипу/IDF)
- `catalog_list_bmgr_peripherals` — периферия BMGR (фильтры: тип, роль, формат, чип)
- `catalog_list_bmgr_boards` — список плат BMGR (реальные SoC, фильтр по чипу)
- `catalog_list_socs` — каталог возможностей SoC
- `catalog_get_bmgr_doc` — документ BMGR по плате
- `catalog_list_skills` / `catalog_get_skill` — AI-скиллы (ресурсы, agents)
- `catalog_list_adf_gmf_capabilities` / `catalog_get_adf_gmf_capability` — возможности ADF/GMF (мультимедиа)
- `catalog_list_adf_gmf_scenarios` — примеры ADF (имя, категория, github_url)
- `server_info` — метаданные каталога (источники: esp-board-manager, esp-gmf f654a316, esp-adf-internal 2a1552b4e)

Пример вызова:
```
python3 scripts/mcp_registry_client.py --url https://mcp.esp-pilot.espressif.com/mcp \
  call catalog_list_bmgr_boards '{"chip":"esp32p4","limit":20}'
```

## 2. Серверы с OAuth (ts-mcp, rainmaker, docs)

Все три отдают 401 и поддерживают ТОЛЬКО grant `authorization_code` (+ refresh_token),
т.е. требуется вход человека в браузере. Серверы `client_credentials` не дают.

Проверено (scripts/oauth_flow_probe.py):
- **docs**: динамическая регистрация клиента работает (client_id выдаётся), но
  `/authorize` возвращает HTML-страницу входа: GitHub или WeChat. Автоодобрения нет.
- **ts-mcp**: динамическая регистрация ОТКЛОНЯЕТ произвольные redirect_uri
  (`invalid_redirect_uri` — только заранее одобренные клиенты). Discovery:
  `https://ts-mcp.espressif.com/.well-known/oauth-authorization-server`.
- **rainmaker**: Cognito (user pool us-east-1_L9u4S0N1i), scopes openid/email/phone;
  discovery: `https://mcp.rainmaker.espressif.com/.well-known/oauth-protected-resource`.

Как использовать в дальнейшем:
1) Вариант «у себя»: добавить эти URL в MCP-клиент с браузером (Claude Desktop,
   Cursor, VS Code) — там OAuth-вход пройдёт штатно.
2) Вариант «здесь»: получить bearer-токен в своём MCP-клиенте и прислать его —
   тогда добавить в клиент опцию `--token <JWT>` и передавать
   `Authorization: Bearer <токен>` (реализация ~5 строк, место в _headers помечено).
3) Для rainmaker есть `GET /api/mcp/reauthenticate` — сброс сессии.

## 3. Напоминание: клиент

`scripts/mcp_registry_client.py`:
- `list` — список инструментов (JSON)
- `call <tool> '<json>'` — вызов инструмента
- `search '<запрос>'` — авто-поиск через инструмент с "search" в имени
- `--url <адрес>` — выбор сервера (по умолчанию реестр компонентов)
