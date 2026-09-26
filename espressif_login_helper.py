#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
espressif_login_helper.py — двухшаговый OAuth-вход на MCP-серверы Espressif
(ts-mcp / rainmaker / docs) из чата с AI-агентом, где нет браузера.

Аналог kapa_login_helper.py, но для серверов Espressif. Схема:
  ШАГ 1 (агент): python3 espressif_login_helper.py start <сервер>
      -> печатает ссылку авторизации, сохраняет PKCE-состояние
  ШАГ 2 (человек): открыть ссылку в браузере, войти (GitHub/WeChat/аккаунт RM),
      после входа браузер уйдёт на http://localhost:1455/callback?code=...
      Страница НЕ загрузится — скопировать ПОЛНЫЙ адрес из адресной строки.
  ШАГ 3 (агент): python3 espressif_login_helper.py finish '<вставленный-адрес>'
      -> помощник сам определит сервер по state, обменяет code на токен,
         проверит подключение к MCP и сохранит токен в espressif_token_<сервер>.txt

Серверы:
  docs       — https://mcp.espressif.com/docs          (вход GitHub / WeChat)
  rainmaker  — https://mcp.rainmaker.espressif.com/api/mcp (аккаунт ESP RainMaker)
  ts-mcp     — https://ts-mcp.espressif.com/mcp        (БЛОКИРОВАН: их /register
               принимает только заранее одобренные redirect_uri — ручной флоу
               невозможен, нужен только готовый токен от пользователя)

Особенности реализации:
  - оба рабочих сервера регистрируют ПУБЛИЧНОГО клиента (token_endpoint_auth_method
    = none), обмен токена идёт по PKCE без client_secret;
  - параметр resource (RFC 8707) передаётся и в /authorize, и в /token — это
    требование спецификации MCP; если сервер его не принял, делается повтор
    обмена без resource (страховка).
"""

import base64
import glob
import hashlib
import json
import os
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request

REDIRECT = "http://localhost:1455/callback"
CLIENT_NAME = "espressif-mcp-kit (Super Z)"

# Адреса и параметры серверов (сверены с discovery-метаданными 2026-09-27)
SERVERS = {
    "docs": {
        "name": "Espressif Documentation MCP",
        "mcp": "https://mcp.espressif.com/docs",
        "register": "https://mcp.espressif.com/docs/register",
        "authorize": "https://mcp.espressif.com/docs/authorize",
        "token": "https://mcp.espressif.com/docs/token",
        "resource": "https://mcp.espressif.com/docs",
        "scope": "read:user",
        "login": "GitHub или WeChat",
        "available": True,
    },
    "rainmaker": {
        "name": "ESP RainMaker MCP Server",
        "mcp": "https://mcp.rainmaker.espressif.com/api/mcp",
        "register": "https://mcp.rainmaker.espressif.com/oauth/register",
        "authorize": "https://mcp.rainmaker.espressif.com/oauth2/authorize",
        "token": "https://mcp.rainmaker.espressif.com/oauth2/token",
        "resource": "https://mcp.rainmaker.espressif.com/api/mcp",
        "scope": "openid",
        "login": "аккаунт ESP RainMaker (Cognito: email/пароль или соцсеть)",
        "available": True,
    },
    "ts-mcp": {
        "name": "Espressif Technical Support MCP",
        "mcp": "https://ts-mcp.espressif.com/mcp",
        "register": "https://ts-mcp.espressif.com/register",
        "authorize": "https://ts-mcp.espressif.com/authorize",
        "token": "https://ts-mcp.espressif.com/token",
        "resource": "https://ts-mcp.espressif.com/mcp",
        "scope": "openid",
        "login": "аккаунт Espressif",
        "available": False,  # /register отклоняет посторонние redirect_uri
    },
}

STATE_GLOB = "espressif_oauth_state_*.json"


def pkce_pair():
    """Пара verifier/challenge для PKCE (S256)."""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def list_servers():
    print("Доступные серверы:")
    for sid, s in SERVERS.items():
        flag = "ДОСТУПЕН для входа" if s["available"] else "БЛОКИРОВАН (ручной вход невозможен)"
        print(f"  {sid:10s} {s['mcp']}")
        print(f"  {'':10s} вход: {s['login']} — {flag}")


def register_client(s):
    """Динамическая регистрация публичного клиента (RFC 7591)."""
    payload = json.dumps({
        "client_name": CLIENT_NAME,
        "redirect_uris": [REDIRECT],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    }).encode()
    req = urllib.request.Request(s["register"], data=payload,
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=30).read().decode())


def start(server_id, reuse=False):
    if server_id not in SERVERS:
        print(f"Неизвестный сервер: {server_id}. Доступны: {', '.join(SERVERS)}",
              file=sys.stderr)
        sys.exit(2)
    s = SERVERS[server_id]
    if not s["available"]:
        print(f"Сервер {server_id} блокирует ручной вход: их /register принимает "
              f"только заранее одобренных клиентов (проверено 2026-09-27). "
              f"Возможен только готовый bearer-токен от пользователя.",
              file=sys.stderr)
        sys.exit(1)

    state_file = f"espressif_oauth_state_{server_id}.json"
    if reuse and os.path.exists(state_file):
        old = json.load(open(state_file))
        client = {"client_id": old["client_id"]}
        print(f"Переиспользую клиента {old['client_id']} сервера {server_id}")
    else:
        client = register_client(s)
        print(f"Зарегистрирован новый клиент: {client['client_id']}")

    verifier, challenge = pkce_pair()
    state = secrets.token_urlsafe(16)
    qs = urllib.parse.urlencode({
        "response_type": "code",
        "client_id": client["client_id"],
        "redirect_uri": REDIRECT,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "scope": s["scope"],
        "resource": s["resource"],  # RFC 8707
    })
    json.dump({"client_id": client["client_id"], "verifier": verifier,
               "state": state, "server": server_id}, open(state_file, "w"))
    print("=" * 72)
    print(f"ШАГ 1 готов [{s['name']}]. Ссылка для пользователя (открыть в браузере):")
    print()
    print(s["authorize"] + "?" + qs)
    print()
    print(f"Вход: {s['login']}. После входа браузер уйдёт на {REDIRECT}?code=...")
    print("Страница не загрузится — скопируйте ПОЛНЫЙ адрес и вставьте в чат.")
    print(f"Состояние сохранено: {state_file}")
    print("=" * 72)


def find_state_by_value(state_value):
    """Ищет файл состояния по значению state (для автоопределения сервера)."""
    for f in glob.glob(STATE_GLOB):
        st = json.load(open(f))
        if st.get("state") == state_value:
            return f, st
    return None, None


def finish(callback_url):
    u = urllib.parse.urlparse(callback_url.strip())
    q = urllib.parse.parse_qs(u.query)
    if "code" not in q:
        # Ошибочный колбэк вида ?error=... — покажем суть
        if "error" in q:
            print(f"ОШИБКА АВТОРИЗАЦИИ НА СЕРВЕРЕ: {q['error'][0]} — "
                  f"{urllib.parse.unquote_plus(q.get('error_description',[''])[0])}",
                  file=sys.stderr)
        else:
            print("В адресе нет ?code=... — вставьте ПОЛНЫЙ адрес редиректа",
                  file=sys.stderr)
        sys.exit(1)
    code = q["code"][0]
    cb_state = q.get("state", [""])[0]

    state_file, st = find_state_by_value(cb_state)
    if not st:
        print("state не совпал ни с одним сохранённым — начните заново: start <сервер>",
              file=sys.stderr)
        sys.exit(1)
    server_id = st["server"]
    s = SERVERS[server_id]
    print(f"Сервер определён по state: {server_id} ({s['name']})")

    # Обмен code -> токен: публичный клиент, PKCE + resource (RFC 8707)
    def exchange(with_resource):
        data = urllib.parse.urlencode({
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT,
            "client_id": st["client_id"],
            "code_verifier": st["verifier"],
            **({"resource": s["resource"]} if with_resource else {}),
        }).encode()
        req = urllib.request.Request(s["token"], data=data, headers={
            "Content-Type": "application/x-www-form-urlencoded"}, method="POST")
        return json.loads(urllib.request.urlopen(req, timeout=30).read().decode())

    try:
        tok = exchange(True)
    except urllib.error.HTTPError as e:
        if e.code in (400, 401) and s["resource"]:
            print("Сервер не принял resource в /token — повтор без него...")
            tok = exchange(False)
        else:
            body = e.read().decode("utf-8", "replace")[:300]
            print(f"ОШИБКА обмена токена: HTTP {e.code}: {body}", file=sys.stderr)
            sys.exit(1)

    access = tok.get("access_token", "")
    refresh = tok.get("refresh_token", "")
    print(f"Токен получен: {access[:18]}... (длина {len(access)})")
    if refresh:
        print("Refresh-токен тоже выдан (сохранён рядом).")
    token_file = f"espressif_token_{server_id}.txt"
    with open(token_file, "w") as f:
        f.write(access + ("\n" + refresh if refresh else ""))

    # Проверка подключения: initialize + tools/list
    print(f"\nПроверяю подключение к {s['mcp']} ...")
    def mcp_call(payload, token):
        req = urllib.request.Request(s["mcp"], data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json",
                                              "Accept": "application/json, text/event-stream",
                                              "Authorization": f"Bearer {token}"},
                                     method="POST")
        body = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
        for line in body.splitlines():
            line = line.strip()
            if line.startswith("data:"):
                body = line[5:].strip()
                break
        return json.loads(body)

    init = mcp_call({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2025-03-26", "capabilities": {},
        "clientInfo": {"name": CLIENT_NAME, "version": "1.0.0"}}}, access)
    si = init.get("result", init).get("serverInfo", {})
    print(f"ПОДКЛЮЧЕНО: {si.get('name','?')} v{si.get('version','?')}")

    try:
        tools = mcp_call({"jsonrpc": "2.0", "id": 2, "method": "tools/list",
                          "params": {}}, access)
        tl = tools.get("result", tools).get("tools", [])
        print(f"Инструментов: {len(tl)}")
        for t in tl[:10]:
            print(f"  - {t['name']}: {t.get('description','')[:90]}")
    except Exception as e:
        print(f"(tools/list не прошёл: {str(e)[:120]})")

    print(f"\nТокен сохранён: {token_file}")
    print(f"Использование: python3 mcp_client.py --url {s['mcp']} "
          f"--token \"$(head -1 {token_file})\" info")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "list":
        list_servers()
    elif len(sys.argv) >= 3 and sys.argv[1] == "start":
        start(sys.argv[2], reuse="--reuse" in sys.argv)
    elif len(sys.argv) >= 3 and sys.argv[1] == "finish":
        finish(sys.argv[2])
    else:
        print(__doc__)
        sys.exit(0)
