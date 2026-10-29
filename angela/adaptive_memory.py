"""Memória local e restrita de preferências de interação, sem privilégios."""
from __future__ import annotations
import json
import os
from pathlib import Path
from .actions import normalize

PREF_PATH = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'AngelaAI' / 'preferences.json'
SUPPORTED = {'resposta curta': 'short_answers', 'respostas curtas': 'short_answers', 'fale pouco': 'short_answers'}


def preference_request(message: str):
    clean = normalize(message).strip(' .,!?')
    if clean in {'angela fale pouco', 'fale pouco', 'prefiro respostas curtas', 'angela prefiro respostas curtas'}:
        return ('short_answers', True)
    if clean in {'pode voltar a explicar normalmente', 'respostas normais', 'fale normalmente'}:
        return ('short_answers', False)
    return None


def load_preferences(path=None):
    path = Path(path) if path else PREF_PATH
    try:
        obj = json.loads(path.read_text(encoding='utf-8'))
        return {'short_answers': bool(obj.get('short_answers', False))} if isinstance(obj, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def save_preference(key, value, path=None):
    if key != 'short_answers' or not isinstance(value, bool):
        raise ValueError('Preferência não suportada')
    path = Path(path) if path else PREF_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    data = load_preferences(path)
    data[key] = value
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)
    return data
