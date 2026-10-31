"""Descoberta limitada e segura de projetos locais no Windows."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import re
import shutil
import subprocess
import time

from .actions import normalize
from .audit_log import record

MARKERS = ("pubspec.yaml", "package.json", "pyproject.toml", "Cargo.toml", ".git")
EXCLUDE = {"node_modules", ".venv", "venv", ".git", "build", "dist", ".dart_tool", ".next"}
_CODE_NAMES = ("Code.exe", "code.cmd", "code")


@dataclass(frozen=True)
class Project:
    name: str
    path: Path


def project_roots() -> tuple[Path, ...]:
    home = Path.home()
    roots = [
        Path(r"D:\RHBM TechWorks\Meus Softwares"),
        home / "Documents" / "Projetos",
        home / "source" / "repos",
    ]
    return tuple(p for p in roots if p.is_dir())


def discover_projects(roots=None, depth: int = 2, limit: int = 150) -> list[Project]:
    """Varredura limitada a raízes conhecidas, sem arquivos privados."""
    roots = tuple(roots if roots is not None else project_roots())
    found = []
    seen = set()

    def visit(folder: Path, level: int) -> None:
        if len(found) >= limit or not folder.is_dir():
            return
        try:
            resolved = folder.resolve(strict=True)
            if not any(resolved == r.resolve() or r.resolve() in resolved.parents for r in roots):
                return
            if folder.is_symlink() or str(resolved).lower() in seen:
                return
            seen.add(str(resolved).lower())
            # As pastas diretamente em Meus Softwares são projetos conhecidos,
            # mesmo quando não possuem manifesto na raiz.
            if level == 1 and normalize(folder.parent.name) == normalize('Meus Softwares'):
                found.append(Project(folder.name, folder))
                return
            if any((folder / marker).exists() for marker in MARKERS):
                found.append(Project(folder.name, folder))
                return
            if level >= depth:
                return
            for child in sorted(folder.iterdir(), key=lambda p: p.name.lower()):
                if child.is_dir() and not child.is_symlink() and child.name.lower() not in EXCLUDE:
                    visit(child, level + 1)
                    if len(found) >= limit:
                        break
        except (OSError, PermissionError):
            return

    for root in roots:
        visit(root, 0)
    return found


def match_project(name: str, projects: list[Project]) -> list[Project]:
    key = normalize(name).replace("-", " ").replace("_", " ").strip()
    # Common Portuguese speech-to-text spellings of the Zynix name.
    aliases = {"zinix": "zynix", "zenix": "zynix", "zinics": "zynix", "ziniks": "zynix"}
    aliases.update({"sinix": "zynix", "zinicos": "zynix", "siniquos": "zynix", "iniquos": "zynix"})
    aliases.update({"achei app": "achei", "app achei": "achei", "ponto calc": "rhbm ponto flutter v1"})
    if key == "valorize":
        preferred = [p for p in projects if normalize(p.name).replace("_", " ") == "valorize site"]
        if preferred:
            return preferred
    key = aliases.get(key, key)
    if not key:
        return []
    exact = [p for p in projects if normalize(p.name).replace("-", " ").replace("_", " ") == key]
    if exact:
        return exact
    # Prefere projetos cujo nome começa pelo pedido: 'Valorize' entre backups.
    prefix = [p for p in projects if normalize(p.name).replace("-", " ").replace("_", " ").startswith(key + " ")]
    if prefix:
        return prefix
    return [p for p in projects if key in normalize(p.name).replace("-", " ").replace("_", " ")]


def parse_project_request(text: str) -> str | None:
    cleaned = normalize(text).strip(" ,.!?")
    cleaned = re.sub(r"^(?:oi |ola |bom dia |boa tarde |boa noite )*(?:angela |anjela )?", "", cleaned).strip()
    cleaned = re.sub(r"\s+(?:por favor|pra mim|para mim)$", "", cleaned)
    cleaned = re.sub(r"^(?:voce pode |pode |consegue |por favor )+", "", cleaned)
    cleaned = re.sub(r"^(?:abra|abre|abrir|inicie|inicia)\s+(?:o|a)\s+meu\s+projeto\s+", "abra o projeto ", cleaned)
    # O Vosk costuma trocar 'VS Code' por 'verso', 'estúdio com' ou 'estúdio cores'.
    # Corrigir apenas quando a expressão estiver ligada a 'no/na/pelo VS Code'.
    cleaned = re.sub(r"\b(?:no|na|pelo|com)\s+(?:visual\s+)?(?:estudio\s+(?:code|cod|com|cores)|studio\s+(?:code|cod|com|cores)|versiculo|verso|vence\s+code|viesse\s+code|vs\s+code|vscode)\s*$", "no vs code", cleaned)
    # Custom project names are often transcribed as unrelated Portuguese words.
    # Resolve ONLY within an explicit project-opening request, never arbitrary speech.
    phonetic_zynix = re.search(r"\b(?:zinix|zenix|sinix|zinics|ziniks|zinicos|siniquos|siniquo|iniquos|inicos)\b", cleaned)
    if phonetic_zynix and re.match(r"^(?:angela\s+)?(?:abra|abre|abrir|inicie|inicia)\s+", cleaned):
        return "zynix"
    cleaned = re.sub(r"^(?:angela|anjela)[, ]*", "", cleaned).strip()
    patterns = (
        r"^(?:abra|abre|abrir|abro|inicie|inicia)\s+(?:(?:o|a)\s+)?(?:(?:meu|minha)\s+)?(?:projeto|projetos|repositorio)\s+(.+?)(?:\s+(?:no|na|pelo|com)\s+(?:vs code|vscode|visual studio code|vence code|visual studio|verso|versiculo))?$",
        r"^(?:abra|abre|abrir|inicie|inicia)\s+(?:o\s+)?(?:vs code|vscode|visual studio code)\s+(?:no|com|na pasta do)\s+(?:projeto\s+)?(.+)$",
    )
    for pattern in patterns:
        match = re.match(pattern, cleaned)
        if match:
            return match.group(1).strip()
    return None


def find_vscode() -> str | None:
    locations = (
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Microsoft VS Code" / "Code.exe",
        Path(os.environ.get("PROGRAMFILES", "")) / "Microsoft VS Code" / "Code.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Microsoft VS Code" / "Code.exe",
    )
    for executable in locations:
        if executable.is_file():
            return str(executable)
    # VS Code may be installed in a custom folder, with only code.cmd on
    # PATH (e.g. C:\Apps de programação\Microsoft VS Code\bin\code.cmd).
    # Prefer the trusted sibling Code.exe: launch with shell=False, never
    # treat a .cmd script as a program path.
    from_path = shutil.which("code") or shutil.which("code.cmd")
    if from_path:
        candidate = Path(from_path)
        if candidate.suffix.lower() == ".exe" and candidate.is_file():
            return str(candidate)
        executable = candidate.parent.parent / "Code.exe"
        if executable.is_file():
            return str(executable)
    return None


def launch_project(project: Project, executable=None, launcher=None, sleep=None, windows=None) -> str:
    record('project_launch_attempt', name=project.name, path=str(project.path), method='vscode_new_window')
    if not project.path.is_dir():
        record('project_launch_result', status='failure', reason='directory_missing')
        return "A pasta do projeto não existe mais."
    code = executable or find_vscode()
    if not code:
        record('project_launch_result', status='failure', reason='vscode_missing')
        return "Não encontrei o VS Code instalado."
    launch = launcher or subprocess.Popen
    pause = sleep or time.sleep
    from .windows_windows import enumerate_windows
    get_windows = windows or enumerate_windows
    try:
        existing_handles = {item.hwnd for item in get_windows()}
        record('process_launch', executable=str(code), arguments=['--new-window', str(project.path)])
        proc = launch([str(code), "--new-window", str(project.path)])
        pause(0.45)
        if proc.poll() is not None and proc.returncode != 0:
            record('project_launch_result', status='failure', return_code=proc.returncode)
            return "O VS Code encerrou com erro durante a abertura."
        for attempt in range(6):
            titles = [item.title for item in get_windows()
                      if item.hwnd not in existing_handles]
            if any(normalize(project.name) in normalize(title) and
                   'visual studio code' in normalize(title) for title in titles):
                record('project_launch_result', status='success', window_confirmed=True, path=str(project.path))
                return f"Confirmei a abertura da janela do VS Code para {project.name}."
            if attempt < 5:
                pause(0.4)
    except (OSError, ValueError) as exc:
        record('project_launch_result', status='failure', error_type=type(exc).__name__)
        return "Não consegui iniciar o VS Code."
    record('project_launch_result', status='unconfirmed', path=str(project.path))
    return (f"Enviei o projeto {project.name} para o VS Code na pasta {project.path}. "
            "O comando foi aceito, mas ainda não identifiquei uma nova janela.")


def handle_project_request(message: str, roots=None, launcher=None, executable=None, sleep=None) -> str | None:
    target = parse_project_request(message)
    if target is None:
        return None
    projects = discover_projects(roots=roots)
    record('project_search', requested=target, roots=[str(p) for p in (roots if roots is not None else project_roots())], discovered=len(projects))
    matches = match_project(target, projects)
    record('project_matches', requested=target, matches=[str(p.path) for p in matches])
    if not matches:
        return f"Não encontrei o projeto {target} nas pastas de desenvolvimento."
    if len(matches) > 1:
        return "Encontrei mais de um projeto: " + "; ".join(str(p.path) for p in matches[:4]) + ". Especifique o nome completo."
    return launch_project(matches[0], executable=executable, launcher=launcher, sleep=sleep)
