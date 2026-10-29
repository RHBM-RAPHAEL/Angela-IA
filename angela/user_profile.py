"""Perfil local mínimo e editável da pessoa que usa a Ângela.

Não salvar credenciais, endereço ou outros dados sensíveis neste módulo.
O perfil ajuda na interpretação; nunca autoriza ações automaticamente.
"""
from __future__ import annotations

PROFILE = {
    "name": "Rafael",
    "age": 21,
    "field": "Engenharia de Software",
    "occupation": "programação e desenvolvimento de software",
    "common_apps": ("Visual Studio Code", "Opera GX", "GitHub"),
}


def profile_context() -> str:
    return (
        "Informações que o usuário forneceu: nome Rafael, 21 anos, "
        "área de Engenharia de Software, trabalha com programação. "
        "Programas e serviços frequentes: VS Code, Opera GX e GitHub. "
        "Use como contexto para interpretar termos, mas nunca pressuponha "
        "que uma ação foi solicitada nem execute algo só por causa do perfil."
    )
