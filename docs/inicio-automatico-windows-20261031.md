# Angela AI - iniciar automaticamente com o Windows

## Ativado para usuario atual

O atalho em `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup`
executa um inicializador PowerShell sem janela de terminal.
Funciona na proxima entrada do usuario na area de trabalho Windows;
nao antes do login, e nao requer direitos de administrador.

## Fluxo de inicio

- Verifica se `AngelaAI.exe` ja esta aberto; se sim, nao duplica.
- Verifica o servidor do holograma em `http://127.0.0.1:18766/`.
- Se ausente, inicia o servidor HTTP local com Python 3.12.
- Inicia `AngelaAI.exe` no diretorio correto com
  `ANGELA_ENABLE_VOICE=1` aplicado somente ao processo.
- Assim, a miniatura, o holograma e o microfone iniciam juntos.
- Registra somente eventos tecnicos sem audio nem conversas em
  `%LOCALAPPDATA%\AngelaAI\logs\startup.log`.

## Para desativar

Abra PowerShell na pasta raiz do projeto e execute:

`powershell -NoProfile -ExecutionPolicy Bypass -File .\launcher\configure-startup.ps1 -Disable`

Para reativar: use `-Enable`. Para consultar: use `-Status`.
Tambem pode usar o Gerenciador de Tarefas > Aplicativos de Inicializacao.

## Teste em 31/10/2026

- Atalho criado e verificado na pasta de inicializacao do usuario RHBM.
- Inicializador foi executado manualmente, sem precisar reiniciar Windows.
- O processo `AngelaAI.exe` abriu; servidor HUD retornou HTTP 200.
- Historico registrou `desktop_overlay_started voice=True` e
  `microphone_open source=wdmks-raw` apos inicializacao.
- Nova execucao do inicializador retornou `ALREADY_RUNNING` e apenas
  uma instancia de `AngelaAI.exe` ficou aberta.

Limite: o proprio login apos reboot ainda nao foi simulado. O teste
de inicializacao na entrada real do Windows requer o proximo login.
