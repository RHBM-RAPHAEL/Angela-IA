"""Consulta de pastas autorizadas para exibição textual no painel lateral."""
from __future__ import annotations
from pathlib import Path
import re
from .actions import normalize
from .project_tools import project_roots

DEFAULT_FOLDER = Path(r"D:\RHBM TechWorks\Meus Softwares")
LIST_RE = re.compile(r"\b(?:list|liste|listar|lista|mostre|mostrar|mostra|quais|quantos|relacione)\b")


def list_request(text: str) -> Path | None:
    spoken = normalize(text)
    if not LIST_RE.search(spoken):
        return None
    if not re.search(r"\b(?:projetos|softwares|pastas|diretorios)\b", spoken):
        return None
    if ("meus softwares" in spoken or "meus software" in spoken
            or "meu software" in spoken or "meu softwares" in spoken):
        return DEFAULT_FOLDER
    if re.search(r"\b(?:meus projetos|quais projetos|listar projetos|liste projetos)\b", spoken):
        return DEFAULT_FOLDER
    # Nesta versão, não deduzir caminhos arbitrários ditados por voz.
    return None


def list_folders(folder: Path) -> list[str]:
    allowed = [root.resolve() for root in project_roots()]
    target = folder.resolve(strict=True)
    if not any(target == root or root in target.parents for root in allowed):
        raise PermissionError("Pasta não autorizada.")
    return sorted((item.name for item in target.iterdir()
                   if item.is_dir() and not item.is_symlink()), key=str.casefold)


def listing_reply(names: list[str]) -> str:
    if not names:
        return "Não encontrei pastas de projetos nesse local."
    preview = ", ".join(names[:5])
    extra = f" e mais {len(names)-5}" if len(names) > 5 else ""
    return f"Encontrei {len(names)} pastas em Meus Softwares. Algumas são: {preview}{extra}. A lista está no painel lateral."
