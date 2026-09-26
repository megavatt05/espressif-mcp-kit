#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kapa_login_helper.py — двухшаговый OAuth-вход на MCP-сервер kapa.ai (LVGL и др.)
из чата с AI-агентом, где нет браузера. Работает вручную, без локального listener:

  ШАГ 1 (агент): python3 kapa_login_helper.py start
      -> печатает ссылку авторизации и сохраняет PKCE-состояние в kapa_oauth_state.json

  ШАГ 2 (человек): открыть ссылку в браузере, войти через Google/GitHub.
      После входа браузер уйдёт на http://localhost:1455/callback?code=...&state=...
      Страница НЕ загрузится — это нормально. Скопируйте ПОЛНЫЙ адрес из адресной
      строки и передайте агенту.

  ШАГ 3 (агент): python3 kapa_login_helper.py finish '<вставленный-адрес>'
      -> обменяет code на access_token, проверит подключение к MCP-серверу
      и сохранит токен в kapa_token.txt (НЕ коммитится — добавить в .gitignore!)

Серверы kapa.ai, подходящие для этого входа (MCP-эндпоинт = корень):
  https://lvgl.mcp.kapa.ai/          — LVGL (провайдеры: Google, GitHub)
"""

import base64
import hashlib
import json
import secrets
import sys
import urllib.parse
import urllib.request

AUTH = "https://mcp.kapa.ai/auth/public"
MCP_SERVER = "https://lvgl.mcp.kapa.ai/"
REDIRECT = "http://localhost:1455/callback"
STATE_FILE = "kapa_oauth_state.json"
TOKEN_FILE = "kapa_token.txt"

# RFC 8707 Resource Indicators: kapa.ai ТРЕБУЕТ параметр resource и в /authorize,
# и в /token — по нему определяется MCP-проект (tenant). Без него их сервер
# возвращает error=server_error (подтверждено сотрудником kapa в
# github.com/openai/codex#11292). Значение берём из discovery-метаданных
# /.well-known/oauth-protected-resource — вместе с завершающим слэшем.
RESOURCE = "https://lvgl.mcp.kapa.ai/"

CLIENT_NAME = "espressif-mcp-kit (Super Z)"


def register_client():
    """Динамическая регистрация OAuth-клиента (RFC 7591) — kapa.ai позволяет анонимно."""
    payload = json.dumps({
        "client_name": CLIENT_NAME,
        "redirect_uris": [REDIRECT],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "client_secret_post",
    }).encode()
    req = urllib.request.Request(AUTH + "/register", data=payload,
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=30).read().decode())


def pkce_pair():
    """Пара verifier/challenge для PKCE (S256)."""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def start(reuse_client=False):
    """Шаг 1: регистрация + генерация ссылки авторизации.
    reuse_client=True — не регистрировать нового клиента, взять сохранённого
    (полезно при повторе после server_error, чтобы не упираться в лимиты)."""
    if reuse_client:
        try:
            client = json.load(open(STATE_FILE))
            client = {"client_id": client["client_id"],
                      "client_secret": client.get("client_secret", "")}
            print("Переиспользую ранее зарегистрированного клиента:", client["client_id"])
        except Exception:
            print("Сохранённого клиента нет — регистрирую нового.")
            client = register_client()
    else:
        client = register_client()
    verifier, challenge = pkce_pair()
    state = secrets.token_urlsafe(16)
    qs = urllib.parse.urlencode({
        "response_type": "code",
        "client_id": client["client_id"],
        "redirect_uri": REDIRECT,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "scope": "openid",
        "resource": RESOURCE,  # RFC 8707 — без него kapa даёт server_error!
    })
    with open(STATE_FILE, "w") as f:
        json.dump({"client_id": client["client_id"],
                   "client_secret": client.get("client_secret", ""),
                   "verifier": verifier, "state": state}, f)
    print("=" * 72)
    print("ШАГ 1 готов. Передайте пользователю ссылку (открыть в браузере):")
    print()
    print(AUTH + "/authorize?" + qs)
    print()
    print("После входа (Google/GitHub) браузер уйдёт на " + REDIRECT + "?code=...")
    print("Страница не загрузится — пусть пользователь скопирует полный адрес")
    print("из адресной строки и вставит его в чат.")
    print("Состояние PKCE сохранено: " + STATE_FILE)
    print("=" * 72)


def finish(callback_url):
    """Шаг 3: обмен code на токен + проверка MCP-подключения."""
    # Разбираем вставленный адрес
    u = urllib.parse.urlparse(callback_url.strip())
    q = urllib.parse.parse_qs(u.query)
    if "code" not in q:
        print("ОШИБКА: в адресе нет ?code=... — вставьте ПОЛНЫЙ адрес редиректа",
              file=sys.stderr)
        sys.exit(1)
    code = q["code"][0]
    cb_state = q.get("state", [""])[0]

    st = json.load(open(STATE_FILE))
    if cb_state and cb_state != st["state"]:
        print("ОШИБКА: state не совпал (защита CSRF). Начните заново: start",
              file=sys.stderr)
        sys.exit(1)

    # Обмен code -> access_token (client_secret_post, PKCE + resource по RFC 8707)
    data = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT,
        "client_id": st["client_id"],
        "client_secret": st["client_secret"],
        "code_verifier": st["verifier"],
        "resource": RESOURCE,  # обязателен для kapa (консистентность с /authorize)
    }).encode()
    req = urllib.request.Request(AUTH + "/token", data=data,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"},
                                 method="POST")
    try:
        tok = json.loads(urllib.request.urlopen(req, timeout=30).read().decode())
    except urllib.error.HTTPError as e:
        print(f"ОШИБКА обмена токена: HTTP {e.code}: {e.read().decode('utf-8','replace')[:300]}",
              file=sys.stderr)
        sys.exit(1)

    access = tok.get("access_token", "")
    refresh = tok.get("refresh_token", "")
    print(f"Токен получен: {access[:18]}... (длина {len(access)})")
    if refresh:
        print("Refresh-токен тоже выдан (сохранён рядом).")
    with open(TOKEN_FILE, "w") as f:
        f.write(access + ("\n" + refresh if refresh else ""))

    # Проверка подключения к MCP-серверу с токеном
    print(f"\nПроверяю подключение к {MCP_SERVER} ...")
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2025-03-26", "capabilities": {},
        "clientInfo": {"name": CLIENT_NAME, "version": "1.0.0"}}}).encode()
    req = urllib.request.Request(MCP_SERVER, data=payload, headers={
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Authorization": f"Bearer {access}"}, method="POST")
    body = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
    # Ответ может быть JSON или SSE — вытащим serverInfo
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            body = line[5:].strip()
            break
    init = json.loads(body)
    si = init.get("result", init).get("serverInfo", {})
    print(f"ПОДКЛЮЧЕНО: {si.get('name','?')} v{si.get('version','?')}")
    print(f"\nТокен сохранён: {TOKEN_FILE}")
    print("Использование с клиентом комплекта:")
    print(f"  python3 mcp_client.py --url {MCP_SERVER} --token <из {TOKEN_FILE}> info")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "start":
        # start [--reuse] : --reuse не регистрирует нового клиента заново
        start(reuse_client="--reuse" in sys.argv)
    elif len(sys.argv) >= 3 and sys.argv[1] == "finish":
        finish(sys.argv[2])
    else:
        print(__doc__)
