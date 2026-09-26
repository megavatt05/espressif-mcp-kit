#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
oauth_flow_probe.py — проверка, можно ли получить OAuth-токен у MCP-серверов
Espressif БЕЗ участия человека (авторегистрация + автоодобрение авторизации).

Логика:
  1) POST <registration_endpoint> — динамическая регистрация клиента (RFC 7591)
  2) GET  <authorization_endpoint>?response_type=code&client_id=...&redirect_uri=...
     с PKCE — если сервер сразу редиректит с code, вход не нужен; если
     возвращает HTML-страницу логина — требуется участие пользователя.
"""

import hashlib
import base64
import json
import secrets
import sys
import urllib.parse
import urllib.request

# Не открываем редиректы — нам важно увидеть Location 302-ответа
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

OPENER = urllib.request.build_opener(NoRedirect)

def probe(base_url, reg_path, auth_path):
    print(f"\n=== {base_url} ===")

    # --- Шаг 1: динамическая регистрация клиента ---
    reg_url = base_url + reg_path
    payload = json.dumps({
        "client_name": "superz-mcp-probe",
        "redirect_uris": ["http://localhost:1455/callback"],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    }).encode()
    req = urllib.request.Request(reg_url, data=payload,
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        resp = OPENER.open(req, timeout=30)
        client = json.loads(resp.read().decode())
        cid = client.get("client_id", "?")
        print(f"[Регистрация] OK, client_id={cid[:24]}...")
    except Exception as e:
        print(f"[Регистрация] НЕ УДАЛАСЬ: {e}")
        return

    # --- Шаг 2: авторизация с PKCE, смотрим ответ ---
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(8)
    qs = urllib.parse.urlencode({
        "response_type": "code",
        "client_id": cid,
        "redirect_uri": "http://localhost:1455/callback",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "scope": "read:user",
    })
    auth_url = base_url + auth_path + "?" + qs
    req = urllib.request.Request(auth_url, headers={"User-Agent": "superz-probe/1.0"})
    try:
        resp = OPENER.open(req, timeout=30)
        body = resp.read(400).decode("utf-8", "replace")
        ctype = resp.headers.get("Content-Type", "")
        print(f"[Авторизация] HTTP {resp.status}, {ctype}")
        if "<html" in body.lower() or "login" in body.lower() or "sign in" in body.lower():
            print("[Вывод] сервер показывает СТРАНИЦУ ВХОДА — нужен человек (браузер)")
        else:
            print(f"[Вывод] тело начинается с: {body[:200]!r}")
    except urllib.error.HTTPError as e:
        loc = e.headers.get("Location", "")
        print(f"[Авторизация] HTTP {e.code}, Location={loc[:120]}")
        if "code=" in loc:
            print("[Вывод] код выдан СРАЗУ — авторизация автоматическая!")
        elif e.code in (302, 303) and not loc:
            print("[Вывод] редирект без кода — вероятно, страница логина")
        else:
            b = e.read(300).decode("utf-8", "replace")
            print(f"[Вывод] тело: {b[:250]!r}")
    except Exception as e:
        print(f"[Авторизация] ошибка: {e}")

# Адреса взяты из discovery-метаданных каждого сервера
probe("https://ts-mcp.espressif.com", "/register", "/authorize")
probe("https://mcp.espressif.com/docs", "/register", "/authorize")
