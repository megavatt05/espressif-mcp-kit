#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mcp_client.py — универсальный MCP-клиент для серверов Espressif.
Один файл, без внешних зависимостей (только стандартная библиотека Python 3).

Реализует транспорт MCP "Streamable HTTP": JSON-RPC 2.0 поверх POST.
  1) initialize                   — рукопожатие, получение Mcp-Session-Id
  2) notifications/initialized    — подтверждение
  3) tools/list                   — список инструментов сервера
  4) tools/call                   — вызов инструмента

ПОДКЛЮЧАЕМЫЕ СЕРВЕЫРЫ (полный реестр — в файле servers.json рядом):
  БЕЗ авторизации (работают сразу):
    https://components.espressif.com/mcp          — реестр компонентов (по умолчанию)
    https://mcp.esp-pilot.espressif.com/mcp       — ESP-Pilot: платы BMGR, AI-скиллы, ADF/GMF
  ТРЕБУЮТ OAuth-токен (передайте через --token или переменную окружения MCP_TOKEN):
    https://ts-mcp.espressif.com/mcp              — техническая поддержка Espressif
    https://mcp.rainmaker.espressif.com/api/mcp   — ESP RainMaker (облако IoT)
    https://mcp.espressif.com/docs                — документация Espressif

ИСПОЛЬЗОВАНИЕ:
  python3 mcp_client.py info                           # сводка по серверу по умолчанию
  python3 mcp_client.py --url <адрес> info             # сводка по другому серверу
  python3 mcp_client.py --url <адрес> list             # полный JSON списка инструментов
  python3 mcp_client.py --url <адрес> call <tool> '<json-args>'
  python3 mcp_client.py --url <адрес> search '<запрос>'  # автопоиск через инструмент с "search"
  Токен: --token <JWT>  или  export MCP_TOKEN=...      # для закрытых серверов

ПРИМЕРЫ:
  python3 mcp_client.py --url https://mcp.esp-pilot.espressif.com/mcp call server_info '{}'
  python3 mcp_client.py search jd9165
  python3 mcp_client.py --url https://mcp.espressif.com/docs --token eyJ... list
"""

import json
import os
import sys
import urllib.error
import urllib.request

# Адрес по умолчанию — реестр компонентов Espressif (работает без токена)
MCP_URL = "https://components.espressif.com/mcp"

# Версия протокола MCP; если сервер её не поддерживает, он ответит ошибкой
# со списком поддерживаемых версий — тогда возьмём из его ответа.
PROTOCOL_VERSION = "2025-03-26"

CLIENT_INFO = {"name": "espressif-mcp-kit-client", "version": "1.0.0"}


class MCPClient:
    """Синхронный MCP-клиент поверх urllib — без внешних зависимостей."""

    def __init__(self, url=MCP_URL, token=None):
        self.url = url
        self.token = token or os.environ.get("MCP_TOKEN")  # токен из опции или окружения
        self.session_id = None  # Mcp-Session-Id из рукопожатия (сервер может не выдать)
        self.next_id = 1

    def _headers(self):
        """Заголовки запроса. Для закрытых серверов добавляем Bearer-токен."""
        h = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "User-Agent": "espressif-mcp-kit/1.0",
        }
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        if self.session_id:
            h["Mcp-Session-Id"] = self.session_id
        return h

    def _post(self, payload):
        """POST JSON-RPC. Возвращает список распарсенных сообщений (JSON или SSE)."""
        req = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        try:
            resp = urllib.request.urlopen(req, timeout=90)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            if e.code == 401:
                # Понятная подсказка вместо сырого трейсбека — важно для
                # восстановления подключения в новом чате
                raise RuntimeError(
                    f"HTTP 401: сервер {self.url} требует OAuth-токен.\n"
                    f"  Передайте его: --token <JWT> или export MCP_TOKEN=<JWT>.\n"
                    f"  Ответ сервера: {body[:300]}"
                ) from e
            raise RuntimeError(f"HTTP {e.code} на POST {self.url}: {body[:500]}") from e

        sid = resp.headers.get("Mcp-Session-Id")
        if sid:
            self.session_id = sid
        ctype = resp.headers.get("Content-Type", "")
        status = resp.status
        raw = resp.read().decode("utf-8", "replace")

        # 202 Accepted без тела — подтверждение уведомления (notify)
        if status == 202 or not raw.strip():
            return []

        if "text/event-stream" in ctype:
            # SSE: сообщения идут строками "data: <json>"
            msgs = []
            for line in raw.splitlines():
                line = line.strip()
                if line.startswith("data:"):
                    data = line[5:].strip()
                    if data and data != "[DONE]":
                        try:
                            msgs.append(json.loads(data))
                        except json.JSONDecodeError:
                            pass
            return msgs

        # Обычный application/json (возможна конкатенация нескольких объектов)
        msgs, dec, idx = [], json.JSONDecoder(), 0
        raw = raw.strip()
        while idx < len(raw):
            obj, end = dec.raw_decode(raw, idx)
            msgs.append(obj)
            idx = end
            while idx < len(raw) and raw[idx] in " \t\r\n":
                idx += 1
        return msgs

    def rpc(self, method, params=None, notify=False):
        """Один JSON-RPC вызов; для notify (без id) сервер отвечает 202."""
        payload = {"jsonrpc": "2.0", "method": method}
        if not notify:
            payload["id"] = self.next_id
            self.next_id += 1
        if params is not None:
            payload["params"] = params
        msgs = self._post(payload)
        for m in msgs:
            if not notify and isinstance(m, dict) and m.get("id") == payload.get("id"):
                if "error" in m:
                    raise RuntimeError(f"JSON-RPC ошибка ({method}): {m['error']}")
                return m.get("result")
        if notify:
            return None
        raise RuntimeError(f"Нет ответа на {method} (id={payload.get('id')})")

    def initialize(self):
        """Рукопожатие MCP: initialize + notifications/initialized."""
        result = self.rpc(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": CLIENT_INFO,
            },
        )
        self.rpc("notifications/initialized", notify=True)
        return result

    def list_tools(self):
        return self.rpc("tools/list", {})

    def call_tool(self, name, arguments=None):
        return self.rpc("tools/call", {"name": name, "arguments": arguments or {}})


def _extract_text(result):
    """Человекочитаемый текст из результата tools/call."""
    parts = []
    content = result.get("content", []) if isinstance(result, dict) else []
    for c in content:
        if c.get("type") == "text":
            parts.append(c.get("text", ""))
        else:
            parts.append(json.dumps(c, ensure_ascii=False)[:2000])
    if isinstance(result, dict) and result.get("isError"):
        parts.append("[СЕРВЕР СООБЩИЛ ОБ ОШИБКЕ]")
    return "\n".join(parts)


def main():
    try:
        run()
    except RuntimeError as e:
        # Ошибки (включая 401 с подсказкой про токен) печатаем БЕЗ трейсбека —
        # так их проще читать и человеку, и AI-агенту в новом чате
        print(f"ОШИБКА: {e}", file=sys.stderr)
        sys.exit(1)


def run():
    args = sys.argv[1:]

    # --- Разбор опций --url и --token (порядок не важен) ---
    url = MCP_URL
    token = None
    while "--url" in args or "--token" in args:
        if "--url" in args:
            i = args.index("--url")
            if i + 1 >= len(args):
                print("После --url укажите адрес сервера", file=sys.stderr)
                sys.exit(2)
            url = args[i + 1]
            del args[i:i + 2]
        if "--token" in args:
            i = args.index("--token")
            if i + 1 >= len(args):
                print("После --token укажите значение токена", file=sys.stderr)
                sys.exit(2)
            token = args[i + 1]
            del args[i:i + 2]

    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    cmd = args[0]
    client = MCPClient(url, token)

    # --- Рукопожатие ---
    init = client.initialize()
    server = init.get("serverInfo", {}) if isinstance(init, dict) else {}
    print(f"# Подключено: {server.get('name','?')} v{server.get('version','?')} "
          f"(протокол {init.get('protocolVersion','?')}, сессия {client.session_id})",
          file=sys.stderr)

    if cmd == "info":
        # Компактная сводка: имя сервера + список имён инструментов с кратким описанием
        tools = client.list_tools().get("tools", [])
        print(f"Сервер: {server.get('name','?')} v{server.get('version','?')}")
        print(f"URL:    {url}")
        print(f"Инструментов: {len(tools)}")
        for t in tools:
            d = t.get("description", "").split(".")[0]
            print(f"  - {t['name']}: {d[:100]}")
    elif cmd == "list":
        tools = client.list_tools()
        print(json.dumps(tools, ensure_ascii=False, indent=2))
    elif cmd == "call":
        if len(args) < 2:
            print("Укажите имя инструмента", file=sys.stderr)
            sys.exit(2)
        name = args[1]
        tool_args = json.loads(args[2]) if len(args) > 2 else {}
        result = client.call_tool(name, tool_args)
        print(_extract_text(result))
    elif cmd == "search":
        query = args[1] if len(args) > 1 else ""
        # Имя поискового инструмента определяем автоматически
        tools = client.list_tools().get("tools", [])
        names = [t["name"] for t in tools]
        search_tool = next((n for n in names if "search" in n.lower()), None)
        if not search_tool:
            print(f"Поисковый инструмент не найден. Доступны: {names}", file=sys.stderr)
            sys.exit(1)
        result = client.call_tool(search_tool, {"query": query})
        print(_extract_text(result))
    else:
        print(f"Неизвестная команда: {cmd} (доступны: info, list, call, search)",
              file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()