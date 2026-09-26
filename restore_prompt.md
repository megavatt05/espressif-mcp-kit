# restore_prompt.md — вставьте этот блок в любой новый чат с AI-агентом

Скопируйте текст ниже целиком (от линии до линии) и вставьте в начало нового диалога.
Агент сам скачает клиент, проверит серверы и восстановит подключения.

---

Подключись к MCP-серверам Espressif. У меня есть готовый комплект знаний — репозиторий
https://github.com/megavatt05/espressif-mcp-kit — сделай так:

1. Скачай клиент и реестр серверов:
   - https://raw.githubusercontent.com/megavatt05/espressif-mcp-kit/main/mcp_client.py
   - https://raw.githubusercontent.com/megavatt05/espressif-mcp-kit/main/servers.json
   Клиент — один файл на чистом Python 3 (stdlib), без зависимостей. Сохрани оба файла
   в рабочую папку (например, scripts/).

2. Прочитай servers.json: там адреса всех серверов, их статусы, полный список
   инструментов и OAuth-детали (поле recovery_hints.for_ai_agent — тебе).

3. Проверь серверы, которые работают без токена (status=WORKS):
   python3 mcp_client.py --url https://components.espressif.com/mcp info
   python3 mcp_client.py --url https://mcp.esp-pilot.espressif.com/mcp info
   Команды клиента: info (сводка), list (полный JSON инструментов),
   call <tool> '<json-args>' (вызов), search '<запрос>' (автопоиск).

4. Серверы с авторизацией требуют OAuth-токен: спроси у меня bearer-токен, если он
   мне нужен, и вызывай их так:
   python3 mcp_client.py --url <адрес> --token <JWT> info
   При HTTP 401 — токен отсутствует/просрочен; попроси новый. Без токена эти серверы
   не открываются: grant только authorization_code (вход в браузере), автоматизации нет.
   ОСОБОЕ: сервер LVGL (https://lvgl.mcp.kapa.ai/, вход Google/GitHub) подключается
   через готовый помощник kapa_login_helper.py из этого же репозитория:
     python3 kapa_login_helper.py start --reuse      # выдаст ссылку — отдай мне
     (я войду через Google и вставлю сюда адрес http://localhost:1455/callback?code=...)
     python3 kapa_login_helper.py finish '<вставленный адрес>'   # получит токен
   КРИТИЧНО для kapa.ai: в /authorize и /token обязателен параметр resource
   (RFC 8707) = https://lvgl.mcp.kapa.ai/ — без него server_error. Помощник
   это уже учитывает. Токен живёт в kapa_token.txt (в .gitignore).

5. Для вызовов инструментов используй списки из servers.json (там схемы аргументов).
   Реестр компонентов: search_components(query), fetch_component_detailed_information
   (namespace, component). ESP-Pilot: catalog_list_bmgr_boards {chip}, server_info и др.

Краткая справка: WORKS = components registry (реестр компонентов IDF), esp-pilot
(платы BMGR, AI-скиллы Espressif, примеры ADF/GMF). TOKEN_REQUIRED = ts-mcp
(техподдержка, аккаунт Espressif), rainmaker (облако IoT, аккаунт RainMaker/Cognito),
docs (документация, вход GitHub/WeChat).

---
