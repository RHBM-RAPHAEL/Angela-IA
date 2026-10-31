"""Open user-saved folder aliases as VS Code workspaces, without AI guessing.

Recognize only explicit project/editor requests with exact *registered* names.
Conservative contextual ASR variants are valid only inside this route.
Never execute a path, script, or URL supplied by speech.
"""
from __future__ import annotations

import re
from pathlib import Path

from .actions import normalize
from .audit_log import record
from .folder_registry import FolderRegistry, checked_folder_path
from .project_tools import Project, launch_project


_WAKE = re.compile(r"^(?:(?:ei|oi)\s+)?(?:angela|anjela)[,;:\s]+")
_OPEN = r"(?:abra|abre|abrir|abro|inicie|inicia|iniciar|acesse|acessa|acessar|carregue)"
# Not a global STT correction! "no conto" is VS Code ONLY if the user also
# clearly mentions a registered project name and requests opening it.
_EDITOR = (
    r"(?:vs\s*code|vscode|v\s*s\s*code|visual\s+studio\s+code|"
    r"visual\s+estudio\s+code|visual\s+estudio\s+com\s+molde|"
    r"visual\s+estudio\s+com\s+modulo|visual\s+estudio\s+com\s+mode|"
    r"visual\s+studio\s+com\s+molde|visual\s+estudio\s+com|"
    r"no\s+conto|conto)"
)
_EDITOR_PREP = rf"(?:no|na|com|pelo|pelo aplicativo|usando|via|dentro do)\s+{_EDITOR}"
_PREFIXES = re.compile(r"^(?:por favor\s+|voce pode\s+|pode\s+|consegue\s+)+")


def _clean(message: str) -> str:
    if not isinstance(message, str):
        return ""
    s = " ".join(normalize(message).replace(",", " ").split())
    s = _WAKE.sub("", s).strip(" .!?,;:")
    return _PREFIXES.sub("", s).strip()


def _safe_alias(alias: str) -> str:
    return re.escape(" ".join(normalize(alias).split()))


def registered_project_alias(message: str, names: list[str]) -> str | None:
    """Return a single registered folder alias only on explicit commands.

    Project name alone, standalone VS Code, or ordinary statements are NOT
    interpreted as permission to launch a program.
    """
    s = _clean(message)
    if not 0 < len(s) < 230:
        return None
    names = [name for name in names if name and len(name) <= 45]
    matches = []
    for name in names:
        alias = _safe_alias(name)
        # "abra (o meu) projeto Curso (no VS Code)"
        # "abra a pasta Curso no VS Code"
        # "projeto Curso no visual estúdio com molde"
        pattern_project = (
            rf"(?:(?:{_OPEN})\s+)?(?:(?:o|a)\s+)?"
            rf"(?:(?:meu|minha)\s+)?(?:projeto|repositorio)\s+{alias}"
            rf"(?P<editor>\s+(?:{_EDITOR_PREP}))?"
        )
        pattern_folder = (
            rf"(?:{_OPEN})\s+(?:(?:o|a)\s+)?"
            rf"(?:pasta|diretorio)\s+{alias}"
            rf"\s+(?:{_EDITOR_PREP})"
        )
        # "abra Curso no VS Code", "abra VS Code na pasta Curso"
        pattern_short = (
            rf"(?:{_OPEN})\s+(?:(?:o|a)\s+)?{alias}"
            rf"\s+(?:{_EDITOR_PREP})"
        )
        pattern_code_first = (
            rf"(?:{_OPEN})\s+(?:(?:o|a)\s+)?{_EDITOR}"
            rf"\s+(?:no|com|na|do|da|na pasta|no projeto)\s+"
            rf"(?:(?:o|a)\s+)?(?:(?:projeto|pasta|repositorio)\s+)?{alias}"
        )
        proj = re.fullmatch(pattern_project, s)
        if proj:
            # With "projeto" + explicit launch verb, VS Code is the default
            # (consistent with existing project_tools). Missing verb only
            # works if the editor is explicitly mentioned.
            if proj.group("editor") or re.match(rf"^{_OPEN}\b", s):
                matches.append(name)
        elif re.fullmatch(pattern_folder, s):
            matches.append(name)
        elif re.fullmatch(pattern_short, s):
            matches.append(name)
        elif re.fullmatch(pattern_code_first, s):
            matches.append(name)
    return matches[0] if len(matches) == 1 else None


def open_registered_project(
    message: str, registry: FolderRegistry, *, launcher=None
) -> str | None:
    """Launch a saved folder in the installed VS Code; None if not a match."""
    entries = registry.all()
    label = registered_project_alias(message, list(entries))
    if label is None:
        return None
    try:
        # Validate again before launching: folder may have moved.
        target = checked_folder_path(entries[label])
    except ValueError:
        record("saved_workspace_unavailable", kind="folder")
        return f"A pasta {label} não está disponível. Confira o cadastro."
    record("saved_workspace_open_requested", app="vscode", alias_matched=True)
    answer = (launcher or launch_project)(Project(label, Path(target)))
    # VS Code cold starts can take longer than the short window-check period.
    # Say what was requested, not a long disclaimer or a false guarantee.
    if answer.startswith("Enviei o projeto "):
        return f"Solicitei a abertura do projeto {label} no VS Code."
    return answer
