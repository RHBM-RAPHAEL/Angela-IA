# Ângela AI — Assistente para Windows

Projeto pessoal de código aberto. A Ângela reconhece a palavra "Ângela" pelo Vosk local, responde com voz feminina Dora/Kokoro e pode consultar Groq opcionalmente.

**Versão 0.5 — protótipo.** Ações de Windows ampliadas, mas ainda sem visão de tela, câmera, envio de WhatsApp ou automação geral por mouse.

## O que há de novo na v0.5

- Descobre aplicativos sem cadastro manual, consultando atalhos do Menu Iniciar, App Paths do Registro e Get-StartApps da Microsoft Store.
- Abre aplicativos encontrados pelo nome: Chrome, Opera, WhatsApp ou outros registrados. Quando encontrar vários nomes próximos, pede para escolher.
- Lista e pesquisa aplicativos instalados.
- Abre pastas dos SSDs: diga "Abra a pasta Imagens no SSD D" ou informe um caminho como D:\Imagens. Valida se existe antes de abrir.
- Lista janelas visíveis e solicita fechamento normal via WM_CLOSE, mediante confirmação explícita. Não encerra processos à força.
- Diálogo para escolher entre programas e confirmar ou cancelar fechamento. As solicitações pendentes expiram após 90 segundos.
- Mantém a escuta por "Ângela", Dora local, comandos anteriores, arquivos de modelo e seu .env intactos.

## Atualizar da versão 0.4 (PowerShell do VS Code)

Feche primeiro a janela da Ângela:

    cd "D:\RHBM TechWorks\Meus Softwares\Angela-IA"
    git pull origin main
    .\.venv\Scripts\python.exe -m unittest discover -s tests -v
    .\.venv\Scripts\python.exe -m angela

Não precisa reinstalar voz nem Ollama.

## O que testar

1. Marque "Ativar escuta por 'Ângela'".
2. "Ângela, quais aplicativos instalados?"
3. "Ângela, abra o Opera" — se houver Opera e Opera GX, escolha pelo número.
4. "Ângela, abra a pasta Imagens no SSD D" — deve abrir a pasta D:\Imagens.
5. "Ângela, quais janelas abertas?"
6. "Ângela, feche a calculadora" — deve pedir confirmação. Teste "cancelar" e depois "sim" caso não haja trabalho não salvo.
7. Verifique a voz Dora e os comandos anteriores.

Alguns apps portáteis sem atalhos ou registro ainda podem não aparecer. O catálogo é atualizado a cada cinco minutos, ou imediatamente quando você pede para listar os aplicativos.

## Privacidade e limitações

- Não executa comandos arbitrários de terminal. Apenas ferramentas locais implementadas e explícitas.
- Fechar uma janela exige confirmação e envia a solicitação normal do Windows; programas podem pedir para salvar o trabalho.
- Abrir pasta não significa abrir ou executar arquivos. A versão atual aceita caminhos de unidades locais, não caminhos de rede.
- Mensagens como "mande WhatsApp para minha mãe" não são executadas; o envio exigirá futura integração autorizada, seleção do contato e confirmação.
- A lista de aplicativos e janelas é consultada localmente, sem passar para a Groq.
- Voz Dora e palavra de ativação usam bibliotecas locais; microfone contínuo começa desligado e só é ativado pelo usuário.
- O reconhecimento do nome utiliza transcrição Vosk e ainda pode errar em ambientes barulhentos.
- Ainda não há acesso a todos os programas, visão de tela, automação completa de interface ou controle da câmera.

## Instalação nova

Pré-requisitos: Git, Python 3.12, Windows 10/11.

    git clone https://github.com/RHBM-RAPHAEL/Angela-IA.git
    cd Angela-IA
    py -3.12 -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    .\.venv\Scripts\python.exe -m angela.download_model
    Copy-Item .env.example .env
    .\.venv\Scripts\python.exe -m pip install -r requirements-voice-kokoro.txt
    .\.venv\Scripts\python.exe -m angela.download_kokoro
    .\.venv\Scripts\python.exe -m angela

## Arquitetura da v0.5

- angela/windows_apps.py: inventário e abertura dos apps registrados.
- angela/windows_folders.py: caminhos dos SSDs e abertura de pastas.
- angela/windows_windows.py: janelas visíveis e WM_CLOSE.
- angela/windows_controller.py: comandos, escolhas e confirmações.
- angela/assistant.py: roteamento de pedidos para ferramentas locais e chat.
- angela/ui.py, wake.py, speech.py: janela, escuta por nome e voz Dora.

Executar testes:

    .\.venv\Scripts\python.exe -m unittest discover -s tests -v

Os testes no GitHub simulam as ações. O funcionamento com apps e janelas reais deve ser validado no seu notebook.

Licença MIT. Dependências e modelos mantêm suas respectivas licenças.
