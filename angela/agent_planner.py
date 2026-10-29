"""Bounded AI planner: language understanding never means unrestricted shell access."""
from __future__ import annotations
import json
import re
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from .audit_log import record
from .perf_metrics import timed
from .chat import API_URL
from .windows_resources import SETTINGS, open_resource
from .windows_apps import rank_matches
from .actions import normalize

TOOLS = {"open_settings", "open_app", "open_website", "close_window"}
SITES = {"youtube": "https://www.youtube.com", "google": "https://www.google.com",
         "github": "https://github.com", "gmail": "https://mail.google.com"}
BROWSER = {"opera gx": "opera gx", "opera": "opera", "chrome": "chrome", "edge": "edge"}
MAX_STEPS = 3
_PLANNER_RETRY_AFTER = 0.0

PLANNER_PROMPT = """Você é um planejador de tarefas locais do Windows.
Interprete o pedido inteiro, incluindo cumprimentos, contexto e expressões indiretas.
Responda SOMENTE um objeto JSON no formato
{"steps":[{"tool":"open_app","target":"Opera GX"},{"tool":"open_website","target":"youtube","browser":"Opera GX"}]}
Ferramentas: open_app(nome de app instalado), open_settings(nome da configuração),
open_website(site reconhecido, browser opcional), close_window(título de janela).
Se for conversa ou pergunta informativa, responda {"steps":[]}.
Nunca execute terminal, apague arquivos, instale softwares, faça compras, envie mensagens
ou sugira comandos PowerShell. Não invente ferramentas.
Máximo de 3 etapas. Se pedir para abrir YouTube no Opera GX, use APENAS open_website
com browser Opera GX; essa ferramenta abre o navegador e o endereço em uma etapa.
Fechar janela pede confirmação dentro da ferramenta."""


def parse_plan(value):
    if not isinstance(value, dict) or not isinstance(value.get("steps"), list):
        return None
    steps = value["steps"]
    if len(steps) > MAX_STEPS:
        return None
    cleaned = []
    for step in steps:
        if not isinstance(step, dict) or step.get("tool") not in TOOLS:
            return None
        target = step.get("target")
        if not isinstance(target, str) or not target.strip() or len(target) > 120:
            return None
        browser = step.get("browser", "")
        if not isinstance(browser, str) or len(browser) > 80:
            return None
        cleaned.append({"tool": step["tool"], "target": target.strip(), "browser": browser.strip()})
    return cleaned


def local_fallback_plan(message):
    """Safe recovery for familiar web requests when the AI planner is offline."""
    text = normalize(message)
    if not re.search(r"\b(?:abra|abre|abrir|acesse|acessar|entre|entrar|quero ver|quero assistir|mostre)\b", text):
        return None
    sites = [key for key in SITES if re.search(r"\b" + re.escape(key) + r"\b", text)]
    if len(sites) != 1:
        return None
    browser = ""
    if re.search(r"\b(?:opera gx|opera g x|opera|pelo golpe|pelo gol pe|pelo opera|navegador opera)\b", text):
        browser = "Opera GX"
    elif re.search(r"\bchrome\b", text):
        browser = "chrome"
    elif re.search(r"\bedge\b", text):
        browser = "edge"
    return [{"tool": "open_website", "target": sites[0], "browser": browser}]


def plan_via_groq(message, chat):
    global _PLANNER_RETRY_AFTER
    if time.monotonic() < _PLANNER_RETRY_AFTER:
        return None
    if not getattr(chat, "available", False):
        return None
    payload = {"model": chat.model, "messages": [
        {"role": "system", "content": PLANNER_PROMPT},
        {"role": "user", "content": message}],
        "temperature": 0, "max_completion_tokens": 250,
        "response_format": {"type": "json_object"}}
    request = Request(API_URL, data=json.dumps(payload).encode("utf-8"),
                      headers={"Authorization": f"Bearer {chat.api_key}",
                               "Content-Type": "application/json"}, method="POST")
    try:
        with timed("intent_routing"):
            with urlopen(request, timeout=12) as response:
                obj = json.loads(response.read().decode("utf-8"))
        plan = parse_plan(json.loads(obj["choices"][0]["message"]["content"]))
        record("agent_plan", steps=plan, status="valid" if plan is not None else "invalid")
        return plan
    except (HTTPError, URLError, TimeoutError, ValueError, KeyError, IndexError, TypeError) as exc:
        code = getattr(exc, 'code', None)
        if code in (401, 403, 429):
            _PLANNER_RETRY_AFTER = time.monotonic() + (600 if code in (401, 403) else 60)
            record('agent_planner_paused', http_status=code)
        record("agent_plan_error", error_type=type(exc).__name__, http_status=code)
        return None


def _website_url(target):
    key = normalize(target).replace("site do ", "").replace("site ", "").strip()
    if key in SITES:
        return SITES[key]
    # The planner may only select known HTTPS sites, never invent arbitrary URLs.
    if key in ("youtube.com", "www.youtube.com"):
        return SITES["youtube"]
    return None


def execute_plan(steps, windows, *, startfile=None):
    """Execute only a bounded, validated plan; stop on uncertainty."""
    import os
    result = []
    # os.startfile não existe em Linux: permitir teste/planejamento sem Windows.
    opener = startfile if startfile is not None else getattr(os, 'startfile', None)
    for step in steps[:MAX_STEPS]:
        tool, target = step["tool"], step["target"]
        record("agent_step_attempt", tool=tool, target=target, browser=step["browser"])
        if tool == "open_settings":
            name = normalize(target).strip()
            if name.startswith("as "):
                name = name[3:]
            uri = SETTINGS.get(name)
            outcome = open_resource(("settings", uri)) if uri else "Não reconheci essa configuração."
        elif tool == "open_app":
            matches = rank_matches(windows.catalog.list_apps(), target)
            if len(matches) != 1:
                outcome = f"Não encontrei um aplicativo único chamado {target}." if not matches else f"Encontrei várias opções de {target}; diga qual deseja."
            else:
                outcome = windows._launch(matches[0])
        elif tool == "close_window":
            outcome = windows._close_window(target)
        elif tool == "open_website":
            url = _website_url(target)
            browser = normalize(step["browser"])
            if not url:
                outcome = "Esse site ainda não está identificado com segurança."
            elif browser:
                browser_name = BROWSER.get(browser)
                apps = windows.catalog.list_apps()
                matches = rank_matches(apps, browser_name) if browser_name else []
                if browser_name == 'opera gx':
                    matches = [app for app in apps if app.source == 'exe' and ('opera' in normalize(app.name) or 'opera gx' in normalize(app.target))]
                else:
                    matches = [app for app in matches if app.source == 'exe']
                if len(matches) != 1:
                    outcome = f"Não encontrei um executável único do navegador {step['browser']}."
                else:
                    import subprocess
                    try:
                        subprocess.Popen([matches[0].target, url], shell=False)
                        outcome = f"Solicitei a abertura de {target} no {matches[0].name}."
                    except OSError:
                        outcome = f"Não consegui abrir o navegador {step['browser']}."
            elif opener is None:
                outcome = 'A abertura de sites no navegador padrão está disponível apenas no Windows.'
            else:
                try:
                    opener(url)
                    outcome = f"Solicitei a abertura do site {target} no navegador padrão."
                except OSError:
                    outcome = "Não consegui abrir o site."
        else:
            outcome = "Ferramenta não permitida."
        result.append(outcome)
        record("agent_step_result", tool=tool, target=target, outcome=outcome)
        if any(s in normalize(outcome) for s in ("nao encontrei", "nao consegui", "nao reconheci", "varias opcoes", "nao esta", "nao permitido")):
            break
    return " ".join(result)
