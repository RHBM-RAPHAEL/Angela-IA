# Ângela AI — inicializador com identidade própria

O Windows mostra o nome do executável que utiliza o microfone. Quando a
Ângela executa diretamente por python.exe, aparece Python.
Este inicializador hospeda o mesmo CPython dentro de AngelaAI.exe, com
FileDescription e ProductName definidos como Ângela AI.

## Construção e atalho

Use PowerShell, na raiz do repositório:

    powershell -ExecutionPolicy Bypass -File .\launcher\build-launcher.ps1 -CreateDesktopShortcut

O build cria launcher/AngelaAI/bin/Release/net9.0/AngelaAI.exe, como
aplicativo Windows sem console, e um atalho Ângela AI na área de trabalho.
Abra pelo atalho, não pelo comando antigo python.exe -m angela.desktop_overlay.

O launcher encontra a raiz do repositório e utiliza a instalação Python
3.12 atual com os mesmos pacotes de voz, Qt, Vosk e visão computacional.
O diretório Python padrão é %LOCALAPPDATA%/Programs/Python/Python312.
Pode ser alterado pela variável ANGELA_PYTHON_HOME quando necessário.

Com argumentos, executa o Python por Py_Main dentro do próprio processo.
Logo, comandos de câmera via sys.executable -m angela.camera_worker
continuam funcionais; não criam nem enviam imagens sem consentimento.

## Compatibilidade, segurança e rollback

- Nunca altera o interpretador Python original nem seu registro no sistema.
- Não interfere com outros programas, inclusive o Zynix.
- Não modifica permissões do microfone, câmera ou outros dispositivos.
- Processos antigos python.exe mantêm esse nome até serem encerrados.
- Para rollback, inicie normalmente por python.exe -m angela.desktop_overlay.
- O visual exato da indicação depende da versão do Windows; precisa ser
  validado com o app usando o microfone após iniciar pelo novo atalho.
- O build não inicia a Ângela nem abre microfone/câmera.

Para depurar no terminal, compile Debug (OutputType Exe). Em Release,
WinExe evita abrir console adicional na área de trabalho.
