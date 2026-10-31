# Ângela AI — Projetos cadastrados no VS Code | 31/10/2026

## Falha real nos registros

O usuário havia cadastrado o apelido Curso para
`D:\Curso de Dart e Flutter\Dart\exercicios_dart`.
Mas o Vosk registrou 'abra o projeto curso no conto' e
'projeto curso no visual estúdio com molde'. O programa não conectava
os apelidos de pastas ao roteador de projetos em VS Code.

## Correção

- `registered_projects.py`: reconhece pedidos explícitos com apelidos
  cadastrados, sem adivinhar pastas ou executar palavras como scripts.
- As variantes transcritas 'no conto' e 'visual estúdio com molde'
  só equivalem a VS Code quando o usuário pede o projeto cadastrado.
- 'abra o projeto Curso' abre VS Code; 'abra a pasta Curso' mantém Explorer.
- 'abra a pasta Curso no VS Code' também abre o projeto no editor.
- 'abra o projeto' seguido de 'Curso' usa o alias no turno seguinte.
- Se o apelido não existe ou seu caminho foi removido, não abre outra pasta.
- O VS Code instalado fora do padrão é descoberto pelo `code.cmd` no PATH
  e o executável real é localizado em sua pasta pai `Code.exe`.
- A abertura usa lista de argumentos e `shell=False` (sem execução de comandos).
- Resposta oral curta quando o processo abriu mas a janela ainda
  não foi confirmada: 'Solicitei a abertura do projeto Curso no VS Code'.

## Evidência de execução real

VS Code instalado em `C:\Apps de programação\Microsoft VS Code\Code.exe`.
O comando de teste abriu o processo `Code.exe --new-window` com
`D:\Curso de Dart e Flutter\Dart\exercicios_dart`.
Janela observada: `Bem-vindo - exercicios_dart - Visual Studio Code`.
Sem alteração nos arquivos do curso; apenas o editor foi iniciado.

## Testes

9 testes novos para transcrições reais, comandos negativos, abertura por
apelido, exclusão de pastas indisponíveis, continuidade de contexto e
detecção do VS Code em instalação personalizada.
Suite inteira Windows (QT_QPA_PLATFORM=offscreen): 358 testes, exit 0.

Limite: testes de texto não medem melhora no reconhecimento acústico
do Vosk. O sucesso real dos comandos falados exige novo teste pelo usuário.
